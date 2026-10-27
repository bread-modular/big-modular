# MIDI firmware (ATtiny1616)

Port of the Bread Modular `midi` firmware
(`~/data/projects/bread-modular/modules/midi/code/midi`, 2.0.1) for both
hardware versions of this module. The V1 and V2 boards use the Bread Modular pin
map unchanged (checked against the `U1` nets of `hardware/v1` and `hardware/v2`):

| | CH1 | CH2 | CH3 | CH4 | CH5 | CH6 | CH7 | CH8 |
|---|---|---|---|---|---|---|---|---|
| TX | PA5 | PA6 | PA7 | PB5 | PB4 | PB1 | PB0 | PB2 (USART TX) |
| LED | PC0 | PC1 | PC2 | PC3 | PA1 | PA2 | PA3 | PA4 |

RX is PB3 (USART RX), UPDI is PA0 (J11).

- Receives MIDI on the hardware UART, forwards note on/off and CC of an
  8-channel window to CH1-CH8 (CH1-CH7 `SoftwareSerial`, CH8 the USART TX), and
  broadcasts realtime (clock, start/stop) to all eight.
- Drives each channel LED high on note on, low on note off.

## Hardware version (required)

The version is a compile-time flag, chosen by the first argument of
`compile.sh` / `flash.sh` (or interactively when omitted, or `MIDI_VERSION=`):

| Target | Board | Defines | RX (PB3) |
|---|---|---|---|
| `v1` | V1.0 | `MIDI_HW_VERSION=1 MIDI_RX_INVERT=0` | direct input, not inverted |
| `v2` | V2.0, JP2 1-2 (protected) | `MIDI_HW_VERSION=2 MIDI_RX_INVERT=1` | NPN stage inverts: `PORT_INVEN` |
| `v2-direct` | V2.0, JP2 2-3 (debug bypass) | `MIDI_HW_VERSION=2 MIDI_RX_INVERT=0` | direct path, not inverted |

A build without `MIDI_HW_VERSION` stops with `#error`. Flashing `v2` on a board
with JP2 at 2-3 (or `v1`/`v2-direct` on a protected V2) receives nothing usable.

## Use

```sh
./setup.sh                      # once: arduino-cli + megaTinyCore into ~/bin
./compile.sh v2                 # build only
./flash.sh v2                   # build + flash, pick the UPDI port
./flash.sh v1 /dev/ttyACM0      # explicit port
```

`compile.sh` / `flash.sh` call the shared `opt/attiny1616-tools` scripts
(20 MHz internal, `jtag2updi` programmer by default, `PROGRAMMER=` to override).

### MIDI channel window

Copy `.config.example` to `.config` (ignored) and set `MIDI_CHAN_START=9` for
channels 9-16 (default 1-8).

## Changes from Bread Modular

- One source for both versions: the `midi-2.0` `PORT_INVEN` on PB3 is behind
  `MIDI_RX_INVERT` (set in `setup()` after `Serial.begin`).
- `setupGates()` looped `1..8`, so CH1's LED pin (PC0) was never set as an output
  (only its pull-up toggled). It now loops `0..7`.
- `sendMIDI()` takes the `SoftwareSerial` by reference instead of copying it.
- `SimpleMIDI.h` is the Bread Modular file, unchanged.

Built with arduino-cli 2026-10-27 (megaTinyCore 2.6.11): `v1` 3741 B, `v2` 3751 B
flash, 471 B RAM. Not bench-tested on either board yet.
