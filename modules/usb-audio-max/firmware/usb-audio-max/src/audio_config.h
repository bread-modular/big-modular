// Audio stream constants shared by the USB descriptors, TinyUSB and the TDM path.
#ifndef AUDIO_CONFIG_H_
#define AUDIO_CONFIG_H_

#define AUDIO_IN_CHANNELS      6      // IN 1-6 jacks -> host
#define AUDIO_OUT_CHANNELS     8      // host -> OUT 1-8 jacks
#define AUDIO_SUBSLOT_BYTES    4      // 24-bit samples, MSB-justified in 32-bit subslots
#define AUDIO_RESOLUTION       24
#define AUDIO_IN_FRAME_BYTES   (AUDIO_IN_CHANNELS * AUDIO_SUBSLOT_BYTES)
#define AUDIO_OUT_FRAME_BYTES  (AUDIO_OUT_CHANNELS * AUDIO_SUBSLOT_BYTES)
// 48 kHz only: 96 kHz needs the second TDM line pair on SPI1 (not used yet).
#define AUDIO_RATE             48000

// High-speed iso packet: one per 125 us microframe, nominal + 1 frame.
#define AUDIO_EP_OUT_SIZE      ((AUDIO_RATE / 8000 + 1) * AUDIO_OUT_FRAME_BYTES)
#define AUDIO_EP_IN_SIZE       ((AUDIO_RATE / 8000 + 1) * AUDIO_IN_FRAME_BYTES)

// Buffers between USB and TDM, as modules/usb-audio: each stream is held at
// its target level (never less than AUDIO_TARGET_MS of audio, audio.c).
//   OUT: TinyUSB FIFO, bytes: the largest target (AUDIO_TARGET_MS_MAX, reached
//        after OUT underruns) + one TDM block + the 3 ms the level may rise
//        before the surplus is dropped = 384 frames.
//   IN:  ring in audio.c, frames (power of two): target + one TDM block + the
//        2 ms before an idle host is noticed + the block written meanwhile.
#define AUDIO_OUT_FIFO_BYTES   (384 * AUDIO_OUT_FRAME_BYTES)
#define AUDIO_IN_RING_FRAMES   512
#define AUDIO_TARGET_MS        2
#define AUDIO_TARGET_MS_MAX    4

#endif
