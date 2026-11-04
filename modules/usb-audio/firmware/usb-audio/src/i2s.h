// Two I2S slaves on the codec's SCLK/LRCK: I2S2 receives SDOUT (ADC), I2S3
// sends SDIN (DAC). 32-bit slots, circular DMA in two halves of
// AUDIO_BLOCK_FRAMES; every half calls audio.c from the audio worker
// (i2s_service).
//
// Start (measured on the board, 2026-11-04): the CH32V307 slaves do not wait
// for a WS edge. Enabled while the clocks run, they start their 64-bit frame
// wherever the enable lands, so the bit alignment changed with the enable
// timing (a lost sign bit on the DAC was the output distortion). Enabled while
// the codec holds SCLK / LRCK still (after a codec reset, before PDN is
// cleared), both start on the codec's first SCLK edge with the same alignment
// every time, at 48, 96 and 192 kHz and whatever the codec's I2S / LJ setting:
//   - each 32-bit word is one codec slot, channel B (right) first;
//   - the codec's 24 data bits are word bits 30..7 both ways (one bit later
//     than MSB-first). RX bits 6..1 are always zero (codec slot bits 25..30),
//     which i2s_check() uses to catch a slip.
// CPOL low. CPOL high gives the I2S alignment directly but samples on the
// codec's data edges: bit-7 races, and a 192 kHz start failed with APB1 at
// 36 MHz, where CPOL low still held.
#ifndef I2S_H_
#define I2S_H_

#include <stdbool.h>
#include <stdint.h>

#define I2S_SLOT_A 1   // codec channel A = IN 1 / OUT 1
#define I2S_SLOT_B 0   // codec channel B = IN 2 / OUT 2
#define I2S_RX_ZERO_BITS 0x0000007Eu

// Received word -> sample MSB-justified in 32 bits (24 bits used).
static inline uint32_t i2s_rx_to_sample(uint32_t w) {
  return (w << 1) & 0xFFFFFF00u;
}

// Sample MSB-justified in 32 bits (24 bits used) -> word to send.
static inline uint32_t i2s_sample_to_tx(uint32_t s) {
  return (uint32_t) ((int32_t) (s & 0xFFFFFF00u) >> 1);
}

// Arm and enable both slaves. The codec must hold its clocks still
// (codec_prepare); its first SCLK edge after codec_run() starts the frames.
void i2s_start(void);
void i2s_stop(void);
bool i2s_running(void);
// Called from the main loop: true while both streams are healthy. Returns
// false (and stops) on an overrun / underrun, a slip or when the clocks stop.
bool i2s_check(void);
// True once LRCK toggles within `timeout_us` (after codec_run: the slaves are running).
bool i2s_lrck_toggling(uint32_t timeout_us);
// Audio worker (board.c): services one DMA half that is ready, false if none is.
bool i2s_service(void);
// audio.c: a received half had non-zero bits in I2S_RX_ZERO_BITS.
void i2s_report_slip(void);

extern volatile uint32_t i2s_rx_blocks, i2s_tx_blocks;
extern uint32_t i2s_err_ovr, i2s_err_udr, i2s_err_stall, i2s_err_late, i2s_err_slip;

#endif
