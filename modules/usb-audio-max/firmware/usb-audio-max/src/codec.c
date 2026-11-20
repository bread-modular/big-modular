#include "codec.h"

#include "board.h"

// 7-bit addresses, in probing order (codec.h)
#define ADDR_S3_MASTER  0x47
#define ADDR_S3_SLAVE   0x45
#define ADDR_S2         0x44
#define I2C_TIMEOUT_US  2000

// DAC Control 1 (41h): DAC slave, 24-bit I2S-mode TDM.
#define DAC_TDM_I2S     0x06
// ADC Control 1 (51h): MSAD master 512 fS (48 kHz single rate) / 256 fS (96 kHz
// dual rate) from the 24.576 MHz SCKI, FMTAD 24-bit I2S-mode TDM.
#define ADC_MASTER_512  0x20
#define ADC_MASTER_256  0x40
#define ADC_TDM_I2S     0x06
// ADC Control 2 (52h): HPF bypassed on all pairs (DC passes), no power save.
#define ADC_BYP_ALL     0x07
// ADC 1-6 single-ended (VINn- = VCOM_REF) and inverted (the input drivers invert).
#define ADC_ALL6        0x3F

static codec_state_t state = CODEC_OFF;
static uint8_t addr = ADDR_S3_MASTER;   // address in use (probed in codec_prepare)
static uint8_t found;                   // address that answered, 0 = none
static uint32_t state_rate;
static uint8_t bad_reg, bad_got, bad_want;

const char *codec_state_name(codec_state_t s) {
  switch (s) {
    case CODEC_OFF: return "off";
    case CODEC_NO_ACK: return "no I2C answer at 0x47 / 0x45 / 0x44";
    case CODEC_BAD_REGS: return "registers do not read back";
    case CODEC_READY: return "configured, clocks not started";
    case CODEC_RUNNING: return "running";
  }
  return "?";
}

codec_state_t codec_state(void) {
  return state;
}

uint8_t codec_address(void) {
  return found;
}

bool codec_linked(void) {
  return found == ADDR_S3_SLAVE;
}

void codec_bad_reg(uint8_t *reg, uint8_t *got, uint8_t *want) {
  *reg = bad_reg;
  *got = bad_got;
  *want = bad_want;
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

static bool wait_flag(uint32_t flag) {
  for (uint32_t t = 0; t < I2C_TIMEOUT_US; t++) {
    if (I2C_GetFlagStatus(I2C2, flag) == SET) return true;
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

static bool i2c_start_write(void) {
  // Let a previous STOP finish first.
  for (uint32_t t = 0; t < I2C_TIMEOUT_US && I2C_GetFlagStatus(I2C2, I2C_FLAG_BUSY) == SET; t++) {
    board_delay_us(1);
  }
  I2C_GenerateSTART(I2C2, ENABLE);
  if (!wait_event(I2C_EVENT_MASTER_MODE_SELECT)) return false;
  I2C_Send7bitAddress(I2C2, (uint8_t) (addr << 1), I2C_Direction_Transmitter);
  return wait_event(I2C_EVENT_MASTER_TRANSMITTER_MODE_SELECTED);
}

bool codec_write(uint8_t reg, uint8_t val) {
  if (!i2c_start_write()) goto fail;
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

// Read (datasheet figure 46): register address, repeated START, one byte, NACK.
bool codec_read(uint8_t reg, uint8_t *val) {
  if (!i2c_start_write()) goto fail;
  I2C_SendData(I2C2, reg);
  if (!wait_event(I2C_EVENT_MASTER_BYTE_TRANSMITTED)) goto fail;
  I2C_GenerateSTART(I2C2, ENABLE);
  if (!wait_event(I2C_EVENT_MASTER_MODE_SELECT)) goto fail;

  // Single byte: ACK off before ADDR is cleared, STOP right after it, before
  // the byte (90 us) is in. No interrupt handler may run in between, or the
  // peripheral takes a second byte and the bus hangs.
  I2C_AcknowledgeConfig(I2C2, DISABLE);
  I2C_Send7bitAddress(I2C2, (uint8_t) (addr << 1), I2C_Direction_Receiver);
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

// Write and read back; on a mismatch the register is kept for codec_bad_reg().
static bool write_check(uint8_t reg, uint8_t val) {
  uint8_t got = 0;
  if (!codec_write(reg, val) || !codec_read(reg, &got)) return false;
  if (got != val) {
    bad_reg = reg;
    bad_got = got;
    bad_want = val;
    state = CODEC_BAD_REGS;
    return false;
  }
  return true;
}

codec_state_t codec_prepare(uint32_t rate) {
  static bool i2c_ready;
  if (!i2c_ready) {
    i2c_init();
    i2c_ready = true;
  }

  // Reset with SCKI (Y1, free running) and the supplies stable. The internal
  // reset is released 3846 SCKI (157 us) after RST goes high; the registers are
  // at their defaults then and the ADC is a slave, so BCK / LRCK stay low.
  board_codec_reset(true);
  board_delay_ms(2);
  board_codec_reset(false);
  board_delay_ms(1);

  // Find the address (codec.h) and identify the chip by a reset default: ADC
  // attenuation 1 = 0 dB (0xD7). Second round after an I2C bus reset.
  static const uint8_t addrs[] = {ADDR_S3_MASTER, ADDR_S3_SLAVE, ADDR_S2};
  uint8_t id = 0;
  found = 0;
  for (int round = 0; round < 2 && !found; round++) {
    if (round) i2c_init();
    for (unsigned i = 0; i < sizeof(addrs) && !found; i++) {
      addr = addrs[i];
      if (codec_read(PCM_ADC_ATT0 + 1, &id)) found = addr;
    }
  }
  if (!found) {
    board_codec_reset(true);
    return state = CODEC_NO_ACK;
  }
  state = CODEC_OFF;
  if (id != 0xD7) {
    bad_reg = PCM_ADC_ATT0 + 1;
    bad_got = id;
    bad_want = 0xD7;
    board_codec_reset(true);
    return state = CODEC_BAD_REGS;
  }

  // Analog chain (docs/research.md D3-D5): single-ended inputs, HPF off so DC
  // passes, ADC inverted against the inverting input drivers; DAC outputs in
  // their normal phase (difference amplifier, VOUTn- to its inverting input).
  // De-emphasis, mutes and attenuators stay at their defaults (off, 0 dB).
  bool const ok = write_check(PCM_DAC_CTL1, DAC_TDM_I2S) &&
                  write_check(PCM_ADC_CTL2, ADC_BYP_ALL) &&
                  write_check(PCM_ADC_INPUT, ADC_ALL6) &&
                  write_check(PCM_ADC_PHASE, ADC_ALL6) &&
                  write_check(PCM_DAC_PHASE, 0x00) &&
                  write_check(PCM_DAC_MUTE, 0x00);
  if (!ok) {
    board_codec_reset(true);
    if (state != CODEC_BAD_REGS) state = CODEC_NO_ACK;
    return state;
  }
  state_rate = rate;
  return state = CODEC_READY;
}

bool codec_alive(void) {
  uint8_t v;
  return found && codec_read(PCM_ADC_ATT0 + 1, &v);
}

// Clock master only: with CLK IN connected the link receiver drives BCK / LRCK
// (100R in series), so the ADC stays a slave and nothing is started here.
bool codec_run(void) {
  if (codec_linked()) return false;
  uint8_t const ctl = (state_rate == 96000 ? ADC_MASTER_256 : ADC_MASTER_512) | ADC_TDM_I2S;
  if (state == CODEC_READY && codec_write(PCM_ADC_CTL1, ctl)) {
    state = CODEC_RUNNING;
    return true;
  }
  board_codec_reset(true);
  state = CODEC_OFF;
  return false;
}

void codec_stop(void) {
  board_codec_reset(true);
  state = CODEC_OFF;
}
