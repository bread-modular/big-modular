// Additions of the local dcd_ch32_usbhs.c (capture interrupt + processing).
#ifndef DCD_CAPTURE_H_
#define DCD_CAPTURE_H_

#include <stdint.h>

// FRAME_NO (frame in bits 10:0, microframe in bits 15:13) captured with the
// event being processed.
uint16_t dcd_ch32_event_frame(void);

// Events dropped on a full capture queue; iso packets whose end did not come.
extern volatile uint32_t dcd_capture_overflows, dcd_capture_iso_timeouts;

#endif
