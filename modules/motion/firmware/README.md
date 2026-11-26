# MOTION firmware (ATtiny1616)

Four knobs, four CV outputs, takes recorded straight into the MB85RC256V FRAM. Written
2026-11-24 for the S1 / R1 board; pin map from `../tools/build_schematic.py` (circuit in
`../docs/research.md` section 3). No Bread Modular firmware exists for this module.

| Pin | Use |
|---|---|
| PA1 / PA2 / PA6 / PA7 | Knobs 1-4, ADC0, VDD reference, 12 bits (16x accumulated) |
| PB0 / PB1 | SCL / SDA, TWI0 400 kHz: FRAM U4 0x50, DAC U3 0x60 |
| PB2 / PA3 / PA4 / PA5 | Motion LEDs 1-4, TCA0 split WO2..WO5 |
| PB3 / PB4 | REC / DEL LEDs (schematic `LED_REC` / `LED_RANGE`), TCA0 WO0 / WO1 on their `PORTMUX.CTRLC` alternates |
| PC0 / PC1 | REC / DEL buttons (schematic SW1 REC / SW2 RANGE) to GND, internal pull-ups |
| PB5, PC2, PC3 | Spare: input pull-up |

## Use on the panel

Every output is -5..+5 V (no range setting, user 2026-11-26). The second button (SW2, `RANGE`
on the S1 schematic) is **DEL**.

- **No take**: the output follows its knob, knob centre = 0 V.
- **Record** (REC only records): hold REC and move a knob. From its first move (48 counts of
  4095 past where it was at the press) until REC is released, that knob is recorded, 50 frames
  a second, straight into the FRAM; its output follows the knob. Every knob moved in the same
  hold gets its own take with its own length. REC LED on while held, blinking while recording.
- **Loop**: at the release each take loops on its own: the take, then a glide from its last
  value back to its first (a quarter of the take, 250 ms .. 2 s, shorter for steps under
  2.5 V), so the loop never jumps. Takes of different lengths drift against each other. Up to **81.7 s per
  knob** (4088 frames); a full take closes itself and loops while REC is still held.
- **Re-record**: move a knob that has a take during a REC hold; the new take replaces it, no
  overdub: only the knob is recorded. The output fades from what was playing to the knob over
  300 ms; that fade is heard, not recorded.
- **Attenuate (the knob)**: for 1 s after its take closes the knob does nothing (the hand
  leaves it). After that, once the knob has moved 48 counts, it scales the take towards 0 V:
  turning it fully down takes the gain to 0 (0 V), fully up to 1 (the take as recorded), in
  proportion in between from where it started, so the level never jumps. When the knob rests
  1 s the gain is saved and the next turn starts from there (so a knob left at its bottom end
  can be turned up, rested, then turned down). A take loaded at power-up is attenuated the same
  way from the knob's first move.
- **Delete one take**: hold DEL and move a knob: its take is deleted and the output glides to
  the knob over 0.6 s. Other takes play on.
- **Erase all**: hold DEL 5 s without moving a knob. The DEL LED stays on for 1 s, then blinks
  faster each second; at 5 s every take is erased, all six LEDs flash three times and each
  output glides to its knob over 0.6 s. A knob moved in the hold stops the countdown.
- **REC and DEL**: the button pressed first owns the hold; the other is ignored until it is
  pressed again on its own. A take shorter than 0.2 s is dropped.
- **Motion LEDs**: brightness = output voltage, 0 V off, +5 V full (squared). Below 0 V the LED
  blinks (4 a second) at the brightness of the voltage, so the knob from left to right is:
  bright blink, dimmer blink, off at the centre, steady and brighter to +5 V.
- **Always saved**: takes and gains are in the FRAM. Each recorded frame also updates its
  take's length, so a power cut mid-take keeps what was recorded until then.
- **No FRAM on the bus** at power-up: the REC LED flashes five times, the knobs work live,
  nothing records.

## Details

- **FRAM layout** (`motion/MotionIo.h`): magic `MOT` + version at 0x0000, 0x0004 reserved (the
  old range byte, ignored; takes recorded by the range builds load unchanged, they are stored as
  output codes), four track headers (frames, gain 0..4096 = 0..1; u16 LE) at 0x0008, frames from 0x0040, 8176
  bytes per track (12-bit DAC codes, 2048 = 0 V, u16 LE). A FRAM without the magic of this
  version (2; version 1 held knob positions + offset references) is initialised empty.
- **DAC**: MCP4728 fast write of all four channels once a millisecond when a code changed;
  VREF = VDD (+5VA) is selected at every start. The recorder works in DAC codes: a knob
  maps 1:1 onto 0..4095 (-5..+5 V); gains scale around 2048. At the first start on a new chip the firmware writes VREF = VDD,
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
| `motion/MotionRecorder.h` | Take recorder (no Arduino dependency): the modules/16bit cpx4 `FreeMotionRecorder` behaviour in integer maths on a frame store, plus REC / DEL handling (knob attenuation, delete one, 5 s DEL erase) |
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

Built 2026-11-26 with arduino-cli (megaTinyCore 2.6.11): 9840 B flash, 383 B RAM. Host test:
84 checks pass. Earlier 2026-11-26 builds were flashed and tried by the user (a take recorded
and played fine; the RANGE click was confusing). This build (range removed, -5..+5 V only,
DEL button, knob attenuates 1 s after its take) **not flashed**.
