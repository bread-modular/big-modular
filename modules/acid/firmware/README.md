# ACID firmware (ATtiny1616)

Merge of the Bread Modular MCO firmware (`~/data/projects/bread-modular/modules/mco/code/mco`,
MCO VERSION 1.0.1, commit `ed24597`, as `modules/low/firmware`) and the BM ENV
firmware (`.../modules/env/code/env`, ENV VERSION 1.2.1, commit `aec7e9a`) on
the one ACID MCU, plus the shared `CvRecorder` on the REC button. Pin map:
`../docs/research.md` 3.1.

| Pin | Use |
|---|---|
| PB3 | MIDI RX (USART, channel 1) |
| PB4 / PB5 | Tone 1 (TCB0) / tone 2 (TCB1, detuned) square waves -> MCO mix (AUDIO normal) |
| PB0 | DETUNE knob: tone 2 is 0..12 semitones below tone 1 |
| PA6 | DAC = envelope -> ENV_CV (SVF CV normal, ENV OUT) |
| PA1 / PA2 | ATTACK (hold in HR) / RELEASE knobs |
| PC0 | MODE button: envelope model |
| PC1 / PA4 / PA5 | HR / AR / ASR LEDs, up to 10 % brightness (the selected model's LED follows the envelope level; lit 1 s after power-up / MODE) |
| PC2 / PC3 | REC button / LED |
| PB2 | `Serial` TX (MIDI thru, start message): NC on this board |

- **MCO**: note-on sets both tones (as BM/LOW); MIX is analog.
- **Envelope**: the MIDI gate (note-on .. note-off) drives the BM ENV
  models: **HR** instant attack, hold 1..100 ms (ATTACK), release 0..100 ms;
  **AR** attack 0..1 s, release 0..1 s (one-shot); **ASR** attack 0..0.5 s,
  sustain while held, release 0..1 s. All phases are timed from the clock
  (not one step per loop) and a knob <= 8 counts as 0 (`ENV_KNOB_ZERO`). An
  instant attack holds full level for at least 1 ms (`ENV_MIN_PULSE_US`), so
  with both knobs at 0 every model gives a 1 ms pulse with an instant drop
  (ASR when the gate is shorter than 1 ms; a longer gate sustains). MIDI
  CC 22 / CC 75 add to ATTACK / RELEASE, as BM. Envelope 0..255 is scaled
  to DAC codes 0..194 = 0..3.3 V (research.md 3.2), so ENV OUT tops at ~5 V.
- **MODE**: a click (50 ms debounce) steps HR -> AR -> ASR; the model is
  stored in EEPROM (BM index 1). Its LED brightness follows the envelope
  level (0..10 %, any non-zero level lit, so ramps and release tails show;
  each trigger shows its peak for at least 30 ms, so short pulses flash),
  and it is lit at 10 % for 1 s after power-up or a MODE change to show the
  selection. PWM is TCA0 split mode at 305 Hz, 8-bit: PA4 / PA5 hardware
  PWM (WO4 / WO5), PC1 (no TCA output) software PWM on the low counter,
  whose interrupts run only while the HR LED is lit.
- **REC**: 4-bar ATTACK/RELEASE motion recorder on MIDI clock, the 8bit crash
  behaviour (shared `opt/attiny1616-tools/lib/CvRecorder`): click to record
  (LED blinks), after 4 bars it loops (LED solid); the knobs are ignored for
  the first looped pass, then shift the whole recorded curve. Click again for
  live knobs. Needs a running MIDI clock; MIDI Start rewinds. The take is in
  RAM only (lost at power-off).

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
through `jumper.sh`, as `modules/low/firmware`. Flash through J11 (UPDI, B silk
`GND UPDI`) with the module powered from the ±12 V header.

## Changes from Bread Modular

- `acid.ino` (new): the LOW `mco.ino` (MIDI library, tones, DETUNE, the
  `MIDI_RX_INVERT` guard and `PORTB.PIN3CTRL |= PORT_INVEN_bm`) merged with
  BM `env.ino`. MIDI note on/off is the envelope gate (no gate input, no
  gate-mode button: PC2/PC3 are REC). The MCO velocity DAC and gate pin (PA7)
  are gone: the DAC carries the envelope. Note-off closes the gate only for
  the last note-on, so overlapping (legato) notes hold the envelope open
  (BM: any note-off). Knobs are read every 2 ms (BM reads them at each phase
  start) so the recorder sees them.
- MODE LEDs: one LED per model, brightness following the
  envelope level (max 10 %) (BM: one LED blinks 1-3 times). MODE steps on a click (BM: a
  press > 0.5 s). TCA0 is taken from `analogWrite` for the LED PWM.
- `Env*.h`: `update()` takes the effective ATTACK/RELEASE values
  (knob or recorded take + CC, 0..1023) instead of reading `PIN_CV1/2` and
  adding the CC itself; times and state machines unchanged. `PinConfig.h`
  dropped.
- `EnvelopeGenerator.h`: DAC scaled to 0..194 (`ENV_DAC_MAX`).
- `CvRecorder.h`: symlink to the shared `opt/attiny1616-tools/lib/CvRecorder/CvRecorder.h`.
- Everything else (`tones.*`, `utils.*`, `ToggleMode.h`, the vendored
  FortySevenEffects MIDI Library v5.0.2, the 4.34 V DAC reference setting) is
  the BM file, unchanged. BM ENV's `SimpleMIDI.h` is replaced by the MCO MIDI
  library (clock/Start handlers for the recorder).

Built with arduino-cli 2026-11-05 (megaTinyCore 2.6.11), `p` / `d`:
11693 / 11683 B flash, 1293 B RAM (768 B recorder). Not bench-tested on the
ACID carrier yet.
