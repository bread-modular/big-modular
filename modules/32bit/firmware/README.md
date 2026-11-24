# 32bit firmware (ESP32-S3)

Three firmwares, one ESP-IDF project each: `polysynth` (default), `fxrack`
(the Bread Modular 32bit fxrack, see [fxrack](#fxrack)) and `master` (end-of-chain
processor for a live set, set up from a web page over USB, see [master](#master)).
Pick one with the first argument of `compile.sh` / `flash.sh`.

## polysynth

9-voice MIDI poly synth after the Bread Modular 16bit polysynth
(`~/data/projects/bread-modular/modules/16bit/code/16bit`, `polysynth_app.cpp`,
`Voice.h`, `AttackHoldRelease.h`, `fx/filter_fx.h`, `mod/Ladder.h`), on the BM
32bit-5v ESP-IDF drivers (`modules/32bit-5v/code/32bit/main`) with the 32bit R1
pin changes (`../docs/firmware-pins.md`). There is no MCC yet, so the two knobs
set the sound.

| Control | Function |
|---|---|
| MIDI in (any channel) | notes to 9 voices; when all 9 are busy the oldest released voice (else the oldest) is stolen. CC 64 = sustain pedal (>= 64 down: released keys hold until pedal up), CC 120 / 123 = all notes off |
| CV1 (knob 1) | **release**: amp envelope is attack 5 ms -> hold while the key is held (gate) -> release 10 ms .. 4 s (exponential knob) |
| CV2 (knob 2) | **filter**: fully down = filter bypassed (all frequencies). Turning up crossfades into a ladder low pass over the first 10 %, then closes 18 kHz -> 50 Hz (exponential) while the resonance rises to its maximum at 60 % (~525 Hz). The resonance fades out as the cutoff falls from 400 Hz to 200 Hz: no resonance below 200 Hz |
| MODE button | next waveform position: 0 saw (default), 1 vox, 2 organ, 3 reed, 4 fm, 5 sync, 6 metal, 7 fold, then back to saw. The change crossfades over 20 ms. The position is saved in NVS and restored at power-up |
| LED | flashes (40 ms) on every MIDI channel message (notes, CC, pitch bend, ...); MIDI clock / active sensing do not light it. Brightness (PWM, gamma corrected) = waveform position, dim (15 %, saw) to full (fold); after a button press it stays on 0.6 s at the new brightness |
| OUT L / OUT R | the same mono synth signal |
| IN L / IN R | not used |

The knob reads are knob x CV: unpatched each jack is normalled to +5 V, so a
patched 0..+5 V CV does the same as the knob (scaled by it). Knob 2 at 0 bypasses
the filter exactly; the bottom 2 % of the knob is a dead zone for that.

Knob 2 positions (from `polysynth/tests`):

| knob | cutoff | resonance k | peak over passband |
|---|---|---|---|
| 0 | bypass | 0 | - |
| 0.2 | 5.5 kHz | 0.32 | small |
| 0.4 | 1.7 kHz | 0.63 | ~5 dB |
| 0.6 | 527 Hz | 0.95 | ~17 dB |
| 0.7 | 292 Hz | 0.54 | ~8 dB |
| 0.8 .. 1.0 | 162 .. 50 Hz | 0 | none |

## Waveforms

Position 0 is the PolyBLEP saw. Positions 1..7 are single-cycle wavetables made
offline by `polysynth/tools/gen_wavetables.py` (pure Python, run by the build
and by the host tests; nothing is computed per note): vox (vowel formants),
organ (drawbars), reed (narrow pulse + saw), fm (2-op FM), sync (hard-synced
saw), metal (sparse odd partials), fold (wavefolded sine). Each is stored as an
octave mipmap (level l keeps harmonics 1 .. 1024 >> l, ~140 KB in flash); a note
uses the level whose top harmonic stays under 24 kHz, so no alias lands below
20 kHz. All are scaled to the saw's RMS where their peak allows (within 2.3 dB).

The waveform is saved in NVS (`polysynth` / `wave`) 2 s after the last press,
once no voice is sounding (a flash write stalls the audio task for a moment).

## Output level

One full-velocity voice peaks at 0.8 of digital full scale (about ±3.6 V at
the jack with the codec at 0 dB and the x3.55 stage; BM's `/ 4` mix gave
-12 dBFS, about ±1.1 V).

Chords: the summed voice level L = sum(envelope x velocity) is tracked (up at
once, down over 300 ms so releasing notes do not pump the held ones) and the
mix gain is 0.8 / max(1, L)^0.8. Host test, random full-velocity chords, RMS
vs one voice and the worst limiter gain reduction:

| notes | 1 | 2 | 3 | 4 | 6 | 9 |
|---|---|---|---|---|---|---|
| RMS vs one voice | 0 | -1.9 | -3.1 | -3.6 | -4.7 | -5.6 dB |
| limiter, filter open | 0 | 0 | 0.5 | 0.9 | 1.2 | 1.2 dB |

What is left (phase-aligned chords, resonant peaks: one voice at knob 2 = 0.45
takes 3.5 dB) goes through a look-ahead limiter at 0.9 of full scale: 0.7 ms
look-ahead (added latency), 60 ms hold, 250 ms release, so its gain does not
move within a waveform cycle (the old instant-attack limiter flattened each
new peak, which sounded like clipping), then a soft clip.
The ladder makes up its full pass-band loss `(1 + r)`, so closing the filter
keeps the level until the cutoff reaches the note (A3: -0.1 / -1.3 / -2.5 /
-2.5 / 0 dB at knob 0.1 .. 0.6, was down to -6 dB); the dips left are the
limiter holding resonant peaks under full scale.

The codec stays at its 0 dB output volume (`bm_audio.c`, register value 30).
Its analog output can go to +4.5 dB (33), but ~0.9 Vrms full scale on a 3.3 V
supply has only ~2 dB to the rail, so a full-scale signal would clip in the
codec; the level is made in the digital domain instead.

## JP1 setting (required)

JP1 picks the MIDI input path and the firmware must match it, as in the 8bit /
LOW firmwares. Pass it as the first argument of `compile.sh` / `flash.sh` (or
interactively, or `JP1=`):

| Setting | JP1 | Define | RX (GPIO44, UART0) |
|---|---|---|---|
| `p` | 1-2 (silk P), protected NPN front end | `MIDI_RX_INVERT=1` | inverted: `UART_SIGNAL_RXD_INV` |
| `d` | 2-3 (silk D), direct (as BM) | `MIDI_RX_INVERT=0` | not inverted |

A build without the setting stops at CMake (and `bm_midi.c` has an `#error`).

## Board: S3 or ES1

Two ES8388 boards differ in who makes the I2S clocks. Pick the board with `BOARD=` (all three firmwares):

| `BOARD=` | Board | Define | Clocks |
|---|---|---|---|
| `s3` (default) | S3 carrier (`hardware/` before S4, the built boards) | `CODEC_CLOCK_MASTER=0` | ESP32-S3 = I2S master, MCLK 256 fs on GPIO21 from its PLL |
| `es1` | ES1 carrier (`hardware/es/`, docs/research.md section 10) | `CODEC_CLOCK_MASTER=1` | Y2 11.2896 MHz -> ES8388 MCLK; ES8388 = I2S master (register 8 = 0x84: BCLK = MCLK / 4 = 64 fs), ESP32-S3 = slave, GPIO21 unused |

Both keep 44.1 kHz, 24-bit (master) or 16-bit (fxrack, polysynth) words. Use the matching build: an ES1 build on an S3
board gets no MCLK (silence), an S3 build on an ES1 board runs the codec on Y2 against the ESP32-S3's own BCLK /
LRCK (two unrelated clocks: clicks and drift). The ES1 builds compile; no ES1 board exists yet, so they are not
bench-tested.

```sh
BOARD=es1 ./compile.sh master
BOARD=es1 ./flash.sh p fxrack
```

## Use

```sh
./setup.sh                    # once: checks / reuses ESP-IDF v5.5.1 (~/esp/esp-idf, ~/.espressif)
./compile.sh p                # build only (polysynth = the default)
./compile.sh p fxrack         # build the fxrack firmware (also: fxrack p)
./compile.sh master           # build master (no MIDI in it: no JP1 setting)
./flash.sh                    # pick the firmware, JP1 and the port from menus
./flash.sh p                  # pick the firmware (Enter = polysynth) and the port
./flash.sh p fxrack           # build + flash fxrack over the module's USB-C, no firmware menu
./flash.sh p fxrack /dev/ttyACM0   # explicit port (macOS: /dev/cu.usbmodemXXXX)
./flash.sh master             # build + flash master
MONITOR=1 ./flash.sh p fxrack # flash, then show the log (Ctrl-] quits)
```

`flash.sh` asks which firmware to flash (as the 16bit `flash.sh` asks for the
app) unless it is on the command line or in `FIRMWARE=`; `compile.sh` never
asks and builds polysynth by default.

The scripts are wrappers (`jumper.sh`) over the shared `opt/esp32-tools`, like
the ATtiny1616 firmwares over `opt/attiny1616-tools`. `setup.sh` downloads
nothing when ESP-IDF and its tools are already installed; only a machine without
them gets the BM install (clone v5.5.1, `install.sh esp32s3`, cmake + ninja).

Flash with the module on USB-C (native USB-Serial/JTAG, `/dev/ttyACM*`). If no
port appears or flashing fails, hold BOOT, tap RESET, release BOOT, retry, then
tap RESET. The log (same USB port, `MONITOR=1`) prints every 5 s: active voices,
worst audio block time against the 1451 us budget, and the CV1 / CV2 voltages.

## Host tests

```sh
cd polysynth/tests && make
cd fxrack/tests && make
cd master/tests && make
```

Builds `main/src/ps_dsp.c` on the host and checks the knob 2 map (bypass at 0, no
resonance at or below 200 Hz), the filter response and that it never
self-oscillates, the release / attack times, voice stealing, the sustain pedal,
output range with 9 voices on a resonant setting, one-voice level near full
scale and the level with the filter closing, A4 = 440 Hz, every waveform's
level and mip level (no aliasing), the waveform crossfade (no click), and
1..9-note chords (level and limiter work).

## Changes from Bread Modular

- DSP ported from the 16bit C++ classes to C (`main/src/ps_dsp.c`): same 9
  voices, velocity^2, linear attack-hold-release envelope and
  Moog ladder with tanh stages.
- Knobs: BM CV1 / CV2 = attack 1..500 ms / release 10..1000 ms and the filter on
  MCC CC20..23. Here attack is fixed at 5 ms, CV1 = release 10 ms..4 s, CV2 = the
  one-knob filter above. No filter envelope (BM's MCC env / depth), no motion
  recorder, no web-serial commands.
- Ladder cutoff calibrated so the knob's Hz is the filter's Hz (BM's
  `p = f(1.8 - 0.8 f)` puts the -3 dB point near a quarter of the set value);
  feedback and smoothing as BM; the ladder runs at BM's level (x0.3 in,
  /0.3 out) but makes up the full pass-band loss (BM: `1 + k / 2`).
- Level: one voice x0.8, a polyphony gain, a look-ahead limiter and soft clip
  (BM: `/ 4` and tanh), see Output level.
- Oscillators: phase accumulators, PolyBLEP saw (BM: integer samples-per-cycle,
  out of tune high up). BM's square / triangle / web-serial waveform choice is
  replaced by the 7 wavetables above on the MODE button, saved in NVS.
- Envelope retrigger ramps from the current level (BM waits for a zero crossing);
  BM drops notes when all voices are busy, here the oldest voice is stolen.
- Both outputs carry the filtered signal (BM 16bit: right output dry).
- Latency: I2S DMA 3 x 64 frames (4.4 ms output buffering; BM 32bit-5v 2 x 511
  frames, ~23 ms plus 11.6 ms event bursts) and the MIDI UART hands every byte
  over at once (FIFO threshold 1, RX timeout 1 byte; BM waits for 32 bytes or
  20 ms). Added CC64 sustain pedal; the LED is a MIDI activity flash (LEDC
  PWM for the brightness).
- Drivers: BM 32bit-5v `bm_es8388`, `bm_audio`, `bm_midi`, `bm_button`, `bm_led`
  copied, with I2C SDA/SCL IO39/IO38, codec input 2, the JP1 RX inversion;
  `bm_cv.c` reworked for IO1/IO2 (ADC1 CH0/CH1), calibrated mV and the R1 CV
  scaling. Console on USB-Serial/JTAG so UART0 is MIDI only; no Wi-Fi/BT.

Built with ESP-IDF v5.5.1 (2026-10-31), `p` and `d`: 414 KB app, no warnings;
host tests pass. Not bench-tested on the 32bit carrier yet (no hardware): audio
level, CV scaling and CPU load are still to be checked on the module.

## fxrack

The Bread Modular 32bit-5v `fxrack` app
(`~/data/projects/bread-modular/modules/32bit-5v/code/32bit`, VERSION 1.1.3,
`main/src/apps/bm_app_fxrack.c` and its `audio/` + `lib/` code) on the 32bit
drivers above (R1 pins, JP1, CV scaling, 64-frame audio blocks). The left and
right channels are two separate effects.

| Control | Function |
|---|---|
| IN L -> OUT L | delay -> hall reverb (the reverb gets the input only, see [Hall reverb](#hall-reverb)). OUT L = (1 - mix) x delay + mix x reverb. The delay output is the delayed signal only (BM comb, no dry): with CV2 at 0 it is the input delayed by the CV1 time |
| CV1 (knob 1) | left delay time, 10 samples .. half a beat (250 ms at 120 BPM) |
| CV2 (knob 2) | left delay feedback 0 .. 1 (1 = endless repeats) |
| MIDI CC 20 | reverb decay (RT60 below ~1 kHz), exponential: 0 = 0.3 s, 64 = 2.5 s, 127 = 20 s (3 s until a CC arrives) |
| MIDI CC 21 | reverb mix 0 .. 1 (default 0: no reverb) |
| IN R -> OUT R | short comb delay, wet only (default 1 sample: a pass-through) |
| MIDI CC 22 | right delay time 1 .. 50 ms |
| MIDI CC 23 | right delay feedback 0.5 .. 1 |
| MIDI clock | sets the BPM, so the CV1 range (half a beat); 120 BPM until a clock arrives |
| MODE press | 4-bar **motion recorder** on MIDI clock (as the 8bit/16bit recorders): press to record CV1, CV2 and CC 20..23; after 4 bars (384 clocks) it loops; hold while looping and move a control to overdub it; click again for live controls (a press while recording aborts the take). See below |
| LED | blinking = recording or overdubbing, solid = looping, off = live |

Motion recorder (`main/src/lib/bm_motion_recorder.c`, RAM only, lost at power
off). Needs a running MIDI clock; MIDI Start rewinds the take or loop.

- Recording: every clock stores CV1, CV2 (knob x CV) and the latest CC 20..23
  values; the live controls keep driving the sound.
- Looping: every clock replays the stored frame. For the first 4-bar pass the
  knobs, CVs and CCs are ignored; at its end their positions are the reference,
  and from then on moving one shifts its whole recorded curve (clamped).
- A CC that never arrived before or during the take is not recorded and stays
  live; one first sent part-way through is held at its first value before that.
- Overdub (as the 16bit recorder): hold MODE while it loops and move CV1,
  CV2 or a CC 20..23 control. From its first move (CVs more than ~1.2 % of the
  travel, CCs any change) until MODE is released it re-records at the
  playhead (the others keep playing, LED blinks). Release keeps looping with
  the new curve, no offset until the control moves again. A CC that wasn't
  in the take joins it, keeping its pre-hold value outside the overdub.
- A click (press and release, nothing moved) back to live: the current knob /
  CV / CC values are applied again.

CCs are read on any MIDI channel (BM MCC bank A numbers, `bm_midi.h`).

Changes from BM:

- Drivers: the 32bit ones (polysynth above). CV1 / CV2 arrive as the 0..1 knob
  position (0..+5 V at the jack), not the raw 0..3.3 V ADC value.
- A MIDI clock BPM change re-applies the CV1 delay time: the 32bit CV driver
  only reports changes (BM re-sent every value every 5 s).
- Below 15 BPM half a beat is longer than the 2 s left buffer: the range is
  clamped to the buffer (BM wrapped around it).
- `bm_all_pass_filter.c`: the buffer is allocated with all `max_delay_length`
  samples; BM allocated one fewer and wrote one float past the end (ASan finds
  it in the host test with the BM file).
- Not ported: the BM web-installer USB serial commands (`bm_usb_serial.c`, the
  USB port carries the log here) and the `pipe` app. The log prints every 5 s the
  worst audio block time (1451 us budget), the BPM and the CV1 / CV2 voltages.
- **PSRAM on**: the delay buffers are in the module's 8 MB octal PSRAM,
  as BM (`CONFIG_SPIRAM`, octal, 80 MHz; ~0.36 MB used). The hall reverb's
  150 KB of delay lines go to internal SRAM (`allocate_fast`, PSRAM only if
  less than 64 KB would be left). The polysynth does not
  use PSRAM. The extra supply current on U8 (the 5 V linear regulator) is part
  of the bench check.
- Hall reverb instead of BM's classic reverb (user request, 2026-11-06), see
  below; CC 20 is its 0.3 .. 20 s decay (BM: RT60 0.1 .. 3 s).
- Pipe delay removed (user request, 2026-11-04): BM's MODE hold that also fed
  the delay into the reverb, saved in NVS. The reverb always gets the input only
  (BM's default), and nothing is saved in NVS.
- MODE runs the motion recorder instead (user request, 2026-11-04), on the
  press; the button is debounced (30 ms) in the app.

Host tests (`fxrack/tests`, ASan + UBSan): comb echo times and gains, all-pass
unity energy, BM classic reverb RT60 1 s = 58.8 dB drop over 1 s, hall reverb
decay (T30 below 800 Hz 0.26 / 0.97 / 3.96 / 19.4 s at 0.3 / 1 / 4 / 20 s, the
treble shorter), echo density (0.99 of a Gaussian tail), 20 s of full-scale noise
at 20 s decay (finite, peak 0.999 under the soft limit), the dry path through the
app at CC defaults, the slow-BPM clamp (echo at 1.999 s), the wet reverb (blocks
DC, rings on after a burst),
the LED, button debounce, and the motion recorder
(record, loop, guard pass, offsets and clamps, CC back-fill and unrecorded CCs,
MIDI Start, abort, overdub hold / click / new CC; in the app, a recorded CV1
overrides the live knob and the overdub LED blinks).

Built with ESP-IDF v5.5.1 (2026-11-06), `p` and `d`: 284 KB app (hall reverb, motion recorder), no warnings;
host tests pass. Not bench-tested: input -> output level (ES8388 ADC at 0 dB
PGA on the x0.18 input divider, DAC at 0 dB into the x3.55 stage), PSRAM load
and CPU time are still to be checked on the module.

### Hall reverb

`main/src/audio/bm_hall_reverb.c` replaces BM's classic reverb (4 parallel
combs of 32..37 ms + 4 series all-passes, `bm_classic_reverb.c`, kept for the A/B
render). Those few short combs give a sparse, ringing, plate-like tail. The hall:

```
IN L -> high pass 90 Hz -> low pass 9 kHz -> pre-delay 22 ms -> 8 channels
     -> diffuser: 4 x (8 delays spread over 4 / 9 / 18 / 36 ms, polarity flips, 8x8 Hadamard)
     -> 8-line feedback delay network: 50..92 ms prime-length lines,
        Householder feedback, +-10 samples slow sine modulation (0.31..0.89 Hz),
        per-line one-pole damping (Jot): RT60 at Nyquist = 1/4 of the set RT60
     -> out = late tail x 0.5 / sqrt(1 + RT60) + 0.25 x diffused early sound
     -> soft limit above 0.7 of full scale
```

Simulation (host render of the firmware C, `fxrack/tools`: `make render` writes
WAVs, plots and `metrics.md` to the ignored `../research/fxrack-reverb/`; models only,
not listened to on the module):

| | BM classic, 3 s (its max) | hall 4 s | hall 20 s |
|---|---|---|---|
| T30 125 Hz / 1 kHz / 4 kHz / 8 kHz | 3.0 / 3.0 / 3.0 / 3.0 s | 4.1 / 3.8 / 2.7 / 1.6 s | 19.6 / 18.3 / 9.9 / 4.5 s |
| echo density reaches 0.9 of Gaussian | never (~0.6) | 20 ms after the first echo | same |
| late-tail spectrum, deviation from its 1/3-octave trend (std) | 23.7 dB (comb teeth) | 6.1 dB | 6.0 dB |
| wet RMS vs dry, drums / plucks | +1.1 / +11.9 dB | -2.5 / -0.9 dB | -2.1 / -0.4 dB |

A noise-like, uncoloured tail has ~5.6 dB deviation; the classic's 23.7 dB is the
comb resonances heard as ringing. The hall's treble decays faster than its bass
(air absorption), the decay curves are straight lines (r^2 >= 0.999), and the
full-scale pad peaks at 0.96 fully wet.

CPU: ~1530 instructions per sample (ESP-IDF QEMU esp32s3, `-icount`; BM classic
reverb not measured), so roughly 0.55 of the 1451 us block budget at 160 MHz if
the LX7 needs ~1.3 cycles per instruction. Check the `worst block` log line on
the module; 240 MHz is the margin if it is short (more U8 current).

## master

End-of-chain processor for a live set, in place of the DAW chain it copies: the
kick on IN L, everything else (the 4MIX main) on IN R, one mono main on both
outputs. Every setting is made from a web page over the USB-C port and saved in
the module, which then runs alone; on stage the two CV knobs, the MODE button and
the LED do what the page set them up for (section The panel below).
`master/main/src/ms_dsp.c` is the chain, `ms_params.c` the settings table,
`ms_proto.c` the USB protocol, `ms_ctl.c` the panel, `master/web/` the page. No
MIDI, so no JP1 setting.

```
IN L kick -> trim -> filter -> limiter ----------------+--> kick level --+
                       | key, at the limiter's input   +--> send --+     |
                       v                                           v     v
IN R mix  -> trim -> filter -> 3-band dynamics --------+--> send -> parallel compressor -> return
                                                       +--> mix level ------------------------(+)
OUT L = OUT R <- output level <- limiter <- filter <- glue compressor <-----------------------+
```

The drawing is the factory order. Since 0.3.0 the effects of each strip run in
any order (settings `k_order`, `m_order`, `o_order`; on the page: drag a slot up /
down): kick filter / limiter, mix filter / multiband, master glue / filter /
limiter (all six orders). The multiband key is always the kick at the kick
limiter's input, so it keeps its lead over the delayed mix.

| Stage | What it does | Settings |
|---|---|---|
| Inputs | trim per input; the page shows both levels and a CLIP flag at the converter's full scale | kick / mix trim +-24 dB |
| Filter (kick, mix, master) | one device on each of the three strips: a low cut (high pass) and a high cut (low pass), each with its own switch; Butterworth at resonance 0.71, the resonance is the Q of a 12 dB/oct cut and on 24 / 48 dB/oct scales the sharpest section (Q 2 = +6 dB at the cut frequency on 12 dB/oct) | on; per cut: on, 10 Hz..20 kHz, resonance 0.5..6 (0.71), 12 / 24 / 48 dB/oct. Factory: kick low cut 25 Hz 24 dB/oct; mix low cut 40 Hz 12 dB/oct; master low cut 30 Hz 12 dB/oct, high cut off (16 kHz); the high cuts off |
| Kick limiter | look-ahead peak limiter | on, gain 0..24 dB, ceiling (-3 dB), release 1..1000 ms (60), auto release (off), look-ahead 0..5 ms (1.0) |
| Multiband dynamics | Linkwitz-Riley 24 dB/oct split into low / mid / high (120 Hz, 2.5 kHz); each band a downward compressor keyed by **the same band of the kick** (or of the mix itself: sidechain Self). The key is taken before the kick limiter, so it leads the audio by that look-ahead | on, sidechain Kick / Self, sidechain gain, the two split frequencies, peak / RMS detector, soft knee (6 dB), amount 0..100 %, output, solo band; per band: on, threshold, ratio 1..20, attack 0.1..200 ms, release 5..2000 ms, gain |
| Parallel compression | kick send + mix send -> one heavy compressor (6 dB knee) -> make-up -> return into the main | on, the two sends, threshold (-35 dB), ratio 1.5..20 (10), attack (2 ms), release (150 ms), make-up (20 dB), return (-6 dB) |
| Glue compressor | bus compressor on the main sum: a circuit model of the analog VCA bus compressor behind the Glue (feedback detector, RC timing, gain cell colour; section Glue compressor below) with the Glue's controls: ratio 2 / 4 / 10, attack .01 .. 30 ms and release .1 .. 1.2 s in the same steps, release A (two capacitors: a short peak recovers in ~0.1 s, a long loud passage over ~5 s), range (most reduction), dry / wet, sidechain high pass, soft clip (bends from -6 dB to a -0.5 dB top) | on, threshold (-10 dB), ratio (2), attack (10 ms), release (A), make-up, range, dry / wet, SC high pass, soft clip |
| Limiter | look-ahead peak limiter, last in the chain (factory order): the output never passes the ceiling | on, gain, ceiling (-1 dB), release (100 ms), auto release (on), look-ahead (1.5 ms) |
| Channels | off and solo on the kick, the mix and the parallel bus, off on the master (0.4.0). Off takes the channel's level and its send; solo leaves only the soloed channels in the main and keeps every send, so a soloed parallel bus is still fed; the multiband key stays (a kick that is off still ducks the mix). They are gains, so they fade in 10 ms like a fader, and they act in bypass too | off, solo; never saved |
| Output | level, and a bypass (kick + mix straight out) for comparing | output level -60..0 dB; bypass is never saved |

Levels in dB with a -60 dB minimum are off at the minimum. The factory order of
the last three differs from "glue, limiter, EQ": the filter sits before the
limiter, because a filter after a limiter lets peaks through above its ceiling
(any effect after the limiter can; only the output's hard clip at full scale
stays).

**Auto release** (both limiters; the release setting does nothing while it is
on). Ableton's Limiter has the same switch, documented only as "analyzes incoming
audio and continuously updates its release time"
(<https://www.ableton.com/en/manual/live-audio-effect-reference/>); how it does it
is not published, so this is the usual program-dependent two-stage release: the
gain is the lower of a fast stage (takes every peak, lets go in 30 ms) and a slow
stage that follows the wanted gain with a 100 ms attack and lets go in 1 s. A
lone peak hardly moves the slow stage, so the gain is back quickly (10 ms peak 12
dB over: 0.6 dB left after 150 ms); while the limiter works all the time the slow
stage sits at the average reduction and the fast one returns only to it, so the
gain does not pump on every hit (after 3 s of limiting: 8.9 dB left after 150 ms).

Settings files and stored settings of 0.2.x still load: `k_hp_*`, `m_hp_*`,
`eq_lo_*` and `eq_hi_*` are read as the filters' low and high cuts (also over
`set`).

Not the DAW's sound: the multiband is this firmware's own compressor behind the
same controls (the Above half only, no upward compression / expansion below a
threshold), and the glue is a model of the analog circuit, not of the DAW's
device. Peak limiting is on samples, not on the reconstructed wave (no true-peak
detection): keep the ceiling a little under 0 dB.

### Glue compressor

The sidechain of an analog VCA bus compressor (SSL G series), modelled as a
circuit (`glue_run` in `ms_dsp.c`, the network in `ms_dsp.h`). A model of how the
circuit works, not a copy of one unit, and not compared with one.

- **Feedback detector.** The detector reads the signal behind a second gain cell
  that follows the audio one, so it measures the compressed level. The gain
  behind the threshold is ratio - 1, which closes to the ratio on the switch.
  The loop makes the attack faster the harder it works: the 10 ms attack takes
  63 % of a 20 dB overshoot in 7.5 / 3.9 / 1.6 ms at 2 / 4 / 10:1 (30 ms: 11 ms
  at 4:1). The first version of this firmware took 15 ms for the same setting,
  so a transient that passed then may need the next slower attack now.
- **RC timing.** The gain reduction is the voltage of a timing capacitor. The
  attack resistor charges it through a diode, the release resistor across it
  discharges it all the time; attack and release are their RC products. A slow
  attack with a fast release therefore compresses less (4:1 on a tone 20 dB
  over, release 0.1 s: 14.9 dB at attack 0.1 ms, 12.3 dB at 30 ms), and a short
  release leaves ripple on bass (100 Hz under 14 dB of reduction: THD 0.6 % at
  release A, 1.5 % at 0.1 s; 1 kHz: 0.1 %).
- **Release A** is the G series network: two capacitors in series, each with
  its resistor (91k x 0.47 uF = 43 ms, 750k x 6.8 uF = 5.1 s). A short peak
  goes to the small one and is gone in ~0.1 s; the large one fills while the
  compressor works (over ~0.6 s) and lets go slowly. After 14 dB of reduction:
  a 20 ms hit leaves 2.6 dB after 0.1 s and 1.2 dB after 0.5 s; 2 s of loud
  signal leaves 12.7 dB after 0.1 s, 8.6 dB after 2 s and 4.7 dB after 5 s. On a
  steady beat it holds a level and moves a little on each kick.
- **Colour.** The rectifier's two halves are 2.8 % apart (as measured on a
  unit: second harmonic under reduction), and the gain cell adds second and
  third harmonic that grow with the level into it: 0.05 % and 0.03 % at -6 dB,
  a choice within what such VCAs do. Dry / wet at 0 is the clean input.
- **Each sample is one implicit step** of the network with the loop in it: no
  sample of delay in the feedback, no overshoot at the 0.01 ms attack at 10:1.

Not from the unit: the threshold is in dB and does not move with the ratio (the
unit shifts it), the bend at the threshold is about 6 / 4 / 4 dB of input level
wide (a measured unit: about 4 / 1 dB at 2 / 4:1), and the 0.01 ms attack, the
0.2 / 0.4 / 0.8 s releases, range, dry / wet, the sidechain filter and the soft
clip are the Glue's additions. Circuit facts from the Gyraf SSL clone notes
(<https://www.gyraf.dk/gy_pd/ssl/ssl.htm>) and the circuit mapping of
<https://github.com/chijenpeng/classic-bus-compressor> (no code from it).

| Panel | |
|---|---|
| IN L / IN R | kick / mix. They clip a little above +-5 V: trim hot sources before the module |
| OUT L / OUT R | the same mono main |
| LED | dim = running, bright = an input is at the converter's full scale, slow blink = bypass |
| MODE button, CV1 / CV2, MIDI in | not used |

### The panel: CV knobs, MODE button, LED

Since 0.4.0 (`main/src/ms_ctl.c`, `ms_io.c`). Set up on the page's **Panel** tab,
saved with the settings (`map` lines after the `set` lines; a file of 0.3.x has
none):

| Control | What it does |
|---|---|
| CV 1, CV 2 | each moves up to 8 settings, each between its own two values (knob down -> up; the two may be the other way round). Frequencies and times move on a log scale, lists step. The knob reads knob x CV (normalled to +5 V), smoothed (~30 ms) and with a 0.4 % step so the ADC's noise moves nothing. A setting follows its knob when the knob moves, at power-up, after Revert and when it is mapped; a value set on the page stays until the knob moves. Not the look-aheads (each change restarts that limiter) |
| MODE | switches up to 8 on / off settings (bypass, channel off / solo, an effect's switch, ...) to their values and back, in **one** way picked on the page (0.4.1; setting `mode_act`, saved): **click** (a press switches them over, the next press back, on the press), **hold** (holding the button 0.5 s switches them over, the next hold back; a short press does nothing), or **push** (over only while the button is down; back on the release even if the way was changed meanwhile). MODE is "over" while all its settings are at their values, also when they got there from the page. 0.4.0 had three lists (click, hold and push at once); their `map click` / `map hold` / `map push` lines now load into the one MODE list |
| LED | shows the status (dim = running, slow blink = bypass; the 0.3.x LED), the output level (-48..0 dB), the kick level, the gain reduction of the glue / limiter (0..12 dB), whether MODE is over (dim if not), or nothing; brightness; full on while an input clips the converter (switchable) |

**No cost to the audio.** The knobs and the button only change settings, as a
`set` from the page does: core 0 reads them every 10 ms in the main task (ADC
one-shot reads and a GPIO, no task or interrupt of its own), works out new
coefficients when something moved and hands them to the audio task, which takes
them at a block boundary (a copy, as for every page change). Nothing new runs per
sample: the channel switches are two more smoothed gains per block, QEMU counts
1166 / 1736 instructions per sample at the factory settings / all on (0.3.0:
1165 / 1735), and the chain renders as before (QEMU against the host, within 8
steps of 24 bits). What remains to hear on the module: a filter frequency on a
knob steps every 10 ms (as when it is dragged on the page; the gains are
smoothed, the filters are not), and the LED is PWM at 5 kHz as before, whose
duty now moves in the level modes (if it is heard in the audio, pick Status or
Off).

Pins: CV1 GPIO1, CV2 GPIO2, MODE GPIO8, LED GPIO18 (S3 and ES1 boards). The S4
board has them elsewhere and the master firmware has no CS4272 driver yet.

### Web page

`master/web/index.html`, for Chrome or Edge on a computer (Web Serial; not
Firefox or Safari). Serve it and open `http://localhost:3000` (or open the file
itself):

```sh
master/web/run.sh             # port 3000; whatever listens there is stopped first
PORT=3001 master/web/run.sh   # another port
```

Connect (side panel on the right) and pick the module's port (Espressif USB
JTAG/serial). The page fills the window: the mixer of four channel strips on top,
the selected effect in a panel of fixed height (400 px) under it, and the side
panel on the right. Strips, signal top to bottom:

| Strip | Top to bottom |
|---|---|
| KICK (IN L) | OFF / S(olo), trim knob + input level / CLIP and the send into the parallel bus, effects (Filter, Limiter), level fader |
| MIX (IN R) | OFF / S, trim and send, effects (Filter, Multiband), level fader |
| PARALLEL | OFF / S, the two sends that feed it, Compressor, return fader |
| MASTER | OFF, what feeds it, effects (Glue compressor, Filter, Limiter), output fader |

Each effect is a slot with its on / off lamp, its main values and a small
gain-reduction bar. **Drag a slot up / down (or Alt + arrow keys) to move it in
its strip's chain.** **Click a slot and it opens in the panel**: a graph drawn on
the page from the settings and the meters it polls anyway, and its settings as
knobs, switches and choice buttons:

| Effect | Graph |
|---|---|
| Filter | the response (10 Hz..20 kHz, the firmware's own filter math) with a point per cut: drag left / right = frequency, up / down or the wheel = resonance, double-click = that cut on / off; a card per cut (on, slope, frequency, resonance) |
| Limiter | reduction and level over the last 10 s against the ceiling, and the release as a shape (auto: the two stages) |
| Compressor (parallel) | the static curve with a dot where it works now, reduction and return over 10 s, attack / release shape |
| Glue compressor | the static curve, a reduction needle (0..20 dB, VU-like ballistics), attack / release shape (release A: two stages) |
| Multiband | the three bands over frequency with their live reduction drawn in; drag a split line left / right, a band up / down for its gain; a row of knobs per band with its reduction |
| Channel (click a strip's name) | the strip's levels over 10 s, its trim, send and level |

Knobs and faders: drag up / down (Shift = fine), arrow keys, double-click = the
factory value; click a knob's value to type one ("off" for a send or fader at its
minimum, "1.2k" for 1200), click its name for the factory value. Colours: grey
surfaces, one amber accent for what is set or acting (lamps, knobs, curves, gain
reduction); level meters grey, amber above -6 dB and red above -1 dB.

A change is heard at once. **Save to module** writes all settings to flash (the
audio drops for a moment while it writes); without it they are gone at
power-off, and the side panel shows "Unsaved changes" until then. Revert goes
back to the saved settings, Factory to the defaults, Export / Import keep a set as
a text file. Bypass (at the top of the side panel, above the tabs, so it stays on
screen while it is dragged onto MODE) sends kick + mix straight out to compare. The side panel also
shows the audio task's CPU load (mean and worst block) and the latency estimate.

The side panel's second tab, **Panel**, is the module's CV 1, CV 2 (with where
each knob is now), MODE (Click / Hold / Push picked with one segmented switch,
one list, a lamp lit while it is switched over and a Press button that does the
same as the button, held down for Push) and LED
(what it shows, brightness, clip flash, and the LED as it is now). **Drag a
control's name onto CV 1, CV 2 or MODE** (a knob's name, a strip's
Trim / Send / Level caption, a slot's lamp, OFF / S, Bypass, any switch): CV
starts over the setting's whole range, a switch goes to the other state (the
drag is a copy: a link-only drop is refused on Wayland). Each
mapping is a row with the value now, the two values (typed as on a knob, a
choice for lists), turn round and remove. Mapped controls carry a CV1 / CV2 / M
badge. **Right-click a control** (mouse) or, **on a touch screen, hold it** (0.55 s,
still) and pick CV 1, CV 2 or MODE in the sheet that opens; a tap still works the control, a
mapped one is taken off from there too.

**On a phone** (below 900 px wide, or a touch screen under 520 px high) the page
shows the four strips alone under a thin bar (link state, SAVE while there are
unsaved changes, BYPASSED while bypassed, ☰). Not connected, a Connect / Demo
box sits in the middle. A slot or a strip's name opens that effect full screen
(‹ or the browser's back returns); its graphs and knobs are laid out for the
screen (upright: graphs above the controls; on its side: beside them; the
multiband's bands as tabs, one band's knobs at a time) and it never scrolls:
when it does not fit, the knobs get smaller, then the extra graphs go. ☰ opens
the side panel as a drawer (settings buttons, Panel tab). Hold any control to
put it on CV 1, CV 2 or MODE; a note at the bottom says where its range is set.

The ranges, names and choices come from the firmware's own settings table
(`desc`); the page's `STRIPS` table only says which strip and slot each one
belongs to, and a setting it does not know shows up in an "Other" slot on the
master strip.

**Demo** (or `http://localhost:3000/?demo`) runs the page without the board:
every control works, the meters are invented and nothing is processed.
`web/demo.js` holds the settings table for it and is generated (`make web` in
`master/tools`; the host tests fail when it is stale).

`master/tests/web_check.mjs` drives the page in headless Chromium (node >= 22):
demo mode with real mouse drags (knobs, faders, the filter's points, the
multiband split, slots dragged to a new order), the layout (side panel, fixed
panel height, no page scroll), the Panel tab (drag and drop onto CV / MODE,
typed ranges, Press, LED, saved / reverted / exported with the settings), strip
off / solo, a touch screen (hold -> sheet, a tap still switches, a 412 px
window), the phone layout (full-screen effect and back, the bar's SAVE, every
effect without scrolling at 390 x 760, 360 x 640, 800 x 370 and 740 x 360, the
Connect box), a native browser drag (copy, onto CV 2) and right-click -> sheet, and
the Web Serial path against a fake port. Not
part of `make`; a second argument saves screenshots of every view there:

```sh
master/web/run.sh &
node master/tests/web_check.mjs http://localhost:3000/ [folder]
```

The protocol is plain text lines (`master/main/include/ms_proto.h`): `hello`,
`desc`, `get`, `set <id> <value>`, `m` (meters), `save`, `load`, `defaults`, and
for the panel `ctl`, `map <src> <id> <a> [<b>]`, `unmap`, `fire [on|off]` (protocol 3 since 0.4.1; 2 in 0.4.0, whose panel the page no longer drives). It
shares the USB port with the ESP-IDF log, whose lines the page shows at the
bottom of the side panel. `MONITOR=1 ./flash.sh master` gives a terminal on it.

### Hearing it without the module

```sh
cd master/tools && make
./ms_render [-s settings.txt] kick.wav mix.wav out.wav   # the firmware C over two WAV files
make demo                                                # synthetic 128 BPM loop, WAVs + plot
make glue                                                # the glue alone on test signals: glue.md + glue.png
cpu-bench/audio.sh                                       # the loop through the chain on the emulated ESP32-S3
```

`ms_render` takes 16 / 24 / 32-bit or float WAVs of one sample rate and the
page's export file (add `set bypass 1` for the dry sum); it prints the peaks and
the most gain reduction per stage. `make demo` writes its files to the ignored
`../research/master/`. `make glue` measures the glue's curve, attack / release,
release A and harmonics there (`glue/`; `make glue OLD=<an ms_render of another
version>` draws that one beside it). `cpu-bench/audio.sh` builds two bars of the
loop into the bench, runs it in Espressif's QEMU (the chip's instruction set and
single-precision FPU; not the codec, not cycle timing) and compares every output
sample with `ms_render`: 2026-11-22 within 8 steps of 24 bits (-120 dB) through
the whole chain and 2 steps (-132 dB) through the glue alone; the emulated
output is kept as `qemu/qemu-*.wav`. On that loop the factory settings duck the mix below
120 Hz by 9.5 dB right after each kick (0.9 dB left before the next) and the mids
by 4 dB; a model of a set, not a recording.

### Latency

| Part | Delay |
|---|---|
| I2S buffers: 16-frame blocks, 3 DMA buffers (fxrack / polysynth: 64 frames) | 1.1 .. 1.45 ms (3 to 4 blocks, by the start phase) |
| ES8388 converter filters (ADC + DAC) | ~1 ms assumed, not from a data sheet |
| Kick limiter look-ahead (the mix is delayed by the same amount) | 1.0 ms as shipped, 0..5 ms |
| Main limiter look-ahead | 1.5 ms as shipped, 0..5 ms |
| **Total as shipped** | **about 4.8 ms** (page: "Latency"), **not measured** |

Look-ahead 0 is allowed: the limiter then acts at once (in effect a clipper with
a release), and the total falls to about 2.3 ms.

### Audio path details

- 24-bit samples (codec word length 24, 32-bit I2S slots; fxrack / polysynth use
  16): the chain adds gain, so 16-bit input steps would come up with it.
- 44.1 kHz, single-precision float, state-variable filters (well conditioned at
  a 10 Hz cut), log2 / 2^x approximations within 0.006 dB.
- **240 MHz** (the others run at 160): QEMU counts 1166 instructions per sample
  at the factory settings (0.4.0; 0.3.0: 1165; 0.2.0: 1148), 1736 with everything
  on (worst block 1938 in the 0.4.0 run; every filter's low and high cut at 48 dB/oct, auto release; 0.2.0:
  1388 / 1562 with 24 dB/oct cuts), 66 in bypass (`master/tools/cpu-bench/run.sh`,
  needs Espressif's `qemu-xtensa`). The cycles per instruction on the chip are
  not known here; at 2 the worst block would take 69 % of a 240 MHz core before
  the I2S driver's own share of each 363 us block. Read the page's CPU figure on the module; the
  extra supply current is a U8 bench item.
- PSRAM off (not used). Settings in NVS as text (`set <id> <value>` lines, the
  export format): an unknown name is skipped, so a later firmware can read an
  older set.

### State

0.4.1 (2026-11-24, user: "In the MODE, allow us to select either Click, Hold or
Push. Not all."): one MODE list instead of three, worked one way, picked on the
Panel tab (`mode_act`: Click / Hold / Push, saved with the settings); `fire on` /
`fire off` for the page's Push button; 0.4.0's click / hold / push mappings load
into the one list; protocol 3. Built with ESP-IDF v5.5.1 (S3 and ES1), no
warnings. Host tests 963 checks (each way: click on the press, a long press only
once; hold not before 0.5 s; push back on the release, also after a change of
way while down), page checks 97, all pass. **Not flashed.**

0.4.0 (2026-11-24): the panel (CV 1 / CV 2 mappings with ranges, MODE click /
hold / push actions, LED modes; saved with the settings), channel off / solo on
every strip and master off, the page's Panel tab with drag and drop and, on touch
screens, hold to attach; protocol 2. Built with ESP-IDF v5.5.1 (S3 and ES1):
353 KB app, no warnings. Host tests 945 checks (+ off / solo on the chain and in
bypass, the fade, mapping rules, knob smoothing / noise / end stops / log
ranges, button debounce / click / hold / push, LED modes, protocol, save and
power-up), page checks all pass. **Not flashed, not heard; the knobs, button
and LED have not been read on the module.**

0.3.0 (2026-11-23): the cuts became one filter device per strip (low + high cut,
resonance, 12 / 24 / 48 dB/oct), the effects of each strip can change order, the
limiters have auto release; the page was rebuilt (side panel, fixed-height effect
panel with graphs and knobs, slots dragged into a new order, one accent colour).
Built with ESP-IDF v5.5.1: 332 KB app, no warnings. The demo loop through the
chain in QEMU equals the host render within 8 steps of 24 bits (2026-11-23).
**Not flashed, not heard.** Host tests
(`master/tests`, ASan + UBSan, 778 checks): filter frequencies, slopes,
resonance, band pass and switch, the order settings (kick, mix, master), auto
release (fast after a lone peak, held after long limiting), settings of 0.2.x
read as the filters, the three
bands adding up flat (within 0.001 dB), compressor curve and timing, kick-keyed
ducking and recovery, limiter ceiling at every look-ahead, chain delay, glue
ratios / range / dry-wet / sidechain filter / soft clip / auto release, the glue
circuit (no overshoot and the right level at every attack and ratio, feedback
attack times, attack against release, colour, ripple distortion), parallel
lift, bypass, random settings over loud noise (always finite and under the
ceiling), settings export / import, the whole protocol. The page was driven in
headless Chromium (demo mode and a fake serial port).

**Not bench-tested: the 32bit board is not built.** Open on the module: the
24-bit codec setting and the 16-frame I2S blocks (first use), CPU load at
240 MHz and U8 heat, measured in -> out latency, input / output levels, the audio
drop on Save, and whether opening or closing the port resets the chip on the
user's computer (the USB-Serial/JTAG reset lines; the page waits for a restart).
The sound has not been heard: the factory settings are starting points.
