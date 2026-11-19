// TDM link to the PCM3168A at 48 kHz (single rate, BCK 256 fS = 12.288 MHz,
// 24-bit I2S-mode TDM, 8 slots of 32 BCK per frame): I2S2 slave RX <- DOUT1
// (ADC 1-6 in slots 1-6), I2S3 slave TX -> DIN1 (DAC 1-8 in slots 1-8). Both
// run with 32-bit words, circular DMA in two halves of TDM_BLOCK_FRAMES frames.
//
// The CH32V307 I2S slaves do not wait for a WS edge (modules/usb-audio,
// usb-audio/src/i2s.h): they start their words on the first BCK edge after
// they are enabled. Both are enabled while the codec still holds BCK / LRCK
// low (ADC slave after a reset), so they start on the same edge; where the
// codec frame sits in their word stream is then found from the received data
// (tdm_align_*): each slot's 24 data bits are followed by 8 zero bits and the
// noise of every ADC toggles its LSB, so the zero bits and the toggling LSBs
// mark the slots, and slots 7/8 (no ADC) stay zero. TX uses the same position.
#ifndef TDM_H_
#define TDM_H_

#include <stdbool.h>
#include <stdint.h>

#define TDM_SLOTS          8
#define TDM_IN_CHANNELS    6
#define TDM_OUT_CHANNELS   8
#define TDM_BLOCK_FRAMES   48     // 1 ms at 48 kHz per DMA half

// Audio worker context (tdm_service), once the frame position is known.
// Samples are 24-bit codes (sign-extended), channel n-1 = IN n / OUT n; a block
// is TDM_BLOCK_FRAMES frames.
void audio_tdm_rx(int32_t const in[][TDM_IN_CHANNELS]);
void audio_tdm_tx(int32_t out[][TDM_OUT_CHANNELS]);
// USB transfer processing between the quarters of a block: an iso endpoint has
// to be served within 125 us of its last packet (audio.c).
#define TDM_SERVICE_FRAMES (TDM_BLOCK_FRAMES / 4)
void audio_usb_service(void);

// Arm and enable both slaves. The codec must hold BCK still (codec_prepare);
// codec_run() starts it.
void tdm_start(void);
void tdm_stop(void);
bool tdm_running(void);
// Main loop: true while both streams are healthy. Returns false (and stops)
// on an overrun / underrun, a slip (non-zero bits where the codec sends zeros)
// or when the clocks stop.
bool tdm_check(void);
// True once LRCK toggles within `timeout_us`.
bool tdm_lrck_toggling(uint32_t timeout_us);
// Audio worker (board.c): services one DMA half that is ready, false if none is.
bool tdm_service(void);

typedef enum {
  TDM_ALIGN_NONE,        // not measured since the start
  TDM_ALIGN_MEASURING,
  TDM_ALIGN_OK,
  TDM_ALIGN_FAILED,      // no consistent slot position (no data from the ADC yet?)
} tdm_align_t;

typedef struct {
  tdm_align_t state;
  int offset;            // bit of the word stream where slot 1 starts (0..255), -1 unknown
  int lsb_toggling;      // slots 1-6 whose LSB toggled at that offset
  int candidates;        // offsets that passed (1 when unique)
  bool slots78_zero;     // slots 7/8 held zero
  uint32_t toggled[TDM_SLOTS], ones[TDM_SLOTS];   // per stream word of the frame, MSB first
} tdm_align_info_t;

// Collect the toggling / one bits over `frames` frames, then find the slot
// position (tdm_align_task in the main loop).
void tdm_align_start(uint32_t frames);
void tdm_align_task(void);
void tdm_align_get(tdm_align_info_t *info);

// The first `n` received words (<= 32) of the next DMA half.
bool tdm_raw_capture(uint32_t *words, int n, uint32_t timeout_ms);

// Worker timing (SysTick counts, cleared by the reader): the longest stretch
// of a half without a USB service point, the longest RX / TX half.
void tdm_service_mark(void);
extern uint32_t tdm_gap_max, tdm_half_max[2];

extern volatile uint32_t tdm_rx_blocks, tdm_tx_blocks;
extern uint32_t tdm_err_ovr, tdm_err_udr, tdm_err_stall, tdm_err_late, tdm_err_slip;

#endif
