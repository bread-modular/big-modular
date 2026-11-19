# 12bit firmware (STM32G071C8T6)

Bare metal (CMSIS headers only), built with the shared `opt/stm32g0-tools`
(as `modules/hats/firmware/`). Three firmwares, `clapsnare`, `crash` and
`osc3`, and the `humtest` bench test.

| Pin | clapsnare | crash | osc3 |
|---|---|---|---|
| PB7 USART1_RX | MIDI in | MIDI in | not used |
| PA1 ADC_IN1 | P1: MORPH | P1: MORPH | P1: oscillator 1 frequency |
| PA6 ADC_IN6 | P2: TONE | P2: TONE | P2: oscillator 2 frequency |
| PA7 ADC_IN7 | P3: DECAY | P3: FILTER | P3: oscillator 3 frequency |
| PA4 DAC1_OUT1 | OUT 1 | OUT 1 | OUT 1: mix |
| PA5 DAC1_OUT2 | OUT 2: same signal | OUT 2: same signal | OUT 2: same mix |
| PB4 | MODE button: knob recorder | MODE button: knob recorder | MODE button: next waveform |
| PB5 | MODE LED | MODE LED | MODE LED |
| PA0 ADC_IN0 | CV in: added to TONE | CV in: added to FILTER | CV in: not used |

All: 48 kHz sample interrupt (TIM6), both DAC channels written together, DAC
mid-scale = 0 V, full scale +-1700 codes = about +-4.7 V at the jacks (x3.4
stage, from the design notes, not measured). Knobs: read at 1 kHz
with a ~16 ms one-pole smoother.

Knob ADC and output noise (first board, 2026-11-18): a software ADC scan every
millisecond (16x oversampled, 208 us of conversions, then idle) is a 1 kHz buzz
at the outputs, found with `humtest`: the DACs' reference is the +3V3 rail.
clapsnare instead lets TIM6 start one scan of its four channels per sample
(13 of the 20.8 us), stored by DMA in a 16-scan ring that the 1 kHz read
averages, so the ADC load repeats at 48 kHz. The user (2026-11-18): almost
gone, a faint rest left, bearable. So since 2026-11-19 **clapsnare only scans
while the drum sounds or a take is recorded**: a note-on with the scan off
starts it, waits one ring of fresh scans (0.33 ms), jumps the knob filters to
it and then fires, and the scan stops when the voice has died away. Between
hits the ADC is enabled and idle, as humtest step 3, which the user heard as
silent. Not confirmed by ear; the stop of the scan after each hit is one
supply step and might be a faint tick. **osc3 still has the 1 kHz software
scan** (its tone covers the buzz).

A knob cannot raise an interrupt by itself: its voltage has to be converted to
see that it moved (the ADC analog watchdog interrupt also needs the
conversions running). What stays for a later board is hardware: the FB1
ferrite on VREF+ does not filter audio frequencies; an RC (or a reference
IC) for VREF+ and the VOFF divider would (ST AN2834: filter the reference
separately; on the G071 VDDA is the VDD pin). Not measured.

## JP1 setting (clapsnare, crash)

JP1 picks the MIDI input path and the firmware must match it; pass it as the
second argument of `compile.sh` / `flash.sh` (or interactively, or `JP1=`):

| Setting | JP1 | Define | RX (PB7) |
|---|---|---|---|
| `p` | 1-2, protected NPN front end | `MIDI_RX_INVERT=1` | inverted: USART1 `RXINV` |
| `d` | 2-3, direct (as BM) | `MIDI_RX_INVERT=0` | not inverted |

A build without `MIDI_RX_INVERT` stops with `#error`. A firmware built for the
other setting receives nothing usable. `osc3` has no MIDI and takes no JP1
setting. With nothing patched PB7 idles low for `p` and high for `d`; the
first board reads low (driven, 2026-11-18), so it is built as `p`.

## Use

```sh
./setup.sh                # once: ARM GCC from ~/.breadmodular, CMSIS + OpenOCD
./compile.sh clapsnare p  # -> clapsnare/.build/p/clapsnare-p.{elf,bin,hex}
./flash.sh clapsnare p    # build + program over SWD, CMSIS-DAP (DAPLink) probe
./flash.sh crash p        # crash cymbal + cowbell
./flash.sh osc3           # no JP1 setting
./flash.sh humtest        # output noise bench test, no JP1 setting
OPENOCD_INTERFACE=interface/stlink.cfg ./flash.sh clapsnare p   # ST-Link instead
clapsnare/test.sh         # host tests
clapsnare/test.sh wav     # + preview WAVs in clapsnare/.build/wav/
crash/test.sh             # host tests (crash/test.sh wav: preview WAVs)
crash/test.sh cal         # after a change to the crash sound or the clapsnare level: measure its level tables again
osc3/test.sh              # host tests
```

Wire the probe to J6: 2 SWDIO, 3 SWCLK, 4 GND, 5 NRST; leave pin 1 (+3V3
sense) off unless the probe only senses VTref. Power the module from its
Eurorack header while flashing.

## clapsnare: hand clap + snare (side) drum

A synthesized drum voice (no samples) after the modules/8bit `crash`
firmware, tuned for techno / house: any MIDI note-on fires it, velocity sets
the level, the note number and note-off are ignored, all channels.

| Knob | Does |
|---|---|
| **P1 MORPH** | Clap fully left, snare fully right. In between they are layered: clap at full level with the snare fading in up to the middle, then the snare at full level with the clap fading out |
| **P2 TONE** | Clap: band-pass centre 650 Hz (dark, big) .. 2.4 kHz (bright, thin). Snare: body tuning 135 .. 300 Hz, and its noise gets thinner (high-pass 0.8 .. 3.2 kHz) |
| **P3 DECAY** | Clap tail 30 .. 500 ms, snare noise 30 .. 400 ms and body 25 .. 110 ms (time constants): tight and dry on the left, long on the right |

- **Clap**: noise through a band-pass, three short bursts 10.5 ms apart and a
  fourth hit that carries the tail (TR-808 / 909 structure). The loudness
  stays even over TONE.
- **Snare**: two sine partials (1 : 1.83) that start 60 % sharp and drop to
  the tuning in ~10 ms, plus noise through a resonant high-pass with a snappy
  (22 ms) and a long envelope.
- The noise runs freely, so no two hits are identical. The mix goes through a
  soft clipper: hard hits and the layered middle saturate instead of
  clipping, soft hits stay clean. Velocity curve between linear and squared
  (100 = -3 dB, 64 = -8 dB).
- **MODE = 4-bar knob recorder on MIDI clock** (as crash, here for all three
  knobs): click to record (LED blinks), after 4 bars it loops (LED solid);
  click again for live knobs. While looping the knobs are ignored for the
  first pass, then turning one shifts its whole recorded curve. Overdub (as
  the 16bit recorder): hold MODE while it loops and turn a knob; from its
  first move (> 48 ADC steps) until MODE is released that knob re-records at
  the playhead (the others keep playing, LED blinks), release keeps looping
  with the new curve; a click without a move returns to live. Needs a
  running MIDI clock; MIDI Start rewinds. A click while recording discards
  the take.
- **LED**: the recorder only (blinks while recording or overdubbing, solid while looping,
  off in live mode). It does not flash on MIDI notes (user, 2026-11-19).
- **CV in modulates TONE**: the P2 knob sets the centre and the CV moves it
  both ways, 5 V = the whole knob travel (knob fully left + 0 .. 5 V sweeps the
  whole range; knob in the middle takes +-2.5 V), clamped at the ends. Nothing
  patched = 0 V = the knob alone (+-0.07 V dead band for the part tolerances).
  ~4 ms smoothing at the 1 kHz read, so envelopes, LFOs and sequencer steps
  work, audio rate does not. The CV is added after the recorder: it is never
  recorded and still works over a loop.
- OUT 1 and OUT 2 carry the same signal.

Sources: `clapsnare/src/main.cpp` (hardware), `clapsnare/src/clapsnare_logic.h`
(sound, recorder, MIDI parser; integer maths, tuning constants at the top;
host-tested by `clapsnare/test.sh`). `g_sampleIsrMaxTicks` holds the worst
sample-interrupt time in 1 / 64 MHz counts (1333 per sample) and `g_cvAdc`
the smoothed CV ADC code (0 V = 2021, 342.9 codes per volt) for a read over
SWD.

Status (2026-11-19, later): the user heard the gated scan: "pretty good now".
The LED no longer flashes on a note: `p` build flashed and verified, host tests
pass, the LED itself not looked at. After that a 20 ms start-up wait was added
before the ADC calibration (the S3 board's +3V0 reference comes up ~13 ms after
the MCU supply; harmless on the first board): compiled, host tests pass, **not
flashed** (the probe no longer reached the board).

Status (2026-11-19): `p` build with the gated knob scan flashed on the first
board (17316 B flash; over SWD: idle = ADSTART 0, DMA counter still, DAC
constant; 25 note-ons written into the receive buffer each started the scan,
kept the channel order in the ring and stopped it again, 0 overruns; forcing
RECORDING keeps it running; worst sample interrupt 670 of 1333 counts).
**Not confirmed by ear.** `g_scanning` / `g_scanWakes` show the gate over SWD.
A/B by ear without a probe: MODE (LED blinks, recording) = scan on, MODE
again = scan off. Before that (2026-11-18): compiled, host tests
pass, `p` build with the TIM6-timed knob scan flashed on the first board
(over SWD: scans stop with TIM6, CV reads 2022, the three knobs, all fully
left, read 0..2 as single manual conversions do, a forced ADC overrun
recovers with the channel order kept, `g_adcOverruns`; knobs at mid-travel
not checked); the user heard a faint rest of the buzz. CV on TONE: with 0 V at the jack
the board reads ADC code 2020 (expected 2021) and TONE follows the knob alone;
**no voltage was patched in, so the CV sweep itself is only host-tested**. Checked on the board over SWD by
writing note-ons into the MIDI receive buffer: hits play on the DAC, the LED
flashes, worst sample interrupt 702 of 1333 counts (53 %). **Not heard and
not measured by me**: the sound was tuned from the rendered waveforms and
spectra only. Not tested with a real MIDI source, and the recorder only on
the host.

## crash: crash cymbal + cowbell

A synthesized drum voice (no samples) for techno: a TR-808 / TR-909 style
crash at one end of P1, the TR-808 cowbell at the other, a resonant FILTER on
P3, and **every setting at the same level, the level of clapsnare**. **With
TONE fully left both are the classic sounds**; turning TONE up colours them.
Any MIDI note-on fires it (velocity = level on the clapsnare curve, 100 =
-3 dB, 64 = -8 dB; note ignored, all channels); any note-off sends it
into the fast release (23 ms), so the gate length is the length of the sound:
the crash rings for 1.5 s with the note held and 0.12 s when tapped (0.35 s
for an eighth note at 126 BPM), the cowbell 0.47 s / 0.12 s.

| Knob | Does |
|---|---|
| **P1 MORPH** | Crash fully left, cowbell fully right, both layered in between. An equal-power fade, so the middle is as loud as the ends; a little dead travel at both ends, so the ends are the pure sounds |
| **P2 TONE** | **Fully left = the classic crash and cowbell.** Turning it up tunes both higher: the crash by up to a fifth (x1.5: its oscillators and every filter together, a smaller and brighter cymbal, centre of its spectrum 6 kHz -> 9 kHz), the cowbell by up to an octave (540 + 800 Hz -> 1080 + 1600 Hz) |
| **P3 FILTER** | Resonant low-pass (12 dB / octave) on the whole voice. **Fully left = no filtering**: the filter is bypassed (the bottom 40 of 4095 codes, so pot and ADC tolerances can't leave it in; host-tested to be sample for sample the voice without it). Above that its corner falls exponentially from 16 kHz (flat in the audio band, so it comes in without a step) to 400 Hz fully right, and the resonance comes in over the first 30 % of the travel (Q 0.7 -> 4, +12 dB at the corner, from 5.3 kHz down). A make-up gain keeps the level |

- **Crash**: the TR-808 cymbal structure with the wash and the length of a
  TR-909 crash. The six square oscillators of the 808 (205.3, 304.4, 369.6,
  522.7, 540, 800 Hz) plus low-passed noise go through a 12 dB / octave
  high-pass at 2 kHz (no fundamentals, only the shimmer) and two band-passes:
  3.6 kHz (Q 1) with the long ring and 7.1 kHz (Q 1.5), which has a second,
  shorter envelope on top: bright at the start, darker in the tail. A little
  of the signal from before the second high-pass stays under it (the low end
  of a real cymbal; it is also what a closed FILTER still finds: a dark
  metallic cluster). Random oscillator phases: no two hits are alike.
- **Cowbell**: two band-limited pulses 540 + 800 Hz (widths 0.36 / 0.44, so
  they have the even harmonics of the 808's) through a band-pass at 900 Hz
  (Q 2), a 9 ms strike (76 %) on a 110 ms tail. The 800 Hz tone leads, as on
  the 808. Every hit is the same. The pulses are band-limited (polyBLEP;
  host test: what folds back at 48 kHz is under 1 / 100 of a plain pulse's).
- **Set against recordings, not by ear**: TR-808 cymbal, TR-909 crash and
  TR-808 cowbell samples (public sample sets, not in the repository) were
  measured and the constants set to them:

  | | TR-808 cymbal | TR-909 crash | crash, TONE left |
  |---|---|---|---|
  | Centre of the spectrum, first 0.2 s | 7.0 .. 8.8 kHz | 2.6 .. 5.4 kHz | 6.2 kHz |
  | ... 0.2 .. 0.6 s | 4.0 .. 5.6 kHz | 5.0 .. 5.6 kHz | 5.5 kHz |
  | How tonal (spectral flatness 3 .. 9 kHz) | -5.2 dB | -3.4 .. -4.5 dB | -4.2 dB |
  | -10 dB / -20 dB after | 0.17 / 0.57 s (decay at half) | 0.43 .. 0.52 / 0.8 .. 0.97 s | 0.36 / 0.79 s |
  | 0.5 .. 1 kHz band after the attack | -34 .. -24 dB | -22 .. -17 dB | -24 .. -19 dB |

  | | TR-808 cowbell (two recordings) | cowbell, TONE left |
  |---|---|---|
  | 540 Hz tone re the 800 Hz one | -14 / -12 dB | -11 dB |
  | Its octave (1080 Hz) | -13 / -10 dB | -12 dB |
  | 2.4 kHz | -25 / -19 dB | -23 dB |
  | Level after 10 / 20 / 80 / 160 ms | -6 / -11 / -19 / -24 dB | -5 / -9 / -15 / -22 dB before the clipper |
  | -40 dB after | 0.35 / 0.39 s | 0.36 s |

  The second version had a crash centred at 2.7 kHz and a cowbell with all
  its partials up to 4 kHz at the same level.
- **Same level everywhere**: `crash/src/crash_levels.h` holds tables measured
  on the voice itself (`crash/test.sh cal` -> `tools/calibrate.cpp`): the gain
  that makes each engine as loud as the classic crash over TONE, and what the
  FILTER lets through of each engine over TONE x FILTER, from which the
  make-up gain behind the filter is computed (the crash needs up to +20 dB
  with the filter closed; limit +36 dB). The level of a hit = the RMS below
  12 kHz of the first 100 ms after the soft clipper (hiss above 12 kHz adds
  to the RMS, not to what is heard). The cowbell is set 1.5 dB above the
  crash (`BELL_LIFT_Q8`, see below). Measured on the host over MORPH x TONE x
  FILTER (7 x 14 x 12 settings): crash within 0.7 dB, cowbell within 0.2 dB,
  1.5 dB at the most at one MORPH setting, everything -6.9 .. -4.3 dBFS.
- **As loud as clapsnare** (user, 2026-11-19: the third version sounded
  quieter than clap / snare). Both firmwares peak at full scale and read
  about the same on a meter (third version -10.2 dBFS, clap -9.1, snare
  -11.1), so the meter does not show it. `crash/tools/loudness.h` is a
  loudness model for the host (after Glasberg & Moore 2002, simplified:
  ISO 226 ear weighting, excitation on the ERB scale, short-term loudness;
  host-tested on tones and noise): the ear is 7 .. 12 dB less sensitive at
  6 .. 10 kHz, where the crash sits, than at 1 kHz, and a tonal hit sounds
  quieter than a noisy one at the same level. By it the third version's
  crash was 3.6 phon and its cowbell 7.8 phon under the clap (TONE and DECAY
  at noon, 102.2 phon; 10 phon = twice as loud).
  The calibration now measures the clap and sets a **drive** into the soft
  clipper (x2.97 in `crash_levels.h`, 5.9 dB more than before) so that the
  classic crash is as loud as it:

  | Full velocity, knobs as said | Loudness model | On a meter (RMS, first 100 ms) |
  |---|---|---|
  | clapsnare clap / layered / snare, TONE and DECAY at noon | 102.2 / 103.5 / 100.6 phon | -9.1 / -8.5 / -11.1 dBFS |
  | crash, TONE left .. right | 102.2 .. 101.6 phon (was 98.6) | -5.9 dBFS (was -10.2) |
  | crash + cowbell, MORPH at noon | 104.1 .. 102.8 phon | -4.9 dBFS |
  | cowbell, TONE left .. right | 100.4 .. 98.8 phon (was 94.4) | -4.4 dBFS (was -10.2) |

  At velocity 100 / 64 the crash is at 100.5 / 97.0 phon, the clap at 100.2 /
  96.5 (same velocity curve). The cowbell stays 2 phon under the clap, as
  loud as the snare: to match the clap by the model it would have to read
  3.2 dB above the crash (another 3.6 dB of gain), which turns its strike
  into a tone burst (full level for 80 ms), so it got 1.5 dB
  (`BELL_LIFT_Q8` in `crash_logic.h`, then `crash/test.sh cal`). FILTER keeps
  the meter level as before; by the model a closed filter is up to 3 phon
  quieter on the crash (a dark sound), as in the third version.
- **What the drive does to the sounds**: the crash has 3.4 % of its first
  100 ms at the rail (clap: 0.1 %); its spectrum stays (73 % of the energy at
  3 .. 9 kHz, centre 6.0 kHz), the ring looks longer after the clipper: -10 /
  -20 dB after 0.43 / 0.88 s (before it 0.34 / 0.79 s; TR-909: 0.43 .. 0.52 /
  0.8 .. 0.97 s). The cowbell is saturated: 9.5 % at the rail, its strike is
  full level for the first 30 ms, then -3 dB after 80 ms and -7 dB after
  160 ms (third version: -3 dB after 20 ms, -12 / -16 dB after 80 / 160 ms);
  its partials stay within 2 dB (540 Hz -12 dB, 1080 Hz -13 dB re 800 Hz).
  The tables above (set against recordings) are the sounds before the clipper.
- **CV in modulates FILTER** (as TONE in clapsnare): 5 V = the whole knob
  travel, bipolar, clamped, +-0.07 V dead band, after the recorder. Nothing
  patched = 0 V = the knob alone, so FILTER fully left stays off. The make-up
  gain follows the CV with the corner.
- **MODE = 4-bar knob recorder on MIDI clock**, the clapsnare recorder (the
  8bit crash's, here for all three knobs, overdub by holding MODE); LED as
  clapsnare. Needs a running MIDI clock; MIDI Start rewinds.
- Knob scan gated as clapsnare (runs only while the voice sounds, a take is
  recorded or MODE is held), so no 1 kHz buzz between hits.
- An engine that MORPH has faded out completely is not started, so a pure
  cowbell ends after 0.47 s (the knob scan too).
- No GATE output (the 12bit has none).

Sources: `crash/src/main.cpp` (hardware, from clapsnare),
`crash/src/crash_logic.h` (voice, filter, recorder, MIDI parser; integer
maths, tuning constants at the top), `crash/src/crash_levels.h` (generated
drive and level tables), `crash/tools/calibrate.cpp` (reads
`clapsnare/src/clapsnare_logic.h` for the reference), `crash/tools/loudness.h`
(the loudness model); host-tested by `crash/test.sh` (it also checks the
crash against the clap by the model, so it fails after a level change in
either firmware until `crash/test.sh cal` has run; `crash/test.sh wav` writes
preview WAVs: the classic sounds, TONE and FILTER settings, a sweep of each
knob, and `level-vs-clapsnare.wav`: clap, crash, snare, cowbell in turn).
Built with `-O3` (the others `-Os`): the sample interrupt is the longest of
the three firmwares.

Status (2026-11-19, fourth version, user: "compared to the clap / snare the
perceived volume is low"): the drive into the clipper and the clapsnare
velocity curve as above; the sounds themselves (oscillators, filters,
envelopes) are those of the third version. `p` and `d` compile without
warnings (27.5 KB flash, 7.7 KB RAM), host tests pass. The code per sample
is unchanged (the drive is part of the velocity gain; the note-on has two
more multiplications), so the timing below still holds. **Not flashed, not
heard, not measured**: "as loud" is the loudness model's verdict on rendered
hits, not a listening test, and the model is a simplified one.

Before that (2026-11-19, third version, user requests after the second one: TONE
fully left = an 808 / 909 style crash and the techno cowbell, TONE = colour,
FILTER kept): `p` and `d` compile without warnings (27.5 KB flash, 7.6 KB
RAM), host tests pass. Sample interrupt not measured on the board: an
instruction-level emulation of the Cortex-M0+ code with a cycle model (2
flash wait states) gives 920 cycles for the worst sample (the trigger, both
engines + filter), 835 for the worst one after it and 783 on average with
both engines and the filter running (480 for the crash alone, 410 for the
cowbell alone), of the 1333 per sample, plus ~32 for interrupt entry and
exit; the same model gave 706 for clapsnare, which measured 670 .. 702 on the
board. **Not flashed, not heard, not measured**: the sounds were set against
measurements of recordings and the levels from rendered hits. The gate
length still cuts the sound (as the 8bit crash): a full crash needs a note
of 1.5 s. The first version (BRIGHT / HISS / 4-pole low-pass) was flashed and
heard by the user (too quiet at P1 0 / P2 full).

## osc3: three-oscillator mixer

A first test firmware: three oscillators, one per knob, summed at equal level;
OUT 1 and OUT 2 both carry the mix.

- Knobs: exponential, 20 Hz .. 2560 Hz (7 octaves).
- Waveform (all three oscillators): 1 sine, 2 triangle, 3 saw, 4 square;
  MODE steps through them, the LED flashes 1..4 times. Boots on sine.
- MIDI (PB7) and CV (PA0) are not used, so JP1 does not matter.

Sources: `osc3/src/main.cpp` (hardware), `osc3/src/osc3_logic.h` (behaviour,
host-tested by `osc3/test.sh`), `osc3/stm32g071x8.ld`.

Status: compiled, host-tested, flashed on the first board 2026-11-18 and
confirmed working by the user.

## humtest: output noise bench test

For a hum or whine at the outputs (first board, 2026-11-18: a high-pitched hum
between the clapsnare hits, also with the probe's USB unplugged). No sound:
both DACs hold mid-scale (0 V at the jacks). MODE steps through what the MCU
is doing; the LED flashes the step number, then stays off. The step where the
hum changes names its source.

| Step | MCU clock | Knob scan | 48 kHz sample interrupt | MIDI receiver | Heard (user, 2026-11-18) |
|---|---|---|---|---|---|
| 1 | 64 MHz (PLL) | 1 kHz software bursts | on | on (the first clapsnare, idle) | loudest |
| 2 | 16 MHz (HSI16, PLL off) | 1 kHz software bursts | on | on | about half |
| 3 | 64 MHz | off (ADC enabled, idle) | on | on | nothing |
| 4 | 64 MHz | off | off | on | nothing |
| 5 | 1 MHz (HSI16 / 16) | off (ADC off) | off | off | nothing |
| 6 | 64 MHz | one scan per sample, TIM6 + DMA | on | on (clapsnare now, idle) | not listened to |
| 7 | 64 MHz | 1 kHz software bursts, **DAC output buffers off** | on | on | not listened to, not flashed |

So the hum is the 1 kHz burst scan, not the clock, the sample interrupt or the
MIDI receiver. Step 6 is the fix as built into clapsnare, for an A/B against
step 1.

Step 7 (2026-11-19) is step 1 with the DAC output buffers off, to learn which
way the hum reaches the outputs before the S3 board (LM4040 reference on its
own +3V0 rail, `../Code.md`) is ordered. Unbuffered, the DAC pins are the
resistor strings on VREF+ alone (11.7k, so the tone is duller: 2.7 kHz
low-pass with the 4.7n). Hum still there = it rides on the reference, which S3
takes off the MCU supply. Hum gone = it comes through the buffers' supply
(VDD/VDDA), which S3 does not change. User, first board, 2026-11-19: the hum
is still there and a bit duller, so it is the reference path (heard, not
measured; not read back over the debugger).

The ADC clock is 16 MHz in steps 1 and 2, so a scan takes the same 208 us of
every millisecond at both clocks. The 1 ms SysTick runs in every step (button
and LED). Over SWD: `g_step`, `g_scanCount`, `g_sampleCount`, `g_adc` (step 6:
CV, P1, P2, P3); writing 1..7 to `g_stepRequest` selects a step.

Source: `humtest/src/main.cpp`. Status (2026-11-18): steps 1..5 listened to by
the user on the first board; step 6 added afterwards and read back over SWD
(scan order kept across step changes, 1 kHz reads, 48 kHz samples), not
listened to. clapsnare is back on the board.
