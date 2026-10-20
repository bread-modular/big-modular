# MCC research notes

## Routing R1 (2026-10-20)

### Router attempt (failed fast)

Input: research copy of the R2 placement with GND pours on both layers and tighter
router-only classes (Default 0.25 mm / 0.2 mm clearance, Power 0.4 mm, Fine 0.2 mm on the
QFN nets); `research/r1/prep.py`. Native rules untouched.

| Router | Run | Result |
| --- | --- | --- |
| TraceMaker 0.10.0 (hash-verified release, `--no-kb --no-gpu --soft-zones --via-cost-mm 12`, 300 s, 8 variants) | `research/r1/tm-out2/` | 91/98 connections, 20 vias; 7 boxed in at U1 (POT1, POT3, CV3_ADC, RX, TX, BANK_SW, LED_C) plus 12 opens after the pour refill. Not usable. |
| Freerouting 2.5.0 (repo-pinned, DSN/SES) | `research/r1/fr.py` | Two background runs ended without an SES; not retried. |

No GPU build: this TraceMaker release is CPU-only and a CUDA toolkit would be a system
change. On user direction ("fail fast and do it manually") routing went manual.

The router result showed the real blocker: with U1 at 180 deg every side of the QFN had
signals bound for the opposite side (LEDs on top going down, knob 1 on the right going up,
RX/TX and the bank button sharing the left side in reverse order).

### Placement and pin changes that made it routable (R3 placement, S3 schematic)

- U1 turned to 90 deg (back side). Top: PB3 RX, PB2 TX, PB1, PB0, PC0. Right: PC1-PC3, PA0.
  Bottom: PA2, PA3, VDD, PA4. Left: PA5-PA7.
- CV ADC pins reassigned among the spare ADC0 pins so each faces its op-amp:
  CV1 PB0 (AIN11), CV2 PB1 (AIN10) up to U4; CV3 PA2 (AIN2), CV4 PA3 (AIN3) down to U5.
  The Bread Modular map (PA4-PA7 knobs, PC0-PC3 bank, PB2/PB3 MIDI, PA0 UPDI) is unchanged.
  Spare: PA1, PB4, PB5. Schematic CV blocks are drawn next to the pin they feed (CV3/CV4
  above U1, CV1/CV2 below the knobs), so no wire crosses.
- J4 (UPDI) moved to the front gap between the J12 and J13 jack bodies (pins horizontal,
  pin 1 west); R5 between U1 and J4.
- C1 west of U1 (+5V pad fed from the knob +5V column), C7 above U5 pin 8, R10 turned
  (reference pad up, GND pad open to the pour).

### Manual route (tools/route_plan.py, 173 shared ops)

- B.Cu: CV clusters, op-amps, +5V east trunk (X28.4) with stubs, knob +5V column (X10.5)
  through the pot middles, power entry, MIDI front ends.
- F.Cu: bank button and LED lanes dropping through U1's package shadow (EP GND via between
  them), knob lanes through the pot middles, RX/TX/PB0 lanes up the middle strip, PA3 down,
  MIDI-band +5V from the trunk, the four jack-tip jumps over the jack pads.
- 41 vias (8 GND stitching/EP), 271 segments, 1107 mm of track (F 535, B 573).
  Minimum width 0.2 mm (QFN fan-out only; signal 0.25, +5V 0.3, power 0.4).

### Gates

Shared `pcb plan/apply` accepted the candidate (`research/route-cand-r1`), shared
`pcb promote` copied it to `hardware/`. Shared `check`: ERC 0, DRC 0, unconnected 0,
schematic parity 0, no exclusions. `order_ready` stays false: no source manifest and no
JLCPCB export yet.

### J4 pin labels (silk only)

Back silkscreen `UPDI` and `GND` (0.8 mm, the board minimum) added under J4 pin 1 and
pin 2 via `geometry.json` `back_silk`. Base rebuilt, the unchanged route plan re-applied
(`research/route-cand-r2`) and promoted; tracks are identical to R1. Shared `check`: ERC 0,
DRC 0, unconnected 0, schematic parity 0, no exclusions.

### J4 pin labels, R3 (silk only)

The R2 labels ran together (`GND UPDI` on one line). R3: 1.0 mm text, each centred on its own
pin, `UPDI` below pin 1 (X22.6) and `GND` above pin 2 (X25.14). Base rebuilt, the unchanged
route plan re-applied (`research/route-cand-r3`) and promoted; tracks identical to R1/R2.
Candidate DRC 0 / 0 unconnected / parity 0.

## JLCPCB export (2026-10-20)

Shared `opt/kicad-tools/jlcpcb/export.py` into `jlcpcb/` (carrier bottom-side SMD assembly,
panel PCB-only); commands, upload map and checks in `jlcpcb/README.md`. Shared `check` after
the export: ERC 0, DRC 0, unconnected 0, parity 0, manifest equal (5 sources). Not
supplier-accepted.

## V1: R4 to 0.5 W 1206, back silk `MCC V1` (S4/R4, 2026-10-20)

Pre-fab review, on user direction (manual edit, no router).

- **R4 (MIDI OUT series 1k)**: 0805 (125 mW) was too small. With JP2 on P and a permanent
  -12 V on the J2 tip, PB2 idling high (~5 V) puts ~17 V across R4, ~0.29 W (the old note's
  45 mW was the +12 V case into the +5V clamp). Now ROHM ESR18EZPF1001 C2074262 (1k 1 %,
  0.5 W 1206, Extended; the part modules/8bit R12 uses). PB2 then sources ~17 mA, inside
  the ATtiny1616 pin limit.
- **Placement**: R4 moved from X18.3 to X18.8 so pad 2 stays at X17.34 beside the MIDI_OUT
  via (X16.2) and pad 1 (X20.26) clears the J2 tip pad by 0.33 mm. Route plan: the two TX_P
  legs start at X20.26 and the D2 leg runs at Y13.4 (was 13.2) to clear the taller pads.
- **Silk**: back text `MCC S2` -> `MCC V1` (`geometry.json` `back_silk`).
- Base rebuilt, route plan re-applied (`research/route-cand-r4`), promoted. Against R3 only R4
  and its six B.Cu segments changed; vias, pours and every other track are identical.
  Shared `check`: ERC 0, DRC 0, unconnected 0, parity 0, no exclusions, manifest equal after
  the carrier re-export. The panel is unchanged.
