# 12bit firmware (STM32G071C8T6)

Bare metal (CMSIS headers only), built with the shared `opt/stm32g0-tools`
(as `modules/hats/firmware/`). Two firmwares, `clapsnare` and `osc3`, and the
`humtest` bench test.

| Pin | clapsnare | osc3 |
|---|---|---|
| PB7 USART1_RX | MIDI in | not used |
| PA1 ADC_IN1 | P1: MORPH | P1: oscillator 1 frequency |
| PA6 ADC_IN6 | P2: TONE | P2: oscillator 2 frequency |
| PA7 ADC_IN7 | P3: DECAY | P3: oscillator 3 frequency |
| PA4 DAC1_OUT1 | OUT 1 | OUT 1: mix |
| PA5 DAC1_OUT2 | OUT 2: same signal | OUT 2: same mix |
| PB4 | MODE button: knob recorder | MODE button: next waveform |
| PB5 | MODE LED | MODE LED |
| PA0 ADC_IN0 | CV in: added to TONE | CV in: not used |

Both: 48 kHz sample interrupt (TIM6), both DAC channels written together, DAC
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

## JP1 setting (clapsnare)

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
./flash.sh osc3           # no JP1 setting
./flash.sh humtest        # output noise bench test, no JP1 setting
OPENOCD_INTERFACE=interface/stlink.cfg ./flash.sh clapsnare p   # ST-Link instead
clapsnare/test.sh         # host tests
clapsnare/test.sh wav     # + preview WAVs in clapsnare/.build/wav/
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
  first pass, then turning one shifts its whole recorded curve. Needs a
  running MIDI clock; MIDI Start rewinds. A click while recording discards
  the take.
- **LED**: the recorder only (blinks while recording, solid while looping,
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
