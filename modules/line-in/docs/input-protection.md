# S3/R2 input protection and accepted review findings

## User disposition

The user accepted the existing assembly-review and physical-fit concerns and asked
that the 1k/0.5W output parts be left alone if they match the other modules. Native
sourcing tables and shipping BOMs confirm the exact same **ROHM ESR18EZPF1001,
C2074262, 1k, 1206, 0.5W** in:

| Module | Matching references in its shipping BOM |
|---|---|
| ACID | R43, R44, R48, R49, R53, R54, R57 |
| HATS | R43, R46 |
| 8bit | R12 |
| MCC | R4 |
| Line In | R7, R8, R12 |

R7/R8/R12 and their routing are unchanged. The earlier continuous opposite-rail
fault-rating concern is **accepted as-is**, not disproved by part reuse. The
legacy audit load-line figures are not a guaranteed TL072 current/swing limit.
No false supplier, bench or physical-fit approval has been recorded.

## Circuit implemented

For each channel:

```text
TRS -> LEVEL pot -> C9/C10 1u -> COUP_L/R -> R13/R14 10k -> AC_L/R -> U1A/U2A (+)
                                  |
                               R1/R2 1M
                                  |
                                 GND

Positive clamp: AC -> D3/D5 pin 1 -> two internal diodes -> pin 2 -> GND
Negative clamp: GND -> D4/D6 pin 1 -> two internal diodes -> pin 2 -> AC
All four pin-3 junction midpoints: externally unconnected, explicit schematic NC.
```

D3-D6 are **Nexperia BAV199,215 (C40919), SOT-23**, not generic BAV99 or BAT54
substitutes. The stock BAV99 *graphic* is reused with the identical series-dual
pin topology, but the library identity, value, description, datasheet and sourcing
are BAV199. The manufacturer specifies pin 1=A1, 2=K2, 3=K1/A2. [source](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf)

The MIDI V2 circuit was inspected (`modules/midi/Code.md`, input Q1/R1/D9). Its
MMBT3904 input intentionally reshapes and inverts digital MIDI; copying that
stage would destroy an analog waveform. This design reuses the **current limit +
clamp** principle instead. Ground-referenced clamps were chosen so the external
protection network does not inject fault current into the module's supply rails.

The limiter is **after** the coupling capacitor, so a charged capacitor or a
polarity-changing patch cannot bypass it. The 1M bias stays on the capacitor side
and biases the follower through the additional 10k. There is no intentional
10k/1M signal divider after the limiter; the normal gain-setting resistors,
channel polarity, MONO sum and nominal 0.16Hz high-pass are unchanged.
C9/C10's native Voltage field was corrected from 25V to the existing selected
part's 50V; the C-code/MPN/value/footprint did not change.

## Electrical design envelope and limitations

Design scope: ordinary powered operation on the intended healthy +/-12V Eurorack
supply, with an accidental bounded +/-12.6V signal/step at IN. This is not an
IEC ESD/surge or mains/speaker-output rating.

```text
Worst initial opposite-polarity step envelope: 25.2V
R13/R14 minimum (1% tolerance):                 9900 ohms
Conservative peak current (zero clamp drop):  25.2 / 9900 = 2.545mA
Conservative peak resistor power:            25.2^2 / 9900 = 64.15mW
Selected resistor:                          100mW, 75V, 0603, 1%
Audit ceiling:                              70% power / voltage derating
```

The audit also checks the independent V/I tolerance corners; its conservative
65.44mW bound passes the 70mW design ceiling. The resistor family specifies
continuous rated power through 70C and derating above that ambient. [source](https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2206010045_UNI-ROYAL-Uniroyal-Elec-0603WAF1002T5E_C25804.pdf)
Resistor temperature/pulse qualification still needs prototype validation; do
not extrapolate above the part's rated ambient or to larger fault voltages.

At the manufacturer's stated 25C test points, each BAV199 junction has a maximum
forward drop of 0.9V at 1mA or 1V at 10mA. Thus the two-series-junction string has
a 2V static test-point envelope at a current well above this design's calculated
fault current. The forward-recovery specification is 1.75V per junction at
10mA/20ns, i.e. 3.5V for a pair under that test. These are not full-temperature,
all-waveform guarantees, but both are comfortably inside the healthy powered
TL072 rails. [source](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf)

BAV199 is selected for its low leakage and low capacitance (typical 3pA leakage
at the stated 25C condition, typical 2pF per junction), rather than ordinary
Schottky rail clamps on a high-impedance node. Two junctions in each direction
keep normal input signals below substantial forward conduction: about 0.255V
peak at the follower already produces approximately 10Vpp before output loading,
and about 0.51V peak reaches the intended stage's clipping region. Actual
THD/noise/temperature behavior remains a bench check, not a guaranteed result
from these typical diode specifications. [source](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf)

**Powered-off immunity is NOT established.** The passive network still limits
current and voltage when off, but its clamp is not zero volts. ST says the TL072
input magnitude must not exceed the supply magnitude (or 15V, whichever is
lower), and gives no general powered-off injection-current guarantee. Do not
claim unrestricted hot-plugging while unpowered. A guaranteed power-off rating
would require a separately engineered disconnect/protected-input solution. [source](https://www.st.com/resource/en/datasheet/tl072.pdf)

No SPICE, IEC test, destructive fault test, or hardware THD measurement was run.
The manufacturer datasheet/model were readable through the web-content tool;
direct file downloads returned HTTP 403 and were not bypassed.

## PCB implementation

- All 37 existing footprints retain their exact placement, orientation, side,
  value, footprint and pad geometry; no panel, jack, pot or output resistor moved.
- Six parts added on B: R13/R14, D3-D6. Only the six original AC_L/AC_R track
  segments were replaced; every other pre-existing track/via is unchanged.
- Existing C9.2/R1.1 and C10.2/R2.1 now use COUP_L/COUP_R. The original U1.3/U2.3
  AC nets are the protected sides. Native exact pin/net parity passes.
- D3/D4 sit behind LEVEL L; D5/D6 behind LEVEL R, clear of all through-hole pads.
  R13/R14 sit beside the corresponding buffer group. Protected F.Cu runs and
  raw coupling runs use separate, manually chosen paths; no autorouter.
- 44 vias, all outside SMD copper/mask openings. Added ground stitching connects
  the D6 ground pocket; there are no remaining ground opens.
- Minimum SMD-to-pot/jack-pad clearance **2.081mm** (D6.2 to RV2.1); minimum
  courtyard-to-edge **1.075mm**. Copper-to-edge rule remains 1mm.
- Filled GND geometry: F has two main regions connected through the ground
  network plus four header fragments; B has a main region, header region and
  four header fragments plus the stitched 3.28mm2 D6 pocket. No floating islands.

## Verification and exports

- Native ERC: 0; native full-severity/refilled DRC: 0; unconnected: 0; parity: 0.
- Shared native XML-to-PCB reference/pin/net parity: equal, including seven NCs.
- No rules, exclusions or clearance thresholds weakened.
- BOM/CPL: 36 identical reference sets, 13 rows, all Bottom; original seven THT
  parts remain manual. Native CPL XY/rotation/side checks pass.
- Existing panel source and shipping files unchanged. Carrier Gerbers/BOM/CPL and
  their mirrors regenerated together; source manifest rehashed. The shared-tool
  profile now explicitly declares this manifest.
- R13/R14 are Basic and Economy-eligible. D3-D6 are Extended and Economy-eligible:
  **one additional unique Extended diode type**. All R/C other than the accepted
  ESR18 output resistors were observed Basic. Catalog evidence is a snapshot,
  not an order reservation.
- The strict assembly audit is deliberately not called fully passed: existing
  review attestations remain open, and the shared Basic-only passive gate still
  reports the user-accepted ESR18 exception. It was not weakened or bypassed.

Evidence is in `research/input-protection/`: `native-final/` (and final release
recheck), `geometry-review.json`, `preservation.json`, `assembly-audit.json`, raw
catalog snapshots, per-batch DRC reports and native plots. The original S2/R1
review is historical; this note records its disposition and the new circuit.
