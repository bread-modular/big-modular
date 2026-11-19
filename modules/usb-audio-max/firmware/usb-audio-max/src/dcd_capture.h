// Additions of the local dcd_ch32_usbhs.c (capture interrupt + processing).
#ifndef DCD_CAPTURE_H_
#define DCD_CAPTURE_H_

#include <stdint.h>

// FRAME_NO (frame in bits 10:0, microframe in bits 15:13) captured with the
// event being processed.
uint16_t dcd_ch32_event_frame(void);

// Events dropped on a full capture queue; iso packets whose end did not come;
// zero-length iso OUT packets (skipped).
extern volatile uint32_t dcd_capture_overflows, dcd_capture_iso_timeouts, dcd_iso_out_empty;

// Capture -> end of processing: the longest one (SysTick counts, cleared by the
// reader) and the number over 100 us. An iso endpoint has to be served before
// its next packet, 125 us later.
extern volatile uint32_t dcd_delay_max, dcd_delay_late;

// Iso OUT packets flagged NAK (behind a non-iso completion, INT_BUSY) that
// were taken anyway, and how many of them held the previous packet's bytes.
extern volatile uint32_t dcd_iso_out_nak, dcd_iso_out_nak_stale;

// A captured event (diagnostics: console `misses`).
typedef struct {
  uint8_t flags, fg, status;   // event, INT_FG first read, INT_ST
  uint16_t len, frame;         // RX_LEN, FRAME_NO
  uint32_t t;                  // SysTick count (HCLK, reloads every ms)
} dcd_trace_t;
// From the processing context: the last n events up to the current one.
int dcd_ch32_trace(dcd_trace_t *out, int n);

#endif
