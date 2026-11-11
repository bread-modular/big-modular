// TinyUSB configuration: USBHS device, UAC2 (2 out + 2 in, async with
// explicit feedback) + CDC console.
#ifndef TUSB_CONFIG_H_
#define TUSB_CONFIG_H_

#include "audio_config.h"

#define CFG_TUSB_OS               OPT_OS_NONE
#define CFG_TUSB_DEBUG            0
#define CFG_TUD_ENABLED           1
#define CFG_TUD_MAX_SPEED         OPT_MODE_HIGH_SPEED
#define CFG_TUSB_MEM_SECTION
#define CFG_TUSB_MEM_ALIGN        __attribute__((aligned(4)))
#define CFG_TUD_ENDPOINT0_SIZE    64

#define CFG_TUD_AUDIO             1
#define CFG_TUD_CDC               1
#define CFG_TUD_MSC               0
#define CFG_TUD_HID               0
#define CFG_TUD_MIDI              0
#define CFG_TUD_VENDOR            0

// CDC console
#define CFG_TUD_CDC_RX_BUFSIZE    512
#define CFG_TUD_CDC_TX_BUFSIZE    2048
#define CFG_TUD_CDC_EP_BUFSIZE    512

// Audio: one 24-bit-in-32 format, 48 / 96 / 192 kHz on one clock source.
#define CFG_TUD_AUDIO_ENABLE_EP_OUT              1
#define CFG_TUD_AUDIO_ENABLE_EP_IN               1
#define CFG_TUD_AUDIO_ENABLE_FEEDBACK_EP         1
// The IN packet sizes come from audio.c (one staged packet per microframe).
#define CFG_TUD_AUDIO_EP_IN_FLOW_CONTROL         0
#define CFG_TUD_AUDIO_FUNC_1_EP_OUT_SZ_MAX       AUDIO_EP_SIZE
#define CFG_TUD_AUDIO_FUNC_1_EP_IN_SZ_MAX        AUDIO_EP_SIZE
#define CFG_TUD_AUDIO_FUNC_1_EP_OUT_SW_BUF_SZ    AUDIO_OUT_FIFO_BYTES
#define CFG_TUD_AUDIO_FUNC_1_EP_IN_SW_BUF_SZ     (2 * AUDIO_EP_SIZE)

#endif
