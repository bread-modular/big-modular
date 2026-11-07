// USB descriptors: UAC2 interface (2 ch out, 2 ch in, 24-bit, 48/96/192 kHz,
// asynchronous with an explicit feedback endpoint) + CDC console.
#include <string.h>

#include "tusb.h"
#include "usb_descriptors.h"
#include "board.h"

// pid.codes test VID/PID (development only, not for distribution).
#define USB_VID   0x1209
#define USB_PID   0x0001
#define USB_BCD   0x0100

static tusb_desc_device_t const desc_device = {
  .bLength            = sizeof(tusb_desc_device_t),
  .bDescriptorType    = TUSB_DESC_DEVICE,
  .bcdUSB             = 0x0200,
  // IAD: Miscellaneous / Common / IAD
  .bDeviceClass       = TUSB_CLASS_MISC,
  .bDeviceSubClass    = MISC_SUBCLASS_COMMON,
  .bDeviceProtocol    = MISC_PROTOCOL_IAD,
  .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,
  .idVendor           = USB_VID,
  .idProduct          = USB_PID,
  .bcdDevice          = USB_BCD,
  .iManufacturer      = 0x01,
  .iProduct           = 0x02,
  .iSerialNumber      = 0x03,
  .bNumConfigurations = 0x01
};

uint8_t const *tud_descriptor_device_cb(void) {
  return (uint8_t const *) &desc_device;
}

// Device qualifier: required for a high-speed device (no full-speed configuration is offered).
static tusb_desc_device_qualifier_t const desc_qualifier = {
  .bLength            = sizeof(tusb_desc_device_qualifier_t),
  .bDescriptorType    = TUSB_DESC_DEVICE_QUALIFIER,
  .bcdUSB             = 0x0200,
  .bDeviceClass       = TUSB_CLASS_MISC,
  .bDeviceSubClass    = MISC_SUBCLASS_COMMON,
  .bDeviceProtocol    = MISC_PROTOCOL_IAD,
  .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,
  .bNumConfigurations = 0x00,
  .bReserved          = 0x00
};

uint8_t const *tud_descriptor_device_qualifier_cb(void) {
  return (uint8_t const *) &desc_qualifier;
}

#define AUDIO_CS_AC_LEN (TUD_AUDIO20_DESC_CLK_SRC_LEN + 2 * TUD_AUDIO20_DESC_INPUT_TERM_LEN + \
                         2 * TUD_AUDIO20_DESC_OUTPUT_TERM_LEN)

#define AUDIO_DESC_LEN (TUD_AUDIO20_DESC_IAD_LEN + TUD_AUDIO20_DESC_STD_AC_LEN + TUD_AUDIO20_DESC_CS_AC_LEN + \
    AUDIO_CS_AC_LEN + \
    /* OUT: alt 0, alt 1 (data + feedback) */ \
    TUD_AUDIO20_DESC_STD_AS_LEN + TUD_AUDIO20_DESC_STD_AS_LEN + TUD_AUDIO20_DESC_CS_AS_INT_LEN + \
    TUD_AUDIO20_DESC_TYPE_I_FORMAT_LEN + TUD_AUDIO20_DESC_STD_AS_ISO_EP_LEN + TUD_AUDIO20_DESC_CS_AS_ISO_EP_LEN + \
    TUD_AUDIO20_DESC_STD_AS_ISO_FB_EP_LEN + \
    /* IN: alt 0, alt 1 */ \
    TUD_AUDIO20_DESC_STD_AS_LEN + TUD_AUDIO20_DESC_STD_AS_LEN + TUD_AUDIO20_DESC_CS_AS_INT_LEN + \
    TUD_AUDIO20_DESC_TYPE_I_FORMAT_LEN + TUD_AUDIO20_DESC_STD_AS_ISO_EP_LEN + TUD_AUDIO20_DESC_CS_AS_ISO_EP_LEN)

#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + AUDIO_DESC_LEN + TUD_CDC_DESC_LEN)

#define STEREO (AUDIO20_CHANNEL_CONFIG_FRONT_LEFT | AUDIO20_CHANNEL_CONFIG_FRONT_RIGHT)

enum { STRID_LANGID = 0, STRID_MANUFACTURER, STRID_PRODUCT, STRID_SERIAL, STRID_CDC, STRID_OUT, STRID_IN };

static uint8_t const desc_configuration[] = {
  // Self powered (the module runs from the rack): no VBUS current drawn.
  TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, TUSB_DESC_CONFIG_ATT_SELF_POWERED, 0),

  TUD_AUDIO20_DESC_IAD(ITF_NUM_AUDIO_CONTROL, 3, 0x00),
  TUD_AUDIO20_DESC_STD_AC(ITF_NUM_AUDIO_CONTROL, 0x00, STRID_PRODUCT),
  TUD_AUDIO20_DESC_CS_AC(0x0200, AUDIO20_FUNC_IO_BOX, AUDIO_CS_AC_LEN, 0x00),
  // Internal programmable clock: the codec's 24.576 MHz oscillator, 48 / 96 / 192 kHz.
  TUD_AUDIO20_DESC_CLK_SRC(UAC2_ENTITY_CLOCK, AUDIO20_CLOCK_SOURCE_ATT_INT_PRO_CLK,
                           (AUDIO20_CTRL_RW << AUDIO20_CLOCK_SOURCE_CTRL_CLK_FRQ_POS) |
                           (AUDIO20_CTRL_R << AUDIO20_CLOCK_SOURCE_CTRL_CLK_VAL_POS), 0x00, 0x00),
  // Host -> OUT 1/2
  TUD_AUDIO20_DESC_INPUT_TERM(UAC2_ENTITY_OUT_USB_IT, AUDIO_TERM_TYPE_USB_STREAMING, 0x00, UAC2_ENTITY_CLOCK,
                              AUDIO_CHANNELS, STEREO, 0x00, 0x0000, 0x00),
  TUD_AUDIO20_DESC_OUTPUT_TERM(UAC2_ENTITY_OUT_LINE_OT, AUDIO_TERM_TYPE_EXTERNAL_LINE_CONNECTOR, 0x00,
                               UAC2_ENTITY_OUT_USB_IT, UAC2_ENTITY_CLOCK, 0x0000, STRID_OUT),
  // IN 1/2 -> host
  TUD_AUDIO20_DESC_INPUT_TERM(UAC2_ENTITY_IN_LINE_IT, AUDIO_TERM_TYPE_EXTERNAL_LINE_CONNECTOR, 0x00,
                              UAC2_ENTITY_CLOCK, AUDIO_CHANNELS, STEREO, 0x00, 0x0000, STRID_IN),
  TUD_AUDIO20_DESC_OUTPUT_TERM(UAC2_ENTITY_IN_USB_OT, AUDIO_TERM_TYPE_USB_STREAMING, 0x00,
                               UAC2_ENTITY_IN_LINE_IT, UAC2_ENTITY_CLOCK, 0x0000, 0x00),

  // OUT streaming interface
  TUD_AUDIO20_DESC_STD_AS_INT(ITF_NUM_AUDIO_STREAMING_OUT, 0x00, 0x00, STRID_OUT),
  TUD_AUDIO20_DESC_STD_AS_INT(ITF_NUM_AUDIO_STREAMING_OUT, 0x01, 0x02, STRID_OUT),
  TUD_AUDIO20_DESC_CS_AS_INT(UAC2_ENTITY_OUT_USB_IT, AUDIO20_CTRL_NONE, AUDIO20_FORMAT_TYPE_I,
                             AUDIO20_DATA_FORMAT_TYPE_I_PCM, AUDIO_CHANNELS, STEREO, 0x00),
  TUD_AUDIO20_DESC_TYPE_I_FORMAT(AUDIO_SUBSLOT_BYTES, AUDIO_RESOLUTION),
  TUD_AUDIO20_DESC_STD_AS_ISO_EP(EPNUM_AUDIO_OUT,
                                 (uint8_t) (TUSB_XFER_ISOCHRONOUS | TUSB_ISO_EP_ATT_ASYNCHRONOUS | TUSB_ISO_EP_ATT_DATA),
                                 AUDIO_EP_SIZE, 0x01),
  TUD_AUDIO20_DESC_CS_AS_ISO_EP(AUDIO20_CS_AS_ISO_DATA_EP_ATT_NON_MAX_PACKETS_OK, AUDIO20_CTRL_NONE,
                                AUDIO20_CS_AS_ISO_DATA_EP_LOCK_DELAY_UNIT_UNDEFINED, 0x0000),
  // Feedback every 2^(4-1) microframes = 1 ms
  TUD_AUDIO20_DESC_STD_AS_ISO_FB_EP(EPNUM_AUDIO_FB, 4, 4),

  // IN streaming interface
  TUD_AUDIO20_DESC_STD_AS_INT(ITF_NUM_AUDIO_STREAMING_IN, 0x00, 0x00, STRID_IN),
  TUD_AUDIO20_DESC_STD_AS_INT(ITF_NUM_AUDIO_STREAMING_IN, 0x01, 0x01, STRID_IN),
  TUD_AUDIO20_DESC_CS_AS_INT(UAC2_ENTITY_IN_USB_OT, AUDIO20_CTRL_NONE, AUDIO20_FORMAT_TYPE_I,
                             AUDIO20_DATA_FORMAT_TYPE_I_PCM, AUDIO_CHANNELS, STEREO, 0x00),
  TUD_AUDIO20_DESC_TYPE_I_FORMAT(AUDIO_SUBSLOT_BYTES, AUDIO_RESOLUTION),
  TUD_AUDIO20_DESC_STD_AS_ISO_EP(EPNUM_AUDIO_IN,
                                 (uint8_t) (TUSB_XFER_ISOCHRONOUS | TUSB_ISO_EP_ATT_ASYNCHRONOUS | TUSB_ISO_EP_ATT_DATA),
                                 AUDIO_EP_SIZE, 0x01),
  TUD_AUDIO20_DESC_CS_AS_ISO_EP(AUDIO20_CS_AS_ISO_DATA_EP_ATT_NON_MAX_PACKETS_OK, AUDIO20_CTRL_NONE,
                                AUDIO20_CS_AS_ISO_DATA_EP_LOCK_DELAY_UNIT_UNDEFINED, 0x0000),

  TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, STRID_CDC, EPNUM_CDC_NOTIF, 16, EPNUM_CDC_OUT, EPNUM_CDC_IN, 512),
};

TU_VERIFY_STATIC(sizeof(desc_configuration) == CONFIG_TOTAL_LEN, "descriptor length");

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
  (void) index;
  return desc_configuration;
}

static char const *const string_desc_arr[] = {
  NULL,                      // 0: language (handled below)
  "Bread Modular",           // 1: manufacturer
  "Bread Modular 2X2",       // 2: product
  NULL,                      // 3: serial, from the chip unique ID
  "Bread Modular 2X2 console", // 4: CDC
  "OUT 1-2",                 // 5
  "IN 1-2",                  // 6
};

static uint16_t desc_str[33];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
  (void) langid;
  size_t chr_count;
  char serial[25];

  if (index == STRID_LANGID) {
    desc_str[1] = 0x0409;
    chr_count = 1;
  } else {
    char const *str;
    if (index == STRID_SERIAL) {
      board_serial(serial, sizeof(serial));
      str = serial;
    } else {
      if (index >= TU_ARRAY_SIZE(string_desc_arr)) return NULL;
      str = string_desc_arr[index];
    }
    chr_count = strlen(str);
    if (chr_count > 32) chr_count = 32;
    for (size_t i = 0; i < chr_count; i++) desc_str[1 + i] = str[i];
  }

  desc_str[0] = (uint16_t) ((TUSB_DESC_STRING << 8) | (2 * chr_count + 2));
  return desc_str;
}
