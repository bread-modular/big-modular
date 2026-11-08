# 8bit firmware (ATtiny1616)

Ports of four Bread Modular 8bit firmwares
(`~/data/projects/bread-modular/modules/8bit/code`, VERSION 1.2.1, commit `eeaf6dd`;
`lfo` from commit `b47ff0a`): `drums`, `supersaw`, `crash` and `lfo`. The 8bit carrier keeps the BM pin map
(`../docs/jumpers.md`), so the sources are BM's apart from the changes below.

| Pin | Use |
|---|---|
| PB3 | MIDI RX (USART) |
| PA1 / PA2 | Knob P1 (`PIN_CV1`) / P2 (`PIN_CV2`) |
| PA4 / PA5 | MODE button / LED |
| PA6 | DAC out |
| PA7, PB4 | BM gate / logger TX: still driven, not connected on this board |
| PB0 | CV in: `lfo` only (exponential rate FM); not used by the others |

`lfo` uses no MIDI; its MODE button toggles the output range (-5..+5 V /
0..+5 V).

## JP1 setting (required)

JP1 picks the MIDI input path, and the MIDI firmwares (`drums`, `supersaw`,
`crash`) must match it. Pass it as the second argument of `compile.sh` /
`flash.sh` (or interactively, or `JP1=`). `lfo` has no MIDI and takes no JP1
setting (`./compile.sh lfo`, `./flash.sh lfo [port]`):

| Setting | JP1 | Define | RX (PB3) |
|---|---|---|---|
| `p` | 1-2, protected NPN front end | `MIDI_RX_INVERT=1` | inverted: `PORT_INVEN` |
| `d` | 2-3, direct (as BM) | `MIDI_RX_INVERT=0` | not inverted |

A build without `MIDI_RX_INVERT` stops with `#error`. A firmware built for the
other setting receives nothing usable.

## Use

```sh
./setup.sh                        # once: arduino-cli + megaTinyCore into ~/bin
./compile.sh drums p              # build only
./flash.sh supersaw p             # build + flash, pick the UPDI port
./flash.sh crash d /dev/ttyUSB0   # explicit port (macOS: /dev/cu.usbserial-XXXX)
crash/sim.sh                      # crash host self-tests (no hardware)
../../../opt/attiny1616-tools/lib/CvRecorder/sim.sh  # supersaw/crash recorder host self-tests
lfo/sim.sh                        # lfo rate/FM/shape host self-tests
```

`compile.sh` / `flash.sh` call the shared `opt/attiny1616-tools` scripts
(20 MHz internal, `jtag2updi` programmer by default, `PROGRAMMER=` to override).
Without a port, `flash.sh` looks for the UPDI programmer by the OS's
USB-serial names (Linux `/dev/ttyUSB*`, `/dev/ttyACM*`; macOS
`/dev/cu.usbserial*`, `/dev/cu.wchusbserial*`, `/dev/cu.usbmodem*`) plus what
`arduino-cli board list` reports, and asks when it finds more than one.

## Firmwares

- **drums**: 7 drum samples on MIDI note-on, picked by note in the octave
  (C snare, D clap, E perc, F rim, G closed hat, A open hat, B ride), velocity
  sets the level. MODE cycles 3 modes (stored in EEPROM, LED blinks 1-3 times);
  BM does nothing else with them. Knobs unused.
- **supersaw**: a saw plus an octave-down saw, mixed on the DAC. **MIDI only**:
  pitch from MIDI note-on (notes above 65 ignored, 20-500 Hz). P1 is the
  envelope: each note-on restarts it at a level set by the velocity (linear,
  127 = full; hold mode keeps that level), then it decays
  exponentially, from a ~5 ms pulse at 0 up to a ~3 s time constant; the top
  of the travel (ADC >= 1000) holds until the next note-on. Note-off is
  ignored. Silent until the first note. P2 sets the octave-down level.
  MODE = 4-bar P1/P2 motion recorder on MIDI clock (shared, as crash): click to
  record (LED blinks), after 4 bars it loops (LED solid); click again for
  live knobs (LED off). While looping, the knobs are ignored for the first
  4-bar pass (so the hand that ends the take can't nudge it); after that
  their positions are the reference and turning a knob shifts its whole
  recorded curve up or down (clamped 0..1023). Needs a running MIDI clock;
  MIDI Start rewinds.
- **lfo**: BM's LFO reworked for a wider exponential rate, audio-rate FM and
  more shapes (user request, 2026-11-08), 40 kHz sample rate. Maths in
  `lfo/lfo/LfoMath.h`, host-tested by `lfo/sim.sh`.
  - **P1 = RATE, exponential** (equal turns = equal ratios, as Doepfer
    A-147-2, Tides, Batumi): 12 octaves, **0.01 Hz (100 s) fully CCW** ..
    1 Hz at ~55 % .. 40.6 Hz fully CW.
  - **CV in = exponential FM, ~1 V/oct** (not trimmed; resistor tolerance sets
    the exact scale), added to the knob: ±5.5 V = ±5.5 octaves. Knob CW + 5 V
    is ~1.3 kHz, full +5.5 V ~1.9 kHz (cap 2 kHz); knob CCW - 5.5 V is ~78 min
    per cycle. ±3 counts (±32 mV) around 0 V (`kCvInZero` 509, calibrate per
    unit) are treated as 0 V, so unpatched = knob only. CV is read on every
    `loop()` pass (the two knobs take turns), several kHz, below the 6.3 kHz
    CV input filter.
  - **P2 = WAVE**: sine, triangle, saw, **square**, complex 1, complex 2,
    **random** (sample & hold: a new value at each cycle start, xorshift).
    Neighbours crossfade, and each shape holds pure for ~64 counts around its
    spot (~17° of the travel). Tables are interpolated between entries, so a
    slow wave moves in single DAC steps instead of 256 coarse steps per
    cycle. At audio rate the waves alias (no band-limiting, 8-bit DAC;
    the R7/C13 15.9 kHz corner smooths the steps).
  - **No MIDI** (BM's unused MIDI receiver is removed). **MODE = output
    range**, toggled per click, BIPOLAR at power-up (not stored): BIPOLAR uses
    the full DAC (about -4.8..+4.8 V); UNIPOLAR scales the wave into the upper
    half of the DAC (`128 + sample / 2`, about 0..+4.8 V, 7-bit steps). No
    recorder. The LED follows the wave's position in the active range: dim
    (1/8) in BIPOLAR, full brightness in UNIPOLAR (BM: half brightness, no
    range switch); at audio rate it just glows. Gate (PA7, not connected)
    stays on the wave sample > 127.
  - Use the LFO panel (no MIDI jack, no P3 hole, MODE labelled REC), leave J1
    and RV3 off and wire-bridge RV3 (`../docs/mechanics.md`): with RV3 off the
    board and no bridge, the output is silent.
- **crash**: synthesized TR-808-style crash (no samples) on MIDI note-on,
  velocity = level, note ignored. P1 = brightness, P2 = hiss/metal balance.
  MODE = 4-bar CV motion recorder on MIDI clock: click to record P1/P2 (LED
  blinks), it then loops (LED solid); click again for live knobs. While
  looping, the knobs are ignored for the first 4-bar pass, then turning a
  knob shifts its whole recorded curve (as supersaw). MIDI Start rewinds.
  Tuning constants are in `crash/crash/CrashSynth.h`.

## Changes from Bread Modular

- lfo: rate, FM and shapes reworked (user request, 2026-11-08; replaces the
  2026-11-01 linear CV add and BM's 0.1-20 Hz cubic curve, whose
  operator-precedence slip is gone with it): sample rate 1 kHz -> 40 kHz
  (TCB0 `CCMP` = clocks - 1), exponential knob 0.01-40.6 Hz, CV in on PB0 as
  ~1 V/oct exponential FM up to 2 kHz, integer 2^x (`LfoMath.h`, no 64-bit
  division in the loop), CV read every pass. Shapes: square added after saw,
  BM's looping `RANDOM_TABLE` replaced by a per-cycle sample & hold, hold zones
  on the WAVE knob, interpolated table reads. MIDI removed (user decision 2026-11-01: no MIDI
  on the LFO build): no `SimpleMIDI.h`, no `MIDI.begin()`/`update()`, no
  (empty) callbacks, no `MIDI_RX_INVERT` guard; built without a JP1 setting.
  MODE/LED: own output-range toggle in `lfo.ino` (user request, 2026-11-01;
  replaces the earlier free-time recorder, removed), LED brightness by range.
  Its unused `ModeHandler.h` / `LEDToggler.h` are not copied; `WaveTables.*`
  are the BM files, unchanged (`RANDOM_TABLE` no longer played).

- drums, supersaw, crash: the `MIDI_RX_INVERT` guard and `PORTB.PIN3CTRL |= PORT_INVEN_bm`
  after `MIDI.begin()` for JP1 = P.
- supersaw: the CV1 pitch mode is removed (user decision, MIDI only):
  no `updateFrequencyFromCV()`, no `ModeHandler`. Its unused
  `ModeHandler.h` / `LEDToggler.h` are not copied.
- supersaw: MODE/LED run the crash `CvRecorder.h` (user request, 2026-10-29;
  BM supersaw has none), with crash's `SimpleMIDI.h` (MIDI clock/Start).
  Its `CvRecorder.h` is a symlink to the shared
  `opt/attiny1616-tools/lib/CvRecorder/CvRecorder.h` (crash's recorder plus
  the loop offset, user request 2026-10-29), which adds: a one-pass
  guard (`REC_GUARD_TICKS` = 384 clocks) after the take, then
  `apply(recorded + knob - reference)`. The knobs are read with the deadband
  into `liveCV1/2` in `readKnobs()`; `setDecayFromCV1()` / `setVolumeFromCV2()`
  take the live value, or the recorded one in PLAYBACK.
- supersaw: P1 envelope added (user request; BM has none): `updateDecayFromCV1()`
  and `updateEnvelope()` in `loop()` (1 ms steps on `millis()`), the TCB0 ISR
  scales the mix by `envLevel`. The note-on velocity sets the envelope start
  level (`envVelocity`, linear, 127 = full); BM ignores velocity here.
- Build scripts: module wrappers (`compile.sh`, `flash.sh`, `jumper.sh`) over the
  shared `opt/attiny1616-tools` instead of BM's per-firmware symlinks; BM's
  per-firmware READMEs are folded into this one.
- crash: its `CvRecorder.h` is now the same symlink to the shared
  `opt/attiny1616-tools/lib/CvRecorder/CvRecorder.h` (loop offset, user
  request 2026-10-29). `loop()` reads P1/P2 with the deadband into
  `liveCV1/2` in every state (BM skips the reads in PLAYBACK) and applies
  them to the synth only outside PLAYBACK; leaving PLAYBACK re-applies the
  live knobs at once.
- Everything else (`SimpleMIDI.h` (crash's in supersaw), samples, `CrashSynth.h`,
  the crash `sim/`) is the BM file, unchanged. The crash `sim/` now tests
  the shared recorder through the symlink.

Built with arduino-cli 2026-10-27 (megaTinyCore 2.6.11), `p` / `d`:
drums 15350 / 15340 B flash, 396 B RAM; supersaw 7652 / 7642 B, 1144 B
(recorder, 2026-10-29); crash 6821 / 6811 B, 1168 B (shared recorder,
2026-10-29); lfo 5215 B, 176 B (exponential rate / FM, 40 kHz, 2026-11-08). `crash/sim.sh`: 66
checks, 0 failures; `lfo/sim.sh`: 3114 checks, 0 failures; `lib/CvRecorder/sim.sh`: 50 checks, 0 failures.
Not bench-tested on the 8bit carrier yet.
