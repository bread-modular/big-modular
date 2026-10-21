# LOW research and circuit intent (S2)

## 1. Brief (user, 2026-10-21)

- Bread Modular **MCO** and **LOW** (LPG) as one 6HP Eurorack signal module.
- Keep Bread Modular's **3.3 V internal signal level**, so the vactrol response and
  feel stay the same.
- Inputs: **MIDI** (as 8bit), **AUDIO bypass** (buffered, mapped onto the 0..3.3 V
  level; clipping is acceptable, it is part of the character), **CV bypass**
  (0..5 V mapped onto Bread Modular's 0..3.3 V).
- Unpatched AUDIO = the MCO square mix; unpatched CV = the MCO CV output (velocity DAC).
- Panel top to bottom: MIDI, the two MCO knobs, AUDIO + CV, CUTOFF, OUT. No BLAST button.
- This stage: schematic with every net connected, THT parts placed (vactrols as
  modules/vca-mix), **no routing**.

## 2. Bread Modular baseline (read-only, `~/data/projects/bread-modular/modules/{mco,low}`)

- **MCO 1.0.1**: ATtiny1616 on V_SUPPLY (3.3 V). PB3 MIDI RX, PB4 tone 1 (TCB0),
  PB5 tone 2 (TCB1, detuned 0..12 semitones by the DETUNE pot on PB0), PA7 gate,
  PA6 DAC = note velocity (0 on note off), PB2 TX, PA0 UPDI via 4.7k. Mix: MCP6002 U3A
  inverting summer around a 1k/1k V_MID: tone 1 via 1M, tone 2 via the MIX pot
  (V_MID..tone 2) and 1M, feedback 2 x 200k, 1k output resistor. U3B unused.
- **LOW 1.1.0**: two VTL5C vactrols, each LDR + 10n to a 1k/1k V_MID followed by an
  MCP6002 follower (two poles), 1k output. Driver: U5B follows CV (1M pull-down),
  1M/1M halves it, U5A forces the paralleled LED cathodes to CV/2, so the LED current
  is (CV/2) / (CUTOFF rheostat 50k + 330R). BLAST button (SW1 + 330R) not used here.
- Firmware: `modules/mco/code/mco` runs unchanged (pin map kept). The LOW CV normal is
  the velocity DAC, so an unpatched module is a MIDI-velocity low-pass gate.

## 3. Circuit (S2, `tools/build_schematic.py`; S2 = S1 circuit redrawn with wires)

| Block | Parts | Notes |
| --- | --- | --- |
| Power | J10, D1/D2 B5819W, C1/C2, U1 HT7533-1, C3-C5 | ±12 V through series Schottkys; +3V3 from +12V_F (~20 mA, ~0.2 W). Bulk 100u as BM MCO |
| MIDI | J1, R1 100k, R2 10k, D3, Q1 MMBT3904, R3 22k, JP1 | 8bit / MIDI V2 front end with pull-ups on +3V3. JP1 open: 1-2 protected (PORT_INVEN on PB3), 2-3 direct (stock BM firmware, 3.3 V senders only) |
| MCO | U2, C6, R4, J11 UPDI, R12 1k (DAC -> VEL_CV), RV1 DETUNE, RV2 MIX, R5-R11, U3A, C7 | Bread Modular MCO values. PA7 gate and PB2 TX have no destination |
| AUDIO bypass | J2, R13 100k, C8 1u, R14 100k, R15 33k, U3B, R16 1M | AC coupled, gain -0.33 around V_MID: 10 Vpp -> 3.3 Vpp; hotter clips at the MCP6002 rails. ±12 V safe (100k into the virtual ground) |
| CV bypass | J3, R17 51k, R18 110k, D4 BAT54SW, R19 1M | 5.0 V -> 3.30 V with R23 1M as load; clamp to +3V3/GND; input 161k |
| Normals | U4 TS5A23157 (dual 10R SPDT), C9 | See 3.1 |
| LOW | U5/U7 VTL5C, C11/C12 10n, U6, R20-R22, U8, R23-R26, RV3 CUTOFF, C13/C14 | Bread Modular LOW values, no BLAST |
| Output | C15 1u + R29 100k, U9A TL072, R27 20k, R28 10k, R30 1k 0.5 W, J4 (U9B unused, tied off) | AC coupled (1.6 Hz high-pass) so OUT centres on 0 V whatever the LOW's resting level; x3: 3.3 Vpp -> ±4.95 V |

### 3.1 Why the normals use a switch (decision for user review)

A plain jack normal (MCO signal on the TN contact) would pass the MCO through the same
level converters as the external signal: the square mix would come out at x0.33 and
the velocity CV at x0.66, so the default voice would be quieter and the gate would
never open fully, changing the vactrol response the brief wants to keep. Instead each
jack's TN contact is only a detector: unpatched, TN touches T, which is held near GND by
R13 (audio) or R17+R18 (CV), so IN reads 0.30 V / 0.46 V (low) and U4 connects
COM to NC = MCO_OUT / VEL_CV at their original Bread Modular levels. Patched, TN opens and
the 1M pull-up takes IN high, so COM = NO = the converted input. Cost: one TSSOP-10, two
1M resistors, one 100n. A firmware alternative (jack sense on a spare MCU pin) would
not fix the CV level and changes the BM firmware, so it was not used.

Open points: TS5A23157 pin map taken from the TI DGS pinout (1 IN1, 2 NO1, 3 GND, 4 NO2,
5 IN2, 6 COM2, 7 NC2, 8 V+, 9 NC1, 10 COM1) - verify against the datasheet before
routing. Control-input leakage (datasheet max) through 1M must keep IN above VIH;
typical leakage is nA.

## 4. Placement (P2, `docs/geometry.json`)

6HP, 29 x 110 mm carrier, 2 layers. F: J1 MIDI (Y23), RV1 DETUNE / RV2 MIX (Y42),
J2 AUDIO / J3 CV (Y62), RV3 CUTOFF (Y82), J4 OUT (Y108.5). B: J10 power vertical at the
bottom-left, pin 1 (-12 V) at the bottom (as midi/8bit; P2, user direction), J11 UPDI at the right edge, U5 behind CUTOFF exactly as vca-mix, U7
below CUTOFF. All SMD parts are parked on B off the right board edge.

Native DRC (`--severity-all --schematic-parity`): 3 violations, all U5 stacked under
RV3 (`pth_inside_courtyard`), the same pattern as vca-mix D10; 152 unconnected
(nothing routed); parity 0. No exclusions were added.

## 5. Routing (R1, 2026-10-21)

Manual divide-and-conquer (root AGENTS.md), straight on `hardware/low.kicad_pcb`, one group per
batch with native DRC + parity after each: power entry by J10, output stage right of J4, LOW
poles (U6) right of CUTOFF, LOW driver (U8) above U5, the jack band (U3, U4, bypass parts), then
MCU + MIDI at the top. 2 layers: GND pours on F and B (F stays one piece), Power class 0.4 mm.
Short F hops only where B is boxed in: VAC_+/- (THT to THT), LPG_IN, LPG_B1, AIN_BUF,
MCO_AMP, VMID_MCO, VEL_CV (right edge), TONE2, DETUNE, UPDI. U4 +3V3 enters through a via under
its body. TS5A23157 pin map verified against TI SCDS165F (IN low = NC on). Result: 3 DRC errors
(U5 under RV3, as vca-mix D10, no exclusion), 0 unconnected, parity 0, ERC 0, no vias in SMD
pads. Free track vertices are on the 0.05 mm grid except where they line up with an off-grid pad
row. Open: the 1M sense pull-ups vs. the TS5A23157 worst-case 1 uA IN leakage (2.3 V vs VIH
2.31 V at 3.3 V); typical leakage is 50 nA.

## 6. Not done

Sourcing (no LCSC fields yet), SMD placement, routing, panel fit / 3D check, firmware
check of PORT_INVEN for the protected MIDI path, bench.
