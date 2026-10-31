> **Superseded (2026-11-01):** BASE routing is finished (0 opens); see [final record](/modules/usb-power-45w/docs/r3-base/final/README.md). Kept as history.

# BASE R3 routing completion — progress log (window 5, fresh context)

Status: **in progress, not release.** Imported exact WIP blobs from 1508e4aa (board sha256 7e8b980d…, 101 opens,
verified at start: DRC 0 / parity 0 / exclusions 0). TOP untouched.

Tools: `tools/route_base_r3_final.py` (new unique batches on top of `route_base_r3.py` apply/writeback/audit; the
shared `pcb plan/apply` gate is unchanged). Its `path` sub-command is a ONE-connection suggestion helper: it prints
corner coordinates for one connection of one net; nothing is written by it. Every batch below was written by hand
into `FINAL`, inspected and applied one at a time; sequencing conflicts were rejected by the shared gate and redone.
Raw reports: ignored `research/r3-base-final/`.

## Batches
| batch | content | opens after |
| --- | --- | --- |
| A1-mid-local | START_CT, START_SENSE R69-R70, BAD_RC U15-R72, FAULT_LATCH U12-TP11 | 97 |
| A2-por | POR_SER (B x104.65), POR_SENSE (first try) | 95 |
| A3-rip-porsense | rip own A2 POR_SENSE (blocked the U10 under-body via slot) | 96 |
| A4-reset-start | RESET_N U10 -> B -> under U12; START_READY via 0.67 mm U12.13/12 gap | 94 |
| A5-porsense | POR_SENSE R66.1 -> B -> U10.5 | 93 |
| A6-startsense | START_SENSE U11.5 -> B -> F y84.225 -> R70.1 | 92 |
| A7-faultlatch | FAULT_LATCH U12.9 -> B y94.675 -> TP6 | 91 |
| A8-gnd-badrc | GND U11.2/U10.2 x102.6 -> via; BAD_RC R72.2 -> B -> C51.1 | 88 |
| W1-u13-north | U13.14 V3V3 via moved under the body; MAIN_LED_OK north lane -> U14.1 -> Q6.1 | 86 |
| W2-u13-local | RUN chain U14/U13, V20_OK U13.13-10 (B y64.2), MAIN_OK U13.12 -> B | 79 |
| W3-timer | TIMER_GO U13.8 -> F north over MHB2 -> R69.1 | 78 |
| W4-armed | ARMED U13.4 -> B y71.875 -> TP10 | 77 |
| W5-faultclk | FAULT_CLK U13.6 -> B -> under U12 -> U12.11 | 76 |

## Checkpoint 1
- Board sha256 dcc30cb51ef6d58935945a267b3a5a90f426c2c72d32a91f4505d5406c31e317
- `kicad-cli pcb drc --severity-all --schematic-parity --refill-zones`: violations 0, parity 0, **76 unconnected**
  (list `open-final-ckpt1.txt`); vias in SMD pad/mask 0, In1 tracks 0, zero/dup/dangling 0;
  `check_support_copper.py base --refill`: 0 problems (nearest r3.601).
| E1-east-local | REF_GOOD U18.6-9 + R74-C56, NEG_OFF_LED R60-R59-U16.1, V3V3 C57-R88 | 71 |
| E2-east-xb2 | REF_GOOD C56 -> U18.10, P12_OK U18.1-XB2.4, P5_OK U18.2-XB2.5 | 68 |
| E3-east-status | N12_STATUS U18.14 -> U19.2, MON_20 R84.1 -> U18.11 | 66 |
| E4-east-n12ok | V3V3 U19.5 dogbone, N12_OK Q9.1 -> U19.4 | 64 |
| E5-east-run | RUN R64.1 -> XB2.3 (F y71.325 under MHB3), XB2.3 -> TP9 (B x130) | 62 |
| E6-east-v20-5v | V20_OK U18.13 -> R85.2 (B between XB2 columns, under MHB3); +5V R77.1 -> +5V F track (F y63.725 north lane) | 60 |
| S1-d18a | D18 anode R88.2 -> B south band under MHB4 -> D18.2 | 59 |

## Checkpoint 2 (current)
- Board sha256 f921cd7c9a1f36cca3a74baaa5d3343ad7699c1c54b92e081ed20da367ec3917; 185 vias, 551 tracks.
- Native DRC `--severity-all --schematic-parity --refill-zones`: violations 0, exclusions 0, parity 0,
  **59 unconnected** (`open-final-ckpt2.txt`). Vias in SMD pad/mask 0, In1 tracks 0, zero/dup/dangling 0, every
  zone one piece. `check_support_copper.py base --refill`: 0 problems. `test_support_keepout.py`, `test_tps3808_pins.py` OK.
- `check_stack.py` (scratch research/r3-base-final/check-ckpt2; tracked validation.json NOT updated — not final):
  ERC root/base/top 0, aggregate interconnect equal true, base DRC parity 0 / 59 opens, TOP DRC 0 / 0 opens
  (hardware/top byte-unchanged), courtyard-edge < 1 mm none, hand-solder < 2 mm none, vias in SMD pads none.
- Images: final-ckpt2-whole.png, final-ckpt2-u8.png, final-ckpt2-west-corridor.png.

Remaining 59 by net: N12_RAW 7, LED_RETURN 4, P12_OK/P5_OK/V3V3/VPD/N_VCC/N_UV/N_OUT_PIN 3, RUN/N12_OK/N_OV/V20_OK 2,
1 each: D8-K D8-A D16-K D16-A D17-K D17-A D18-K MAIN_OK RESET_N -12V(R90.1) N_PGD BAD_FILTERED ANY_BAD NOT_RUN
ARMED(TP10-U12.5) NOT_FAULT MON_20(R83.2) +12V(R75.1) VIN(TP4).

## Blockers found (exact, for help)
1. **MHB2 corridor (west logic U13/U14 -> middle/east).** 11 nets still have to leave the U13/U14 block eastward
   (P12_OK U14.2, P5_OK U14.4, N12_OK U14.5, ANY_BAD U14.6, NOT_RUN U14.8, RUN, LED_RETURN Q10.3, V20 west part,
   NOT_FAULT U13.2, RESET_N U13.1, BAD_FILTERED U13.5) plus 6 LED nets (Q6.3/Q7.3/Q8.3, R22.2/R86.2/R87.2 -> D8/D16/D17 at
   y97.9). At the MHB2 longitude (keep-out x78.35-85.55, y63.97-71.18) the free lanes are: F north (taken by
   TIMER_GO y63.775), B north y63.45 (1 lane), B south of MHB2 y71.2-74.3 (ARMED y71.875, MAIN_OK y72.4 already there;
   the MAIN_OK B diagonal (76.2,74.2)-(78.0,72.4), my FAULT_CLK B diagonal (78.4,73.075)-(83.2,77.875), VPD_U1 B x78.85
   (74.75-80.5) and PD_BASE B x72.9 cut the band). Planned fix (own copper, authorised): rip W5 FAULT_CLK and re-lay
   the corridor as 8 parallel B lanes y71.45..74.25 at 0.4 mm pitch (move the MAIN_OK east B diagonal/via into one
   lane), feed them from under-body/south-of-U13 vias, then split east (north through the J2 pin gaps, 0.84 mm, one
   track each, to the B north band y63.4-67) and south (B x86.8-89.8 west of XB1 to U12/U15/R72). LED nets: move the
   AI-placed Q6/Q7/Q8 + R22/R86/R87 next to D8/D16/D17 (SMD >= 2 mm from LED pads) so only gate/V3V3/LED_RETURN cross.
2. **U8 LM5067 escape** (unchanged from HANDOFF): pins 1-3 (N_VCC/N_UV/N_OV) are boxed by the N_PWR F track
   (U8.4 -> x113.55 -> y87.45) on the west and N_SENSE_PIN F y87.5 on the north; only under-body vias (x~116.1)
   are possible, max ~2 at 0.8 mm via pitch beside the N_GATE via (117.6,89.3). N_OUT_PIN (pin 9) must cross them
   westward to D20; N_UV/N_OV go east (U16.4, R55/R54). Waiting for the separate U8 guidance; the R90/D20/C43
   refinement is authorised but not applied.
3. D18-K (Q9.3 -> D18.1): the only path left after D18-A runs north of MHB4 on B y93.175 through the U8 area; held
   back until U8 is done (or re-lay D18-A/D18-K as an outer/inner pair under MHB4: y101.125 / y100.725).

## Checkpoint 3 (U8 escape, Astra suggestions re-validated on own copper)

Board `36be2387068f0d1ade8fcc41da617302242df8481cb32cb89b77af5c2b295f5b`: native DRC all severities 0 violations / 0 exclusions /
parity 0, **45 opens** (`open-final-ckpt3.txt`), no via in SMD pad/mask, no In1 tracks, no zero/duplicate/dangling tracks,
every pour one piece, `check_support_copper.py base --refill` 0 problems, 9 unit tests pass, TOP untouched.

Batches U1-U5 in `tools/route_base_r3_final.py`:
- U1: C43 -> (115.3,91.95,180), R90 -> (118.4,91.95,0) (Astra swap); N12_RAW U8.5 -> C43.2 quiet return.
- U2: N_VCC under-body run at x116.95 (Astra's x116.7 left no room: the exact Astra via pair at (116,88.9)/(116,89.8) failed
  0.166 mm to the N_OV stub); N_UV via (116.3,88.95) -> B -> via (113.9,93.2) -> R53.1 -> R52.2; N_OV via (116.0,89.95);
  N12_RAW C43.2 -> R53.2 -> D20.1 -> D19.1.
- U3: own NEG_OFF_LED B hop moved onto F (x125.0/125.2 -> U16.1); N12_RAW C44.2-R55.2; N_OUT_PIN D20.2-D20.3.
- U4: N_VCC C43.1 -> R50.2 on F, outside the MHB4 keep-out.
- U5: N_OV B y89.95 -> via (123.35,89.75) in the R55/R54 gap; -12V R90.1 -> via (117.6,90.95) -> B y90.95 -> x124.1 ->
  existing -12V via (127.3,84.8); N_UV B y92.6 -> via (127.35,93.45) -> U16.4.

U8 still open: N_VCC R51.2 (boxed by own BAD_RC F x110.2 / POR_SENSE + FAULT_LATCH B), N12_RAW {C44.2,R55.2} and U16.3,
N_OUT_PIN U8.9 + R90.2, N_PGD U8.10 -> U17.2. Core blocker for OUT/PGD: the N_GATE B spine x117.6 (y79.35-89.3) and
N_SENSE_PIN F (y87.5 + x120.25) fence the east pins; proposed next step is the N_SENSE_PIN corridor rework under the body
(F x118.0 to pin 7) so pins 8-10 exit east, plus a re-laid N_GATE R57 branch.

## Checkpoint 4 (U8 finished, N_VCC/N12_RAW joined, LED drivers at the LEDs, middle logic)

Board `3058a7674e8cbc9be68ef285dd7c942790fde58a328e663c30252684a678d460`: native DRC all severities 0 violations /
0 exclusions / parity 0, **25 opens** (`open-final-ckpt4.txt`), no via in SMD pad/mask, no In1 tracks, no
zero/duplicate/dangling tracks, every pour one piece (In2 V3V3 one piece after the N_VCC slot),
`check_support_copper.py base --refill` 0 problems, `pytest tools/test_support_keepout.py tools/test_tps3808_pins.py`
9 passed. `check_stack.py` (scratch research/r3-base-final/check-ckpt4; tracked validation.json restored, not final):
ERC root/base/top 0, interconnect equal true, problems [], fixed interfaces J1/J2/SW1/D8/D16/D17/D18 unchanged,
courtyard-edge < 1 mm none, hand-solder < 2 mm none, base DRC 0 / 25 opens, TOP DRC 0 / 0 opens (hardware/top unchanged).

Batches (tools/route_base_r3_final.py):
- V1 U8 east column: pin 8 -> F straight into Q4.1; R57 rotated 180 in place so its gate pad is east (gate: R57.1 -> via ->
  B x119.9 -> existing gate via (123,88.6); R57.2 N_SENSE -> B x117.6 -> via (116.8,86.3) -> R89.1, Kelvin pickup at the
  R48.1 pad unchanged). N_SENSE_PIN pin 7 -> F under the body x117.95 -> D19/R89.2 run. PGD pin 10 -> via -> B corridor
  x119.3/118.6 -> F -> U17.2. OUT pin 9 -> 0.5/0.3 via in the 1 mm U8/Q4.1 gap -> B -> D20.3 and R90 (rotated 180).
  -12V R90.1 -> via (119.2,91.0) -> B y90.8 -> x124.1 lane. N_OV B moved to y91.75 -> via (123.35,91.5).
- V2 N_VCC R51.2: In2 power-only 0.3 mm hop (user-authorised) (114.6,94.475) -> (107.5,91.5).
- V3 C44 and R55 rotated 180 in place (N12_RAW pads south). V4 N12_RAW C44.2 -> U16.3 (F under U16) and -> B hop -> C43.2;
  own N_UV B lane lifted y92.6 -> y92.4 for the hop vias (MHB4 keep-out below).
- L1 LED drivers moved next to the LEDs (Q6/R22 over D8, Q7/R86 over D16, Q8/R87 row y89.5 for D17), SMD pads <= y95.0
  (>= 2.0 mm from the LED pads); L2 D17 K/A on B, U11.6 V3V3 dogbone (own POR_SENSE R65.2 link moved to B).
- P1 TP4 VIN via to In2 VIN; +12V monitor feed R75.1 -> XB1.12. M1 ARMED U12.5 -> TP10; U9.8 -> U9.5 VPD.
  M2 U9 VPD group -> Q3/TP1 VPD run. M3 RESET_N U13.1 -> R67.2.

### Blocker (exact): the U13/U14 logic block exit
After M3 the one-connection helper finds **NO PATH** for BAD_FILTERED (U13.5 -> U15.4) and NOT_FAULT (U13.2 -> U12.8);
before M3 all four of RESET_N/BAD_FILTERED/NOT_FAULT/ANY_BAD took the same single lane: U13 underside via -> B (76,71.5) ->
F hop (79.3-80.95, 70.9-72.0) under the MHB2 keep-out -> B diagonal past D9 to (84.7,75.6) -> via (89.3,80.2) west of XB1.
Still needing to leave the U13/U14 block: BAD_FILTERED, NOT_FAULT, ANY_BAD, NOT_RUN (-> Q5.1 124.9,98.2), MAIN_LED_OK
(-> Q6.1 78.4,92.4), P12_OK (-> TP12, Q7.1, XB2 run), P5_OK (-> TP13, Q8.1, XB2 run), N12_OK (-> TP14, east B run), RUN
(U14 local + -> R64 run), V20_OK (-> TP15), MAIN_OK (-> XB2.2), LED_RETURN (Q10.3 68.7,81.25 -> Q6/Q7/Q8 -> Q9.2 133.1,97.9).
Also open: VPD R83.1 (only helper path goes round the north of MHB2 and down the U13 east side - not taken), MON_20
R83.2 -> east MON_20 run, D18-K (D18.1 -> Q9.3).
The block is fenced by the north edge (one free B lane y~63.6), MHB2 keep-out (x78.35-85.55), the In2-VIN/USB-PD power
area to the south (D10/D11/U5/Q2/F1/J1 with VPD/EF_IN/VBUS pours) and the west edge. Next step (authorised class, large):
re-place the AI-placed U13/U14 (+ local R/C) toward the U12/U15 logic (free F around x86-100 / y84-96 is gone, so this needs a
placement study), or re-lay the MHB2-south band as parallel B lanes (rip W5 FAULT_CLK, M3, MAIN_OK diag) - capacity of
that band at x81.95 is ~3.8 mm on B (y71.2-75.0, D9 is F only) = about 8 lanes for ~13 nets.
Images: final-ckpt4-whole.png, final-ckpt4-u8.png, final-ckpt4-leds.png, final-ckpt4-corridor.png.
