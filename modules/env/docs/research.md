# ENV research and circuit intent (S4/P7/R1, exported)

## 1. Brief (user, 2026-10-28)

- An ENV module that works with MIDI, taken out of ACID (its MCU + ENV knobs / MODE + LEDs /
  REC + LED / ENV OUT block) into its own module. Schematic + THT layout; recording feature
  and envelope mode selection included.
- **ACID is not changed** in this stage: it is routed and exported, and its SVF CV normal
  uses the envelope. Removing the envelope from ACID (an MCO + SVF ACID) would rip up routed
  copper and needs a re-export: that is the user's call (root AGENTS.md "stop and ask").
- Round 2 (user, 2026-10-28): ENV OUT to the bottom with the ENV LED left of it, power header
  turned, two daisy-chained MIDI jacks (IN, OUT; wire connections only) at the top, more room
  for the ATTACK / RELEASE knobs.
- Round 4 (user, 2026-10-28): MODE button into the mode-LED row, both buttons on the left; J3
  vertical, right of ENV OUT; ENV LED next to the pots; the freed space goes to the pots.
- Round 5 (user, 2026-10-28): RV1 a bit down; J3 just right of the REC row; ENV OUT to the
  centre.
- Round 6 (user, 2026-10-28): ENV LED next to ENV OUT (J2 may move a bit); J4 UPDI to the
  bottom, a corner or a side; review the overall layout ("something is still missing").
- Round 7 (user, 2026-10-28): add GATE IN. GATE IN + MIDI IN in one row at the top, ENV OUT +
  MIDI OUT at the bottom; a patched GATE IN bypasses MIDI.
- Round 8 (user, 2026-10-28): start routing (R1, section 4).

## 2. Circuit (S4, `tools/build_schematic.py`)

Inherited ACID research.md 2-3 values, except S4: U1 HT7550-1 / +5V and R5-R8 1k
(user-approved conversion, section 6). The ACID references are in brackets.

| Block | Parts | Notes |
| --- | --- | --- |
| Power | J3, D1/D2 B5819W, C1/C2, U1 HT7550-1, C3-C5 | +5V as our 8bit; estimated 20 mA budget, ~0.13 W LDO loss at 11.6 V input |
| MIDI | J1, R1-R3, D3, Q1, JP1 | ACID / modules/low front end (JP1 1-2 protected / 2-3 direct) |
| MIDI OUT | J5 | Passive thru: tip on MIDI_IN, sleeve GND, in parallel with J1 (no buffer). The downstream module sees the upstream sender plus R1 100k / R2 10k loading |
| GATE IN (S3) | J6, R14-R19, D9, Q2 | MIDI front end again: R14 100k tip pull-down, R15 100k / R16 51k base divider (threshold ~1.9 V, 0.11 mA at +/-12 V), D9 B-E clamp, Q2 inverts to PB2 (R17 22k pull-up). Jack detect as ACID: TN -> R18 51k -> PB1 GATE_SENSE with R19 1M to +5V. Unpatched TN touches the tip: ~0.50 V (low); patched TN opens: 5 V (high). R18 keeps the PB1 clamp current at 0.24 mA when a +/-12 V plug touches TN during insertion |
| MCU | U2 ATtiny1616, C6, R4, J4 UPDI | ACID U2 pin map minus the MCO pins |
| ENV UI | RV1 ATTACK, RV2 RELEASE (50k), SW1 MODE, SW2 REC, D4-D7 + R5-R8 1k | ACID UI; S4 indicators ~3 mA at 5 V with ~2 V red LEDs |
| Envelope | R9 1k (DAC -> ENV_CV) | ACID R12 |
| ENV OUT | U3A TL072 x1.51 (R10 51k / R11 100k), R12 1k 0.5 W 1206, J2 | ACID U11B, R55-R57, J5: 3.30 V -> 4.98 V |
| ENV LED | R13 1k, D8 from U3A out (before R12) | New: ~3 mA at 5 V, lights above ~1.8 V; a patched load does not dim it |
| Spare | U3B grounded follower | TL072 half unused |
| Supplies | C7 / C8 100n | U3 +/-12 V decoupling |

Firmware pin map (ACID's ENV pins):

| Pin | Use |
| --- | --- |
| PB3 | MIDI RX (PORT_INVEN when JP1 = protected) |
| PB2 | GATE IN (inverted by Q2: PORT_INVEN; gate high = envelope on) |
| PB1 | GATE_SENSE (no pull-up): high = GATE IN patched -> the gate drives the envelope and MIDI notes are ignored (bypassed); low = MIDI notes drive it |
| PA6 | DAC envelope (scale to codes 0..194 with the 4.34 V reference setting at a 5 V supply; section 6) |
| PA1, PA2 | ATTACK (hold in HR) / RELEASE knobs |
| PC0 | MODE button (pull-up): HR -> AR -> ASR, saved in EEPROM |
| PC1, PA4, PA5 | mode LEDs HR / AR / ASR |
| PC2 | REC button (pull-up): record the knob positions |
| PC3 | REC LED |
| PA0 | UPDI |
| PA3, PA7, PB0, PB4, PB5 | unused (no-connect) |

Sourcing: inherited ACID rows plus our 8bit HT7550-1 C16106; R5-R8 now use the existing
1k 0603 C21190 row. Current export/catalog status: `jlcpcb/README.md`.

## 3. Placement (P7, `docs/geometry.json`)

6HP (user, 2026-10-28; P1/P2 were 4HP), 30.0 x 128.5 mm panel, 29.0 x 110 mm carrier (as
modules/hats and modules/low), rail holes X12.58. Inputs over outputs in two jack columns X7 /
X23 (16 mm pitch): top row J6 GATE IN (7, 17) + J1 MIDI IN (23, 17); bottom row J2 ENV OUT
(7, 110) + J5 MIDI OUT (23, 110), with D8 ENV LED (14.5, 110) between them, next to ENV OUT (the
16 mm pitch is what lets the LED fit between the jack courtyards). RV1 ATTACK shaft (15, 36.5);
RV2 RELEASE (15, 66.5), 30 mm pitch; SW1 MODE (6.5, 84) with D4 / D5 / D6 HR / AR / ASR at
X14.5 / 20 / 25.5 in the same row; SW2 REC (6.5, 96) with D7 REC LED (14.5, 96) right of it.
B: J3 power moved off the REC row (P5/P6) because a 10- or 16-pin socket there would cover the
MIDI OUT pads: it now stands vertical on the right edge between the pots (rot 180, odd pins
X23.8, even X26.34, pin 1/2 -12 V at the bottom Y56.58, 9/10 +12 V at Y46.42); a 16-pin socket
overhangs upwards to Y35.0 over the free right strip (envelope X >= 21.27, clear of the RV1
lug pads at X <= 21.16 and of every other B-side pad). J4 UPDI vertical on the left edge between
the pots (3.5, 51.5; pin 1 UPDI on top). SMD parked off the right edge (placed during routing, section 4).

Checks (P7): ERC 0; KiCad DRC 0, 107 unconnected (nothing routed), parity 0; shared gate ERC 0,
DRC 107 (the unconnected items). Closest courtyards to the edge: J4 1.16, SW1 / SW2 1.18, J3
1.31, J2 / J5 1.38 mm; no courtyard overlaps; no pad under the IDC16 envelope. Panel DRC 0.

## 4. Routing (R1, 2026-10-28)

Manual divide-and-conquer straight on `hardware/env.kicad_pcb` (root AGENTS.md), 2 layers, GND
pours on F and B; Power class 0.4 mm, signals 0.25 mm (0.2 mm at the U2 pins). Native check after
every batch (`research/r1-b1` .. `r1-b12`); batch scripts in `research/route/`. All SMD on B:

1. Power by J3: D1 / C1 / C3 / U1 / C4 / C5 left of J3, D2 / C2 below it.
2. Output stage in the right strip below J3: U3 (rot 90) with C7 / C8, R10 / R11 below it, R13 /
   R12 above the LED row. +12V_F hops on F (X122.2), -12V_F runs on B left of U3.
3. +3V3 to the pots (RV1 on F, RV2 on B); ENV OUT (F, X111.5 lane) and ENV LED (F, between D5 and
   D6, then X119) down to the bottom row.
4. U2 between the pots (rot 270), C6 above it, R4 by J4, R9 below: UPDI, ENV_A (B), ENV_R (F,
   left of U2, under RV2), DAC -> R9 -> ENV_CV (F) -> via under U3.
5. LED resistors by their LEDs (R5 / R6 above the LED row, R7 below D6, R8 right of D7). LED_AR /
   LED_ASR go down the RV2 pin gaps (B), LED_REC / REC_SW / LED_HR down the left lane (B); MODE_SW
   and REC_SW reach the buttons on F; each button's two pin-1 pads are linked on F.
6. MIDI and GATE front ends between the top jacks (B), +3V3 up from RV1.3 between its lugs.
   MIDI_IN thru on F along the right edge (X128.1) to J5.
7. RX / GATE / GATE_SENSE: fan-out vias under U2, F runs past RV1's left lug to vias by JP1 /
   R17 / R19.
8. to 12. +12V_F via moved off the MIDI lane; D3 0.15 mm down (R2 courtyard); GND stitching vias;
   board label ENV R1.

A one-connection path finder (`research/route/path1.py`, A* on a 0.05 mm grid) proposed a few
single paths (ENV_CV, ENV_R, GATE_TN and the three MCU runs). Each path was reviewed and written as
its own connection. No autorouter was used.

Process note: until batch 11 the scripts loaded the board from a `/tmp` copy. pcbnew then had no
project and saved default settings over `env.kicad_pro` (copper edge 0.5 mm, no Power class, ERC
map dropped), so the batch 1-10 checks ran with those defaults. The project file was restored from
the pre-routing backup. Saves now go through a scratch copy, refill natively (`kicad-cli pcb drc
--refill-zones --save-board`) and copy back only the `.kicad_pcb`. The result below uses the
restored project.

Result (`research/r1-b12`): ERC 0; KiCad DRC 0 (warnings included, no ignored checks or
exclusions), 0 unconnected, parity 0. 188 tracks, 26 vias, none in or at an SMD pad. Copper >= 1.0
mm from the edge; courtyards >= 1.02 mm (C7, R10, R13). SMD to pot / jack pads >= 2.10 mm
(D3-J1.TN), then D1-RV1.3 2.21 and R17-J6.S 2.25 mm. Pours: one main piece per layer, plus one F
piece between the F runs and four small B pieces (under RV2, around U3), tied by THT GND pads and
stitching vias. Free track vertices on the 0.05 mm grid except one on J1's tip-pad row (Y62.08).
D1, U1 and C5 courtyards reach up to 0.7 mm into the IDC16 socket outline next to J3; they are
<= 1.8 mm tall, under the header's 2.5 mm spacer.

### 4.1 Pad-clearance cleanup (batches 13-17, user request)

Tracks were moved off the hand-soldered pads and out of the gaps between pot pins
(`research/route/clear.py` measures track/via copper to every THT pad of another net):

- 13. RV1: GATE / RX (F) cross between the lugs and drop left of pin 1; GATE_SENSE (F) passes left
  of the left lug; ENV_A (B) lands on the wiper from below; +3V3 (B) at X117.0 off the right lug;
  GATE_TN (B) leaves J6.TN to the left of J6.S.
- 14. RV2 F: ENV_R comes down left of the left lug (X107.6) and lands on the wiper from above;
  MODE_SW via + F run moved left (X105.7); ENV_CV passes under the right lug; +3V3 (F) lands on
  RV1.3 from below.
- 15. RV2 B: LED_AR / LED_ASR no longer run between the RV2 pins: down between the lugs, out
  below the left lug, left of pin 1, then right under the pin row (Y126.1 / 126.6, LED_HR 127.1);
  +3V3 (B) to RV2.3 at X117.0.
- 16. LED_REC / REC_SW (B) run down the middle of the SW1 body instead of past its left pads;
  REC_SW via moved into the SW2 gap.
- 17. +12V_F (F) at X121.6 off the J3 pin column; +12V (B) straight from J3.9 to D1; MIDI_IN (F)
  at X128.35 (on the 1 mm edge line); one duplicated +12V_F segment removed.

Result (`research/r1-b17`): ERC 0; KiCad DRC 0 / unconnected 0 / parity 0; 217 tracks, 26 vias,
none in or at an SMD pad; no track between pot pins; every track >= 1.03 mm from pot, jack and J3
pads (GATE_TN-J6.S closest). Still under 1 mm, limited by part spacing: tracks through the LED
row gaps (ENV_LED_A 0.45, LED_ASR 0.48, MIDI_IN-D6 0.56 mm) and ENV_OUT between the button and
LED columns (0.63 mm). Pours merged to one main piece per layer plus one B piece under RV2 (GND
via) and one around U3; the J3 inter-pin fragments are tied by the GND pins. Two free vertices sit
on pad rows (J6.TN Y70.38, J1.T Y62.08).

## 5. Silk labels and JLCPCB export (2026-10-28, user request)

B silk, 0.8 mm / 0.15 mm stroke, mirrored, as ACID 5.1: `P` under JP1 pad 1 (RX_Q, protected,
X115.3 Y80.3), `D` under pad 3 (MIDI_IN, direct, X117.9 Y80.3) and the legend
`JP1 D=DIRECT P=PROT` below them (X116.6 Y82.5); `UPDI` above J4 pin 1 (X103.5 Y97.8) and `GND`
below pin 2 (X103.3 Y105.3). Placed by a free-space scan against B pads (+0.2 mm) and B silk.
Silk only (text inserted into the board file, no pcbnew save), board backed up to
`/tmp/env-r1-pre-silk.kicad_pcb`. Native DRC with all severities: 0 / 0 unconnected / parity 0;
a zone refill on a scratch copy is byte-identical. Export: `jlcpcb/README.md` (bottom Economic,
36 parts / 19 rows; Extended: R12 ESR18 and the ATtiny1616).

## 6. S4: 5 V supply and 1k indicator resistors (user-approved)

The user requested our working `modules/8bit` supply/reference arrangement and the 1k LED
change, followed by a fresh Gerber export. This changes ENV only; ACID, 8bit and Bread Modular
sources are untouched.

- U1: **HT7533-1 C14289 -> HT7550-1 C16106**, same SOT-89-3 footprint and pin mapping:
  1 GND, 2/tab +12V_F, 3 +5V. Rename the entire former +3V3 net to +5V, including the
  project Power net-class assignment, supply symbols, MCU, pots and MIDI/gate pull-ups.
- R5-R8: **330R C23138 -> 1k C21190 / 0603WAF1001T5E**, same 0603 land patterns.
  Approximate indicator current is (5 - 2) / 1000 = 3 mA. Even with a shorted LED and
  5.5 V supply, the 1% resistor dissipates <31 mW versus its 100 mW catalog rating.
- **No footprint, pad, track, via, silk, model, board edge or panel geometry changed.**
  R1 routing remains 217 segments / 26 vias. R9-R13, including the separate ENV LED's
  existing 1k R13, are unchanged. The PCB title block now correctly identifies S4/R1
  instead of claiming the routed board is an unrouted P7 placement.

### Reference, output and firmware contract

Microchip DS40002204A Table 36-22 requires VDD >=4.75 V for INT43V; Table 36-29 applies that
requirement to the DAC. Our 8bit uses HT7550-1 and `VREF_DAC0REFSEL_4V34_gc`; S4 adopts that
supply/reference combination rather than relying on Bread Modular's undocumented behavior
with the same reference selection at 3.3 V. [source](https://ww1.microchip.com/downloads/en/DeviceDoc/ATtiny1614-16-17-DataSheet-DS40002204A.pdf)

Keep U3A gain = 1 + 51k/100k = 1.51 and scale the envelope to **DAC codes 0..194**. At a
4.34 V assumed reference, code 194 gives 3.289 V DAC and 4.966 V before R12/loading; using
4.3 V gives 4.921 V. These are nominal calculations, not a precision 5 V guarantee.
Full 0..255 codes would instead give approximately 6.5 V with this amplifier, so do **not**
copy 8bit's DAC sample range or bipolar output circuit. The future firmware should scale
0..255 envelope values to 0..194 (not simply saturate at 194), use **VDD as the knob ADC
reference**, and preserve the PB1/PB2 gate-detect/inversion behavior. No ENV firmware exists
or was written in this hardware task.

### Interfaces and electrical checks

- **MIDI:** Q1/R3 translate the protected input to the new MCU rail; 3.3 V senders must use
  JP1 P (1-2, PB3 inversion enabled). Direct mode is unprotected **5 V logic only**: the MCU
  input-high specification is 0.7 x VDD, so 3.3 V is not guaranteed high at a 5 V target.
  J5 is still a passive thru, not a new 5 V output driver. [source](https://ww1.microchip.com/downloads/en/DeviceDoc/ATtiny1614-16-17-DataSheet-DS40002204A.pdf)
- **GATE:** no resistor/topology change. Q2 collector pull-up now draws approximately
  5/22k = 0.23 mA. The ~1.9 V base-divider figure is an onset estimate; actual switching
  threshold/hysteresis must be measured. The nominal unpatched PB1 voltage is
  5 x (51k + (100k || 151k)) / (1M + 51k + (100k || 151k)) = 0.50 V, below the 1.5 V
  input-low limit at 5 V; patched TN open tends to 5 V. Leakage, insertion transients and
  clamp behavior remain bench checks, not guaranteed by ERC.
- **UPDI/pots/buttons:** J4 remains UPDI/GND only, with the module powered externally;
  use a 5 V-compatible programmer. Pots span the same VDD used as the ADC reference;
  buttons still switch to GND using internal pull-ups.
- **Supply/capacitors:** HT7550-1 is pin-compatible; its specified 25 C output at 7 V in /
  10 mA is 4.85..5.15 V. C4 (25 V), C5 (6.3 V), C6 (50 V) remain above the nominal 5 V rail;
  this does not establish effective MLCC capacitance or transient margin. Holtek warns
  about fast-input-rise overshoot; verify startup, load changes, rail staying above
  4.75 V while using INT43V and below MCU/capacitor limits, and LDO temperature on a prototype.
  No new universal rail/current guarantee is claimed. [source](https://www.holtek.com/webapi/116711/HT75xx-1v281.pdf) [source](https://www.holtek.com/webapi/116745/an0553en.pdf)

### Implementation and checks

A private candidate was edited using the shared native block tokenizer because the common
PCB/schematic edit APIs do not expose value/field/net-name edits. The schematic generator's
`circuit()` and sourcing rows were updated, but **neither the schematic wire router nor
`build_layout.py` was run**. Native schematic geometry/UUIDs and all PCB geometry/model paths
were retained; only approved fields, the rail name and presentation notes changed. A native
save/refill on a scratch copy reproduced all 13 saved fill polygons; native schematic
save/reload preserved the netlist. Full candidate ERC/DRC, exact ref/pin/net/NC delta, and
all generator/native field checks passed. Project rules/exclusions were not weakened.

Raw evidence is in ignored `research/5v-conversion/`; it includes the baseline, scoped edit
record, native before/candidate/final checks, geometry/field comparison, schematic render,
refill proof and catalog evidence. Shipping files and remaining release gates are in
`jlcpcb/README.md`. The earlier ignored `research/fab-review/REVIEW.md` describes the S3
snapshot and is historical, not the current S4 verdict.

## 7. Not done

FreeCAD printed panel, firmware (MIDI / GATE IN gate with the PB1 bypass, three models, REC),
supplier preview / order gates, bench.
