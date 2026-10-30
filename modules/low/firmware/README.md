# LOW firmware (ATtiny1616)

Port of the Bread Modular MCO firmware
(`~/data/projects/bread-modular/modules/mco/code/mco`, MCO VERSION 1.0.1,
commit `ed24597`). The LOW carrier keeps the BM MCO pin map
(`../docs/research.md` §2-3), so the sources are BM's apart from the JP1
change below.

| Pin | Use |
|---|---|
| PB3 | MIDI RX (USART, channel 1) |
| PB4 / PB5 | Tone 1 (TCB0) / tone 2 (TCB1, detuned) square waves -> U3A mix |
| PB0 | DETUNE knob (RV1): tone 2 is 0..12 semitones below tone 1 |
| PA6 | DAC = note velocity (0 on note off) -> VEL_CV, the CV normal of the LPG |
| PA7, PB2 | BM gate / TX: still driven, not connected on this board |

The MIX knob (RV2) is analog (tone 2 level), not read by the firmware.
Unpatched, the module is a MIDI-velocity low-pass gate: note on opens the
vactrols by the velocity, note off (any note) closes them.

## JP1 setting (required)

JP1 picks the MIDI input path, and the firmware must match it. Pass it as the
first argument of `compile.sh` / `flash.sh` (or interactively, or `JP1=`):

| Setting | JP1 | Define | RX (PB3) |
|---|---|---|---|
| `p` | 1-2 (silk P), protected NPN front end | `MIDI_RX_INVERT=1` | inverted: `PORT_INVEN` |
| `d` | 2-3 (silk D), direct (as BM; 3.3 V senders only) | `MIDI_RX_INVERT=0` | not inverted |

A build without `MIDI_RX_INVERT` stops with `#error`. A firmware built for the
other setting receives nothing usable. JP1 ships open: solder one side first.

## Use

```sh
./setup.sh                    # once: arduino-cli + megaTinyCore into ~/bin
./compile.sh p                # build only
./flash.sh p                  # build + flash, pick the UPDI port
./flash.sh d /dev/ttyUSB0     # explicit port (macOS: /dev/cu.usbserial-XXXX)
```

`compile.sh` / `flash.sh` call the shared `opt/attiny1616-tools` scripts
(20 MHz internal, `jtag2updi` programmer by default, `PROGRAMMER=` to override)
through `jumper.sh`, as `modules/8bit/firmware`. Flash through J11 (UPDI) with
the module powered from the ±12 V header.

## Changes from Bread Modular

- `mco.ino`: the `MIDI_RX_INVERT` guard and `PORTB.PIN3CTRL |= PORT_INVEN_bm`
  after `MIDI.begin(1)` for JP1 = P (as the 8bit firmwares).
- Build scripts: module wrappers (`compile.sh`, `flash.sh`, `jumper.sh`) over the
  shared `opt/attiny1616-tools` instead of BM's symlinks; BM's README is folded
  into this one.
- Everything else (`tones.*`, `utils.*`, the vendored FortySevenEffects MIDI
  Library v5.0.2) is the BM file, unchanged. As BM, the velocity DAC uses the
  4.34 V reference setting at VDD = 3.3 V (BM comment: forces VDD as the
  reference), so velocity 127 gives about the +3V3 rail.

Built with arduino-cli 2026-10-30 (megaTinyCore 2.6.11), `p` / `d`:
6610 / 6600 B flash (BM: 6600 B), 373 B RAM. Not bench-tested on the LOW
carrier yet.
