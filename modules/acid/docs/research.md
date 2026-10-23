# ACID research and circuit intent (S2/P3)

## 1. Brief (user, 2026-10-22)

- Bread Modular **MCO**, **ENV** and **SVF** as one Eurorack signal module, named **ACID**, 8HP.
- Keep Bread Modular's **3.3 V internal signal level** (vactrol response curve and feel).
- Inputs: **MIDI** (as 8bit), **AUDIO bypass** (buffered, mapped onto 0..3.3 V; clipping is
  part of the character), **CV bypass** (0..5 V mapped onto the internal envelope range; the
  range follows what the ENV DAC really gives).
- Unpatched AUDIO = the MCO square mix; unpatched CV = the envelope on the MCU DAC (the ENV
  firmware moves into the MCO firmware).
- Output loudness: the user runs the BM SVF into the BM **DRIVE** with its knob at **75 %**
  (linear pots); ACID builds that in.
- **Envelope CV out**: the DAC envelope mapped to 0..5 V, protected.
- Panel top to bottom: MIDI; MCO two knobs; ENV two knobs; envelope model selector with three
  LEDs; REC button + LED (records the envelope knob positions, as the 8bit crash firmware;
  no firmware now); AUDIO + CV bypass; SVF three knobs; audio OUT at the bottom.
- Vactrols on B as modules/low / modules/vca-mix. This stage: schematic with every net wired,
  THT parts placed, **no routing**.

### 1.1 S2 review (user, 2026-10-22)

- DAC / CV mapping as modules/low: the envelope is 0..3.3 V; CV bypass 0..5 V -> 0..3.3 V,
  ENV OUT 0..3.3 V -> 0..5 V.
- 500k pots are in stock too: RESONANCE back to BM 500k.
- **No DRIVE**; but give the outputs the gain the user got from it, on **LP, HP and BP** outs
  (BM LF / HF / BF), each with **one TL072 stage** doing the gain and the Eurorack mapping.
- Board edits by the user (P1 -> P2): DETUNE/MIX moved up (vactrol pads now under the pots:
  accepted), ENV pots + LED column + buttons as one group, ENV OUT beside the buttons (rot 90),
  bottom row LP / HP / BP OUT (two copies of OUT), J10 moved to the right edge.

## 2. Bread Modular baseline (read-only, `~/data/projects/bread-modular/modules/`)

- **MCO 1.0.1**: as modules/low research.md 2 (PB3 RX, PB4/PB5 tones, PB0 DETUNE, PA6 velocity
  DAC, PA0 UPDI; MCP6002 summer around a 1k/1k V_MID, MIX pot on tone 2).
- **ENV 1.2.1**: ATtiny1616; PA1/PA2 CV1/CV2 (attack-or-hold / release time, knobs RV2/RV3 1M
  as attenuators of buffered CV inputs pulled up to V_SUPPLY), PC0 ALGO button + PC1 LED (three
  algorithms: hold-release, attack-release, attack-sustain-release, saved in EEPROM), PC2 gate-
  mode button + PC3 LED, PB2 gate in, PA6 DAC -> MCP6002 follower -> 1k -> ENV_OUT. The firmware
  sets `VREF_DAC0REFSEL_4V34` and ramps the DAC code 0..255.
- **SVF 1.0.0**: U4A inverting summer (R1 51k in, R6/R7/R8 10k), two inverting integrators
  (VTL5C LDR + 10n), U3B damping amp (R11 51k + RESONANCE 500k rheostat, R12 51k), V_MID 1k/1k.
  Driver U5: FREQ 1M pot attenuates V_CV (pulled up to V_SUPPLY by R13 100k), U5A follower,
  R14 1k + R15/R16 1M halve it, U5B forces the paralleled LED cathodes to CV/2:
  I_LED = (CV/2) / (FREQ CURVE 50k rheostat + R17 5.1k).
- **DRIVE 1.0.0**: U1A inverting x1 (100k/100k), U1B inverting gain 51k / (GAIN 50k rheostat
  + 1k), OD1/OD2 = two series SS14 + 500k rheostat per polarity in the feedback, CLEAN out
  via 1k, DIRTY out via antiparallel diodes + 1k. RV09 pin 1 open, wiper to U1A, pin 3 to R3:
  CW lowers the resistance (modules/8bit geometry note: CW turns the wiper toward pin 3).

## 3. Circuit (S2, `tools/build_schematic.py`)

| Block | Parts | Notes |
| --- | --- | --- |
| Power | J10, D1/D2 B5819W, C1/C2, U1 HT7533-1, C3-C5 | As modules/low. +3V3 load ~30 mA (MCU, 4 x MCP6002, 4 LEDs) -> ~0.25 W in the SOT-89 |
| MIDI | J1, R1-R3, D3, Q1, JP1 | modules/low front end (JP1 1-2 protected / 2-3 direct) |
| MCU | U2 ATtiny1616, C6, R4, J11 UPDI | One MCU for MCO + ENV (3.2) |
| MCO | RV1 DETUNE, RV2 MIX, R5-R11, U3A, C7 | Bread Modular MCO values |
| ENV UI | RV3 ATTACK, RV4 RELEASE (50k), SW1 MODE, SW2 REC, D4-D7 + R13-R16 330R | BM ENV PA1/PA2/PC0-PC3 map; knobs are plain dividers (no CV inputs), as the MCO DETUNE pot |
| Envelope | R12 1k (DAC -> ENV_CV) | SVF CV normal and CV OUT source |
| AUDIO bypass | J2, R17, C8, R18, R19, U3B, R20 | As modules/low: AC coupled, x-0.33 around V_MID, clips at the rails |
| CV bypass | J3, R21 47k, R22 100k, D8 BAT54SW, R23 | 5.0 V -> 3.30 V (100k \|\| FREQ 1M = 90.9k), clamp; input 147k (as modules/low S3) |
| Normals | U4 TS5A23157, C9 | As modules/low 3.1 (jack TN = detector, 1M pull-ups) |
| SVF | R24 51k, R25 22k, U5, U6, U7/U8 VTL5C, C10/C11 10n, R26-R28 10k, RV5 RES 500k, R32/R33 51k, R30/R31, C12/C13 | BM SVF 1.0.0 values; LP / HP / BP out via the BM 1k resistors R29 / R38 / R39 |
| SVF driver | RV6 FREQ 1M, U9, R34 1k, R35/R36 1M, RV7 CURVE 50k, R37 5.1k, C14 | BM SVF; R13 pull-up omitted: U4 always drives SVF_CV |
| LP / HP / BP out | C15-C17 1u, R40/R45/R50 100k, U10A / U10B / U11A TL072 x22.3 (100k / 4.7k), 1k 0.5 W series + 1k shunt each (R43/R44, R48/R49, R53/R54), J4 / J6 / J7 | 3.4 |
| CV out | U11B x1.51 (R55 51k / R56 100k), R57 1k 0.5 W, J5 | 3.2, 3.3 |
| Supplies | C18-C21 100n | U10 / U11 +/-12 V decoupling |

Firmware pin map (one ATtiny1616, for the later MCO+ENV firmware):

| Pin | Use | Origin |
| --- | --- | --- |
| PB3 | MIDI RX | MCO/ENV |
| PB4, PB5 | tone 1, tone 2 (TCB0/TCB1 ISR toggles) | MCO |
| PB0 | DETUNE knob | MCO |
| PA6 | DAC: envelope (was MCO velocity) | MCO/ENV |
| PA1, PA2 | ATTACK (hold in HR) / RELEASE knobs | ENV CV1/CV2 |
| PC0 | MODE button (envelope model), pull-up | ENV algo button |
| PC1, PA4, PA5 | mode LEDs HR / AR / ASR | ENV algo LED + 2 new |
| PC2 | REC button, pull-up | ENV gate-mode button |
| PC3 | REC LED | ENV gate-mode LED |
| PA0 | UPDI | |
| PA3, PA7, PB1, PB2 | unused (no-connect) | PA7 MCO gate, PB2 ENV gate in / MCO TX |

### 3.2 Envelope range (DAC at 3.3 V), as modules/low

BM ENV and MCO select the 4.34 V DAC reference with a 3.3 V supply; the output cannot exceed
VDD, so codes above ~194 (3.3 / 4.34 x 256) sit at the rail. ACID follows modules/low and treats
the envelope as **0..3.3 V** (firmware: scale the envelope to codes 0..194 so the top is not
flat; not written yet):
- CV bypass: R21 47k / (R22 100k || RV6 1M) maps 5.0 V to 3.30 V, the same vactrol range as the
  internal envelope; D8 clamps above ~3.6 V. 47k / 100k are the modules/low S3 values.
- ENV OUT: U11B x(1 + 51k / 100k) = x1.51 maps 3.30 V to 4.98 V.

### 3.3 CV output protection

U11B is DC coupled on +/-12 V; R57 1k 0.5 W (1206) limits the current into any mis-patch to
~12 mA (TL072 outputs are short-circuit protected), as the modules/low audio output.

### 3.4 Output gain (no DRIVE), simulation

The BM SVF passes its input at 10k / 51k = 0.2, so an MCO mix gives only ~0.6 Vpp at LP with no
resonance. The user's SVF -> DRIVE at 75 % added x3.9 (51k / (12.5k + 1k)) with clipping at the
DRIVE's 3.3 V rails, then the x3 output stage: **x11.7 overall with a ~10 Vpp ceiling**.

ACID does that in one TL072 stage per output: AC coupled (1u / 100k, 1.6 Hz), non-inverting
**x22.3** (100k / 4.7k), clipping at the TL072 rails (~+/-10 V into 2k on the +/-11.6 V filtered
rails), then a **1k series + 1k shunt** halves it: **x11.1 small signal, ~10 Vpp ceiling**,
500R output impedance. Without the ceiling a resonant SVF (up to 3.3 Vpp) would drive x11 into
~37 Vpp and clip at ~21 Vpp. The clipping is hard (op-amp rail), like the DRIVE's MCP6002 rails.

`tools/sim_level.py` (`research/s2/sim.txt`), OUT Vpp LP / BP / HP, two MCO tones, MIX full:

| LDR R (fc) | RES 0 | RES 100k | RES 250k | RES 500k |
| --- | --- | --- | --- | --- |
| 100k (159 Hz) | 7.3 / 6.6 / 9.6 | 10.3 (all) | 10.3 | 10.3 |
| 10k (1.6 kHz) | 7.0 / 4.2 / 6.6 | 9.9 / 6.9 / 7.5 | 10.3 / 8.0 / 7.8 | 10.3 / 8.4 / 7.8 |
| 3k (5.3 kHz) | 6.7 / 3.5 / 6.3 | 9.7 / 6.5 / 7.8 | 10.3 / 8.3 / 9.0 | 10.3 / 9.4 / 9.7 |

One tone: 3.3..8 Vpp; a 10 Vpp square on AUDIO: 8..10.3 Vpp. The modules/low x3 stage would give
only 0.9..5 Vpp here (9.5 Vpp only at high resonance). The LDR curve of the Chinese VTL5C parts is
not modelled (cutoff swept directly). TL072 offset x22 is at most ~0.1 V at the jack (DC gain not
rolled off; acceptable for audio).

### 3.5 Choices made for the user to review

- **ENV knobs 50k** plain dividers (BM ENV used 1M attenuators of its CV inputs, which ACID does
  not have); the BM ENV gate input, CV inputs and envelope LED are not built.
- **Output order** left to right LP / HP / BP (the user's "LF/HF/BF").
- **JLCPCB fields** (re-checked live 2026-10-22, `build_schematic.py` SOURCING): the 1k 1206
  output/CV-out series resistors (R57 and the LP/HP/BP 1k) are now ROHM ESR18EZPF1001 (C2074262,
  0.5 W, Extended: no Basic 0.5 W 1206 1k exists); modules/low's C4410 is a 250 mW part. R37 5.1k
  0603 got UNI-ROYAL 0603WAF5101T5E (C23186). Stock is a dated observation, not a guarantee.

## 4. Placement (P3, `docs/geometry.json`)

8HP, 40.3 x 128.5 mm panel, 39.3 x 110 mm carrier, 2 layers. P2 = the user's board edits, read
back from the board into geometry.json; the rebuilt board matches all 92 THT pads exactly.
F (panel Y): J1 MIDI (17.5); DETUNE / MIX (30.5); ATTACK / RELEASE (46.5) with the ASR / AR / HR
LED column between them (X20.3, Y48.5 / 53.2 / 57.9); REC LED (9.2, 58.2) over the REC button
(9.35, 64.35), MODE button (20.1, 64.4) under the LED column, ENV OUT J5 (31.5, 63.9, rot 90);
AUDIO, FREQ, CV (76.5); RES / CURVE (~91.3); LP / HP / BP OUT J4 / J6 / J7 (~110.1).
B: vactrols U8 / U7 in the top corners (now partly under DETUNE / MIX: user-accepted), J11 UPDI
at the right edge by J1, J10 power vertical at the right edge (pin 1 -12 V at the bottom,
Y98.46). SMD parked off the right edge.

P3 (user OK 2026-10-22: "J10 change as needed", "J5 change as needed", "align as needed"):
- J10 1.25 mm left (columns X34.41 / 36.95): even pads 2.0 mm, courtyard 1.03 mm from the right
  edge; the IDC16 socket envelope now ends at X39.48, inside the 40.3 mm panel.
- CURVE RV7 1.27 mm left (shaft X26.2): its right lug sat in the moved J10 courtyard (mask
  bridge + clearance). RES / CURVE are now 0.86 mm left of the panel centre line.
- J5 ENV OUT 0.625 mm left (X30.9, still rot 90): courtyard 1.06 mm, S pad 1.37 mm from the edge.
  Rot 270 was rejected: its S pad would land on the MODE button pad. MODE SW1 0.4 mm left
  (X19.7) so the J5 and SW1 courtyards no longer overlap.
- Aligned: LP / HP / BP on the AUDIO / FREQ / CV columns (X7.5 / 20.15 / 32.8) at Y110.1;
  DETUNE / MIX Y30.45; RES / CURVE Y91.3; REC button Y64.4; labels follow.

Checks (P3): shared gate ERC 0, parity 0, 240 unconnected (nothing routed), **DRC 0 active**,
8 user-approved exclusions (2026-10-22): 4 x pth_inside_courtyard + 4 x silk_over_copper, U7 / U8
LDR pads under RV2 / RV1 (the modules/low U5 pattern), written only by
`tools/vactrol_exclusions.py`, which refuses any other finding. Closest courtyards to the edge:
J10 1.03, J5 1.06, J4/J6/J7 1.31 mm. Panel DRC 0.

## 5. R1 routing (2026-10-22/23, done)

User direction: space is tight, so the vactrol spots may be used for components; go to 4 layers
and see whether the board routes. Manual divide and conquer (root AGENTS.md), straight on
`hardware/acid.kicad_pcb`, board backed up to `/tmp/acid.kicad_pcb.r1-*` before every batch;
batch scripts, path helper, checks and DRC reports in the ignored `research/r1/`.

- **4 layers** (modules/32bit stack-up): F signal + GND pour, In1 solid GND, In2 +3V3 plane,
  B signal + GND pour. Pours: 0.25 clearance, 0.2 min width, thermal 0.25 / 0.4. Power class
  0.4 mm (GND, +3V3, +/-12 V).
- **Space audit** (`research/r1/spots.py`): with every SMD pad 2 mm from the pot/jack pads, the
  back side has legal SOIC-8 spots only in the two top corners, between the pot rows at the
  centre (one IC) and between the bottom jacks (U10, U11). With the vactrols in the top corners
  the six top-half ICs (U1, U2, U3, U5, U6, U9) had one slot.
- **Vactrols moved (user-approved 2026-10-22, "The vactrols placements is fine")**: U8 / U7 now lie under ATTACK / RELEASE (RV3 / RV4),
  between the lug row (Y46.5) and the pin row (Y54.0), LED ends (pads 1, 2) toward the centre
  (X16.5 / X23.8), LDR ends toward the board edges (X3.8 / X36.5); pads 0.3 mm from the pot
  lugs/pins. Their old DETUNE / MIX stacking exclusions no longer match (dropped by KiCad). The
  new stacking gives **22 DRC findings** (18 pth_inside_courtyard, 4 vactrol outline over the
  RV3 / RV4 lugs), now written as exclusions by `tools/vactrol_exclusions.py` (refuses any other
  finding); the +/- and SOLDER FIRST / TRIM FLUSH texts were moved off the pads.
- **Routed** (DRC clean apart from the items above and stub vias for links not drawn yet):
  - Outputs: U10 (LP + HP) and U11 (BP + CV out gain) between the bottom jacks, feedback pairs
    in the gaps under J4 / J6 / J7 (between T and TN), 1206 output pairs on the edge strips
    (R43 / R44 / R49 left, R53 / R54 right), R48 beside RES / CURVE, R57 by ENV OUT.
  - Power entry: D1 / C1 above J10, D2 / C2 below it; +12V_F on F (X33 past J10, lane Y107.25),
    -12V_F on F (over J7.T, lane Y109.3 between the jack T / TN pads), decoupling at each pin.
  - Bypass / normals: U4 above FREQ (rot 180) with +3V3, GND and AIN_BUF vias under its body,
    SVF_CV down the pocket under FREQ, R23 in that pocket, AUDIO parts (R17, C8, R20) on the
    left edge, CV divider (R21, R22) on the right edge, D8 beside U4.
- **Top half** (batches 11-26): U1 (LDO) + U2 (MCU) side by side in the centre slot between
  the pot rows with C3-C6, J11 (UPDI) + R4 top right, LED resistors R13-R16 in the LED column,
  U5 + U9 top left, U3 + U6 top right, MIDI front end beside J1, VAC_POS / VAC_NEG from U9 down
  to the vactrols, the MCU fan-out (west fan on B, east fan hopping to F next to the MCU).
- **Long links** (14: RX, UPDI, SVF_BPO / LPO / RQ / BP, VAC_NEG, MCO_OUT, AIN_BUF, ENV_CV x2,
  AIN_AC, FREQ_W, CURVE_R): my first batch-28 diagonals walled off the middle, so they were
  ripped up (back to the pre-b28 board) and re-routed one connection at a time with the path
  helper, trying orders and single/double rip-ups on dry copies (`plan_long.py`, `fix.py`);
  only complete sets kept. Chosen set: 59 vias for the 14 links (FREQ_W 7 vias / 125 mm and
  CURVE_R 3 vias, both DC pot lines; AIN_AC 9). No via in or touching an SMD pad.
- **Batch 30 (GND repairs after the long links)**: the links cut the B pour pieces that tied
  R37.1 and R36.1 / C14.2 to GND (pcbnew: 66 of 69 GND pads in the main cluster) -> a GND via in
  R36's piece (16.6, 19.73) and a B dogbone from R37.1 to a via at (2.9, 41.9); SW1.2 had only
  one F thermal spoke left -> short F + B track to a GND via at (22.2, 63.8).

Checks after batch 30: KiCad DRC **0 active / 22 excluded (the approved vactrol stacking) / 0
unconnected / 0 parity**; shared gate ERC 0, DRC 22 (it counts exclusions, as on LOW), 0
unconnected, parity 0. 168 vias, none in or touching an SMD pad; no tracks on In1; In1 GND and
In2 +3V3 one piece each; courtyards >= 1.0 mm from the edge (J10 1.00, J11 1.02, R43 1.02);
closest SMD pad to a pot/jack pad 2.08 mm (R7-J1.S). 138 free off-grid track vertices, all from
batches before the long links (45-degree jogs off off-grid SMD pads); the long links added none.

### 5.1 Silk labels and JLCPCB export (2026-10-23, user request)

B silk, 0.8 mm / 0.15 mm stroke, mirrored, as modules/low and 32bit: `GND UPDI` under J11
(X135.8 Y64.4; GND under pad 2, UPDI under the square pad 1), `D` beside JP1 pad 3 (MIDI_IN,
direct, X117.4 Y62.7), `P` below JP1 pad 1 (RX_Q, protected, X115.6 Y66.85) and the legend
`JP1 D=DIRECT P=PROT` in the free strip above JP1 (X111.5 Y60.75). Board version text
`ACID P3` -> `ACID R1`. Silk only, no copper or placement change; DRC 0 active / 22 excluded /
0 unconnected / parity 0 with the silk checks on. Export: `jlcpcb/README.md`.

## 6. Not done

A cleanup pass (fewer vias on the long links, off-grid jogs), firmware (MCO + ENV
merge, REC knob recording, PORT_INVEN for the protected MIDI path), panel fit / 3D check, bench
(DAC range, vactrol range, output level).
