#include "codec.h"

#include "board.h"

#define CODEC_ADDR      (0x48 << 1)
#define I2C_TIMEOUT_US  2000

// Mode control (03h): FM[5:4] speed (master), MCLK_FREQ[3:1] divider, POPG = 0.
// MCLK is the 24.576 MHz oscillator; every rate uses MCLK / 2 (datasheet table 7):
//   192 kHz quad speed MCLK/LRCK 128, 96 kHz double 256, 48 kHz single 512.
#define MODE_1X         0x00
#define MODE_2X         0x10
#define MODE_4X         0x20
#define MODE_DIV2       0x04

#define PWR_PDN         0x01
#define FMT_FRZ_A       0x80
#define FMT_FRZ_B       0x40
#define FMT_DAC_I2S     0x08
#define FMT_ADC_I2S     0x01
#define TRANS_INV_ADC_B 0x10
#define TRANS_INV_ADC_A 0x08

static codec_state_t state = CODEC_OFF;
static uint8_t chip_id;

const char *codec_state_name(codec_state_t s) {
  switch (s) {
    case CODEC_OFF: return "off";
    case CODEC_NO_ACK: return "no I2C answer at 0x48";
    case CODEC_BAD_ID: return "wrong chip ID";
    case CODEC_READY: return "configured, not started";
    case CODEC_RUNNING: return "running";
  }
  return "?";
}

codec_state_t codec_state(void) {
  return state;
}

uint8_t codec_chip_id(void) {
  return chip_id;
}

// ---- I2C2 (PB10 SCL, PB11 SDA, 2.2k pull-ups on the carrier), 100 kHz, polled

static bool wait_event(uint32_t event) {
  for (uint32_t t = 0; t < I2C_TIMEOUT_US; t++) {
    if (I2C_CheckEvent(I2C2, event) == READY) return true;
    if (I2C_GetFlagStatus(I2C2, I2C_FLAG_AF) == SET) break;   // NACK
    board_delay_us(1);
  }
  return false;
}


// Clock out a slave that holds SDA low (e.g. after a reset mid-transfer).
static void i2c_bus_clear(void) {
  GPIO_InitTypeDef gpio = {0};
  gpio.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
  gpio.GPIO_Mode = GPIO_Mode_Out_OD;
  gpio.GPIO_Speed = GPIO_Speed_2MHz;
  GPIO_SetBits(GPIOB, GPIO_Pin_10 | GPIO_Pin_11);
  GPIO_Init(GPIOB, &gpio);
  for (int i = 0; i < 9 && GPIO_ReadInputDataBit(GPIOB, GPIO_Pin_11) == Bit_RESET; i++) {
    GPIO_ResetBits(GPIOB, GPIO_Pin_10);
    board_delay_us(5);
    GPIO_SetBits(GPIOB, GPIO_Pin_10);
    board_delay_us(5);
  }
  // STOP: SDA low -> high while SCL high
  GPIO_ResetBits(GPIOB, GPIO_Pin_11);
  board_delay_us(5);
  GPIO_SetBits(GPIOB, GPIO_Pin_11);
  board_delay_us(5);
}

static void i2c_init(void) {
  RCC_APB1PeriphClockCmd(RCC_APB1Periph_I2C2, ENABLE);
  i2c_bus_clear();

  GPIO_InitTypeDef gpio = {0};
  gpio.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
  gpio.GPIO_Mode = GPIO_Mode_AF_OD;
  gpio.GPIO_Speed = GPIO_Speed_50MHz;
  GPIO_Init(GPIOB, &gpio);

  I2C_DeInit(I2C2);
  I2C_InitTypeDef i2c = {0};
  i2c.I2C_ClockSpeed = 100000;
  i2c.I2C_Mode = I2C_Mode_I2C;
  i2c.I2C_DutyCycle = I2C_DutyCycle_2;
  i2c.I2C_OwnAddress1 = 0x02;
  i2c.I2C_Ack = I2C_Ack_Enable;
  i2c.I2C_AcknowledgedAddress = I2C_AcknowledgedAddress_7bit;
  I2C_Init(I2C2, &i2c);
  I2C_Cmd(I2C2, ENABLE);
}

// After a failed transfer: STOP, and if the bus stays busy, clear it and
// restart the peripheral so the next transfer starts clean.
static void i2c_abort(void) {
  I2C_ClearFlag(I2C2, I2C_FLAG_AF);
  I2C_AcknowledgeConfig(I2C2, ENABLE);
  I2C_GenerateSTOP(I2C2, ENABLE);
  for (uint32_t t = 0; t < I2C_TIMEOUT_US && I2C_GetFlagStatus(I2C2, I2C_FLAG_BUSY) == SET; t++) {
    board_delay_us(1);
  }
  if (I2C_GetFlagStatus(I2C2, I2C_FLAG_BUSY) == SET) i2c_init();
}

static bool wait_flag(uint32_t flag) {
  for (uint32_t t = 0; t < I2C_TIMEOUT_US; t++) {
    if (I2C_GetFlagStatus(I2C2, flag) == SET) return true;
    if (I2C_GetFlagStatus(I2C2, I2C_FLAG_AF) == SET) break;   // NACK
    board_delay_us(1);
  }
  return false;
}

static bool i2c_start_addr(uint8_t dir) {
  // Let a previous STOP finish first.
  for (uint32_t t = 0; t < I2C_TIMEOUT_US && I2C_GetFlagStatus(I2C2, I2C_FLAG_BUSY) == SET; t++) {
    board_delay_us(1);
  }
  I2C_GenerateSTART(I2C2, ENABLE);
  if (!wait_event(I2C_EVENT_MASTER_MODE_SELECT)) return false;
  I2C_Send7bitAddress(I2C2, CODEC_ADDR, dir);
  return wait_event(dir == I2C_Direction_Transmitter ? I2C_EVENT_MASTER_TRANSMITTER_MODE_SELECTED
                                                     : I2C_EVENT_MASTER_RECEIVER_MODE_SELECTED);
}

bool codec_write(uint8_t reg, uint8_t val) {
  if (!i2c_start_addr(I2C_Direction_Transmitter)) goto fail;
  I2C_SendData(I2C2, reg);
  if (!wait_event(I2C_EVENT_MASTER_BYTE_TRANSMITTED)) goto fail;
  I2C_SendData(I2C2, val);
  if (!wait_event(I2C_EVENT_MASTER_BYTE_TRANSMITTED)) goto fail;
  I2C_GenerateSTOP(I2C2, ENABLE);
  return true;
fail:
  i2c_abort();
  return false;
}

// Read: a write of the MAP byte (aborted write, datasheet 6.1.2), then a one-byte read.
bool codec_read(uint8_t reg, uint8_t *val) {
  if (!i2c_start_addr(I2C_Direction_Transmitter)) goto fail;
  I2C_SendData(I2C2, reg);
  if (!wait_event(I2C_EVENT_MASTER_BYTE_TRANSMITTED)) goto fail;
  I2C_GenerateSTOP(I2C2, ENABLE);
  board_delay_us(20);

  // Single byte: ACK off before ADDR is cleared, STOP right after it, before
  // the byte (90 us) is in. The audio worker must not run in between, or the
  // peripheral takes a second byte and the bus hangs.
  I2C_AcknowledgeConfig(I2C2, DISABLE);
  for (uint32_t t = 0; t < I2C_TIMEOUT_US && I2C_GetFlagStatus(I2C2, I2C_FLAG_BUSY) == SET; t++) {
    board_delay_us(1);
  }
  I2C_GenerateSTART(I2C2, ENABLE);
  if (!wait_event(I2C_EVENT_MASTER_MODE_SELECT)) goto fail;
  I2C_Send7bitAddress(I2C2, CODEC_ADDR, I2C_Direction_Receiver);
  if (!wait_flag(I2C_FLAG_ADDR)) goto fail;
  uint32_t const irq = board_irq_mask();
  (void) I2C2->STAR1;
  (void) I2C2->STAR2;   // clears ADDR: the byte is clocked in
  I2C_GenerateSTOP(I2C2, ENABLE);
  board_irq_restore(irq);
  if (!wait_flag(I2C_FLAG_RXNE)) goto fail;
  *val = I2C_ReceiveData(I2C2);
  I2C_AcknowledgeConfig(I2C2, ENABLE);
  return true;
fail:
  i2c_abort();
  return false;
}

static uint8_t mode_for_rate(uint32_t rate) {
  switch (rate) {
    case 48000: return MODE_1X | MODE_DIV2;
    case 96000: return MODE_2X | MODE_DIV2;
    default: return MODE_4X | MODE_DIV2;   // 192000
  }
}

codec_state_t codec_prepare(uint32_t rate) {
  static bool i2c_ready;
  if (!i2c_ready) {
    i2c_init();
    i2c_ready = true;
  }

  // Reset with MCLK (Y1, free running) and the supplies stable, then enter
  // control-port mode by setting PDN within 1045 LRCK periods of releasing RST.
  board_codec_reset(true);
  board_delay_ms(2);
  board_codec_reset(false);
  board_delay_us(500);

  if (!codec_write(CS4270_PWRCTL, PWR_PDN)) {
    // Retry once after an I2C bus reset.
    i2c_ready = false;
    i2c_init();
    i2c_ready = true;
    if (!codec_write(CS4270_PWRCTL, PWR_PDN)) {
      board_codec_reset(true);
      return state = CODEC_NO_ACK;
    }
  }

  if (!codec_read(CS4270_CHIPID, &chip_id) || (chip_id & 0xF0) != 0xC0) {
    board_codec_reset(true);
    return state = CODEC_BAD_ID;
  }

  bool ok = codec_write(CS4270_MODE, mode_for_rate(rate)) &&
            // ADC high-pass frozen from the start: its offset stays at zero, so
            // DC passes and the input offset is calibrated in audio.c instead
            // (a codec reset would lose a frozen HPF value).
            codec_write(CS4270_FORMAT, FMT_FRZ_A | FMT_FRZ_B | FMT_DAC_I2S | FMT_ADC_I2S) &&
            // The input drivers invert (U6A/B): ADC_INV restores the polarity.
            // Soft ramp / zero cross off: no volume changes are used.
            codec_write(CS4270_TRANS, TRANS_INV_ADC_A | TRANS_INV_ADC_B) &&
            // Auto-mute off: a DC-coupled output must hold a static code.
            codec_write(CS4270_MUTE, 0x00) &&
            codec_write(CS4270_VOLA, 0x00) &&
            codec_write(CS4270_VOLB, 0x00);
  if (!ok) {
    board_codec_reset(true);
    return state = CODEC_NO_ACK;
  }
  return state = CODEC_READY;
}

bool codec_run(void) {
  if (state == CODEC_READY && codec_write(CS4270_PWRCTL, 0x00)) {
    state = CODEC_RUNNING;
    return true;
  }
  board_codec_reset(true);
  state = CODEC_OFF;
  return false;
}

void codec_stop(void) {
  if (state == CODEC_RUNNING || state == CODEC_READY) codec_write(CS4270_PWRCTL, PWR_PDN);
  board_codec_reset(true);
  state = CODEC_OFF;
}
