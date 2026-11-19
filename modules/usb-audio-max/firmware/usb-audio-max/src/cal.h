// Per-channel DC calibration: input offsets, output offsets and the gain of
// every OUT -> IN loop, measured on the board and kept in the settings page.
//
//   `cal in`   IN 1-6 unpatched (0 V through the jack's normal): the input
//              offsets. Every output is driven to +2 V meanwhile, so an input
//              that is patched to an output shows up and is skipped.
//   `cal out`  outputs patched to inputs, any pairing (found from the data):
//              each output's offset and the loop gain through its input.
//   `cal ref`  optional absolute reference: a meter on one output.
//
// The loop gain is the product of the DAC and ADC gains; without a meter it
// is split evenly between the two (square root), with `cal ref` the measured
// output sets the split for every channel (the common error is the codec's
// +5VA reference, the rest is 1 % resistors). Offsets need `cal in` for the
// split too: without it an output's offset includes its input's.
// Afterwards a sample of AUDIO_FS_MV (5.87 V) full scale is that voltage at
// every OUT and reads the same on every IN.
#ifndef CAL_H_
#define CAL_H_

#include <stdbool.h>
#include <stdint.h>

// Load the saved measurements and apply them (audio_set_coef).
void cal_init(void);
// Main loop: runs a measurement started below.
void cal_task(void);
bool cal_busy(void);

void cal_start_inputs(void);     // `cal in`
void cal_start_outputs(void);    // `cal out`
void cal_start_looptest(void);   // `looptest`: the patched pairs with the calibration in use
// `cal ref <out> <volts>`: OUT `out` (1-8, set with `dc`) measured at `mv` with a meter.
bool cal_ref(int out, int32_t mv);
bool cal_erase(void);
void cal_print(void);            // `cal`: the measurements and coefficients in use
void cal_print_summary(void);    // one line for `status`

#endif
