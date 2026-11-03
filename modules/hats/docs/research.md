# HATS circuit intent and revision notes (S3/R2/P4)

## Brief and baseline

HATS combines Bread Modular NOISE (blue output only) and HIHAT in one 6HP module.
The read-only baseline is `~/data/projects/bread-modular/modules/{noise,hihat}`.

Two ATtiny1616 retain their original functional pin maps: NOISE needs the PA6 DAC for
noise and PA7 for TONE; HIHAT needs the PA6 DAC for velocity, PA5 gate and PA7 open-hat
selection. Both receive one RX net and have separate UPDI headers (J11 NOISE, J12 HIHAT).
The MIDI split is <=60 closed / >60 open, with velocity as accent, as in the baseline.

## Current circuit

| Block | Parts / behavior |
|---|---|
| Power | J10, D1/D2 series protection, C1-C5, U1 HT7533-1; +/-12 V output stage, +3V3 internal signals |
| MIDI | J1, R1-R3, D3, Q1, JP1; JP1 shipped open. 1-2 protected/inverting requires PB3 inversion in both firmwares; 2-3 direct/unprotected is for 3.3 V senders only |
| Noise | U2, C6, R4, J11; PA6 -> R6 -> U4A white follower; C8 / RV2 BLUE TONE / R7 high-pass; U4B blue follower and R8; R9/R10 midpoint; RV1 NOISE TONE to PA7 |
| External noise | J2, R11 100k, C10, R12 100k, R13 33k, U9B: AC-coupled inverting gain -0.33 around VMID_H |
| Normalling | U5 TS5A23157, C11; empty = BLUE_NOISE, patched = NIN_BUF. R14 470k / R49 22k / D7 BAV199 protect the independent TN sense path; see `noise-in-protection.md` |
| Filter / VCA | C12/R15, U6A bridged-T filter, R16/C13/C14/R17/RV3 CUTOFF; U7 VTL5C, R18-R23 and U6B x3.2; R24/R25/C15 VMID_H |
| HiHat MCU | U3, C7, R5, J12; original gate / velocity / open-hat pin assignments |
| Envelope | R26-R39, C17/C18, U8, U9A, Q2/Q4 SS8050, Q3 SS8550, D4, RV4 DECAY; BM values and topology |
| Outputs | U10 TL072 on protected +/-12 V: AUDIO x3, C21/R40-R43/J3; CV x1.51, R44-R46/J4; R47/D5 ENV LED |

BM substitutions retained: B5819W in place of SS14; U10B replaces the BM CV follower,
freeing U9B for external-noise conditioning. Nominal audio/CV ranges are design targets,
not measured or calibrated guarantees. Pot direction and electrical pin numbering are
unchanged (R3: all four pot footprints are upright again).

## User-directed S3/R2 changes

- Remove recording entirely, not merely from firmware: SW1, D6, R48, their nets, PCB
  copper and two panel apertures are gone. U2 PC2 and U3 PC2/PC3 are explicit NCs.
  There is no promise of recording analog CUTOFF/DECAY movements.
- Increase pot row pitch from 24 to **34 mm**: upper shafts Y41, lower shafts Y75.
  Lower pots rotate 180 degrees with pin rows at Y67.5. Jack locations stay fixed. The ENV LED D5 (with R47) sat beside the HAT CV jack, body X26 Y93 (user direction 2026-10-24; was X15 Y54.8); R3 moved it below the jack (see below).
- Move the vactrol down **3.3 mm to Y88**, clearing the lower pots without an overlapping
  switch. Local SMD placement and affected connections were reworked; unrelated routing
  and functional nets were retained. No full-board or bulk router was used.
- Restore **1.0 mm copper-edge rule** and refill/save all four layers. Actual filled
  polygons have 1.0005 mm setback. Remove obsolete switch/vactrol exclusions; re-enable
  all five previously ignored DRC severities and four ignored ERC defaults, and fix off-centre via endpoints.
- Strengthen NOISE IN sensing without changing the 100k input loading or analog gain:
  R14 470k; R49 22k sense-only series resistor; low-leakage D7 BAV199 dual rail clamp.
- Leave clock/reference firmware settings untouched, per explicit user direction.

The previous S2/R1 audit is historical (`research/fab-review-20261024/REVIEW.md`), not
current release status. S3 removes its recording requirement and repairs the requested
copper/manifest/sense issues; the firmware finding is deferred, not technically disproved.

## User-directed S3/R3 change (2026-11-03): pots upright, vactrol under CUTOFF

The user rejected the 180-degree lower pots. RV3/RV4 are back at 0 degrees (same shafts,
pin rows now Y82.5 below the bodies), and the vactrol U7 lies on B under the CUTOFF pot,
as on modules/low (U5 under RV3) and modules/acid: centre X9.5 Y79.4, native 90 degrees,
LDR leads on the left (VCA_IN, FILTERED at X3.15), LED leads on the right (VAC_K, HAT_CV at
X15.85), between the RV3 bracket row and its pin row. Panel unchanged.

Moved to make room, all on B (schematic unchanged): U6 into the lower-left band (old vactrol
area); R18-R22, C21 under RV3/RV4 pins; C15 beside them; the HPF parts C12-C14/R15-R17 into the
band freed by the old lower pin row; R27 by C17; R23, R34-R37, C18, Q4 into the right band
(R36 0.5 mm up); D4 turned 180 degrees. Copper in that band was ripped up and re-routed by
hand, a few links per batch, with full DRC after each (`research/pot-flip/`: `layout.py`,
`ba.py`..`bd.py`). Crossings use short F.Cu runs (FILTERED, CUT_R, VMID_H, HAT_CV, VAC_K,
VCA_IN, ENV_BUF, GATE_OPEN); no autorouter, no inner tracks.

Stacking findings, **user-approved DRC exclusions** (2026-11-03, as on LOW/ACID; written by
`tools/vactrol_exclusions.py`): 10 `pth_inside_courtyard` errors (U7 leads inside the RV3/RV4
courtyards; RV3 pins/brackets and the RV4 left bracket inside the U7 courtyard) and 8
`silk_over_copper` warnings (RV3 side silk over the U7 LDR pads; the U7 body outline over the
three nearby bracket pads). The U7 SOLDER FIRST / TRIM FLUSH notes were laid flat between
the bracket and pin rows, clear of every pad.

ENV LED below HAT CV (2026-11-03, user direction): D5 body X22.25 Y112.2 (KiCad 122.25/162.2),
centred under J4, rot 180 (anode pad 2 left), its courtyard 0.1 mm clear of the J4 courtyard.
The 3V3 regulator group around it on B was re-placed: U1 HT7533 rot 180 bottom right, D1 vertical
left of the LED (+12V from J10 pin 9 at the top), C3 under D1, C5 under the LED; GND/+3V3 go to
In1/In2 by vias. +12V_F runs from D1/C3 to the U1 tab under the LED pads and up the right side to
the existing feed at C1. R47 stays by the CVO_AMP source; LED_A drops through a via beside R47 and
runs on F.Cu west of the J4 pads (`research/pot-flip/le3.py`..`le9.py`). The panel LED hole and
ENV label (now below the LED, Y115.6) were regenerated from `docs/geometry.json`, FR4 and printed.

ENV LED between AUDIO OUT and HAT CV (2026-11-03, user direction, supersedes the spot below J4):
D5 body X15 Y105 (KiCad 115/155), rot 90 (anode pad 2 up at Y103.73, K/GND pad 1 at Y106.27).
Its F courtyard is rotated so it fits the 4.9 mm gap between the J3/J4 courtyards (0.19 mm each
side); it sits 3 mm below the jack centre row so its leads clear the U10 courtyard on B (0.08 mm)
with U10 unmoved. R41/R42 moved vertical below the LED (X112.525/114.125, Y158.9), C22 vertical
right of it (X117.475 Y156.3); R42/C22 GND tie to the LED K pad (In1 via its barrel). OUT_AMP runs
straight down from U10 pin 1; OUT_FB leaves pin 2 to a via and runs on F west of the LED to a
via by R41. LED_A runs on F from R47 diagonally over U10. The regulator group stays where it was
(the old LED spot is now empty). ENV label at Y108.8 below the LED (`research/pot-flip/lm1.py`,
`lm2.py`).

ENV LED on the jack centre line (2026-11-03, user direction, supersedes X15 Y105): D5 body X15
Y102 (KiCad 115/152), midway between J3 and J4, rot 90 (anode pad 2 at Y100.73, K/GND pad 1 at
Y103.27). U10 (TL072, B) had to leave that spot: it moved down to KiCad 115/157.1, where the LED,
R41/R42 and C22 were; its body clears the LED lead pads by 0.5 mm. R42 (GND top, to the C23 GND
via) and R41 (OUT_AMP bottom) stand vertical left of the LED at X112.6, C22 below U10 (Y160.75,
GND straight to J10 pin 7). Pins 2/3/4 (OUT_FB, OUT_IN, -12V_F) and pin 6 (CVO_FB) drop to vias
under the U10 body and run on F beside the LED pads (OUT_FB to a via by R41, OUT_IN to the old
trunk, -12V_F to the existing via by C23, CVO_FB right of the LED to its trunk); pin 1 OUT_AMP
runs on a B lane at X109.9 to R41 and the R43 trunk; HAT_CV and CVO_AMP on B lanes X118.8/119.25
(CVO_AMP also feeds R46). +12V_F reaches U10 pin 8 from D1 on a lane at X119.6; the old
C1-to-U10 trunk across J4 was removed (C1 stays fed from U1). LED_A drops into the anode from
above on F. The CVO_FB lane sits 1.2 mm right of the LED so its K pad keeps two F spokes.
ENV label Y105.8 below the LED. 498 tracks / 94 vias (`research/pot-flip/n1.py`..`n6.py`).

## Verification and manufacturing

R3: native ERC 0; carrier DRC unconnected 0, schematic parity 0, violations only the 18
stacking findings above, all 18 excluded (user-approved). No ignored DRC severities. Panel: only
the LED hole and ENV label moved (native panel DRC 0).

Carrier: 29 x 110 mm, 1.6 mm, four copper layers. All assembled SMD on B; 473 tracks,
89 ordinary 0.3/0.6 mm vias; no inner signal tracks, no via-in-pad/mask overlap, each inner
plane one piece. Outer GND pieces are electrically joined; no disconnected pours remain.
Minimum SMD-to-hand-solder pad gap 2.045 mm (R3). The original approved RV1-RV4 courtyard-edge
exception remains (0.815 mm measured line boxes); no copper-edge exception.

JLCPCB package and reproduction commands: `../jlcpcb/README.md`. Scope and raw evidence:
`research/s3-r2/`. No firmware, supplier uploads, orders or commits were made.

## Remaining gates

Supplier DFM and bottom-side placement preview; exact part/land-pattern/rating review;
stock/attrition at the chosen order quantity; prototype power/thermal, normalling/contact
transients, MIDI jumper/inversion, actual mechanical fit and audio/CV behavior. Existing
Extended 0.5 W output resistors remain disclosed; this is not an all-Basic passive BOM.

Project consistency: repaired the inherited nil top-level sheet UUID / empty sheet list to match the actual native schematic root. Shared PCB inspection now succeeds with all ERC/DRC severity rules enabled.
