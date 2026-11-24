# MOTION firmware (ATtiny1616)

Four knobs, four CV outputs, takes recorded straight into the MB85RC256V FRAM. Written
2026-11-24 for the S1 / R1 board; pin map from `../tools/build_schematic.py` (circuit in
`../docs/research.md` section 3). No Bread Modular firmware exists for this module.

| Pin | Use |
|---|---|
| PA1 / PA2 / PA6 / PA7 | Knobs 1-4, ADC0, VDD reference, 12 bits (16x accumulated) |
| PB0 / PB1 | SCL / SDA, TWI0 400 kHz: FRAM U4 0x50, DAC U3 0x60 |
| PB2 / PA3 / PA4 / PA5 | Motion LEDs 1-4, TCA0 split WO2..WO5 |
| PB3 / PB4 | REC / RANGE LEDs, TCA0 WO0 / WO1 on their `PORTMUX.CTRLC` alternates |
| PC0 / PC1 | REC / RANGE buttons to GND, internal pull-ups |
| PB5, PC2, PC3 | Spare: input pull-up |

## Use on the panel

- **No take**: the output follows its knob.
- **Record**: hold REC and move a knob. From its first move (48 counts of 4095 past where it
  was at the press) until REC is released, that knob is recorded, 50 frames a second, straight
  into the FRAM; its output follows the knob. Every knob moved in the same hold gets its own
  take with its own length. REC LED blinks while recording.
- **Loop**: at the release each take loops on its own: the take, then a glide from its last
  value back to its first (a quarter of the take, 250 ms .. 2 s, shorter for small steps), so
  the loop never jumps. Takes of different lengths drift against each other. Up to **81.7 s per
  knob** (4088 frames); a full take closes itself and loops while REC is still held.
- **Re-record**: move a knob that has a take during a hold; the new take replaces it. The
  output fades from what was playing to the knob over 300 ms (and that is recorded).
- **Move a take up / down**: 0.5 s after the release the knob's position becomes the take's
  reference; turning the knob shifts the whole take by the distance from it, clipped at the
  range ends. The reference is saved, so after power-up a knob that was moved while the module
  was off plays its take shifted by that distance.
- **Erase**: hold REC 5 s without moving a knob. The REC LED stays on for 1 s, then blinks faster
  each second; at 5 s every take is erased, all six LEDs flash three times and each output
  glides to its knob over 0.6 s. Knobs moved later in the same hold are not recorded. A take
  shorter than 0.2 s is dropped.
- **RANGE**: a click toggles all four outputs between 0..+5 V (LED off) and -5..+5 V (LED on).
  The takes are stored as knob positions, so a take plays over the whole selected range.
- **Motion LEDs**: brightness = output position in the selected range (squared).
- **Always saved**: takes, references and the range are in the FRAM. Each recorded frame also
  updates its take's length, so a power cut mid-take keeps what was recorded until then.
- **No FRAM on the bus** at power-up: the REC LED flashes five times, the knobs work live,
  nothing records.

## Details

- **FRAM layout** (`motion/MotionIo.h`): magic `MOT` + version at 0x0000, range at 0x0004,
  four track headers (frames, reference; u16 LE) at 0x0008, frames from 0x0040, 8176 bytes per
  track (12-bit knob values, u16 LE). A FRAM without the magic is initialised empty, range off.
- **DAC**: MCP4728 fast write of all four channels once a millisecond when a code changed;
  VREF = VDD (+5VA) is selected at every start. RANGE off uses codes 2048..4095 (0..+5 V),
  on uses 0..4095 (-5..+5 V). At the first start on a new chip the firmware writes VREF = VDD,
  gain 1, mid-scale into the DAC EEPROM (`research.md` section 3), so the outputs start at 0 V
  before the MCU runs; it checks that EEPROM at each start and rewrites it only if it differs.
- **Knobs**: one knob read per millisecond (each every 4 ms), one-pole low-pass, 16 counts of dead
  zone at each end so the knob reaches 0 / 4095, 2-count hysteresis so a resting knob does not
  move its output.
- **Timing**: one pass per millisecond on `millis()` (TCD0); the recorder works from the clock,
  so a slow pass leaves no gap in a take. FRAM traffic: one frame read per playing track per
  20 ms, one frame + header write per recording track per 20 ms. Pass length not measured on a
  board (estimate: < 1 ms, DAC write ~0.23 ms + 16 ADC conversions).
- **LEDs**: TCA0 split mode, 20 MHz / 64 / 255 = 1.2 kHz, duty 0 = compare output off.

| File | Contents |
|---|---|
| `motion/motion.ino` | Board IO: FRAM, DAC, knobs, buttons, LEDs, main loop |
| `motion/MotionRecorder.h` | Take recorder (no Arduino dependency): the modules/16bit cpx4 `FreeMotionRecorder` behaviour in integer maths on a frame store, plus the 5 s erase |
| `motion/MotionIo.h` | FRAM layout, DAC codes, knob filter, LED curve |
| `tools/sim_motion.cpp`, `test.sh` | Host test: recorder on an array FRAM + the helpers |

## Build and flash

```sh
./setup.sh                 # once: arduino-cli + megaTinyCore into ~/bin
./test.sh                  # host test (c++, ASan / UBSan)
./compile.sh               # build only
./flash.sh                 # build + flash, pick the UPDI port
./flash.sh /dev/ttyACM0    # explicit port
```

The wrappers call the shared `opt/attiny1616-tools` scripts (20 MHz internal, `jtag2updi`
programmer by default, `PROGRAMMER=` to override). Flash through J6 (pin 1 UPDI, pin 2 GND)
with the module on Eurorack power; the MCU runs at 5 V.

Built 2026-11-24 with arduino-cli (megaTinyCore 2.6.11): 8810 B flash, 331 B RAM, no warnings
with `--warnings all`. Host test: 55 checks pass. **Not flashed, not bench-tested.**
