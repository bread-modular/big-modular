# 16bit firmware (RP2350)

Port of the Bread Modular 16bit firmware
(`~/data/projects/bread-modular/modules/16bit/code/16bit`, VERSION 1.6.0,
commit `5ba0067`) in `16bit/`. The carrier keeps the BM GPIO map
(`../docs/research.md` §1, `../Code.md`), so the sources are BM's apart from
the JP1 change below. `16bit/README.md` is the BM README (apps, motion
recorder, serial API, ELab scope protocol).

One app per firmware, picked at build time: `noop`, `sampler`, `polysynth`
(default), `fxrack`, `elab`, `monosynth`, `cpx4` (new, below).

## What the BM firmware sees on this carrier

| BM firmware | GPIO | 16bit carrier |
|---|---|---|
| `io` CV1 / CV2 (`getCV1/2`, the app knobs, e.g. polysynth attack / release) | GPIO28/29, ADC2/3 | **P3 / P4** knobs (+3V3 dividers), full 0..4095 range |
| `AudioInput` left / right (fxrack inputs, ELab A1 / A2) | GPIO26/27, ADC0/1 | **CV1 / CV2** jacks through P1 / P2 (0 V ~ mid-scale; unpatched, P1 / P2 are 0..+5 V knobs on the top ~42 % of the range) |
| MIDI RX, UART1 | GPIO5 | MIDI in through JP1 |
| MODE button / LED | GPIO12 / GPIO13 | MODE button / red LED |
| MIDI TX, gate 1 / 2 | GPIO4, GPIO20 / 19 | not connected (driven, harmless) |
| PT8211 I2S, PSRAM CS | GPIO1-3, GPIO0 | same |

So the BM apps run unchanged: **P3 / P4 are the default knobs**, doing what
the BM CV1 / CV2 knobs do (native netlist: RV3 wiper `POT3` -> U1 GPIO28 =
`CV1_PIN 2`, RV4 wiper `POT4` -> GPIO29 = `CV2_PIN 3`). The
CV jacks reach apps that read the audio inputs (fxrack, elab) and the sampler.

**Sampler (change from BM):** BM filters only group A (notes 0-5: P3
lowpass, P4 highpass); group B (notes 6-11) is unfiltered, as in BM (2026-11-08:
the earlier group B P1 lowpass / P2 highpass is removed). P1 / P2 now shape
group A, mainly the kick (`16bit/includes/audio/apps/sampler/sampler_dsp.h`):

- **P1 = drive**, ahead of the P3 lowpass (so P3 tames the fizz): 0..+36 dB
  into a soft clip with makeup, so the kick's body squares up and its tail
  comes up instead of just getting louder; asymmetric (even harmonics) around
  the middle of the knob, symmetric and hard at the top; DC-blocked, smoothed
  (10 ms). The makeup drops by up to 8 dB with the knob, so a whole kick hit
  stays within about +1 dB of the dry kick at every P1 position. A techno
  rumble tail rises with the knob (squared): the driven kick, lowpassed at
  160 Hz, feeds two short feedback delays (37 / 53 ms, damped at 120 Hz and
  saturated in the loop) that smear into a low wash, with more feedback (a
  longer, grittier tail) toward the top (about +3 dB late in the hit at full). While P1 is up, group A ends in a soft clip
  (knee 0.7, ceiling 0.95), since the squared kick overshoots ~2x through the
  P4 highpass even at 20 Hz.
- **P2 = resonance of the P4 highpass, as a DJ filter** (end of chain).
  **P4** sweeps BM's 20 Hz..20 kHz on a two-part exponential curve: the
  first quarter of the knob climbs 20 Hz..1.2 kHz (100 Hz at 0.10, 530 Hz
  at 0.20), the other three quarters 1.2..20 kHz (3.1 kHz half way), so full
  resonance arrives at the 25 % mark (2026-11-08 rev 6, for P2 off too; rev 5
  squeezed P4 to 20 Hz..1.26 kHz and was reverted). Fully down it is the earlier 12 dB/oct
  highpass (Q 0.707). Turned up it crossfades (first 5 % of the knob) to a
  24 dB/oct highpass whose resonance comes in fast: +11.5 dB at the cutoff at
  a quarter, +17.5 dB half way, +26 dB at the top (2026-11-08 rev 7, was
  +30 dB) (resonant stage Q 1.3..37, exponential in sqrt(knob)). The
  resonance only lives in the high mids and highs, as on a Pioneer DJM
  filter (2026-11-08 rev 6; rev 2 rang from the sub up and got muddy,
  rev 3 started at 800 Hz and faded in up to 3 kHz, rev 5 300..720 Hz):
  up to 500 Hz P4 (knob ~0.20) there is no peak at all (a flat 24 dB/oct
  Butterworth, -3 dB at the cutoff), so the kick, the bass and the low
  mids stay clean; the peak fades in steeply over 500 Hz..1.2 kHz (about +7 dB at
  700 Hz, +12 dB at 775 Hz, +19 dB at 900 Hz at full P2) and is full from
  1.2 kHz (knob 0.25) to the top of P4, where vocals, hats, claps and the
  Rumble burst zing. The
  resonant stage squelches: past a bandpass level of 1.5 its damping
  grows, so a loud tone on the cutoff rings at ~2-3x instead of ~30x,
  while quiet hits ring clean. Passband 0 dB. A peak guard (instant
  attack, 25 ms hold, 60 ms release) keeps the output under 0.95.

The app reads ADC0 / ADC1 from the main loop every 2 ms and rescales the
unpatched knob range (ADC ~2020..3735 = 0..+5 V) to 0..1. Fully down (bottom
2 %) = off: the group A output is bit-exact with the earlier one (host test
`16bit/tools/sim_sampler.cpp`). Patched, P1 / P2 scale the CV, and negative CV
clamps to off. The other apps don't read P1 / P2 as knobs (`../docs/research.md` §5).

**Polysynth wavetables (new, not BM):** the top knobs, with their CV jacks,
drive a wavetable oscillator. **P1 selects the table** in 17 zones: fully
down is **Classic**, where **P2 morphs square -> saw -> tri -> sine** (each
pure shape on frames 0 / 5 / 10 / 15, evenly spaced crossfades between; it
replaces BM's saw / tri / square oscillator and its `set-waveform` /
`get-waveform`, which are removed), then 15 tables and Noise:

| P1 | Table | Kind |
| --- | --- | --- |
| 1-6 | PWM, Sync, MS-20, Analog, PPG, VS | classic synths (PWM computed; saw sync, Korg MS-20 square, Analog Four tri/saw PWM, PPG Wave, Prophet VS) |
| 7-11 | CZ, FM, FM Bright, FM Feedback, Hard FM | phase distortion and FM / PM |
| 12-15 | Fold, Walsh, Modulo, Digital | complex: wavefolding, Walsh functions, modulo, OP-1 digital |
| 16 (top) | Noise | P2: brown -> pink -> white -> blue -> digital -> crackle |

**P2 moves the position** across the table's 16 frames, morphed between
neighbours and smoothed (5 ms). P1 / P2 are read from the main loop every
2 ms on the sampler's 0..+5 V range (ADC ~2020..3735); P1 zones have 15 %
hysteresis; patched, the knob scales the CV and negative CV clamps to the
bottom (Classic / first frame).

**Noise** has no table: each voice makes its own (different seed per voice,
so chords don't stack one noise). P2 crossfades six types, all ~0.3 RMS
except crackle (~0.2): brown (-6 dB / octave), pink (-3 dB / octave, Paul
Kellet's filter), white, blue (+6 dB / octave), digital (a random level held
for 1 / (8 x note frequency), so the keys set its grain) and crackle
(~note frequency / 2 decaying 1 ms clicks a second). The colours ignore the
pitch; the filter and envelopes shape them as usual.

The tables are `16bit/includes/audio/gen/wavetable_data.h` (1.1 MB in flash,
the polysynth UF2 only), generated by `16bit/tools/build_wavetables.py`.
Classic and PWM are computed; the rest are **Kimura Taro's free wavetables**
(CC0 1.0 Universal, the 2021 release made for Serum / Vital), read from the
Vital `.vitaltable` conversion in atsushieno/open-vital-resources (commit
`8c31ac1`, CC0). 16 frames are picked evenly across each source table (32..258
frames), in order and keeping their phase, so P2 follows the original sweep.
None is a filter sweep or sorted by brightness: the polysynth's ladder does
the filtering (the earlier AKWF tables, sorted dark -> bright, sounded
pre-filtered). Vital's and Serum's own factory tables aren't open (Vital's
source is GPLv3, its factory content is not in the repo), so none are
shipped. Each frame is DC-free, normalised to the same peak and stored as 8
band-limited mip levels (harmonics 128..1, eight samples per top-harmonic
period); the oscillator picks the level that keeps every harmonic under
20 kHz and interpolates cubically (`includes/audio/gen/wavetable_osc.h`).
`tools/sim_wavetable.cpp` checks the data, the level choice, pitch, morph
steps, the P1 hysteresis, the noise types (level, spectral slope, keyboard
tracking, voices uncorrelated) and aliasing (worst alias / image energy
-44.5 dB over every table, notes C2..C8). A Serum-format WAV (2048-sample
frames, `clm ` chunk) can replace any table:
`python3 -I tools/build_wavetables.py --kimura <Wavetables dir> --serum FM=table.wav`.
Wavetable pitch is exact (`MIDI::midiNoteToHz`, `AudioGenerator::setFrequencyHz`):
BM's whole-hertz note frequencies were up to 18 cents flat below C4, a
different amount per note, so held chords beat like detuned voices. The
polysynth no longer uses BM's whole-hertz saw / tri / square generators.
The audio core runs from RAM but BM's 9 voices reading the tables straight from
flash missed the XIP cache and overran the 44.1 kHz sample period, so the
DAC ran dry and wavetable chords went out of tune and crackled. The app now
copies the selected table (68 KB) to one of two RAM buffers when P1 changes
(~2 ms, main core) and the position / frame pair is worked out once a sample
for all voices (`WavetableControl::tick()`); the filter envelope, ladder and
AHR envelope lost their per-sample `expf` / divides. On the board
(2026-11-06): a wavetable chord with 7 voices sounding ~77 % of the sample period on average,
no new DAC underruns, single-sample peaks up to ~106 %. So the polysynth
now has 6 voices (BM: 9, `TOTAL_VOICES` in `polysynth_app.h`) for headroom;
as in BM a note-on with every voice still sounding (release included) is
dropped. `audio-load` (any app) prints the average / peak audio
core load since the last query and the underruns since boot.

**Polysynth auto level (new, not BM, after the 32bit polysynth):** BM divides
the voice sum by 4 (one voice -12 dBFS, four in-phase voices hard-clip). Now
one full-velocity voice peaks at 0.8; a polyphony gain 0.8 / max(1, L)^0.8,
L = sum of envelope x velocity (instant up, 300 ms down), turns chords down
by the notes sounding; a linked look-ahead limiter (0.7 ms, 60 ms hold,
250 ms release) keeps both outputs under 0.9, then a soft clip. The ladder
still sees BM's input level (one voice 0.25). `includes/audio/apps/polysynth/
poly_level.h`, tested by `tools/sim_poly_level.cpp`.

**Polysynth filter (new, not BM, after Vital's ladder):** BM's FilterFX /
`Ladder.h` lost level as the cutoff came down: its feedback grows 4x toward low
cutoffs and a ladder's passband falls as 1 / (1 + feedback), so at the
power-on resonance a C3 saw came out 3-7 dB under the dry level anywhere from
fully open down to 434 Hz (only 0.6-2.6 dB with no resonance); its Euler stages sat about an octave below the
set cutoff and the top 60 % of the resonance CC was clamped. The polysynth now
uses `includes/audio/apps/polysynth/poly_filter.h`: four zero-delay-feedback
(TPT) stages with the loop solved exactly (cutoff where it is set, resonance
independent of it), tanh on the stage input (bounded at full resonance), and
the output lifted by 1 + resonance, so the passband stays at 0 dB at every
resonance (Vital lifts the input by 1 + resonance %). A C3 saw at the power-on
resonance now stays within 0.4 dB from open down to 225 Hz and then falls like
any 24 dB lowpass; with no resonance it loses only what the cutoff removes.
MCC (any channel; Banks B `CC27..30` and C `CC85..88` fold onto Bank A, so
every MCC bank page drives the same four parameters and the recorder stores
them as Bank A):

| CC | Parameter | 0 -> 127 | Power-on |
|---|---|---|---|
| CC20 | filter-env attack = release | 5 ms -> 2 s, exponential (BM 5-105 ms linear) | 10 ms (CC 15) |
| CC21 | filter-env depth | 0 -> +8.3 octaves (BM 0 -> +10 kHz) | full (CC 127) |
| CC22 | resonance k | 0 -> 4.1, self-oscillates from ~CC 124 (BM Q clamped from CC 49) | 0.87 (CC 27) |
| CC23 | cutoff (inverted) | 17.6 kHz -> 55 Hz, exponential (BM 14.9 kHz -> 220 Hz, cubic) | open (CC 0) |

The envelope is BM's: one follower for all voices, up while any note is held.
On the board (2026-11-06, idle) the audio core load went from 30.1 % to
25.6 %. Tested by `tools/sim_poly_filter.cpp` (tuning -12 dB at the cutoff,
flat passband to resonance CC 120, level vs cutoff, stability, envelope).
`filter_fx.h` / `Ladder.h` stay as BM files, unused.

**CPX4 (new, not BM): a four-voice drone inspired by the SOMA Lyra-8**, played
from the 16bit knobs and two MCCs running the cpx4 MCC firmware
(`mcc/`, bank fixed, BANK button = a 3-step selector). Our own design, inspired by
the Lyra-8's features (pairs, SHARP, cross-FM, FM routing, a cross-fed delay,
drive after the delay), none of its circuits. DSP
`16bit/includes/audio/apps/cpx4/cpx4_dsp.h`, control map `cpx4_controls.h`,
app `cpx4_app.{h,cpp}`:

```
4 voices -> SHARP -> cross-FM (2x oversampled) -> delay (2 lines, cross-fed)
  -> DRIVE -> ladder LPF -> limiter -> OUT 1 (dry + line 1) / OUT 2 (dry + line 2)
TOTAL FB: the post-drive mix back into the FM
```

| | 1 | 2 | 3 | 4 | Button (3 LEDs) |
|---|---|---|---|---|---|
| 16bit knobs | P1 TUNE 1 | P2 TUNE 2 | P3 TUNE 3 | P4 TUNE 4 | MODE = motion recorder |
| MCC-1 VOICE (CC20-23) | SHARP A | SHARP B | MOD | DRIVE | CC102 FM routing: PAIRS / LOOP / TOTAL FB |
| MCC-2 FX (CC27-30) | DELAY TIME | FEEDBACK | DELAY MIX | CUTOFF (0 = open) | CC103 RESONANCE: Off / Peak / Sing |

- **TUNE 1..4**: one voice each. As on the Lyra-8, every voice covers the full
  range, A0..A7 (27.5..3520 Hz); the knob curve differs. Each is a
  loaded-pot (bilinear) taper, octaves = 7 t / (t + k (1 - t)), that spends
  most of the travel in its own register: voice 1 (k 3) dwells in the bass
  (69 % of the travel below 220 Hz, knob centre ~92 Hz) and reaches the treble
  only near the end stop, voice 2 (k 1.5) centre ~192 Hz, voice 3 (k 1/1.5)
  ~505 Hz, voice 4 (k 1/3) dwells in the treble (55 % above 880 Hz, centre
  ~1047 Hz). At any knob position voice 1 < 2 < 3 < 4. Glide 20 ms, plus a slow random drift of up to 4 cents per voice. **Knob at 0 = voice
  off**: below 3 % of the travel the voice is silent (and out of the FM), above
  5 % it plays from the bottom of its range (hysteresis, no flicker); on / off
  is a 15 ms fade, so it never pops. Read at 12 bits from the main loop
  every 2 ms (4 conversions averaged, smoothed), not through IO's 50-count CV
  callbacks: P1 / P2 use their unpatched 0..+5 V range (ADC 2020..3735),
  P3 / P4 the whole range. Cents per ADC step, fine end / fast end of the
  curve: TUNE 1 1.7 / 15.4, TUNE 2 3.4 / 7.7, TUNE 3 1.5 / 3.3, TUNE 4
  0.7 / 6.5. Patched CV1 / CV2
  jacks turn P1 / P2 into attenuators, as in the polysynth.
- **SHARP A / B**: the pair's waveform, triangle -> rounded -> square
  (tanh(g x) / tanh(g), g 0.3..40 exponential, capped so an edge stays two
  oversampled samples wide). It shapes the FM too.
- **MOD**: through-zero linear FM depth of both pairs (deviation = 2 x MOD^2
  x the carrier): growl, then sidebands, chaos from about 70 %.
- **FM routing** (MCC-1 button): PAIRS 1 <-> 2 and 3 <-> 4; LOOP adds pair A
  <-> pair B; TOTAL FB adds the post-drive output (with the delay) instead.
- **DELAY TIME**: line 1 1 ms..1 s exponential, line 2 at 0.97 x (they beat;
  short times resonate), 120 ms tape-like glide. **FEEDBACK** 0..1.1 (past
  100 %: it sustains, held by a knee clip in the loop), the loop damping
  follows it (12 kHz -> 2.5 kHz), DC-blocked; the lines cross-feed 30 %.
  **DELAY MIX** dry / wet equal power, echo at the dry level.
- **DRIVE**: after the delay, 0..+30 dB into a biased tanh (even harmonics),
  makeup gain.
- **CUTOFF**: the polysynth ladder (`poly_filter.h`, one per output, envelope
  off), inverted as the polysynth's: knob at 0 = open (17.6 kHz, no
  filtering), full = 55 Hz, exponential. **RESONANCE** (MCC-2 button): Off (k 0),
  Peak (k 3, +12 dB at the cutoff), Sing (k 4.1: self-oscillates at the
  cutoff, -6.5 dBFS rms, the output trimmed 6 dB in this step).
- **MIDI notes** (any channel) transpose all four voices (PITCH, C4 = none,
  +-3 octaves, latched); **CC120** All Sound Off empties the delay lines
  (over one line length). Then a look-ahead limiter (`poly_level.h`) under 0.9.
- **MODE** = the free-running motion recorder (`free_motion_recorder.h`, no
  MIDI timing, one track per control): hold MODE and move a knob or MCC knob
  to record it until MODE is released (LED blinks); it then loops on its own
  track (LED solid), gliding from its last value back to its first. Hold
  again and move another control for another track with its own length and
  start; move a recorded one to replace its track. Click MODE to remove every
  track (the controls glide back to their knobs, LED off). It records P1..P4
  and the eight MCC knobs (Bank A + B slots); the two button CCs aren't
  recorded. Up to 60 s per track, 20 ms frames; MODE is debounced and an MCC
  knob flickering by one step is not a move. Details in `16bit/README.md`.

The delay lines are 2 x 88 KB of static RAM, and the app runs from RAM
(`copy_to_ram`, as the polysynth): 106 KB code + 183 KB bss. Power-on values
(until the MCCs send theirs, within a second): SHARP 24, MOD 0, DRIVE 0,
DELAY TIME 64 (31 ms), FEEDBACK 40, MIX 32, CUTOFF 0 (open), PAIRS, Off.
`get-cpx4-params` prints the live DSP state over serial.

`tools/sim_cpx4.cpp` (host, 250 checks) drives every control as the app does
(knob ADC value or CC) and checks it on the rendered output, and that it moves
nothing else: TUNE n moves only voice n's line (heard within 1 cent) over its
own octave-staggered range, TUNE at 0 silences only that voice (and takes it
out of the FM) with a fade that steps no more than the waveform itself, SHARP
crest factor 1.71 -> 1.01 (triangle -> square, only its pair), MOD
off-harmonic power -46 -> -1 dB, the routing couplings, DRIVE THD 0.2 -> 31 %
(level within +5 dB), echo times 1 ms..1 s on both outputs, FEEDBACK tails
and a bounded sustain at full, MIX levels, CUTOFF -12 dB at the cutoff (four
poles), Peak +12 dB, Sing at the cutoff within 1 cent at 136 Hz..10 kHz,
transpose, All Sound Off, a minute with every control up (finite, peak 0.90);
and that `mcc/cpx4_mcc/cpx4_mcc.ino` sends the CCs and step values the map
reads. `./.build/host/sim_cpx4 --wav <dir>` writes listening WAVs (control
sweeps). Built 2026-11-14, `p`: UF2 206336 B, no warnings. Not
bench-tested: the audio core load (`audio-load`) is still to be measured on
the board.

**MODE = 4-bar motion recorder** in the sampler (new; BM's sampler MODE
stopped/restarted the audio), fxrack (new; BM left MODE unused), polysynth and
monosynth (BM). Click MODE to
record (LED blinks), after 4 bars on MIDI clock it loops (LED solid), click
again for live. Each frame holds P1..P4 and all twelve MCC CCs (banks A / B / C).
As on the 8bit recorder, the knobs and MCC are ignored for the first loop
pass; after that, moving one shifts its whole recorded curve. Overdub
(big-modular): hold MODE while the loop plays and move any knob or MCC control
to re-record that parameter for as long as MODE is held (LED blinks); release
keeps the loop, a click without moves returns to live. Needs a running
MIDI clock; RAM only. Details: `16bit/README.md`.

## JP1 setting (required)

JP1 picks the MIDI input path and the firmware must match it, as in the 8bit /
LOW / 32bit firmwares. Pass it as the first argument (or interactively, or
`JP1=`):

| Setting | JP1 | Define | RX (GPIO5, UART1) |
|---|---|---|---|
| `p` | 1-2 (silk P), protected NPN front end | `MIDI_RX_INVERT=1` | inverted: `gpio_set_inover(GPIO_OVERRIDE_INVERT)` |
| `d` | 2-3 (silk D), direct (as BM) | `MIDI_RX_INVERT=0` | not inverted |

A build without the setting stops at CMake (and `midi.h` has an `#error`).

## Apps and the web UI

All six BM 1.6.0 apps are ported: `noop`, `sampler`, `polysynth`, `fxrack`,
`elab`, `monosynth` (BM `dist/` ships the same six), plus the new `cpx4`.

The firmware works with the Bread Modular web UI
(<https://breadmodular.com/ui/16bit>, Web Serial): the serial API
(`includes/api/web_serial.h`, the `::val::...::val::` replies) and the USB
identity (VID 0x2E8A, PID 0x000A, "Bread Modular" / "16bit") are BM's,
unchanged. Checked against bread-modular-website commit `f991473`: every
command the UI sends is handled by the app that answers `get-app`, except the
polysynth waveform menu (removed here, see below):

| App | UI commands |
|---|---|
| all | `get-app` |
| sampler | `get-fx1..3`, `set-fx1..3 <fx>`, `play-sample <n>`, `write-sample-base64 <n> <bytes> <len>` |
| polysynth | none: `get-waveform` / `set-waveform` removed (P2 picks the BM waveform); the website's waveform menu does nothing and `get-waveform` times out after 5 s on connect |
| fxrack | `get-fx1..3`, `set-fx1..3 <fx>` |
| elab | `get-scope-channels`, `start-send`, `start-send-2`, `stop-send` |
| monosynth, noop, cpx4 | none (the UI only shows the app) |

`./webapi-check.sh <app>` looks for these strings in the built ELF;
`package.sh` runs it after every build, so a change that drops one fails. It
is a static check, not a test against the browser: the UI has not been run
against a built board yet.

## Use

```sh
./setup.sh                    # once: reuses ~/.breadmodular (Pico SDK 2.1.1, ARM GCC 14.2, picotool)
./compile.sh p                # build polysynth (or APP_NAME from 16bit/.config)
./compile.sh p sampler        # build another app
./flash.sh                    # menus: JP1 setting, then the app; build + load (picotool)
./flash.sh p                  # menu for the app only
./flash.sh d elab             # no menu
./flash.sh 16bit/dist/polysynth_1.6.0_p/16bit.uf2   # load a packaged UF2
./flash.sh info               # which firmware is on the board
./package.sh p                # every app -> 16bit/dist/<app>_1.6.0_p/16bit.uf2 (+ web API check)
cd 16bit && ./test.sh         # host tests (g++, no SDK)
```

The app is: second argument -> `APP=` -> `APP_NAME=` in `16bit/.config` (copy
`16bit/.config.example`) -> `polysynth`. `flash.sh` without an app shows a
menu of the six apps instead, with that default on Enter.

Every build carries its app and JP1 setting in the UF2 program info
(`pico_set_program_description`, e.g. `polysynth app, JP1=p`). `flash.sh`
prints the UF2's name / version / description before loading it, and
`./flash.sh info` reads them back from the board (`picotool info -f`). The
web UI's `get-app` command reports the app too.

The scripts are wrappers (`jumper.sh`) over the shared `opt/rp2350-tools`, like
the 32bit firmware over `opt/esp32-tools`. `setup.sh` downloads nothing when
the tools are already installed (`~/.breadmodular` from the BM scripts,
`~/.pico-sdk`, or the PATH); only a machine without them gets the BM install,
see `opt/rp2350-tools/README.md` (also the Linux udev rule picotool needs).

No buttons for a running board: `picotool load -f` reboots it into BOOTSEL; if
picotool can't reach it (Linux without the udev rule), `flash.sh` opens its USB
serial port at 1200 baud, which reboots it into BOOTSEL, and copies the UF2 onto
the `RP2350` drive (mounted with `udisksctl` if needed). A blank or crashed
board: hold BOOT, tap RESET, release BOOT, then flash. An up-to-date build is
flashed as is (no rebuild needed).

## Changes from Bread Modular

- `includes/midi.h`: the `MIDI_RX_INVERT` guard and
  `gpio_set_inover(MIDI_RX_PIN, GPIO_OVERRIDE_INVERT)` after the UART pin setup
  for JP1 = P. `CMakeLists.txt` requires `MIDI_RX_INVERT` (0 / 1) and passes
  it on; the version is read from `16bit/VERSION` (BM: `../../VERSION`).
- Build scripts: BM `scripts/{setup,build,deploy,package}.sh` are replaced by
  the module wrappers over `opt/rp2350-tools` (Linux + macOS, tool reuse);
  `scripts/test.sh` moved to `16bit/test.sh`. Packages carry the JP1 setting in
  the folder name.
- `lib/lfs`: BM's littlefs submodule (v2.10.2, `8ed63b27`) vendored with only
  `lfs.c`, `lfs.h`, `lfs_util.c`, `lfs_util.h`, `LICENSE.md`, `README.md`.
- `includes/audio/apps/sampler_app.h`: P1 drive / P2 DJ highpass on group A,
  group B unfiltered (above);
  FX1 defaults to `noop` instead of Rumble (BM started Rumble while `get-fx1`
  reported `noop`); `set-fx1 rumble` still selects it and is saved; MODE runs
  the motion recorder (BM: stop audio while held, kick on release).
- `includes/audio/apps/motion_recorder.h`: frames carry P1..P4 and the twelve
  MCC CCs (BM: CV1 / CV2 and Bank A); 8bit-style loop offset after one guard
  pass; unrecorded CCs stay live; hold MODE in playback to overdub moved
  parameters (playback exits on the MODE release, not the press). Polysynth / monosynth adapted to the new
  frame (`readKnobs`, `ownsCc`); `tools/sim_motion_recorder.cpp` extended.
- Polysynth: P1 / P2 wavetables (above): `includes/audio/gen/Wavetable.h`,
  `wavetable_osc.h`, `wavetable_data.h`, `tools/build_wavetables.py`,
  `tools/sim_wavetable.cpp`; `polysynth_app.{h,cpp}` read P1 / P2, record them
  in the motion recorder; the fully-down zone is the Classic table, P2
  morphing square -> saw -> tri -> sine (BM: saw / tri / square picked by
  `set-waveform` / `get-waveform`, saved to `/polysynth_config.dat`; both
  commands and the config file are dropped).
- Polysynth filter (above): `includes/audio/apps/polysynth/poly_filter.h`
  replaces FilterFX in `polysynth_app.{h,cpp}`; MCC Banks B / C fold onto
  Bank A; `tools/sim_poly_filter.cpp`.
- `src/audio/apps/fxrack_app.cpp`: MODE runs the motion recorder (P3 / P4 and
  all three MCC banks; BM: MODE unused).
- New `cpx4` app (above): `includes/audio/apps/cpx4/`, `cpx4_app.{h,cpp}`,
  `tools/sim_cpx4.cpp`; `main.cpp`, `CMakeLists.txt` (`VALID_APPS`,
  `copy_to_ram`), the scripts' app lists. Its MCC firmware is in `mcc/`.
- Everything else (apps, DSP, drivers, assets, host tools) is the BM file,
  unchanged.

Built 2026-11-02 (Pico SDK 2.1.1, ARM GCC 14.2.1, Linux): all six apps for
`p` and `d`, no warnings. UF2 sizes (rebuilt 2026-11-06 with the polysynth
wavetables): noop 155648, sampler 408576, polysynth 2425344 (1.21 MB binary,
of the 2 MB firmware flash), fxrack 187904, elab 169472, monosynth 191488 B
for both `p` and `d`
(BM's packaged 1.6.0 UF2s: noop, fxrack, elab the same; polysynth 184320,
sampler 393216, monosynth 189440 B; the differences are the group B filters,
the motion recorder changes, the `picotool info` description and the `p` RX
inversion). Host tests: 5 drivers pass (`16bit/test.sh`). Not bench-tested on the 16bit carrier yet.
