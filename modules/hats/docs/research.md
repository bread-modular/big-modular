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
unchanged even though the lower two footprints rotate mechanically.

## User-directed S3/R2 changes

- Remove recording entirely, not merely from firmware: SW1, D6, R48, their nets, PCB
  copper and two panel apertures are gone. U2 PC2 and U3 PC2/PC3 are explicit NCs.
  There is no promise of recording analog CUTOFF/DECAY movements.
- Increase pot row pitch from 24 to **34 mm**: upper shafts Y41, lower shafts Y75.
  Lower pots rotate 180 degrees with pin rows at Y67.5. Jack/ENV LED locations stay fixed.
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

## Verification and manufacturing

Fresh native ERC, carrier DRC (warnings/exclusions included), unconnected count, schematic
parity and exact ref/pin/net comparison are zero. No ignored DRC severities or exclusions.
Panel DRC is also zero; all 11 holes align with the carrier/geometry contract.

Carrier: 29 x 110 mm, 1.6 mm, four copper layers. All assembled SMD on B; 546 tracks,
101 ordinary 0.3/0.6 mm vias; no inner signal tracks, no via-in-pad/mask overlap, each inner
plane one piece. Outer GND pieces are electrically joined; no disconnected pours remain.
Minimum SMD-to-hand-solder pad gap 2.0465 mm. The original approved RV1-RV4 courtyard-edge
exception remains (0.815 mm measured line boxes); no copper-edge exception.

JLCPCB package and reproduction commands: `../jlcpcb/README.md`. Scope and raw evidence:
`research/s3-r2/`. No firmware, supplier uploads, orders or commits were made.

## Remaining gates

Supplier DFM and bottom-side placement preview; exact part/land-pattern/rating review;
stock/attrition at the chosen order quantity; prototype power/thermal, normalling/contact
transients, MIDI jumper/inversion, actual mechanical fit and audio/CV behavior. Existing
Extended 0.5 W output resistors remain disclosed; this is not an all-Basic passive BOM.

Project consistency: repaired the inherited nil top-level sheet UUID / empty sheet list to match the actual native schematic root. Shared PCB inspection now succeeds with all ERC/DRC severity rules enabled.
