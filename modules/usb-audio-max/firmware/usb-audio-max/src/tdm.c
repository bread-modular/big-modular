#include "tdm.h"

#include <string.h>

#include "board.h"

// One frame = 8 words = 16 half-words (MSB half first) in DMA order.
#define FRAME_HALFWORDS (TDM_SLOTS * 2)
#define HALF_WORDS      (TDM_BLOCK_FRAMES * TDM_SLOTS)
#define HALF_HALFWORDS  (TDM_BLOCK_FRAMES * FRAME_HALFWORDS)

static uint16_t rx_buf[2 * HALF_HALFWORDS] __attribute__((aligned(4)));
static uint16_t tx_buf[2 * HALF_HALFWORDS] __attribute__((aligned(4)));

volatile uint32_t tdm_rx_blocks, tdm_tx_blocks;

// Halves the DMA has filled (RX) or freed (TX) and the worker has not serviced yet.
#define PENDING_RX0 1u
#define PENDING_RX1 2u
#define PENDING_TX0 4u
#define PENDING_TX1 8u
static volatile uint32_t pending;
uint32_t tdm_err_ovr, tdm_err_udr, tdm_err_stall, tdm_err_late, tdm_err_slip;

static bool running;
static volatile bool slipped;
static uint32_t last_rx_blocks, last_check_ms;

// Frame position: slot 1 starts at bit `align_b` of stream word `align_wo` of
// each 8-word frame (MSB first). Valid while `aligned`.
static volatile bool aligned;
static int align_wo, align_b;
static bool check_slots78;

// Alignment measurement (RX handler side)
static volatile uint32_t meas_left;
static uint32_t meas_tog[TDM_SLOTS], meas_ones[TDM_SLOTS], meas_prev[TDM_SLOTS];
static bool meas_first;
static tdm_align_info_t info = {.state = TDM_ALIGN_NONE, .offset = -1};

// Raw capture
static volatile int raw_want;
static uint32_t raw_words[32];

// RX words in stream order: the last TAIL words of the previous half (a frame
// may start in it), then this half.
#define TAIL 9
static uint32_t rx_words[TAIL + HALF_WORDS];
// TX: slot words of the last frame sent (smp[0..7] of the next half).
static uint32_t tx_carry[TDM_SLOTS];

#define WS_HIGH() ((GPIOB->INDR & GPIO_Pin_12) != 0)   // LRCK on PB12 (I2S2_WS) = PA15 (I2S3_WS)

bool tdm_running(void) {
  return running;
}

bool tdm_lrck_toggling(uint32_t timeout_us) {
  bool const first = WS_HIGH();
  for (uint32_t t = 0; t < timeout_us; t++) {
    if (WS_HIGH() != first) return true;
    board_delay_us(1);
  }
  return false;
}

static void gpio_setup(void) {
  GPIO_InitTypeDef gpio = {0};
  gpio.GPIO_Speed = GPIO_Speed_50MHz;
  // I2S2 slave RX: PB12 WS, PB13 CK, PB15 SD all inputs.
  // I2S3 slave TX: PB3 CK, PA15 WS inputs.
  gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
  gpio.GPIO_Pin = GPIO_Pin_12 | GPIO_Pin_13 | GPIO_Pin_15 | GPIO_Pin_3;
  GPIO_Init(GPIOB, &gpio);
  gpio.GPIO_Pin = GPIO_Pin_15;
  GPIO_Init(GPIOA, &gpio);
  // PB5 I2S3 SD out (R108 33R -> codec DIN1)
  gpio.GPIO_Mode = GPIO_Mode_AF_PP;
  gpio.GPIO_Pin = GPIO_Pin_5;
  GPIO_Init(GPIOB, &gpio);
}

static void i2s_setup(SPI_TypeDef *spi, uint16_t mode) {
  I2S_InitTypeDef i2s = {0};
  i2s.I2S_Mode = mode;
  i2s.I2S_Standard = I2S_Standard_Phillips;   // ignored once started (tdm.h)
  i2s.I2S_DataFormat = I2S_DataFormat_32b;    // all 32 bits of each slot
  i2s.I2S_MCLKOutput = I2S_MCLKOutput_Disable;
  i2s.I2S_AudioFreq = I2S_AudioFreq_48k;      // unused in slave mode
  i2s.I2S_CPOL = I2S_CPOL_Low;                // as modules/usb-audio
  I2S_Init(spi, &i2s);
}

static void dma_setup(DMA_Channel_TypeDef *ch, volatile uint16_t *periph, uint16_t *mem, uint32_t dir) {
  DMA_DeInit(ch);
  DMA_InitTypeDef dma = {0};
  dma.DMA_PeripheralBaseAddr = (uint32_t) periph;
  dma.DMA_MemoryBaseAddr = (uint32_t) mem;
  dma.DMA_DIR = dir;
  dma.DMA_BufferSize = 2 * HALF_HALFWORDS;
  dma.DMA_PeripheralInc = DMA_PeripheralInc_Disable;
  dma.DMA_MemoryInc = DMA_MemoryInc_Enable;
  dma.DMA_PeripheralDataSize = DMA_PeripheralDataSize_HalfWord;
  dma.DMA_MemoryDataSize = DMA_MemoryDataSize_HalfWord;
  dma.DMA_Mode = DMA_Mode_Circular;
  dma.DMA_Priority = DMA_Priority_VeryHigh;
  dma.DMA_M2M = DMA_M2M_Disable;
  DMA_Init(ch, &dma);
  DMA_ITConfig(ch, DMA_IT_HT | DMA_IT_TC, ENABLE);
}

void tdm_stop(void) {
  NVIC_DisableIRQ(DMA1_Channel4_IRQn);
  NVIC_DisableIRQ(DMA2_Channel2_IRQn);
  if (RCC->APB1PCENR & RCC_APB1Periph_SPI2) I2S_Cmd(SPI2, DISABLE);
  if (RCC->APB1PCENR & RCC_APB1Periph_SPI3) I2S_Cmd(SPI3, DISABLE);
  DMA_Cmd(DMA1_Channel4, DISABLE);
  DMA_Cmd(DMA2_Channel2, DISABLE);
  running = false;
  aligned = false;
  meas_left = 0;
  if (info.state == TDM_ALIGN_MEASURING) info.state = TDM_ALIGN_NONE;
}

void tdm_start(void) {
  tdm_stop();

  RCC_APB1PeriphClockCmd(RCC_APB1Periph_SPI2 | RCC_APB1Periph_SPI3, ENABLE);
  RCC_AHBPeriphClockCmd(RCC_AHBPeriph_DMA1 | RCC_AHBPeriph_DMA2, ENABLE);
  SPI_I2S_DeInit(SPI2);
  SPI_I2S_DeInit(SPI3);
  gpio_setup();
  i2s_setup(SPI2, I2S_Mode_SlaveRx);
  i2s_setup(SPI3, I2S_Mode_SlaveTx);

  memset(rx_buf, 0, sizeof(rx_buf));
  memset(tx_buf, 0, sizeof(tx_buf));
  memset(rx_words, 0, sizeof(rx_words));
  memset(tx_carry, 0, sizeof(tx_carry));
  pending = 0;   // the DMA interrupts are off (tdm_stop)
  slipped = false;
  info.state = TDM_ALIGN_NONE;
  info.offset = -1;
  dma_setup(DMA1_Channel4, &SPI2->DATAR, rx_buf, DMA_DIR_PeripheralSRC);   // SPI2_RX
  dma_setup(DMA2_Channel2, &SPI3->DATAR, tx_buf, DMA_DIR_PeripheralDST);   // SPI3_TX
  DMA_Cmd(DMA1_Channel4, ENABLE);
  DMA_Cmd(DMA2_Channel2, ENABLE);
  SPI_I2S_DMACmd(SPI2, SPI_I2S_DMAReq_Rx, ENABLE);
  SPI_I2S_DMACmd(SPI3, SPI_I2S_DMAReq_Tx, ENABLE);
  I2S_Cmd(SPI2, ENABLE);
  I2S_Cmd(SPI3, ENABLE);

  last_rx_blocks = tdm_rx_blocks;
  last_check_ms = board_millis();
  running = true;
  NVIC_EnableIRQ(DMA1_Channel4_IRQn);
  NVIC_EnableIRQ(DMA2_Channel2_IRQn);
}

bool tdm_check(void) {
  if (!running) return false;
  uint16_t const s2 = SPI2->STATR, s3 = SPI3->STATR;
  bool ok = true;
  if (s2 & SPI_STATR_OVR) {
    tdm_err_ovr++;
    ok = false;
  }
  if (s3 & SPI_STATR_UDR) {
    tdm_err_udr++;
    ok = false;
  }
  if (slipped) {
    tdm_err_slip++;
    ok = false;
  }
  uint32_t const now = board_millis();
  if ((uint32_t) (now - last_check_ms) >= 20) {
    // A 48-frame half completes every 1 ms: 20 ms with none = clocks gone.
    if (tdm_rx_blocks == last_rx_blocks) {
      tdm_err_stall++;
      ok = false;
    }
    last_rx_blocks = tdm_rx_blocks;
    last_check_ms = now;
  }
  if (!ok) tdm_stop();
  return ok;
}

//--------------------------------------------------------------------+
// Frame position
//--------------------------------------------------------------------+

void tdm_align_start(uint32_t frames) {
  uint32_t const irq = board_irq_mask();
  aligned = false;
  memset(meas_tog, 0, sizeof(meas_tog));
  memset(meas_ones, 0, sizeof(meas_ones));
  meas_first = true;
  info.state = TDM_ALIGN_MEASURING;
  info.offset = -1;
  meas_left = frames;
  board_irq_restore(irq);
}

// Bit p (0..255) of the 8-word frame period, MSB of word 0 first.
static inline bool bit_at(uint32_t const *m, int p) {
  p &= 255;
  return (m[p >> 5] >> (31 - (p & 31))) & 1u;
}

void tdm_align_task(void) {
  if (info.state != TDM_ALIGN_MEASURING || meas_left) return;
  memcpy(info.toggled, meas_tog, sizeof(info.toggled));
  memcpy(info.ones, meas_ones, sizeof(info.ones));

  // A candidate start d: in slots 1-6 the 8 bits after the 24 data bits never
  // set; scored by the slots whose LSB (bit 23 after d) toggled. Among the
  // best, prefer the one with slots 7/8 all zero.
  int best = -1, best_score = 0, count = 0;
  bool best78 = false;
  for (int d = 0; d < 256; d++) {
    bool ok = true;
    int score = 0;
    for (int s = 0; ok && s < TDM_IN_CHANNELS; s++) {
      for (int z = 24; z < 32; z++) {
        if (bit_at(info.ones, d + 32 * s + z)) {
          ok = false;
          break;
        }
      }
      if (bit_at(info.toggled, d + 32 * s + 23)) score++;
    }
    if (!ok || score < 3) continue;
    bool zero78 = true;
    for (int z = 192; zero78 && z < 256; z++) zero78 = !bit_at(info.ones, d + z);
    // rank: slots 7/8 zero first, then the LSB score
    int const rank = (zero78 ? 16 : 0) + score;
    int const best_rank = best < 0 ? -1 : (best78 ? 16 : 0) + best_score;
    if (rank > best_rank) {
      best = d;
      best_score = score;
      best78 = zero78;
      count = 1;
    } else if (rank == best_rank) {
      count++;
    }
  }
  info.candidates = count;
  info.lsb_toggling = best_score;
  info.slots78_zero = best78;
  if (best < 0 || count != 1) {
    info.state = TDM_ALIGN_FAILED;
    info.offset = -1;
    return;
  }
  info.offset = best;
  info.state = TDM_ALIGN_OK;
  uint32_t const irq = board_irq_mask();
  align_wo = best >> 5;
  align_b = best & 31;
  check_slots78 = best78;
  slipped = false;
  aligned = true;
  board_irq_restore(irq);
}

void tdm_align_get(tdm_align_info_t *out) {
  uint32_t const irq = board_irq_mask();
  *out = info;
  board_irq_restore(irq);
}

bool tdm_raw_capture(uint32_t *words, int n, uint32_t timeout_ms) {
  if (n > 32) n = 32;
  raw_want = n;
  uint32_t const t0 = board_millis();
  while (raw_want) {
    if (!running || board_millis() - t0 > timeout_ms) {
      raw_want = 0;
      return false;
    }
  }
  memcpy(words, raw_words, (size_t) n * 4u);
  return true;
}

//--------------------------------------------------------------------+
// DMA halves
//--------------------------------------------------------------------+

// DMA order is MSB half-word first: a little-endian word read has the halves swapped.
static inline __attribute__((always_inline)) uint32_t swap16(uint32_t w) {
  return (w >> 16) | (w << 16);
}

static void rx_half(uint16_t const *src) {
  uint32_t const *const src32 = (uint32_t const *) src;
  uint32_t *const words = &rx_words[TAIL];
  for (int i = 0; i < HALF_WORDS; i++) words[i] = swap16(src32[i]);

  if (raw_want) {
    for (int i = 0; i < raw_want; i++) raw_words[i] = words[i];
    raw_want = 0;
  }

  if (meas_left) {
    for (int f = 0; f < TDM_BLOCK_FRAMES && meas_left; f++, meas_left--) {
      for (int j = 0; j < TDM_SLOTS; j++) {
        uint32_t const w = words[f * TDM_SLOTS + j];
        meas_ones[j] |= w;
        if (!meas_first) meas_tog[j] |= w ^ meas_prev[j];
        meas_prev[j] = w;
      }
      meas_first = false;
    }
  }

  if (aligned) {
    // Codec frame f starts in the previous half for f = 0: one frame of delay.
    static int32_t in[TDM_BLOCK_FRAMES][TDM_IN_CHANNELS];   // off the 2 KiB stack
    uint32_t zero = 0;
    uint32_t const b = (uint32_t) align_b;
    uint32_t const zmask78 = check_slots78 ? 0xFFFFFFFFu : 0;
    for (int f0 = 0; f0 < TDM_BLOCK_FRAMES; f0 += TDM_SERVICE_FRAMES) {
      for (int f = f0; f < f0 + TDM_SERVICE_FRAMES; f++) {
        uint32_t const *const p = &words[(f - 1) * TDM_SLOTS + align_wo];
        uint32_t v[TDM_SLOTS];
        for (int s = 0; s < TDM_SLOTS; s++) v[s] = b ? (p[s] << b) | (p[s + 1] >> (32 - b)) : p[s];
        for (int s = 0; s < TDM_IN_CHANNELS; s++) {
          in[f][s] = (int32_t) v[s] >> 8;
          zero |= v[s] & 0xFFu;
        }
        zero |= (v[6] | v[7]) & zmask78;
      }
      audio_usb_service();
    }
    if (zero) slipped = true;
    audio_tdm_rx(in);
  }

  memcpy(rx_words, &rx_words[HALF_WORDS], sizeof(uint32_t) * TAIL);
}

static void tx_half(uint16_t *dst) {
  if (!aligned) {
    memset(dst, 0, HALF_HALFWORDS * 2u);
    memset(tx_carry, 0, sizeof(tx_carry));
    return;
  }
  // Slot words (DAC codes): smp[0..7] = the last frame of the previous half,
  // then this half's frames, filled by audio.c. Static, off the 2 KiB stack:
  // the worker services one half at a time.
  static uint32_t smp[TDM_SLOTS * (TDM_BLOCK_FRAMES + 1)];
  memcpy(smp, tx_carry, sizeof(tx_carry));
  audio_tdm_tx((int32_t (*)[TDM_OUT_CHANNELS]) &smp[TDM_SLOTS]);
  memcpy(tx_carry, &smp[TDM_SLOTS * TDM_BLOCK_FRAMES], sizeof(tx_carry));

  // Each 24-bit code goes MSB first into its 32-bit slot, shifted to the frame position.
  uint32_t const b = (uint32_t) align_b;
  uint32_t const *const k0 = &smp[TDM_SLOTS - align_wo];
  uint32_t *const dst32 = (uint32_t *) dst;
  for (int w0 = 0; w0 < HALF_WORDS; w0 += TDM_SERVICE_FRAMES * TDM_SLOTS) {
    for (int w = w0; w < w0 + TDM_SERVICE_FRAMES * TDM_SLOTS; w++) {
      uint32_t const cur = k0[w] << 8;
      uint32_t const v = b ? (cur >> b) | ((k0[w - 1] << 8) << (32 - b)) : cur;
      dst32[w] = swap16(v);
    }
    audio_usb_service();
  }
}

// The DMA handlers only mark the half that is ready and pend the audio worker
// (board.c), which services it between the USB transfer completions: the
// QingKe interrupt controller does not let an interrupt that became pending
// during a higher one preempt the handler it returns to, so long work here
// would hold the USB processing off (modules/usb-audio, i2s.c).
static inline void half_ready(uint32_t bit) {
  if (pending & bit) tdm_err_late++;   // the worker missed a whole half
  pending |= bit;
  NVIC_SetPendingIRQ(Software_IRQn);
}

__attribute__((interrupt)) void DMA1_Channel4_IRQHandler(void) {
  uint32_t const f = DMA1->INTFR;
  if (f & DMA1_IT_HT4) {
    DMA1->INTFCR = DMA1_IT_HT4;
    half_ready(PENDING_RX0);
    tdm_rx_blocks++;
  }
  if (f & DMA1_IT_TC4) {
    DMA1->INTFCR = DMA1_IT_TC4;
    half_ready(PENDING_RX1);
    tdm_rx_blocks++;
  }
}

__attribute__((interrupt)) void DMA2_Channel2_IRQHandler(void) {
  uint32_t const f = DMA2->INTFR;
  // Half transfer: DMA is now sending the second half, so refill the first.
  if (f & (DMA2_IT_HT2 & 0x0FFFFFFF)) {
    DMA2->INTFCR = DMA2_IT_HT2 & 0x0FFFFFFF;
    half_ready(PENDING_TX0);
    tdm_tx_blocks++;
  }
  if (f & (DMA2_IT_TC2 & 0x0FFFFFFF)) {
    DMA2->INTFCR = DMA2_IT_TC2 & 0x0FFFFFFF;
    half_ready(PENDING_TX1);
    tdm_tx_blocks++;
  }
}

// Worker timing, SysTick counts (HCLK): the longest stretch of a half
// without a USB service point, and the longest half.
uint32_t tdm_gap_max, tdm_half_max[2];
static uint32_t mark;

static inline uint32_t ticks_since(uint32_t t) {
  uint32_t const period = (uint32_t) SysTick->CMP + 1u;
  return ((uint32_t) SysTick->CNT + period - t) % period;
}

void tdm_service_mark(void) {
  uint32_t const d = ticks_since(mark);
  if (d > tdm_gap_max) tdm_gap_max = d;
  mark = (uint32_t) SysTick->CNT;
}

bool tdm_service(void) {
  uint32_t const p = pending;
  if (!p) return false;
  uint32_t const bit = p & (0u - p);   // one half per call
  pending &= ~bit;                     // the DMA handlers run on this level too
  uint32_t const t0 = mark = (uint32_t) SysTick->CNT;
  bool const rx = bit <= PENDING_RX1;
  switch (bit) {
    case PENDING_RX0: rx_half(&rx_buf[0]); break;
    case PENDING_RX1: rx_half(&rx_buf[HALF_HALFWORDS]); break;
    case PENDING_TX0: tx_half(&tx_buf[0]); break;
    default: tx_half(&tx_buf[HALF_HALFWORDS]); break;
  }
  tdm_service_mark();
  uint32_t const d = ticks_since(t0);
  if (d > tdm_half_max[rx ? 0 : 1]) tdm_half_max[rx ? 0 : 1] = d;
  return true;
}
