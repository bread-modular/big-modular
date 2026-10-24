# HATS research and circuit intent (S2/P2)

## 1. Brief (user, 2026-10-23)

- Recreate Bread Modular **NOISE** + **HIHAT** as one module, **HATS**; the **blue noise** feeds the hi-hat.
- Knobs: NOISE TONE and BLUE TONE (noise), CUTOFF and DECAY (hi-hat). An LED for the CV.
- Panel top to bottom (6HP): MIDI In + Noise In; Noise Tone + Blue Tone; Cutoff + Decay; LED;
  Audio Out + HiHat CV Out. This stage: schematic with nets connected, THT placed, **no routing**.

## 2. Bread Modular baseline (read-only, `~/data/projects/bread-modular/modules/{noise,hihat}`)

- **NOISE 1.0.1**: ATtiny1616, PA6 DAC = LFSR white noise via 1k; PA7 TONE pot (sample delay, + MIDI
  CC74); U2A white follower, C2 100p + RV2 1M rheostat + 330R to V_MID = blue high-pass, U2B
  follower, 1k out. Pink section (U3, RV3) not built here.
- **HIHAT 1.0.0**: ATtiny1616, PA5 gate, PA7 open hat (note > 60), PA6 velocity DAC. Noise in via
  100p / 100k into U2A (200k + bridged-T 1n / 1n / 1k + CUTOFF 50k to V_MID); VTL5C LDR + 2 x 330R
  VCA, U2B x3.2, 1k out. Trigger: gate -> 10n / 100k -> U3A comparator -> SS8050 passes the U3B
  accent level (velocity DAC + 1M from V_SUPPLY) -> SS14 -> 4.7u; 22k decay, SS8550 adds 330R +
  DECAY 50k for closed hats; SS8050 follower -> U4A x2 = vactrol LED (330R) and CV out.

## 3. Circuit (S2, `tools/build_schematic.py`)

**Two ATtiny1616: yes.** The tinyAVR has a single DAC and both firmwares need it (NOISE outputs
noise samples on it, HIHAT outputs velocity); NOISE also runs a tight busy-wait sample loop. Two MCUs
keep both Bread Modular firmwares unchanged; they share one RX net and get separate UPDI headers
(J11 NOISE / U2, J12 HIHAT / U3).

| Block | Parts | Notes |
| --- | --- | --- |
| Power | J10, D1/D2, C1-C5, U1 HT7533-1 | As modules/low; ~35 mA on +3V3 (~0.3 W in U1) |
| MIDI | J1, R1-R3, D3, Q1, JP1 | modules/low front end; RX to both MCUs. JP1 1-2 protected needs PORT_INVEN in both firmwares; 2-3 direct runs stock BM firmware |
| Noise MCU | U2, C6, R4, J11 | BM NOISE pin map |
| Noise | R6, RV1 NOISE TONE 50k, U4, C8 100p, RV2 BLUE TONE 1M, R7 330, R8 1k, R9/R10 VMID_N | BM NOISE, no pink |
| NOISE IN | J2, R11, C10, R12, R13 33k, R14 1M, U9B | modules/low AUDIO bypass: x-0.33 around VMID_H |
| Normal | U5 TS5A23157 (ch 2 unused, IN2 low), C11 | Jack empty -> internal BLUE_NOISE, patched -> NIN_BUF (modules/low 3.1) |
| Filter + VCA | C12, R15, U6, R16, C13/C14, R17, RV3 CUTOFF 50k, U7 VTL5C, R18-R23, R24/R25/C15 VMID_H | BM HIHAT values |
| HiHat MCU | U3, C7, R5, J12 | BM HIHAT pin map |
| Trigger/accent/envelope | R26-R39, C17, C18 4.7u, U8, U9A, Q2/Q4 SS8050, Q3 SS8550, D4, RV4 DECAY 50k | BM HIHAT; external gate / accent / open inputs not built |
| REC (S2) | SW1 6x6 tact, R48 330, D6 LED | One button on PC2 of U2 and U3 (internal pull-ups) so both MCUs record: NOISE the TONE moves, HIHAT the envelope moves. REC LED from U3 PC3 only (modules/acid REC pins). Needs new firmware on both chips |
| Outputs | U10 TL072: A AUDIO x3 AC coupled (C21, R40-R43, J3); B HAT CV x1.51 (R44-R46, J4) + R47 1k / D5 LED | As modules/low OUT and modules/acid ENV OUT |

Deviations for review: BM SS14 -> B5819W (same Schottky class, already in BOM); BM U4B CV
follower replaced by U10B, freeing U4B (now U9B) for the NOISE IN stage; BM pot directions kept
(CUTOFF CW = lower, DECAY CW = longer, NOISE TONE CW = darker). SS8050 / SS8550 are Extended parts
(C431710 / C364314); 1n is X7R Basic (C1588). ATtiny1616 at 20 MHz on 3.3 V is outside the datasheet
speed grade, as in every Bread Modular 3.3 V module.

## 4. Placement (P2, `docs/geometry.json`)

6HP, 29 x 110 mm carrier (modules/low outline). User brief 2026-10-23 (P2): power header horizontal at
the bottom, out jacks moved down, envelope LED above the envelope section, REC button below it, more
space between the pots. F: J1 MIDI / J2 NOISE (Y21), RV1 / RV2 (Y41), D5 ENV LED (X15, Y54.8),
RV3 / RV4 (Y65; row pitch 24 mm, courtyard gap 10.2 mm, was 6.2), D6 REC LED (X22.25, Y79), SW1 REC
(X22.25, Y87.5), J3 OUT / J4 CV (Y102). B: U7 vactrol (X7, Y84.7) left of the REC column, J10
horizontal along the bottom (pin 1 -12 V at X4.5 Y113.4, IDC16 overhang to the right), J11 / J12
UPDI at the right / left edge at Y30-32.5. ~89 SMD parts parked off the right edge. Native DRC: 0
violations, 207 unconnected (unrouted), parity 0. Courtyards >= 1 mm from the edge except RV1-RV4
(0.81 mm, the modules/low pot columns).

## 5. Routing (R1) and export

User 2026-10-23: REC LED and button as one row, SW1 inside the U7 vactrol outline (soldered from the
other side). Manual divide-and-conquer routing in 13 batches, 4-layer F.Cu / In1 GND / In2 +3V3 /
B.Cu, all SMD on B: 526 tracks, 97 vias (0.3/0.6 mm), none in SMD pads, no tracks on In1/In2, both
planes one piece. KiCad DRC 0 / unconnected 0 / parity 0. The 4 `pth_inside_courtyard` items (SW1
pins inside U7's courtyard) are native exclusions in `hats.kicad_pro` (user 2026-10-24: "Ignore
those DRC is the PCB"; `tools/sw1_exclusions.py`). RV1-RV4 courtyards are 0.77 mm from the edge
(the 0.81 mm above left out the line width); user-accepted 2026-10-24. Closest SMD pad to a
pot/jack pad: R36-RV4 2.02 mm.

JLCPCB export 2026-10-24 (`jlcpcb/README.md`): bottom Economic, 88 parts in 31 rows, Extended
SS8050, SS8550, ESR18 1k 1206, MCP6002, ATtiny1616 (x2), TS5A23157 (422 in stock).

## 6. Not done

REC firmware for both chips, supplier preview/order, bench.
