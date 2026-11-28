# USB-AUDIO-MAX firmware (CH32V307RCT6)

USB 2.0 High-Speed audio interface **"Bread Modular 6x8"** for the PCM3168A carrier:
6 in / 8 out, 24-bit, 48 kHz, with per-channel DC calibration. TinyUSB UAC2 + WCH
peripheral library, bare metal, built on the modules/usb-audio firmware (USB driver,
stream buffers, feedback, DFU). Sources in `usb-audio-max/src/`, DFU bootloader in
`bootloader/` (modules/usb-audio's, with its own USB IDs), build / flash through the
shared `opt/ch32v307-tools`.

```sh
./setup.sh      # once: RISC-V GCC, TinyUSB, WCH SDK, wchisp (pinned, ~/.big-modular/ch32v307)
./compile.sh    # -> usb-audio-max/.build/usb-audio-max.bin
./flash.sh      # build + write over the panel USB-C, no buttons (the running firmware restarts into its DFU bootloader)
./flash.sh --full        # first install / recovery: hold BOOT, press RESET, release BOOT (WCH ROM bootloader)
./flash.sh --bootloader  # rewrite only the DFU bootloader, through the running firmware's console
tools/console.py status  # one console command from the shell (pyserial)
tools/longrun.py --minutes 60 --out ../research/longrun   # play 8 + record 6 over ALSA, check every 10 ms
```

USB IDs (pid.codes **test** PIDs, development only): firmware `1209:0003`, DFU bootloader
`1209:0004`. modules/usb-audio uses `0001` / `0002`, so both modules can be on one host.
Without udev rules for `4348:55e0` (ROM bootloader) and `1209:0004`, `flash.sh` runs
`wchisp` / `dfu-util` through `sudo` (`opt/ch32v307-tools/README.md`). On Azero OS the OS rules
cover both and `flash.sh` never uses `sudo`; a device it cannot open is reported in one line.

## What the host sees

| Interface | |
|---|---|
| USB Audio Class 2 (driverless: Linux, macOS, Windows 10 1703+) | "Bread Modular 6x8": **8 out** (OUT 1-8 jacks) + **6 in** (IN 1-6 jacks), 24-bit in 32-bit slots, **48 kHz** only, asynchronous: the codec oscillator is the clock, the host follows it through the feedback endpoint. Channels named "OUT 1" .. "OUT 8" / "IN 1" .. "IN 6" (no speaker positions) |
| CDC serial ("Bread Modular 6x8 console", any baud) | commands below |

High speed only. No volume / mute controls: the samples only pass the calibration
(DC / CV). 96 kHz needs the second TDM line pair on SPI1 and is not done.

## Levels and calibration

Full scale (sample ±1.0) is **±5.87 V at every jack, in and out**, once calibrated:
a sample played on an OUT comes back the same on an IN, and a DC sample is that
voltage. Nominal (uncalibrated) scales are IN ±5.89 V, OUT ±5.87 V
(`../docs/research.md` section 2); the first board's loops read 4-5 % low and
-4 .. -47 mV off before calibration.

| Command | Patch | Measures |
|---|---|---|
| `cal in` | nothing in IN 1-6 (the jack's normal holds the input at 0 V) | each input's offset. Every OUT is driven to +2 V meanwhile, so an input that is still patched to an output reads ~2 V and is skipped (`patched?`) |
| `cal out` | any OUT -> IN pairing (found from the data; one output at a time per input) | for each patched output: its offset and the loop gain through its input (steps of 0, ±4 V). Unpatched outputs keep their old values |
| `cal ref <n> <volts>` | a meter on OUT n after `dc <n> 4` | optional absolute reference (below) |
| `cal` / `cal erase` | | show / forget the calibration |

- The loop gain is DAC gain x ADC gain and cannot be split without a reference: it
  is split evenly (square root) unless `cal ref` gives a meter reading; that one
  number then corrects every channel (the common error is the codec's +5VA
  reference, per channel only the 1 % resistors differ).
- An output's offset is measured through an input: without `cal in` that input's
  own offset ends up in the output's (the loop is still right, a patched-in
  external CV reads off by it). Order does not matter, the raw measurements are
  saved and the coefficients derived from all of them.
- Everything is saved in the last flash page of the application (survives
  `flash.sh`, `flash.sh --full` erases it). Each save restarts the codec (about
  0.5 s of silence).
- `looptest` steps every output to ±4 V (calibrated) and reports what each patched
  input reads. PASS: calibrated pairs gain 1 ± 0.002 and 0 V ± 2 mV, every other
  input < 0.001 of the step.

## Signal path

| | |
|---|---|
| Codec | PCM3168A on I2C2 (100 kHz), address found after every reset (1.1.0): 0x47 = S3 carrier, CLK IN open (clock master); 0x45 = S3 carrier, CLK IN connected (clock slave, see Clock link); 0x44 = S2 carrier. After every reset: DAC slave, 24-bit I2S-mode TDM (41h = 06h); HPF bypassed (52h = 07h), ADC 1-6 single-ended (53h = 3Fh) and inverted against the inverting input drivers (54h = 3Fh); then ADC master 512 fS from the 24.576 MHz SCKI, I2S-mode TDM (51h = 26h): 48 kHz, BCK 12.288 MHz. Registers are read back after writing (`status` names a register that does not) |
| TDM | I2S2 slave RX <- DOUT1 (ADC 1-6 in slots 1-6), I2S3 slave TX -> DIN1 (DAC 1-8 in slots 1-8), 32-bit words, circular DMA, 48 frames per half (1 ms). PA6 (DIN2) is held low; SPI1 / 96 kHz is not used |
| Start | The slaves start their words on the first BCK edge after they are enabled, not on a WS edge (modules/usb-audio). They are enabled while the codec, just reset, is still a slave (BCK / LRCK held low by its 50k pull-downs); writing 51h starts BCK, so both see the same first edge |
| Frame position | Found from the data after 400 ms (the ADC sends zeros while it starts): over 4800 frames, the 8 bits after each slot's 24 data bits never set and every ADC's LSB toggles with its noise; slots 7/8 stay zero. TX uses the same position. Afterwards any set bit in those zero positions counts as a `slip` and restarts codec + TDM. The streams carry silence until the position is known |
| Buffers | As modules/usb-audio: OUT = TinyUSB FIFO held at 2 ms by the feedback endpoint (+1 ms per underrun, up to 4 ms); IN = a 512-frame ring held at 2 ms + one TDM block by the IN packet size, one packet loaded per microframe. Both use the same slow proportional loop on the low-passed level (2 s time constant, at most ±1/128 of the rate). Fade in over the first block of a stream, fade to 0 V over one block when it ends or underruns |
| CPU | The USBHS interrupt only captures transfer status (`src/dcd_ch32_usbhs.c`, modules/usb-audio's TinyUSB driver copy); a software interrupt (the audio worker) processes the USB transfers and the TDM halves, with the USB work between the quarters of each half. An iso endpoint has to be served within 125 us of its last packet. `tdm.c` / `audio.c` build at -O2 (at -Os the halves took ~90 % of the CPU and transfers waited up to 174 us); `status` shows the worst wait (`processing delay`) and the worker's halves |
| Codec missing | USB still enumerates; `status` shows the reason and the firmware retries every 2 s |

## Clock link (S3 carrier, firmware 1.1.0)

The S3 carrier has the modules/multi-mix clock link: CLK OUT (J6) repeats SCKI / BCK / LRCK to the next
unit, CLK IN (J7) takes them from the unit upstream. The switching is hardware (LINK_N): the firmware only
reads the result from the codec's I2C address (ADR1 = buffered LINK_N; the MCU board has no free pin).

| State | Address | Firmware 1.1.0 |
|---|---|---|
| CLK IN open | 0x47 | Clock master, as on the S2 carrier: the ADC makes BCK / LRCK from Y1. CLK OUT carries them with no firmware help |
| CLK IN connected | 0x45 | **Not started.** The codec stays in reset, `status` says `clock slave (CLK IN connected): not supported by this firmware yet`; the address is probed again every 2 s, so pulling the ribbon brings the unit back as a master |
| S2 carrier | 0x44 | Clock master (no link on that board) |

While it runs, the codec is read once a second: a ribbon plugged into CLK IN moves the address, the audio
restarts and the unit is found a slave (the ADC is never made a master against the link receiver).

Open, needs a linked pair on the bench: starting the TDM slaves on a clock that is already running. The
CH32V307 I2S slaves start their words on the first BCK edge after they are enabled (`tdm.h`); as a master
both are armed while BCK is still, as a link slave BCK never stops. Planned: count BCK on TIM2 (CH2 = PB3,
reset by LRCK on CH1 = PA15, both pins are on the I2S3 lines already), enable each slave only in a BCK
period where the count did not move before / after the write, and take the frame position from the count;
the data-based `align` then checks it. The same is needed for the modules/multi-mix firmware. 48 kHz only
(the link carries one rate; this firmware has no other).

## Console

Open the CDC port (e.g. `picocom /dev/ttyACM0`) and press Enter, or use `tools/console.py <command>`.

| Command | |
|---|---|
| `status` / Enter | firmware, uptime + last reset cause, USB (+ VBUS dips / unplugs), codec, TDM frame position, calibration summary, stream buffers + feedback, error counters, iso packets / missed since the last status, worker timing, output sources |
| `meter` | toggle a 2 Hz line: frame rate, IN 1-6 mean and peak-to-peak volts (calibrated) |
| `cal`, `cal in`, `cal out`, `cal ref <n> <volts>`, `cal erase`, `looptest` | calibration (above) |
| `tone [n\|all]` | 1 kHz sine at half scale on OUT n (default all) instead of USB |
| `dc <n\|all> <volts>` | DC on OUT n (calibrated volts) instead of USB |
| `off` | every OUT back to the USB audio |
| `regs` | PCM3168A registers 40h-5Eh (45h = DAC zero flags, 56h = ADC overflow flags) |
| `raw` / `align` | 24 received TDM words / measure the frame position again with the bit maps |
| `misses` | the USB events captured up to the first missed iso packet since the last `misses` (time, microframe, token / endpoint, NAK flag, length) |
| `restart [s]`, `reboot`, `dfu`, `blwrite` | as modules/usb-audio (`dfu` / `blwrite` are used by `flash.sh`; `blwrite` receives into the IN ring, the audio stops meanwhile) |

`status` counters, as modules/usb-audio: `OUT underruns` = the host sent too little,
`OUT overruns` = more than the feedback asked for, `IN underruns / overruns` = the same
for the recording side, `TDM ovr / udr / slip / stall / late` and `restarts` = codec link
trouble, `ISO ... missed` = microframes without a packet, `processing delay` = the longest
wait of a captured transfer for the worker (must stay well under 125 us), `iso OUT packets
flagged NAK` = OUT packets that came right behind a console / control transfer and were taken
anyway (1.0.1; the second number counts ones that still held the previous packet: must stay 0),
`VBUS dips` = VBUS sense lows shorter than 50 ms, ignored since 1.0.1 (`unplugs` = longer ones).

## Bench results (first board)

### Bring-up (2026-11-19, bring-up firmware 0.1.0)

- `flash.sh --full` through the ROM bootloader, then `flash.sh` over DFU with no buttons (about 6 s).
- Codec: answers at 0x44, every register reads back as written; 48000 frames/s.
- TDM: slot 1 at stream bit 129 (word 4, bit 1: BCK starts in the LRCK-high half, plus the I2S
  one-bit delay) in 5 of 5 starts; all 6 ADC LSBs toggle, slots 7/8 zero; no overrun, underrun,
  slip or stall. With `dc n 1.0` on one output only, the DAC zero flags (45h) show exactly DAC n.
- Inputs without jacks read +1.89 V (the driver is a follower at VB_IN without the jack's 100k
  path); with jacks fitted, an empty input sits on the jack's normal to GND (0 V by design).
- Loops OUT n -> IN n (n = 1-6), then OUT 7 -> IN 1 / OUT 8 -> IN 2: each output reaches only its
  input (off-diagonal 0.000, so the slot mapping and bit alignment are right), loop gain
  0.946 .. 0.964 uncalibrated, linear from -5.5 to +5.5 V, clipped at ±6 V; offsets -19 .. -38 mV.
  The board dropped off USB once in that session (no reset cause readout then) and not again.

### Firmware 1.0.0 (2026-11-19)

Patched: OUT 3-6 -> IN 3-6, OUT 7 -> IN 1, OUT 8 -> IN 2; OUT 1 / OUT 2 unpatched. Host: Linux,
ALSA `hw` device (`card B6x8`: 8 ch playback, 6 ch capture, S32_LE, 48 kHz, async + feedback).

- `flash.sh` and `flash.sh --bootloader` work with the new firmware; the calibration survives both.
- `cal out` found the six pairs, loop gains 0.946 .. 0.962. `looptest` afterwards: gain
  0.9997 .. 1.0000, ±4 V read as ±3.999 .. 4.001 V, 0 V as -1 mV, others <= 0.0001: PASS.
  `cal in` not run yet (needs IN 1-6 unpatched), so each output's offset still includes its
  input's; no `cal ref` (no meter reading).
- 1 hour (`tools/longrun.py`: 1 kHz-ish sines on all 8 outputs, the 6 inputs recorded and
  fitted every 10 ms; status once a minute): residual -96 dBFS, no reset, no buffer / TDM /
  host error, but 6 clicks (single lost OUT packets, `missed OUT 6`). With a status every 5 s:
  8 in 4 minutes, so the console output caused them (below).

### Firmware 1.0.1 (2026-11-19)

- Lost OUT packets: `misses` showed each one right behind a console bulk IN that the host put
  at the start of the microframe. Its completion flag was still set when the iso OUT packet came
  3 us later, so the controller (INT_BUSY) flagged the OUT packet NAK and the driver dropped it.
  The bytes are in the buffer anyway: 1.0.1 takes such packets. 4 min with a status every 5 s:
  15 flagged, 15 fresh (none with the previous packet's bytes), 0 clicks, 0 missed.
- VBUS sense debounced (a low has to last 50 ms): a single low read used to turn the PHY off.
  `status` counts the dips; 0 in every run so far.
- 1 hour, status every 10 s, port kept open: ran 19.7 min, then the host dropped the board
  (`USB disconnect`, then five more within a minute while nothing was streaming). The MCU did
  not reset (uptime kept counting), VBUS dips / unplugs 0, so the firmware did not let go of
  the bus: link / cable / ground side, not found yet. Before that: one burst at 2.3 min of
  7 OUT + 6 IN packets missing together (about 1 ms with no packet from the host in either
  direction, device processing delay 66 us at worst: host side), every other window clean
  (residual -96 dBFS); 23 NAK-flagged OUT packets taken, 0 stale. Earlier disconnects of the
  same kind: 13:46 and 13:49 (1.0.0).

Not done: `cal in` and `cal ref` on the board, macOS / Windows hosts, 96 kHz (SPI1 for
DOUT2 / DIN2), OUT 1 / OUT 2 calibration (unpatched in this run).

### Firmware 1.1.0 (2026-11-20)

Codec address probing (0x47 / 0x45 / 0x44) and the clock-link handling above. Compiled only: not
flashed, not run on the S2 board (it should find 0x44 after two unanswered probes), and there is no S3
carrier yet.
