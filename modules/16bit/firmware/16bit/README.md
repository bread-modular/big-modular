# 16bit Module Firmware (RP2350)

Firmware for the Bread Modular **16bit** module (Raspberry Pi RP2350), the
Bread Modular README kept as the app / serial API reference. Setup, build and
flash for the Big Modular 16bit carrier (JP1 setting, shared
`opt/rp2350-tools`) are in `../README.md`.

The codebase contains **multiple apps**, but each firmware build compiles **one
app at a time** (same model as the 32bit module). `../package.sh` builds a
separate firmware per app.

## Apps

| App         | Description                                  |
|-------------|----------------------------------------------|
| `noop`      | Minimal app (no audio processing)            |
| `sampler`   | 12-voice sample player with per-sample FX    |
| `polysynth` | 6-voice poly-synth (16 wavetables + Noise on P1 / P2; P1 down: P2 morphs square -> saw -> tri -> sine; P1 up: noise types) |
| `fxrack`    | Multi-FX rack over sample players            |
| `elab`      | Envelope lab (A1/A2 CV/audio scoping)        |
| `monosynth` | Pulsar-23-inspired mono bass synth (percussion mode) |
| `lyra4`     | Lyra-8-style 4-voice drone: TUNE on P1..P4, two lyra4 MCCs (SHARP, MOD, DRIVE, FM routing; delay, feedback, mix, ladder cutoff + resonance), see `../README.md` |

### Motion recorder (sampler, fxrack, monosynth, polysynth & lyra4)

lyra4 runs the free-running variant (no MIDI timing), see
[Free-running recorder (lyra4)](#free-running-recorder-lyra4) below; the rest
of this section is the MIDI-clocked recorder of the other apps.

These apps share the same MODE/LED workflow as the 8bit CV recorder
(`opt/attiny1616-tools/lib/CvRecorder`), loop offset included. The state machine lives in the shared pico-free header
`includes/audio/apps/motion_recorder.h`, and `tools/sim_motion_recorder.cpp`
runs its self-tests on the host.

- Click **MODE** (board button, GPIO12) to cycle `LIVE -> RECORDING -> PLAYBACK`.
- While recording, the LED (GPIO13) blinks and each MIDI clock pulse records the
  raw 12-bit knobs P1..P4 plus the twelve MCC CCs (Bank A `CC20..23`, Bank B
  `CC27..30`, Bank C `CC85..88`).
- A take is four bars of 4/4 (`24 PPQN`, 384 clock frames). On completion the
  LED becomes solid and the frame loop drives the recorded parameters; MODE
  aborts an incomplete take, and a MODE click (press and release, nothing
  moved) stops playback on the release.
- Overdub (big-modular): in playback, hold **MODE** and move any knob P1..P4
  or MCC control. From its first move until MODE is released, that parameter's
  live value replaces the recording at the playhead (the others keep playing)
  and the LED blinks. Release MODE to keep looping with the new curve (no
  offset until the control moves again). Hold again for another pass or
  another parameter; a CC that wasn't in the take joins it, keeping its
  pre-hold value outside the overdubbed span. Knobs must move more than 48 ADC
  steps from their position at the press to count.
- Loop offset (as the 8bit recorder): during the first loop pass the knobs and
  MCC are ignored. Their positions at the end of that pass become the
  reference; after that, moving a knob or MCC control shifts its whole recorded
  curve by (position - reference), clamped (knobs 0..4095, CCs 0..127).
- An MCC CC that never arrived before or during the take isn't recorded and
  stays live in playback; one first moved part-way through is back-filled with
  its first value.
- MIDI **Start** rewinds the active take/loop. The recorder requires a running
  MIDI clock and stores the take in RAM only; it never writes the filesystem or
  flash.

### Free-running recorder (lyra4)

`includes/audio/apps/free_motion_recorder.h`, host tests in
`tools/sim_free_motion_recorder.cpp`. Same frames (P1..P4 + the MCC slots),
overdub hold and loop offset as above, but **no MIDI clock**: the loop length
comes from the MODE presses.

- **Press MODE** to start a take (LED blinks). Every 20 ms the knobs and MCC
  values are stored.
- **Press MODE again** to close the loop. The loop is exactly the time between
  the two presses (to the millisecond, so it doesn't drift against the tempo
  it was tapped to) and plays from the start at that press. Max 60 s (the
  take closes itself there); a second press within 0.2 s drops the take.
- **Playback**: LED solid, dark for 80 ms at each loop restart so you can see
  the loop. Click MODE (nothing moved) to go back to LIVE.
- **Overdub**: hold MODE in playback and move knobs or MCC controls; each moved
  control is re-recorded until you let go (LED blinks), the rest keep playing.
- **Offset**: knobs and MCC are ignored for the first pass; after that moving
  one shifts its recorded curve.
- MIDI clock and Start are ignored. RAM only (60 KB), never the filesystem.

Each app owns what a frame means:

| app        | P1 / P2                          | P3 / P4 (BM CV1 / CV2)                                  | MCC                                                          |
|------------|----------------------------------|---------------------------------------------------------|--------------------------------------------------------------|
| sampler    | group A drive / highpass resonance | group A lowpass / highpass                            | FX1 `CC20..23`, FX2 `CC27..30`, FX3 `CC85..88`               |
| fxrack     | not recorded (audio inputs)      | group A / group B lowpass                               | FX1 `CC20..23`, FX2 `CC27..30`, FX3 `CC85..88`               |
| monosynth  | not used                         | attack / decay times                                    | Bank A: BODY, CHORUS, CUTOFF, RESONANCE                      |
| lyra4      | TUNE 1 / TUNE 2                  | TUNE 3 / TUNE 4                                         | Bank A: SHARP A, SHARP B, MOD, DRIVE; Bank B: DELAY TIME, FEEDBACK, DELAY MIX, CUTOFF (button CCs 102 / 103 not recorded) |
| polysynth  | wavetable select / position (P1 down: P2 = square -> saw -> tri -> sine; P1 up: Noise, P2 = brown -> pink -> white -> blue -> digital -> crackle) | amp-envelope attack (1..500 ms) / release (10..1000 ms) | Bank A: filter-env attack-release time, filter-env depth, resonance, cutoff; Banks B / C fold onto Bank A |

While a polysynth take plays back, each frame updates all six voices'
amp-envelope times, the wavetable and its position plus the filter
parameters (`polysynth/poly_filter.h`), so automation sweeps envelopes, wavetable and filter together.

Sampler (big-modular, not BM): BM's MODE stopped the audio while held and
replayed the kick on release; here it runs the recorder. The sampler applies a
frame's parameters only when they change. CC71 / CC74 (P3 / P4 over MIDI) are
not recorded and are ignored during playback. Any audio restart (`set-fx`,
sample upload) re-creates the FX at their defaults and drops the take.

FXRack (big-modular, not BM: BM left MODE unused) works the same way: frames
apply only what changed, CC71 / CC74 aren't recorded, and `set-fx` drops the
take. Monosynth and polysynth only have Bank A parameters. The polysynth folds
Bank B / C CCs onto Bank A (same parameter, recorded as Bank A); on the
monosynth they do nothing and aren't recorded.

The selected app is fixed at **compile time** and reported over serial via
`get-app`. Each app owns its own baked-in assets and config file, so each
firmware only carries the code and data it actually needs (e.g. the sampler's
sample bank is only compiled into the `sampler` firmware).

## Setup / Build / Flash

See `../README.md`: `../setup.sh` once, then `../compile.sh p|d [app]`,
`../flash.sh p|d [app]`, `../package.sh p|d [app ...]`. The app is resolved
as: command-line app -> `APP=` -> `APP_NAME=` in `.config` (copy
`.config.example`) -> `polysynth`.

## Flash layout

The board is 16 MB total, partitioned as **2 MB firmware + 14 MB filesystem**
(`PICO_FLASH_SIZE_BYTES`). Because each app is its own firmware, each app can
use the full 2 MB firmware region for its own baked-in resources, and the split
can be tuned per app if needed.

## Serial API

All commands are sent as newline-terminated text over USB serial. Responses are
framed as `::val::<value>::val::` (or `::list::…::list::` / `::bin::…::bin::`).

| Command            | Response                                            |
|--------------------|-----------------------------------------------------|
| `whoami`           | `16bit`                                             |
| `get-app`          | Current app name (the compiled-in app)              |
| `set-app <name>`   | No-op unless `<name>` is the compiled-in app        |
| `version`          | Firmware version                                    |
| `ping`             | `pong` + LED blink                                  |
| `psram-usage`      | Bytes of PSRAM in use                               |

> `get-app` now returns only the current (compiled-in) app name, and
> `set-app` only accepts that app — runtime app switching was removed in favor
> of one-firmware-per-app. These commands remain backward compatible with the
> previous multi-app firmware.

### ELab oscilloscope: channel negotiation and legacy compatibility

These commands are specific to the `elab` firmware. Send the **exact command**
followed by a newline (the serial layer also accepts CR/CRLF). Prefixes, suffixes,
arguments, and similar names such as `start-send-20` are not accepted.

| Command | Behavior |
|---------|----------|
| `get-scope-channels` | Replies `::val::2::val::` without changing the stream mode. |
| `start-send` | Starts/continues the **legacy A1-only** stream: exactly **500 raw uint8 bytes** per decoded binary payload. |
| `start-send-2` | Starts/continues the dual stream: exactly **1000 raw uint8 bytes**, planar **A1 [0..499], then A2 [500..999]**. No header or interleaving. |
| `stop-send` | Stops either mode and discards queued complete windows. |

Both stream modes retain the existing `::bin::<base64>::bin::` framing and a
trailing newline. A1 is `AudioInput.left`; A2 is `AudioInput.right`. Dual payload
bytes `i` and `500 + i` come from the **same capture step**, using a shared sample
index. The ADC manager already reads both ADCs in each audio callback; those ADC
conversions are sequential, not hardware-simultaneous.

**Website negotiation:** request `get-scope-channels` first. Only after a positive
capability response of `2` should a new UI use `start-send-2`. Missing, unknown,
or unsupported capability responses must fall back to `start-send`, which remains
500-byte A1-only even on this new firmware. Thus old UIs work unchanged; new UIs
can still work with old firmware. Repeated starts/stops are idempotent, and
switching modes never mixes payload lengths. Commands and sends run sequentially
on the main core: after `stop-send` is processed no more frames are sent, but a
frame already handed to USB before that command cannot be recalled.

**Encoding and timing (unchanged):** normalized input is converted with
`uint8((input + 1) / 2.0 * 255)`, truncating rather than rounding: -1 -> 0,
0 -> 127, +1 -> 255. The existing voltage interpretation/calibration is unchanged.
Out-of-range inputs now saturate to 0/255; NaN encodes as 0. The original integer
sample divider is **4 audio callbacks**, nominally **0.0907 ms at 44.1 kHz**
(approximately 0.1 ms as assumed by the UI), not a new precise 0.1 ms timer. The
existing counter reset after 44,100 also retains its occasional one-callback
interval at rollover. A 500-sample window normally takes about 45 ms to collect;
USB delivery time is separate. No audio/ADC/DAC timing has been changed.

**Ownership and overload:** `includes/audio/apps/elab_scope.h` contains the
Pico-free production helper used by the firmware and host regression tests. It
uses three fixed 1000-byte buffers (3000 payload bytes plus small metadata): one
producer-private write slot and capacity for two published windows, including
any window being encoded/sent. Lock-free 32-bit release/acquire index loads/stores
publish only complete paired windows and release a read slot only after the
synchronous serial send returns. The audio path neither allocates nor waits,
and no audio-critical lock surrounds base64 encoding or USB output. When full,
the producer drops **new complete windows**, never overwriting queued/in-flight
ones. There is no unbounded backlog, timestamp, or overrun marker in the protocol;
a slow host may see gaps, not torn or channel-misaligned windows.

Capture continues even while stopped (as before). A mode change discards queued
complete windows but does not reset audio-owned counters or a partial window, so
the first subsequent window may include samples taken before the command. A
repeated start in the same mode does not discard pending data. USB/serial can
still delay main-core work (including pulse/button updates); it never holds up
the scope's audio-core producer.

Host regressions (no hardware/SDK required):

```sh
./test.sh
# Also run the host drivers with memory/undefined-behavior checks:
CXXFLAGS="-O1 -g -fsanitize=address,undefined,float-cast-overflow -fno-omit-frame-pointer" ./test.sh
```

See `tools/README.md` for the focused scope test and threaded ownership checks.
