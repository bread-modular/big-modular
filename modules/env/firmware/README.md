# ENV firmware (ATtiny1616)

The ACID envelope firmware (`modules/acid/firmware`: Bread Modular ENV 1.2.1, commit `aec7e9a`,
plus the shared `CvRecorder` on REC) without the MCO, plus GATE IN. Pin map:
`../docs/research.md` 2; 5 V supply and DAC contract: research.md 6.

| Pin | Use |
|---|---|
| PB3 | MIDI RX (USART0, channel 1, receive only) |
| PB2 | GATE IN (Q2 collector, inverted: low = gate high at the jack). Also USART0 TX, which stays disabled |
| PB1 | GATE_SENSE: high = GATE IN patched (MIDI notes bypassed), low = MIDI notes drive the envelope |
| PA6 | DAC = envelope, codes 0..194 on the 4.34 V reference -> TL072 x1.51 -> ENV OUT ~0..5 V |
| PA1 / PA2 | ATTACK (hold in HR) / RELEASE knobs, ADC reference VDD |
| PC0 | MODE button: envelope model |
| PC1 / PA4 / PA5 | HR / AR / ASR LEDs, the selected one lit at 10 % |
| PC2 / PC3 | REC button / LED |
| PA3, PA7, PB0, PB4, PB5 | NC: input pull-up |

- **Gate**: with nothing in GATE IN the MIDI gate (note-on .. note-off, channel 1) drives the
  envelope; note-off closes it only for the last note-on, so legato notes hold it open. With a
  cable in GATE IN (PB1 high for 20 ms, debounced against the TN contact bouncing during
  insertion) the jack gate drives it and MIDI notes are ignored; MIDI CC, clock and Start still
  work. Pulling the cable hands back to the current MIDI gate.
- **Envelope**: as ACID. **HR** instant attack, hold 1..100 ms (ATTACK), release 0..100 ms;
  **AR** attack 0..1 s, release 0..1 s (one-shot); **ASR** attack 0..0.5 s, sustain while the
  gate is high, release 0..1 s. Phases are timed from the clock; a knob <= 8 counts as 0, and an
  instant attack holds full level for at least 1 ms. MIDI CC 22 / CC 75 add to ATTACK / RELEASE,
  as BM. Envelope 0..255 is scaled to DAC codes 0..194 (not clipped), so ENV OUT tops at ~5 V.
  At level 0 the DAC output is switched off and PA6 is driven low as a GPIO, so a silent
  envelope is a hard 0 V (the DAC zero-scale offset leaked through the no-dead-zone
  modules/vca-mix vactrol driver).
- **MODE**: a click (50 ms debounce) steps HR -> AR -> ASR, stored in EEPROM (BM index 1). The
  selected model's LED stays lit at 10 % (the ENV LED at the jack shows the envelope level).
  TCA0 split mode at 305 Hz:
  PA4 / PA5 hardware PWM, PC1 software PWM.
- **REC**: 4-bar ATTACK/RELEASE motion recorder on MIDI clock (shared
  `opt/attiny1616-tools/lib/CvRecorder`): click to record (LED blinks), after 4 bars it loops
  (LED solid); the knobs are ignored for the first looped pass, then shift the recorded curve.
  Click again for live knobs. Needs a running MIDI clock on MIDI IN, also when GATE IN is
  patched; MIDI Start rewinds. The take is in RAM only.

## JP1 setting (required)

JP1 picks the MIDI input path, and the firmware must match it. Pass it as the first argument of
`compile.sh` / `flash.sh` (or interactively, or `JP1=`):

| Setting | JP1 | Define | RX (PB3) |
|---|---|---|---|
| `p` | 1-2 (silk P), protected NPN front end; use it for 3.3 V senders | `MIDI_RX_INVERT=1` | inverted: `PORT_INVEN` |
| `d` | 2-3 (silk D), direct, unprotected, 5 V logic senders only | `MIDI_RX_INVERT=0` | not inverted |

A build without `MIDI_RX_INVERT` stops with `#error`. JP1 ships open: solder one side first.

## Use

```sh
./setup.sh                    # once: arduino-cli + megaTinyCore into ~/bin
./compile.sh p                # build only
./flash.sh p                  # build + flash, pick the UPDI port
./flash.sh d /dev/ttyUSB0     # explicit port (macOS: /dev/cu.usbserial-XXXX)
```

`compile.sh` / `flash.sh` call the shared `opt/attiny1616-tools` scripts (20 MHz internal,
`jtag2updi` programmer by default, `PROGRAMMER=` to override) through `jumper.sh`, as ACID.
Flash through J4 (UPDI, B silk `UPDI` / `GND`) with the module powered from the ±12 V header;
the MCU runs at 5 V, so use a 5 V-compatible programmer.

## Changes from ACID

- `env.ino` (from `acid.ino`): MCO removed (tones, DETUNE, `tones.*`, `utils.*`); GATE IN on
  PB2 with the PB1 jack-detect bypass; unused pins pulled up; no start message.
- `serialMIDI.h`: the USART starts with `SERIAL_RX_ONLY` and the MIDI thru is off, because the
  USART0 TX pin PB2 is GATE IN here (ACID left PB2 NC). A TX driver on PB2 would fight Q2 and
  hide the gate. Nothing in the sketch writes to `Serial`.
- `EnvelopeGenerator.h`: same 0..194 scaling, comment updated for VDD = 5 V and the x1.51 stage.
- The DAC reference select is set with a mask instead of `|=` (same 4.34 V value).
- Everything else (`Env*.h`, `ToggleMode.h`, the vendored FortySevenEffects MIDI Library v5.0.2,
  `CvRecorder.h` symlink) is the ACID file.

Built with arduino-cli 2026-11-18 (megaTinyCore 2.6.11), `p` / `d`: 9770 / 9760 B flash,
1285 B RAM (768 B recorder). Not bench-tested.
