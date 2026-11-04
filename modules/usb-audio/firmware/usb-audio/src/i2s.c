#include "i2s.h"

#include <string.h>

#include "audio.h"
#include "audio_config.h"
#include "board.h"

// One frame = slot B hi, slot B lo, slot A hi, slot A lo half-words (i2s.h).
#define HALF_WORDS (AUDIO_BLOCK_FRAMES * 4)

static uint16_t rx_buf[2 * HALF_WORDS] __attribute__((aligned(4)));
static uint16_t tx_buf[2 * HALF_WORDS] __attribute__((aligned(4)));

volatile uint32_t i2s_rx_blocks, i2s_tx_blocks;
uint32_t i2s_err_ovr, i2s_err_udr, i2s_err_stall, i2s_err_late, i2s_err_slip;

// Halves the DMA has filled (RX) or freed (TX) and the worker has not serviced yet.
#define PENDING_RX0 1u
#define PENDING_RX1 2u
#define PENDING_TX0 4u
#define PENDING_TX1 8u
static volatile uint32_t pending;

static bool running;
static volatile bool slipped;
static uint32_t last_rx_blocks, last_check_ms;

#define WS_HIGH() ((GPIOB->INDR & GPIO_Pin_12) != 0)   // LRCK on PB12 (I2S2_WS) = PA15 (I2S3_WS)

bool i2s_running(void) {
  return running;
}

bool i2s_lrck_toggling(uint32_t timeout_us) {
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
  // PB5 I2S3 SD out (R108 33R -> codec SDIN)
  gpio.GPIO_Mode = GPIO_Mode_AF_PP;
  gpio.GPIO_Pin = GPIO_Pin_5;
  GPIO_Init(GPIOB, &gpio);
}

static void i2s_setup(SPI_TypeDef *spi, uint16_t mode) {
  I2S_InitTypeDef i2s = {0};
  i2s.I2S_Mode = mode;
  i2s.I2S_Standard = I2S_Standard_Phillips;   // ignored once started (i2s.h)
  i2s.I2S_DataFormat = I2S_DataFormat_32b;    // all 32 bits of each slot
  i2s.I2S_MCLKOutput = I2S_MCLKOutput_Disable;
  i2s.I2S_AudioFreq = I2S_AudioFreq_48k;   // unused in slave mode
  i2s.I2S_CPOL = I2S_CPOL_Low;
  I2S_Init(spi, &i2s);
}

static void dma_setup(DMA_Channel_TypeDef *ch, volatile uint16_t *periph, uint16_t *mem, uint32_t dir) {
  DMA_DeInit(ch);
  DMA_InitTypeDef dma = {0};
  dma.DMA_PeripheralBaseAddr = (uint32_t) periph;
  dma.DMA_MemoryBaseAddr = (uint32_t) mem;
  dma.DMA_DIR = dir;
  dma.DMA_BufferSize = 2 * HALF_WORDS;
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

void i2s_stop(void) {
  NVIC_DisableIRQ(DMA1_Channel4_IRQn);
  NVIC_DisableIRQ(DMA2_Channel2_IRQn);
  if (RCC->APB1PCENR & RCC_APB1Periph_SPI2) I2S_Cmd(SPI2, DISABLE);
  if (RCC->APB1PCENR & RCC_APB1Periph_SPI3) I2S_Cmd(SPI3, DISABLE);
  DMA_Cmd(DMA1_Channel4, DISABLE);
  DMA_Cmd(DMA2_Channel2, DISABLE);
  running = false;
}

void i2s_start(void) {
  i2s_stop();

  RCC_APB1PeriphClockCmd(RCC_APB1Periph_SPI2 | RCC_APB1Periph_SPI3, ENABLE);
  RCC_AHBPeriphClockCmd(RCC_AHBPeriph_DMA1 | RCC_AHBPeriph_DMA2, ENABLE);
  SPI_I2S_DeInit(SPI2);
  SPI_I2S_DeInit(SPI3);
  gpio_setup();
  i2s_setup(SPI2, I2S_Mode_SlaveRx);
  i2s_setup(SPI3, I2S_Mode_SlaveTx);

  memset(rx_buf, 0, sizeof(rx_buf));
  memset(tx_buf, 0, sizeof(tx_buf));
  pending = 0;   // the DMA interrupts are off (i2s_stop)
  slipped = false;
  dma_setup(DMA1_Channel4, &SPI2->DATAR, rx_buf, DMA_DIR_PeripheralSRC);   // SPI2_RX
  dma_setup(DMA2_Channel2, &SPI3->DATAR, tx_buf, DMA_DIR_PeripheralDST);   // SPI3_TX
  DMA_Cmd(DMA1_Channel4, ENABLE);
  DMA_Cmd(DMA2_Channel2, ENABLE);
  SPI_I2S_DMACmd(SPI2, SPI_I2S_DMAReq_Rx, ENABLE);
  SPI_I2S_DMACmd(SPI3, SPI_I2S_DMAReq_Tx, ENABLE);
  I2S_Cmd(SPI2, ENABLE);
  I2S_Cmd(SPI3, ENABLE);

  last_rx_blocks = i2s_rx_blocks;
  last_check_ms = board_millis();
  running = true;
  NVIC_EnableIRQ(DMA1_Channel4_IRQn);
  NVIC_EnableIRQ(DMA2_Channel2_IRQn);
}

void i2s_report_slip(void) {
  slipped = true;
}

bool i2s_check(void) {
  if (!running) return false;
  uint16_t const s2 = SPI2->STATR, s3 = SPI3->STATR;
  bool ok = true;
  if (s2 & SPI_STATR_OVR) {
    i2s_err_ovr++;
    ok = false;
  }
  if (s3 & SPI_STATR_UDR) {
    i2s_err_udr++;
    ok = false;
  }
  if (slipped) {
    i2s_err_slip++;
    ok = false;
  }
  uint32_t const now = board_millis();
  if ((uint32_t) (now - last_check_ms) >= 20) {
    // At 48 kHz a 48-frame half completes every 1 ms: 20 ms with none = clocks gone.
    if (i2s_rx_blocks == last_rx_blocks) {
      i2s_err_stall++;
      ok = false;
    }
    last_rx_blocks = i2s_rx_blocks;
    last_check_ms = now;
  }
  if (!ok) i2s_stop();
  return ok;
}

// The DMA handlers only mark the half that is ready and pend the audio worker
// (board.c), which services it between the USB transfer completions: the
// QingKe interrupt controller does not let an interrupt that became pending
// during a higher one preempt the handler it returns to, so long work here
// would hold the USB processing off.
static inline void half_ready(uint32_t bit) {
  if (pending & bit) i2s_err_late++;
  pending |= bit;
  NVIC_SetPendingIRQ(Software_IRQn);
}

__attribute__((interrupt)) void DMA1_Channel4_IRQHandler(void) {
  uint32_t const f = DMA1->INTFR;
  if (f & DMA1_IT_HT4) {
    DMA1->INTFCR = DMA1_IT_HT4;
    half_ready(PENDING_RX0);
    i2s_rx_blocks++;
  }
  if (f & DMA1_IT_TC4) {
    DMA1->INTFCR = DMA1_IT_TC4;
    half_ready(PENDING_RX1);
    i2s_rx_blocks++;
  }
}

__attribute__((interrupt)) void DMA2_Channel2_IRQHandler(void) {
  uint32_t const f = DMA2->INTFR;
  // Half transfer: DMA is now sending the second half, so refill the first.
  if (f & (DMA2_IT_HT2 & 0x0FFFFFFF)) {
    DMA2->INTFCR = DMA2_IT_HT2 & 0x0FFFFFFF;
    half_ready(PENDING_TX0);
    i2s_tx_blocks++;
  }
  if (f & (DMA2_IT_TC2 & 0x0FFFFFFF)) {
    DMA2->INTFCR = DMA2_IT_TC2 & 0x0FFFFFFF;
    half_ready(PENDING_TX1);
    i2s_tx_blocks++;
  }
}

bool i2s_service(void) {
  uint32_t const p = pending;
  if (!p) return false;
  uint32_t const bit = p & (0u - p);   // one half per call
  pending &= ~bit;                     // the DMA handlers run on this level too
  switch (bit) {
    case PENDING_RX0: audio_i2s_rx(&rx_buf[0]); break;
    case PENDING_RX1: audio_i2s_rx(&rx_buf[HALF_WORDS]); break;
    case PENDING_TX0: audio_i2s_tx(&tx_buf[0]); break;
    default: audio_i2s_tx(&tx_buf[HALF_WORDS]); break;
  }
  return true;
}
