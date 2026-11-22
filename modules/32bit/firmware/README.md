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
the module, which then runs alone. `master/main/src/ms_dsp.c` is the chain,
`ms_params.c` the settings table, `ms_proto.c` the USB protocol, `master/web/`
the page. No MIDI, so no JP1 setting.

```
IN L kick -> trim -> sub cut -> limiter ---------------+--> kick level --+
                       | key, before the limiter       +--> send --+     |
                       v                                           v     v
IN R mix  -> trim -> low cut -> 3-band dynamics -------+--> send -> parallel compressor -> return
                                                       +--> mix level ------------------------(+)
OUT L = OUT R <- output level <- limiter <- low / high cut <- glue compressor <----------------+
```

| Stage | What it does | Settings |
|---|---|---|
| Inputs | trim per input; the page shows both levels and a CLIP flag at the converter's full scale | kick / mix trim +-24 dB |
| Kick sub cut | Butterworth high pass | on, 10..120 Hz (25), 12 / 24 dB/oct |
| Kick limiter | look-ahead peak limiter | on, gain 0..24 dB, ceiling (-3 dB), release 1..1000 ms (60), look-ahead 0..5 ms (1.0) |
| Mix low cut | Butterworth high pass | on, 20..500 Hz (40), 12 / 24 dB/oct |
| Multiband dynamics | Linkwitz-Riley 24 dB/oct split into low / mid / high (120 Hz, 2.5 kHz); each band a downward compressor keyed by **the same band of the kick** (or of the mix itself: sidechain Self). The key is taken before the kick limiter, so it leads the audio by that look-ahead | on, sidechain Kick / Self, sidechain gain, the two split frequencies, peak / RMS detector, soft knee (6 dB), amount 0..100 %, output, solo band; per band: on, threshold, ratio 1..20, attack 0.1..200 ms, release 5..2000 ms, gain |
| Parallel compression | kick send + mix send -> one heavy compressor (6 dB knee) -> make-up -> return into the main | on, the two sends, threshold (-35 dB), ratio 1.5..20 (10), attack (2 ms), release (150 ms), make-up (20 dB), return (-6 dB) |
| Glue compressor | bus compressor on the main sum with the Glue's controls: ratio 2 / 4 / 10 (knee 12 / 8 / 4 dB, wider at low ratios), attack .01 .. 30 ms and release .1 .. 1.2 s in the same steps, release A (a 0.1 s release plus a slow stage that charges while the compressor works: a single hit recovers fast, a long loud passage over ~2 s), range (most reduction), dry / wet, sidechain high pass, soft clip (bends from -6 dB to a -0.5 dB top) | on, threshold (-10 dB), ratio (2), attack (10 ms), release (A), make-up, range, dry / wet, SC high pass, soft clip |
| Main cuts | Butterworth low cut and high cut | low: on, 15..300 Hz (30); high: off, 2..20 kHz (16 kHz); 12 / 24 dB/oct |
| Limiter | look-ahead peak limiter, last in the chain: the output never passes the ceiling | on, gain, ceiling (-1 dB), release (100 ms), look-ahead (1.5 ms) |
| Output | level, and a bypass (kick + mix straight out) for comparing | output level -60..0 dB; bypass is never saved |

Levels in dB with a -60 dB minimum are off at the minimum. The order of the last
three differs from "glue, limiter, EQ": the cuts sit before the limiter, because a
filter after a limiter lets peaks through above its ceiling.

Not the DAW's sound: the Glue and the multiband are this firmware's own
compressors behind the same controls (the multiband has the Above half only, no
upward compression / expansion below a threshold). Peak limiting is on samples,
not on the reconstructed wave (no true-peak detection): keep the ceiling a
little under 0 dB.

| Panel | |
|---|---|
| IN L / IN R | kick / mix. They clip a little above +-5 V: trim hot sources before the module |
| OUT L / OUT R | the same mono main |
| LED | dim = running, bright = an input is at the converter's full scale, slow blink = bypass |
| MODE button, CV1 / CV2, MIDI in | not used |

### Web page

`master/web/index.html`, for Chrome or Edge on a computer (Web Serial; not
Firefox or Safari). Serve it and open `http://localhost:3000` (or open the file
itself):

```sh
master/web/run.sh             # port 3000; whatever listens there is stopped first
PORT=3001 master/web/run.sh   # another port
```

Connect and pick the module's port (Espressif USB JTAG/serial). The page is a
mixer of four channel strips, signal top to bottom:

| Strip | Top to bottom |
|---|---|
| KICK (IN L) | trim knob + input level / CLIP, effects (Sub cut, Limiter), send into the parallel bus, level fader |
| MIX (IN R) | trim, effects (Low cut, Multiband), send, level fader |
| PARALLEL | the two sends that feed it, Compressor, return fader |
| MASTER | what feeds it, effects (Glue compressor, Cuts, Limiter), output fader |

Each effect is a slot with its on / off lamp, its main values and a small
gain-reduction bar. **Click a slot and its settings show in the panel under the
mixer** (the multiband as three band cards); a click on a strip's name shows the
strip's own trim, send and level there. Beside each fader: gain reduction
(growing downward) and the level after the strip's effects with peak hold; the
sends are taken at that point too, before the fader. Knobs and faders: drag up /
down (Shift = fine), arrow keys, or type the value ("off" for a send or fader at
its minimum); a double-click, or a click on a setting's name in the panel, gives
the factory value.

A change is heard at once. **Save to module** writes all settings to flash (the
audio drops for a moment while it writes); without it they are gone at
power-off, and the header shows "Unsaved" until then. Revert goes back to the
saved settings, Factory to the defaults, Export / Import keep a set as a text
file, Bypass sends kick + mix straight out to compare. The header also shows the
audio task's CPU load (mean and worst block) and the latency estimate.

The ranges, names and choices come from the firmware's own settings table
(`desc`); the page's `STRIPS` table only says which strip and slot each one
belongs to, and a setting it does not know shows up in an "Other" slot on the
master strip.

**Demo** (or `http://localhost:3000/?demo`) runs the page without the board:
every control works, the meters are invented and nothing is processed.
`web/demo.js` holds the settings table for it and is generated (`make web` in
`master/tools`; the host tests fail when it is stale).

`master/tests/web_check.mjs` drives the page in headless Chromium (node >= 22):
demo mode with real mouse drags on a knob and a fader, and the Web Serial path
against a fake port. Not part of `make`:

```sh
master/web/run.sh &
node master/tests/web_check.mjs http://localhost:3000/
```

The protocol is plain text lines (`master/main/include/ms_proto.h`): `hello`,
`desc`, `get`, `set <id> <value>`, `m` (meters), `save`, `load`, `defaults`. It
shares the USB port with the ESP-IDF log, whose lines the page shows at the
bottom. `MONITOR=1 ./flash.sh master` gives a terminal on it.

### Hearing it without the module

```sh
cd master/tools && make
./ms_render [-s settings.txt] kick.wav mix.wav out.wav   # the firmware C over two WAV files
make demo                                                # synthetic 128 BPM loop, WAVs + plot
```

`ms_render` takes 16 / 24 / 32-bit or float WAVs of one sample rate and the
page's export file (add `set bypass 1` for the dry sum); it prints the peaks and
the most gain reduction per stage. `make demo` writes its files to the ignored
`../research/master/`. On that loop the factory settings duck the mix below
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
  the 10 Hz sub cut), log2 / 2^x approximations within 0.006 dB.
- **240 MHz** (the others run at 160): QEMU counts 1120 instructions per sample
  at the factory settings, 1360 with everything on (worst block 1500), 62 in
  bypass (`master/tools/cpu-bench/run.sh`, needs Espressif's `qemu-xtensa`). The
  cycles per instruction on the chip are not known here; at 2 the worst block
  would take 55 % of a 240 MHz core (83 % at 160 MHz) before the I2S driver's
  own share of each 363 us block. Read the page's CPU figure on the module; the
  extra supply current is a U8 bench item.
- PSRAM off (not used). Settings in NVS as text (`set <id> <value>` lines, the
  export format): an unknown name is skipped, so a later firmware can read an
  older set.

### State

Built with ESP-IDF v5.5.1 (2026-11-22): 328 KB app, no warnings. Host tests
(`master/tests`, ASan + UBSan, 585 checks): cut frequencies and slopes, the three
bands adding up flat (within 0.001 dB), compressor curve and timing, kick-keyed
ducking and recovery, limiter ceiling at every look-ahead, chain delay, glue
ratios / range / dry-wet / sidechain filter / soft clip / auto release, parallel
lift, bypass, random settings over loud noise (always finite and under the
ceiling), settings export / import, the whole protocol. The page was driven in
headless Chromium (demo mode and a fake serial port).

**Not bench-tested: the 32bit board is not built.** Open on the module: the
24-bit codec setting and the 16-frame I2S blocks (first use), CPU load at
240 MHz and U8 heat, measured in -> out latency, input / output levels, the audio
drop on Save, and whether opening or closing the port resets the chip on the
user's computer (the USB-Serial/JTAG reset lines; the page waits for a restart).
The sound has not been heard: the factory settings are starting points.
