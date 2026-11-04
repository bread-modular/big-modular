// CS4270 (carrier U3) over I2C2, address 0x48, control-port master mode.
#ifndef CODEC_H_
#define CODEC_H_

#include <stdbool.h>
#include <stdint.h>

// CS4270 registers (datasheet DS686F1 section 7)
#define CS4270_CHIPID   0x01
#define CS4270_PWRCTL   0x02
#define CS4270_MODE     0x03
#define CS4270_FORMAT   0x04
#define CS4270_TRANS    0x05
#define CS4270_MUTE     0x06
#define CS4270_VOLA     0x07
#define CS4270_VOLB     0x08

typedef enum {
  CODEC_OFF = 0,       // not started / held in reset
  CODEC_NO_ACK,        // no I2C answer at 0x48 (codec missing, unpowered or not soldered)
  CODEC_BAD_ID,        // answered, but the chip ID is not CS4270 (0xC_)
  CODEC_READY,         // configured, PDN set: SCLK / LRCK not started yet
  CODEC_RUNNING,
} codec_state_t;

// Reset, enter control-port mode and configure the I2S master for `rate`
// (48000 / 96000 / 192000), leaving PDN set so the clocks have not started:
// CODEC_READY. Every start (power-up, rate change, recovery) goes through the
// reset, so the I2S slaves see the same first clock edges (i2s.h).
codec_state_t codec_prepare(uint32_t rate);
// Clear PDN: the master clocks start. CODEC_READY -> CODEC_RUNNING.
bool codec_run(void);
void codec_stop(void);

codec_state_t codec_state(void);
uint8_t codec_chip_id(void);
bool codec_read(uint8_t reg, uint8_t *val);
bool codec_write(uint8_t reg, uint8_t val);
const char *codec_state_name(codec_state_t s);

#endif
