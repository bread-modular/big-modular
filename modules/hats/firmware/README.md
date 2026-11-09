# HATS firmware (S4, STM32G071C8T6)

One firmware for U2 on the S4/R4 carrier: the Bread Modular NOISE and HIHAT
firmwares (`~/data/projects/bread-modular/modules/{noise,hihat}/code`, BM
VERSION 0.1.0, last code commit `3c8e81b`) ported from the two S3 ATtiny1616s
to one STM32, plus the S4 additions: the CUTOFF knob driving the U11 vactrol
by PWM, and the shared 4-bar REC recorder on CUTOFF and NOISE TONE. Bare
metal (CMSIS headers only), built with the shared `opt/stm32g0-tools`.

The S3 ATtiny ports (`noise/`, `hihat/`) match the S3/R3 board only and were
removed; they are in git history before this change.

| Pin | Use |
|---|---|
| PA4 DAC1_OUT1 | white noise (BM NOISE) -> R6 / U4A, the blue high-pass |
| PA5 DAC1_OUT2 | velocity (BM HIHAT) |
| PA2 / PA3 | gate / open hat (notes <= 60 closed, > 60 open) |
| PA1 ADC_IN1 | NOISE TONE knob RV1 |
| PA6 ADC_IN6 | CUTOFF knob RV3 |
| PB0 TIM3_CH3 | CUTOFF vactrol LED (R51 -> U11), 31.25 kHz PWM |
| PB4 / PB5 | REC button SW1 (internal pull-up) / REC LED D6 |
| PB7 USART1_RX | MIDI, 31250 baud, all channels |

Sources: `hats/src/main.cpp` (hardware), `hats/src/hats_logic.h` (behaviour,
no hardware access, host-tested), `hats/src/CvRecorder.h` (symlink to the
shared `opt/attiny1616-tools/lib/CvRecorder`), `hats/src/Arduino.h` (the GPIO
and `millis()` the recorder needs), `hats/stm32g071x8.ld`.

## Behaviour

- **NOISE** (BM): three 16-bit LFSRs XOR-mixed to DAC1. NOISE TONE plus MIDI
  CC 74 x 8 sets the hold between samples: linear below half, exponential
  above (BM curve, unchanged). The S3 TONE level compensation (`boostSwing`)
  is kept. A 100 kHz timer replaces the BM busy-wait: one tick per BM delay
  unit (~10 us on the 20 MHz ATtiny, estimated from the instruction count,
  not measured), so TONE 0 gives ~33 kHz and full TONE holds a sample ~1.3 s.
- **HIHAT** (BM): note-on sets the gate, open hat for notes above middle C,
  and DAC2 = velocity x 2; note-off drops the gate. As BM, a note-on with
  velocity 0 is not a note-off.
- **CUTOFF**: the knob (or the recorded take) sets the U11 LED PWM so that
  the LDR with R50 51k across it equals knob x 50k, the S3 rheostat, in the
  same direction (knob up = more resistance). The LDR model is generic, not
  measured: `R_ldr = LDR_R_ON x duty^-LDR_GAMMA`, 300 R at 100 % (~4 mA) and
  gamma 1.0 (`hats_logic.h`); re-fit both on the bench. The duty carries 5
  bits below the 11-bit PWM step, dithered per PWM period, because the top
  of the knob needs well under one step.
- **REC** (shared CvRecorder, as modules/acid): press REC to record 4 bars on
  MIDI clock (LED blinks), then it loops the take (LED on); after the first
  loop the knobs offset the take; press again for live. Lane 1 CUTOFF,
  lane 2 NOISE TONE. MIDI Start rewinds. Needs MIDI clock.
- DAC levels: BM writes 8-bit values with the ATtiny reference that its
  author notes ends up as VDD (3.3 V); VREF+ here is +3V3, so 8-bit full
  scale maps to 12-bit full scale and the levels match.

## Changes from Bread Modular

- One MCU and timer-driven noise instead of two ATtiny loops (above).
- MIDI parser: running status and real-time bytes inside messages are
  handled (BM's `SimpleMIDI` lost a message when a clock byte arrived in it,
  and the recorder needs clock).
- TONE + CC 74 is clamped to 1023 (BM let it reach 2039, which held one noise
  sample for hours). A lower TONE takes effect at once instead of after the
  pending hold.
- The `MIDI_RX_INVERT` guard for JP1 (USART1 RXINV), as the 8bit / LOW / ACID
  firmwares.

## JP1 setting (required)

JP1 picks the MIDI input path. Pass it to `compile.sh` / `flash.sh` (or
interactively, or `JP1=`):

| Setting | JP1 | Define | RX (PB7) |
|---|---|---|---|
| `p` | 1-2 (silk P), protected NPN front end | `MIDI_RX_INVERT=1` | inverted: USART1 `RXINV` |
| `d` | 2-3 (silk D), direct (as BM; 3.3 V senders only) | `MIDI_RX_INVERT=0` | not inverted |

A build without `MIDI_RX_INVERT` stops with `#error`. A firmware built for
the other setting receives nothing usable. JP1 ships open: solder one side.

## Use

```sh
./setup.sh          # once: shared opt/stm32g0-tools (CMSIS headers, OpenOCD)
./compile.sh p      # build only -> hats/.build/p/hats-p.{elf,bin,hex}
./flash.sh p        # build + flash U2 over SWD (ST-Link on J11)
hats/test.sh        # host tests of hats_logic.h, no hardware
```

Flash with the module powered from the ±12 V header (J11 pin 1 +3V3 is the
probe's VTref sense).

Built 2026-11-09 with ARM GCC 14.2.rel1, `p` / `d`: 7832 / 7828 B flash,
5560 B RAM (incl. stack/heap reserve), no warnings. Host tests and the shared
CvRecorder tests pass. **Not run on hardware**: clock, ADC, DAC, PWM, UART and
the vactrol model are unverified until the bench.
