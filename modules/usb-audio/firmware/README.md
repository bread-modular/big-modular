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
| CDC serial ("USB-AUDIO console", any baud) | `status`, `meter`, `cal`, `tone`, `regs`, `restart`, `reboot` (below) |

USB IDs `1209:0001` are the pid.codes **test** PID (development only). High
speed only: on a full-speed port the audio interface cannot carry 192 kHz.
No volume / mute controls: samples pass bit-exact (DC / CV), the pots are the
volume.

## Signal path

| | |
|---|---|
| Codec | CS4270 at I2C 0x48, control-port **master**: MCLK 24.576 MHz / 2, quad / double / single speed for 192 / 96 / 48 kHz (MCLK/LRCK 128 / 256 / 512), SCLK = 64 Fs, I2S format both ways |
| I2S | I2S2 slave RX (PB13/PB12/PB15, DMA1 ch4) <- SDOUT; I2S3 slave TX (PB3/PA15/PB5, DMA2 ch2) -> SDIN, 32-bit slots, CPOL low. The CH32V307 slaves do not wait for a WS edge, so every start (power-up, rate change, recovery) resets the codec, arms both slaves while its clocks are still and only then clears PDN: both lock to the first SCLK edge with a fixed alignment (channel B first, data in word bits 30..7, `src/i2s.h`). Received bits 6..1 must stay zero; anything else counts as a `slip` and restarts. Circular DMA, 48 frames per half (0.25 ms at 192 kHz) |
| Buffers | 8 KiB FIFO each way, held at 2 ms of audio (OUT: feedback, IN: packet-size control) |
| DC | Inputs: the ADC high-pass is frozen from the start (reg 04h), so DC passes. The firmware measures each input's offset 0.3-0.8 s after power-up (about +12 / +7 mV on the first board) and subtracts it at every rate, so keep IN 1/2 unpatched at power-up (or run `cal` later). `ADC_INV` undoes the inverting input drivers. Outputs: auto-mute, soft ramp and Popguard off (a DC output must hold a static code) |
| Codec missing | USB still enumerates; the console shows the reason (`no I2C answer at 0x48`, `no LRCK`) and the firmware retries every 2 s |

Full scale at the jacks (pots fully up, `docs/research.md` section 2): IN ±5.49 V,
OUT ±5.2 V. `meter` prints the measured LRCK rate and, per jack, the DC mean
and peak in volts on that scale.

## Console

Open the CDC port (e.g. `picocom /dev/ttyACM0`, `screen /dev/ttyACM0`) and press Enter.

| Command | |
|---|---|
| `status` / Enter | firmware, USB speed, codec state / chip ID / rate, I2S, stream and FIFO state, feedback, error counters |
| `meter` | toggle a 2 Hz line: measured LRCK, IN / OUT DC and peak volts |
| `cal` | measure the input DC offsets again (unpatch IN 1/2 first) |
| `tone` | toggle a 1 kHz test tone at half scale on OUT 1/2 instead of the USB audio |
| `regs` | CS4270 registers 01h-08h |
| `restart` | reset + restart codec and I2S |
| `reboot` | reset the MCU |
| `dfu`, `blwrite` | used by `flash.sh` (DFU bootloader, bootloader rewrite) |

## Bench results (first board, 2026-11-04)

OUT 1 patched to IN 1, both pots fully up, played and recorded over USB at 48,
96 and 192 kHz: steps from ±0.0625 to ±0.9 full scale come back with the same
gain (1.016 / 0.998 / 1.011, the codec's filters differ per speed mode), sign
intact; a 1 kHz sine at half scale has THD about -91 dB. The same result after
10 rate changes and restarts; 40 s of play + record at 48 kHz without a dropout
or a missed packet.

## Not done / limits

Not tested: OUT 2 / IN 2 through a patch cable (same code path, slot B), the
output DC offset (VREF_OUT tracking), long runs at 192 kHz, and Windows / macOS.
