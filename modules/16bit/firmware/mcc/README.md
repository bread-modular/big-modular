# lyra4 MCC firmware (ATtiny1616)

Custom firmware for the two MCC modules that play the 16bit `lyra4` app
(`../16bit/includes/audio/apps/lyra4_app.h`). It is
`modules/mcc/firmware/mcc/mcc.ino` with two changes:

- **The bank is fixed at build time** (`MCC_UNIT`): there is no bank switching.
- **The BANK button and its three LEDs are a 3-step selector.** Each press
  steps 1 -> 2 -> 3 -> 1 and lights LED A / B / C. The press sends the step as
  its own CC (0 / 64 / 127), and the MCC resends it every second with the
  knobs, so the 16bit picks it up after power-up. The step is kept in EEPROM
  (the MCC's `ModeHandler`, where the bank used to be). A plain tap steps: the
  press counts on release and only has to last 20 ms (contact bounce), not the
  stock MCC's 200 ms BANK press.

| Unit | Knobs 1-4 | Button (CC) | Steps 1 / 2 / 3 |
|---|---|---|---|
| `1` MCC-1 VOICE | CC20 SHARP A, CC21 SHARP B, CC22 MOD, CC23 DRIVE | CC102 FM routing | PAIRS / LOOP / TOTAL FB |
| `2` MCC-2 FX | CC27 DELAY TIME, CC28 FEEDBACK, CC29 DELAY MIX, CC30 CUTOFF | CC103 RESONANCE | Off / Peak / Sing |

Everything else is the MCC firmware: knob n + CV n (the CV jacks add to the
knobs, so an LFO into FEEDBACK or SHARP modulates it), MIDI channel 1, values
sent on change (10 ms) and all of them every second, and every incoming note,
CC and realtime message passed through. Chain them
`sequencer -> MCC-1 -> MCC-2 -> 16bit`: MCC-2 passes MCC-1's CCs and the
clock (for the 16bit motion recorder) through.

`SimpleMIDI.h` and `ModeHandler.h` in `lyra4_mcc/` are symlinks to the MCC
firmware's files, so a fix there applies to both firmwares.

## Use

```sh
./setup.sh                    # once: arduino-cli + megaTinyCore (shared opt/attiny1616-tools)
./compile.sh p 1              # JP1 setting (p|d, as modules/mcc/firmware), unit (1|2)
./flash.sh p 1                # build + flash MCC-1, pick the UPDI port
./flash.sh p 2 /dev/ttyUSB0   # MCC-2, explicit port
```

JP1 is the MCC's MIDI input jumper, as in `modules/mcc/firmware/README.md`
(`p` = protected input, RX inverted; `d` = direct). Flash through the MCC's
J4 (UPDI) with the module powered from the ±12 V header. Flashing the stock
MCC firmware back (`modules/mcc/firmware/flash.sh`) restores the banks.

Built with arduino-cli 2026-11-12 (megaTinyCore 2.6.11): units 1 / 2 for
`p` 3927 B flash, `d` 3917 B, 197 B RAM. `../16bit/tools/sim_lyra4.cpp`
checks that the CC numbers and step values here match the 16bit control map.
Not bench-tested.
