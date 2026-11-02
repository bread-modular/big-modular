# 16bit firmware (RP2350)

Port of the Bread Modular 16bit firmware
(`~/data/projects/bread-modular/modules/16bit/code/16bit`, VERSION 1.6.0,
commit `5ba0067`) in `16bit/`. The carrier keeps the BM GPIO map
(`../docs/research.md` §1, `../Code.md`), so the sources are BM's apart from
the JP1 change below. `16bit/README.md` is the BM README (apps, motion
recorder, serial API, ELab scope protocol).

One app per firmware, picked at build time: `noop`, `sampler`, `polysynth`
(default), `fxrack`, `elab`, `monosynth`.

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
lowpass, P4 highpass). Here group B (notes 6-11) gets the same pair: **P1
lowpass** (before FX3) and **P2 highpass** (after FX3), with the P3 / P4
curves. The app reads ADC0 / ADC1 from the main loop every 2 ms and rescales
the unpatched knob range (ADC ~2020..3735 = 0..+5 V) to 0..1; knobs fully
down = both filters open. Patched, P1 / P2 scale the CV, and negative CV
clamps to open. The other apps don't read P1 / P2 as knobs (`../docs/research.md` §5).

**MODE = 4-bar motion recorder** in the sampler (new; BM's sampler MODE
stopped/restarted the audio), fxrack (new; BM left MODE unused), polysynth and
monosynth (BM). Click MODE to
record (LED blinks), after 4 bars on MIDI clock it loops (LED solid), click
again for live. Each frame holds P1..P4 and all twelve MCC CCs (banks A / B / C).
As on the 8bit recorder, the knobs and MCC are ignored for the first loop
pass; after that, moving one shifts its whole recorded curve. Needs a running
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
`elab`, `monosynth` (BM `dist/` ships the same six).

The firmware works with the Bread Modular web UI
(<https://breadmodular.com/ui/16bit>, Web Serial): the serial API
(`includes/api/web_serial.h`, the `::val::...::val::` replies) and the USB
identity (VID 0x2E8A, PID 0x000A, "Bread Modular" / "16bit") are BM's,
unchanged. Checked against bread-modular-website commit `f991473`: every
command the UI sends is handled by the app that answers `get-app`:

| App | UI commands |
|---|---|
| all | `get-app` |
| sampler | `get-fx1..3`, `set-fx1..3 <fx>`, `play-sample <n>`, `write-sample-base64 <n> <bytes> <len>` |
| polysynth | `get-waveform`, `set-waveform <saw\|tri\|square>` |
| fxrack | `get-fx1..3`, `set-fx1..3 <fx>` |
| elab | `get-scope-channels`, `start-send`, `start-send-2`, `stop-send` |
| monosynth, noop | none (the UI only shows the app) |

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
- `includes/audio/apps/sampler_app.h`: group B filter pair on P1 / P2 (above);
  FX1 defaults to `noop` instead of Rumble (BM started Rumble while `get-fx1`
  reported `noop`); `set-fx1 rumble` still selects it and is saved; MODE runs
  the motion recorder (BM: stop audio while held, kick on release).
- `includes/audio/apps/motion_recorder.h`: frames carry P1..P4 and the twelve
  MCC CCs (BM: CV1 / CV2 and Bank A); 8bit-style loop offset after one guard
  pass; unrecorded CCs stay live. Polysynth / monosynth adapted to the new
  frame (`readKnobs`, `ownsCc`); `tools/sim_motion_recorder.cpp` extended.
- `src/audio/apps/fxrack_app.cpp`: MODE runs the motion recorder (P3 / P4 and
  all three MCC banks; BM: MODE unused).
- Everything else (apps, DSP, drivers, assets, host tools) is the BM file,
  unchanged.

Built 2026-11-02 (Pico SDK 2.1.1, ARM GCC 14.2.1, Linux): all six apps for
`p` and `d`, no warnings. UF2 sizes: noop 155648, sampler 409600, polysynth
186368, fxrack 180224, elab 169472, monosynth 191488 B for both `p` and `d`
(BM's packaged 1.6.0 UF2s: noop, fxrack, elab the same; polysynth 184320,
sampler 393216, monosynth 189440 B; the differences are the group B filters,
the motion recorder changes, the `picotool info` description and the `p` RX
inversion). Host tests: 3 drivers pass (recorder: 5033 checks). Not bench-tested on the 16bit carrier yet.
