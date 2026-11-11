# USB-AUDIO firmware (CH32V307RCT6)

USB 2.0 High-Speed audio interface for the carrier's CS4270, written for this
module (TinyUSB UAC2 + WCH peripheral library, bare metal). Sources in
`usb-audio/src/`, build/flash through the shared `opt/ch32v307-tools`.

```sh
./setup.sh      # once: RISC-V GCC, TinyUSB, WCH SDK, wchisp (pinned, ~/.big-modular/ch32v307)
./compile.sh    # -> usb-audio/.build/usb-audio.bin
./flash.sh      # build + write over the panel USB-C, no buttons (the running firmware restarts into its DFU bootloader)
./flash.sh --full        # first install / recovery: hold BOOT, press RESET, release BOOT (WCH ROM bootloader)
./flash.sh --bootloader  # rewrite only the DFU bootloader, through the running firmware's console
```

## What the host sees

| Interface | |
|---|---|
| USB Audio Class 2 (driverless: Linux, macOS, Windows 10 1703+) | "Bread Modular 2X2": **2 out** (OUT 1/2 jacks) + **2 in** (IN 1/2 jacks), 24-bit in 32-bit slots, **48 / 96 / 192 kHz** (host picks), asynchronous: the codec oscillator is the clock, the host follows it through the feedback endpoint |
| CDC serial ("USB-AUDIO console", any baud) | `status`, `meter`, `cal`, `cal erase`, `tone`, `regs`, `restart`, `reboot` (below) |

USB IDs `1209:0001` are the pid.codes **test** PID (development only). High
speed only: on a full-speed port the audio interface cannot carry 192 kHz.
No volume / mute controls: samples pass bit-exact (DC / CV), the pots are the
volume.

## Signal path

| | |
|---|---|
| Codec | CS4270 at I2C 0x48, control-port **master**: MCLK 24.576 MHz / 2, quad / double / single speed for 192 / 96 / 48 kHz (MCLK/LRCK 128 / 256 / 512), SCLK = 64 Fs, I2S format both ways |
| I2S | I2S2 slave RX (PB13/PB12/PB15, DMA1 ch4) <- SDOUT; I2S3 slave TX (PB3/PA15/PB5, DMA2 ch2) -> SDIN, 32-bit slots, CPOL low. The CH32V307 slaves do not wait for a WS edge, so every start (power-up, rate change, recovery) resets the codec, arms both slaves while its clocks are still and only then clears PDN: both lock to the first SCLK edge with a fixed alignment (channel B first, data in word bits 30..7, `src/i2s.h`). Received bits 6..1 must stay zero; anything else counts as a `slip` and restarts. Circular DMA, 48 frames per half (0.25 ms at 192 kHz) |
| Buffers | OUT: TinyUSB FIFO held at 2 ms of audio by the feedback endpoint (+1 ms per underrun, up to 4 ms, until the next reset). IN: a 1024-frame ring held at 2 ms + one I2S block by the IN packet size; the firmware loads exactly one packet per microframe (TinyUSB's IN flow control is off). Both use the same slow proportional loop on the low-passed level (2 s time constant, at most ±1/128 of the rate): the host sees a nearly constant feedback value and packet sizes that are the nominal one with a single ±1 now and then |
| Stream start / stop | Every stream open, rate change and codec restart drops the buffered audio. IN sends silence until the ring is filled and until the ADC sends samples (about 20 ms after a codec start); OUT waits for its target level, fades in over one block and fades to silence when the audio ends or underruns |
| DC | Inputs: the ADC high-pass is frozen from the start (reg 04h), so DC passes. The firmware subtracts each input's offset at every rate. **Run `cal` once with IN 1/2 unpatched**: it measures the offsets and saves them in the last flash page of the application. Without saved offsets they are measured after every power-up (IN 1/2 assumed unpatched then). A measurement only ends when 4 windows of 100 ms in a row are quiet (<= 10 mV peak to peak) and agree within 0.5 mV, and is rejected above 0.1 V or after 10 s (`status` says why), so a patched signal or a rail that is still settling is not taken for an offset. `ADC_INV` undoes the inverting input drivers. Outputs: auto-mute, soft ramp and Popguard off (a DC output must hold a static code) |
| CPU | Interrupt levels: the USBHS interrupt only captures the transfer status; the audio worker (software interrupt) processes the USB transfers and the I2S blocks, with the USB work between the blocks and between the quarters of a block. An iso endpoint has to be served within the 125 us to its next packet; the worst case measured is about 30 us at 192 kHz. `src/mem.c` replaces newlib-nano's byte-wise `memcpy` / `memset` with word-wise ones (every sample is copied three times; it was a third of the CPU at 192 kHz) |
| Codec missing | USB still enumerates; the console shows the reason (`no I2C answer at 0x48`, `no LRCK`) and the firmware retries every 2 s |

Full scale at the jacks (pots fully up, `docs/research.md` section 2): IN ±5.49 V,
OUT ±5.2 V. `meter` prints the measured LRCK rate and, per jack, the DC mean
and peak in volts on that scale.

## Console

Open the CDC port (e.g. `picocom /dev/ttyACM0`, `screen /dev/ttyACM0`) and press Enter.

| Command | |
|---|---|
| `status` / Enter | firmware, USB speed, codec state / chip ID / rate, input offsets, I2S, stream and buffer state, feedback, error counters (below) |
| `meter` | toggle a 2 Hz line: measured LRCK, IN / OUT DC and peak volts |
| `cal` | measure the input DC offsets and save them (unpatch IN 1/2 first; the audio stops for a moment). `cal erase` forgets the saved offsets |
| `tone` | toggle a 1 kHz test tone at half scale on OUT 1/2 instead of the USB audio |
| `regs` | CS4270 registers 01h-08h |
| `restart` | reset + restart codec and I2S; `restart <s>` holds the codec in reset for that many seconds first |
| `reboot` | reset the MCU |
| `dfu`, `blwrite` | used by `flash.sh` (DFU bootloader, bootloader rewrite) |

### After a click or a dropout

Run `status` (each call prints what happened since the previous one):

| Line | Meaning |
|---|---|
| `OUT:` / `IN:` | `buffer N frames (min..max, held at T)`: the level since the last `status`; `feedback` / `packets` is the rate in samples per 125 us |
| `Count:` | `OUT underruns`: the host sent too little (late or missing packets; the OUT target grows 1 ms each time). `OUT overruns`: it sent more than the feedback asked for. `IN underruns / overruns`: the same for the recording side. `I2S ...` and `restarts`: codec clock or alignment trouble |
| `ISO:` | packets per endpoint and how many microframes passed without one (`missed`): the host skipped a packet, or the device was late for it |
| `DCD:` | `processing delay`: the longest time a captured transfer waited for the audio worker (must stay well under 125 us) |

All counters at 0 with a click still heard: the samples were already wrong in what
the host sent, or the click is analog.

## Bench results (first board, 2026-11-04)

OUT 1 patched to IN 1, both pots fully up, played and recorded over USB at 48,
96 and 192 kHz: steps from ±0.0625 to ±0.9 full scale come back with the same
gain (1.016 / 0.998 / 1.011, the codec's filters differ per speed mode), sign
intact; a 1 kHz sine at half scale has THD about -91 dB. The same result after
10 rate changes and restarts; 40 s of play + record at 48 kHz without a dropout
or a missed packet.

## Bench results (firmware 1.1.0, first board, 2026-11-11)

OUT 1 -> IN 1 and OUT 2 -> IN 2 patched, pots fully up, Linux host (ALSA `hw`
device), 1 kHz / 1.5 kHz sines at half scale played and recorded at the same
time, every 10 ms window of the recording fitted against the sine:

| | 48 kHz | 96 kHz | 192 kHz |
|---|---|---|---|
| 200 s run: windows with a click, phase step or level change | 0 | 0 | 0 |
| Missed OUT / IN / feedback packets, under / overruns, I2S errors | 0 | 0 | 0 |
| Longest wait of a transfer for the audio worker | 29 us | 30 us | 33 us |
| Residual (THD + noise) | -88 dB | -87 dB | -74 dB |

- Also clean: 60 s with small host buffers (48 kHz period 64 / buffer 256
  frames, 96 kHz 128 / 512).
- Rate changes 48 -> 96 -> 192 -> 48 kHz with a stream opened right after each:
  the recording is silence, then the sine, steady 10-30 ms after the stream
  starts; no sample above the sine's peak. The input across a codec restart
  stays within 0.01 % of full scale (-81 dBFS).
- Offsets: the same values after three resets; `cal` saves them and they
  survive a reset; `cal` with a tone on the inputs is rejected after 10 s and
  the old offsets stay; `cal erase` returns to the power-up measurement.

## Not done / limits

Not tested: macOS and Windows hosts (the clicks that led to 1.1.0 were heard
on macOS and did not show on Linux with either version, so that test is still
open), a real power cycle with the offsets not saved (only MCU resets here),
the outputs during the 20 ms after a codec start (the ADC is still silent
then), and the output DC offset (VREF_OUT tracking).
