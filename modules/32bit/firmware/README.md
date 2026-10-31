# 32bit firmware (ESP32-S3)

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
./compile.sh p                # build only
./flash.sh p                  # build + flash over the module's USB-C, pick the port
./flash.sh p /dev/ttyACM0     # explicit port (macOS: /dev/cu.usbmodemXXXX)
MONITOR=1 ./flash.sh p        # flash, then show the log (Ctrl-] quits)
```

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
