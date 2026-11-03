# HATS firmware (2 x ATtiny1616)

Ports of the Bread Modular NOISE and HIHAT firmwares
(`~/data/projects/bread-modular/modules/{noise,hihat}/code`, BM VERSION 0.1.0,
last code commit `3c8e81b`, repo at `b47ff0a`). The HATS carrier keeps both BM
pin maps (`../docs/research.md`), so the sources are BM's apart from the JP1
change below.

| Firmware | MCU | UPDI | Pins |
|---|---|---|---|
| `noise` | U2 | J11 (silk UPDI N) | PB3 MIDI RX; PA6 DAC = white noise (-> blue filter); PA7 NOISE TONE knob (RV1) |
| `hihat` | U3 | J12 (silk UPDI H) | PB3 MIDI RX; PA5 gate; PA7 open hat; PA6 DAC = velocity |

Both listen on every MIDI channel (as BM).

- **noise**: three 16-bit LFSRs XOR-mixed to the DAC. NOISE TONE (PA7) plus
  MIDI CC 74 (x8) set the sample delay: linear below half, exponential above.
- **hihat**: note-on sets the gate and DAC = velocity x 2; notes <= 60 (middle C)
  are closed hat, above 60 open hat. Note-off drops the gate. As BM, a note-on
  with velocity 0 is not treated as a note-off.

PB2 (BM `Serial` TX, still driven by `Serial.println`) is NC on both MCUs, so
the two TX pins do not fight.

## JP1 setting (required)

JP1 picks the MIDI input path, shared by both MCUs: flash **both** firmwares
for the same setting. Pass it as the second argument of `compile.sh` /
`flash.sh` (or interactively, or `JP1=`):

| Setting | JP1 | Define | RX (PB3) |
|---|---|---|---|
| `p` | 1-2 (silk P), protected NPN front end | `MIDI_RX_INVERT=1` | inverted: `PORT_INVEN` |
| `d` | 2-3 (silk D), direct (as BM; 3.3 V senders only) | `MIDI_RX_INVERT=0` | not inverted |

A build without `MIDI_RX_INVERT` stops with `#error`. A firmware built for the
other setting receives nothing usable. JP1 ships open: solder one side first.

## Use

```sh
./setup.sh                        # once: arduino-cli + megaTinyCore into ~/bin
./compile.sh noise p              # build only
./flash.sh noise p                # build + flash U2 via J11, pick the UPDI port
./flash.sh hihat p /dev/ttyUSB0   # U3 via J12, explicit port (macOS: /dev/cu.usbserial-XXXX)
```

`compile.sh` / `flash.sh` call the shared `opt/attiny1616-tools` scripts
(20 MHz internal, `jtag2updi` programmer by default, `PROGRAMMER=` to override)
through `jumper.sh`, as `modules/8bit/firmware`. Flash with the module powered
from the ±12 V header.

## Changes from Bread Modular

- `noise.ino`, `hihat.ino`: the `MIDI_RX_INVERT` guard and
  `PORTB.PIN3CTRL |= PORT_INVEN_bm` after `MIDI.begin(31250)` for JP1 = P
  (as the 8bit / LOW firmwares).
- Build scripts: module wrappers (`compile.sh`, `flash.sh`, `jumper.sh`) over the
  shared `opt/attiny1616-tools` instead of BM's symlinks; BM's READMEs are folded
  into this one.
- Everything else (`SimpleMIDI.h`, LFSRs, tone curve, note split, the
  `VREF_DAC0REFSEL_4V34` DAC reference at VDD = 3.3 V, clock) is the BM file,
  unchanged, per the HATS scope (no clock/reference changes).

Built with arduino-cli 2026-11-03 (megaTinyCore), `p` / `d`:
noise 3947 / 3937 B flash (BM: 3937 B), 175 B RAM; hihat 2002 / 1992 B
(BM: 1992 B), 163 B RAM. Not bench-tested on the HATS carrier yet.
