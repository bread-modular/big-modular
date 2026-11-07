// DFU-mode descriptors: one DFU 1.1 interface, alt 0 = the application flash.
#include <string.h>

#include "tusb.h"

// pid.codes test VID/PID (development only); the application is 1209:0001.
#define USB_VID   0x1209
#define USB_PID   0x0002
#define USB_BCD   0x0100

static tusb_desc_device_t const desc_device = {
  .bLength            = sizeof(tusb_desc_device_t),
  .bDescriptorType    = TUSB_DESC_DEVICE,
  .bcdUSB             = 0x0200,
  .bDeviceClass       = 0x00,
  .bDeviceSubClass    = 0x00,
  .bDeviceProtocol    = 0x00,
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

static tusb_desc_device_qualifier_t const desc_qualifier = {
  .bLength            = sizeof(tusb_desc_device_qualifier_t),
  .bDescriptorType    = TUSB_DESC_DEVICE_QUALIFIER,
  .bcdUSB             = 0x0200,
  .bDeviceClass       = 0x00,
  .bDeviceSubClass    = 0x00,
  .bDeviceProtocol    = 0x00,
  .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,
  .bNumConfigurations = 0x00,
  .bReserved          = 0x00
};

uint8_t const *tud_descriptor_device_qualifier_cb(void) {
  return (uint8_t const *) &desc_qualifier;
}

#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_DFU_DESC_LEN(1))
#define DFU_ATTRS        (DFU_ATTR_CAN_DOWNLOAD | DFU_ATTR_MANIFESTATION_TOLERANT)

static uint8_t const desc_config[] = {
  TUD_CONFIG_DESCRIPTOR(1, 1, 0, CONFIG_TOTAL_LEN, 0x00, 100),
  TUD_DFU_DESCRIPTOR(0, 1, 4, DFU_ATTRS, 1000, CFG_TUD_DFU_XFER_BUFSIZE),
};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
  return desc_config;
}

static char const *const string_desc_arr[] = {
  NULL,                      // 0: language
  "Bread Modular",           // 1: manufacturer
  "Bread Modular 2X2 DFU bootloader", // 2: product
  NULL,                      // 3: serial, from the chip unique ID
  "application flash",       // 4: DFU alt 0
};

static uint16_t desc_str[33];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
  size_t chr_count;
  char serial[25];
  char const *str;
  if (index == 0) {
    desc_str[1] = 0x0409;
    chr_count = 1;
  } else {
    if (index == 3) {
      uint32_t const *uid = (uint32_t const *) 0x1FFFF7E8;
      static char const hex[] = "0123456789ABCDEF";
      for (int i = 0; i < 24; i++) serial[i] = hex[(uid[i / 8] >> (28 - 4 * (i % 8))) & 0xF];
      serial[24] = 0;
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
