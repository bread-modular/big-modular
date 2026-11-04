# MCC firmware (ATtiny1616)

Port of the Bread Modular MCC firmware
(`~/data/projects/bread-modular/modules/mcc/code/mcc`, MCC VERSION 1.0.2,
commit `aec7e9a`): CV -> MIDI CC. The carrier keeps the BM MCC pin map and adds
four CV inputs on spare ADC pins (`../tools/build_schematic.py`,
`../docs/research.md`).

| Pin | Use |
|---|---|
| PA4-PA7 | knobs 1-4 (RV1-RV4, 0..5 V) |
| PB0 / PB1 / PA2 / PA3 | CV 1-4 in (8bit CV stage: -5.5..+5.5 V -> 0..5 V, 0 V ~ 509 counts) |
| PC0 | BANK button (to GND): bank A / B / C = CC base 20 / 27 / 85, saved in EEPROM |
| PC1-PC3 | bank A / B / C LEDs (5 % brightness, software PWM) |
| PB3 / PB2 | MIDI RX (through JP1) / MIDI TX (through JP2) |

Channel n sends CC (base + n - 1) on MIDI channel 1 with
**knob n + CV n**: the CV (ADC counts from 0 V, +/-3 counts dead band) adds to
the knob reading, clamped to 0..1023, then / 8 = 0..127. +5 V is about +463
counts (~ +58 CC steps), close to half the knob travel. Unpatched, the jack tip
is grounded (0 V), so the knob alone sets the CC, as BM. As BM, values are sent
on change (checked every 10 ms) and all four every second, and incoming note
on / off, CC and realtime messages are passed through to MIDI out.

## JP1 setting (required)

JP1 picks the MIDI input path, and the firmware must match it. Pass it as the
first argument of `compile.sh` / `flash.sh` (or interactively, or `JP1=`):

| Setting | JP1 | Define | RX (PB3) |
|---|---|---|---|
| `p` | 1-2 (silk P), protected NPN front end | `MIDI_RX_INVERT=1` | inverted: `PORT_INVEN` |
| `d` | 2-3 (silk D), direct (as BM) | `MIDI_RX_INVERT=0` | not inverted |

A build without `MIDI_RX_INVERT` stops with `#error`. JP2 (MIDI out) needs no
firmware setting: both paths are non-inverting. JP1 and JP2 ship open: solder
one side of each first.

## Use

```sh
./setup.sh                    # once: arduino-cli + megaTinyCore into ~/bin
./compile.sh p                # build only
./flash.sh p                  # build + flash, pick the UPDI port
./flash.sh d /dev/ttyUSB0     # explicit port (macOS: /dev/cu.usbserial-XXXX)
```

`compile.sh` / `flash.sh` call the shared `opt/attiny1616-tools` scripts
(20 MHz internal, `jtag2updi` programmer by default, `PROGRAMMER=` to override)
through `jumper.sh`, as `modules/low/firmware`. Flash through J4 (UPDI) with
the module powered from the ±12 V header.

## Changes from Bread Modular

- `mcc.ino`: the `MIDI_RX_INVERT` guard and `PORTB.PIN3CTRL |= PORT_INVEN_bm`
  after `midi.begin()` for JP1 = P; the four CV inputs added to the knobs
  (`readCc`, the `modules/8bit` lfo knob + CV offset with the same zero and
  dead band); the bank LEDs at 1 % brightness (`LED_ON_STEPS`): software
  PWM on PC1-PC3 from a 20 kHz TCB0 interrupt, 200 Hz, 1 of 100 steps on.
- Build scripts: module wrappers (`compile.sh`, `flash.sh`, `jumper.sh`) over the
  shared `opt/attiny1616-tools` instead of BM's copies; BM's README is folded
  into this one.
- `SimpleMIDI.h`, `ModeHandler.h`, `LEDToggler.h` are the BM files, unchanged.

Built with arduino-cli 2026-11-04 (megaTinyCore 2.6.11), `p` / `d`: 3970 / 3960 B
flash (BM: 3824 B), 199 B RAM. Not bench-tested on the MCC carrier yet;
`CV_IN_ZERO` (509) is the nominal 0 V reading, calibrate per unit.
