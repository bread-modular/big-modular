// Audio stream constants shared by the USB descriptors, TinyUSB and the I2S path.
#ifndef AUDIO_CONFIG_H_
#define AUDIO_CONFIG_H_

#define AUDIO_CHANNELS        2
#define AUDIO_SUBSLOT_BYTES   4      // 24-bit samples, MSB-justified in 32-bit subslots
#define AUDIO_RESOLUTION      24
#define AUDIO_FRAME_BYTES     (AUDIO_CHANNELS * AUDIO_SUBSLOT_BYTES)
#define AUDIO_RATE_MAX        192000
#define AUDIO_RATE_DEFAULT    192000

// High-speed iso packet: one per 125 us microframe, nominal + 1 frame.
#define AUDIO_EP_SIZE         ((AUDIO_RATE_MAX / 8000 + 1) * AUDIO_FRAME_BYTES)

// Software FIFOs between USB and I2S (bytes). Each stream is regulated to
// AUDIO_TARGET_MS of audio, so the FIFO must hold at least twice that at 192 kHz.
#define AUDIO_FIFO_BYTES      8192
#define AUDIO_TARGET_MS       2

// I2S DMA: two halves of AUDIO_BLOCK_FRAMES frames each direction
// (250 us at 192 kHz, 1 ms at 48 kHz).
#define AUDIO_BLOCK_FRAMES    48

#endif
