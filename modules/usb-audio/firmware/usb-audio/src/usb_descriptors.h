#ifndef USB_DESCRIPTORS_H_
#define USB_DESCRIPTORS_H_

enum {
  ITF_NUM_AUDIO_CONTROL = 0,
  ITF_NUM_AUDIO_STREAMING_OUT,   // host -> OUT 1/2 jacks
  ITF_NUM_AUDIO_STREAMING_IN,    // IN 1/2 jacks -> host
  ITF_NUM_CDC,
  ITF_NUM_CDC_DATA,
  ITF_NUM_TOTAL
};

// UAC2 entity IDs
#define UAC2_ENTITY_CLOCK          0x04
#define UAC2_ENTITY_OUT_USB_IT     0x01   // USB streaming -> codec DAC
#define UAC2_ENTITY_OUT_LINE_OT    0x03
#define UAC2_ENTITY_IN_LINE_IT     0x11   // codec ADC -> USB streaming
#define UAC2_ENTITY_IN_USB_OT      0x13

// Endpoints
#define EPNUM_AUDIO_OUT   0x01
#define EPNUM_AUDIO_IN    0x81
#define EPNUM_AUDIO_FB    0x82
#define EPNUM_CDC_NOTIF   0x83
#define EPNUM_CDC_OUT     0x04
#define EPNUM_CDC_IN      0x84

#endif
