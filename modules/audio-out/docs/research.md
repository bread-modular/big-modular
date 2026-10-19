# audio-out research: Bread Modular baseline, circuit, decisions

S3 schematic (`hardware/audio-out.kicad_sch`, ERC 0) and R3 routed carrier
(`hardware/audio-out.kicad_pcb`, DRC 0 at all severities, 0 unconnected, parity
equal). This document records the Bread Modular baseline, the circuit as drawn,
the decisions, and what is still open. Nothing has been built or bench-tested.

## 1. Brief

- A Eurorack audio output module based on the Bread Modular `base` headphone/line
  output, redone for ±12 V with better opamps. Pure analog.
- Same board structure as `modules/midi`: one carrier parallel to the panel,
  hung on the jack nuts, SMD on the back (JLCPCB), THT hand-soldered.
- Two TS inputs (L, R). A stereo TRS line out at a proper line level. A TRS
  headphone out with a separate volume per ear, using the Bread Modular RV09 pot
  (stocked as 50k and 1M; 50k is used).
- Stereo by default. The first brief asked for a 2.54 mm MONO jumper; on review
  (2026-10-19) the user dropped it for normalling IN L to IN R when IN R is
  unpatched, without a jumper (section 3.2).
- Panel order (user, 2026-10-19): IN L, IN R, LINE, VOL L, VOL R, PHONES; the
  pots belong to the headphone out, and PHONES at the bottom fits the panel better.
- Small improvements over BM only, nothing major.

## 2. Bread Modular `base` baseline (read-only source)

Source: `~/data/projects/bread-modular/modules/base`. Netlists were exported with
`kicad-cli sch export netlist` from `git archive` copies in `/tmp`: HEAD
(`a960b19`, "base 2.0.1", MONO on SW14) and `ca5f903` (the last jumper version,
MONO on J23 = PZ200 1x2 **2.0 mm** header). The BM checkout was not modified.

| Block | BM base (jumper version) |
|---|---|
| Supply | 3.3 V single supply, +2.5 V virtual ground (R14/R15 divider + C14/C15/C20) |
| Input | INPUT1 pin -> 10k (R58/R59) -> 2M bias (R24) to +2.5 V; DC-coupled |
| Line out | MCP6002 (U4) inverting, Rin 1M / Rf 680k (x0.68), 4.7 uF out cap (C18/C19), 1k series (R20/R21) -> J1 TRS (T = L, R = R) |
| Headphone | MCP6002 (U2) followers -> 50k RV09 (RV1/RV2, pin 3 = signal, pin 1 = GND) -> wiper -> 100k (R6/R7) -> TS922 (U3) inverting, Rf 100k (x1) -> 4 x 100 uF out caps -> 10R (R10/R12) -> J6 TRS |
| Mono | J23 (2.0 mm jumper) drives a TS5A23157 (U18) that feeds the left input to the right **line** amp only; the headphone right channel still takes the right input |

Points carried over: the RV09 50k pot with pin 3 = CW signal end and pin 1 = GND,
the 10R headphone build-out, the separate L/R volume pots, TRS T = left / R =
right, and the 100k-class wiper load that bends the linear pot towards a log
response (BM: 100k into a virtual ground; here a 15k load, section 3.4).

Points changed, and why:
- ±12 V instead of 3.3 V: no virtual ground and no output electrolytics. The
  input is AC-coupled once and every stage after it is DC-coupled.
- No MONO jumper or switch: IN R is normalled to IN L by the IN R jack's own
  switch contact, for both the line and headphone outputs (BM only switched the
  line out) (section 3.2).
- Better opamps: OPA1678 for the buffers, MC33178 (80 mA class) for the
  headphones (section 3.5).

## 3. Circuit (as drawn in S3)

### 3.1 Power

```
J5 (2x5 pin header, 10-pin cable):     +12V_IN -> D1 B5819W -> +12V (C3 10u)
                             -12V_IN -> D2 B5819W -> -12V (C4 10u)
U1: C5/C6 100n.  U2: C7/C8 100n + C9/C10 10u (headphone current peaks)
```

Series Schottky diodes block a reversed cable on either rail. The rails sit
about 0.35 V below the bus. Expected current is a few mA per rail at idle
(datasheet typicals), with peaks up to ~70 mA on loud low-impedance headphones.
J5 is an unshrouded pin header, so nothing keys the cable: fit a 10-pin socket with the red stripe (-12 V) at the bottom, and use a 10-to-16 cable on a 16-pin bus (a 16-pin socket would sit over the PHONES leads). `#FLG01` marks GND at the entry;
`#FLG02`/`#FLG03` mark the rails, which are fed only through D1/D2. ERC cannot see
through the diodes; it is the same pattern as midi's VIN_LDO.

### 3.2 Inputs and the IN R normal

```
Jn T -> 1k (R1/R2) -> 1u X7R 50V (C1/C2) -> T_x -> 47k (R3/R4) -> A_x -> OPA1678 + (follower) = BUF_x
                                                                  |
J2 TN = IN_L (normal: J2 T touches TN while IN R is empty)     56k (R5/R6) to GND
```

- Input impedance ~104 kΩ. The high-pass corner is 1.5 Hz. DC offsets of
  patched CVs are blocked, so neither output carries DC.
- The 47k/56k divider sets the line level (x0.544, −5.3 dB) before the buffer.
  Every output stage then runs at unity gain, and the buffer input stays at
  ±5.4 V even for ±10 V hot signals (well inside the OPA1678 common-mode range).
- **IN R is normalled to IN L**, no jumper. The PJ301M-12 TN contact touches the
  tip spring while no plug is in; J2 TN is wired to IN_L (J1 T):
  - only L patched -> L on both sides of the line and headphone outputs; the
    source sees the two chains in parallel (~52 kΩ), level change −0.17 dB;
  - IN R patched -> the plug lifts the spring off TN, normal stereo;
  - only R patched -> right side only (the usual Eurorack normal direction).
  A short click while plugging into IN R is normal for a switched jack.
- An unpatched input chain sits at GND through its divider, so it is silent.

### 3.3 Line out (proper consumer line level)

```
BUF_L -> 100R (R7) -> J3 T     BUF_R -> 100R (R8) -> J3 R     J3 S = GND   (unbalanced stereo TRS)
```

Eurorack full scale (10 Vpp, 3.54 Vrms) becomes **1.92 Vrms (+5.7 dBV /
+7.9 dBu)**. That is just under the 2 Vrms full-scale level of consumer line
gear (CD/DAC outputs, consumer line inputs). A typical 5 Vpp modular signal lands
near 0.96 Vrms, so it plugs straight into mixers, interfaces and hi-fi inputs
without clipping them. The 100R build-out isolates cable capacitance and limits
a shorted plug. Output impedance is 100 Ω and DC offset is the OPA1678's
(≤0.5 mV).

### 3.4 Headphone out

```
BUF_x -> RV1/RV2 50k pin 3 (pin 1 GND) -> wiper VOL_x (15k R9/R10 to GND) -> MC33178 + (follower) -> 10R (R11/R12) -> J4 T/R
```

- The follower doesn't load the wiper, so the 15k R9/R10 alone set the taper. It
  bends the (B, linear) RV09 towards a log law: 25 % -> −16 dB, 50 % -> −11 dB,
  75 % -> −7 dB, full -> 0 dB. If the pots turn out to be A (log) taper, R9/R10
  can be omitted (fit nothing).
- Maximum level is 1.92 Vrms open circuit at full scale. Into 32 Ω through 10 Ω
  that is ~67 mW with 65 mA peaks, inside the MC33178's 80 mA class. That is
  very loud, so the usual range is the lower part of the pot. High-impedance
  phones get the same voltage.
- The 10R limits current when a plug shorts T/R to S on insertion, and isolates
  cable capacitance (as BM).

### 3.5 Opamp choice

| Ref | Part | Why |
|---|---|---|
| U1 | OPA1678IDR (C192421) | 4.5 nV/√Hz, rail-to-rail out, ±18 V, CMOS input (pA bias, so no offset from the ~25 kΩ divider source), drives the pot plus a line load |
| U2 | MC33178DR2G (C39113) | Standard SOIC-8, ±18 V, 600 Ω-rated, 80 mA output class for headphones, unity-gain stable |

Rejected (`sourcing-candidates.json`): NJM4556AM (70 mA, but its DMP-8 package
needs a non-stock land pattern); NE5532DR (Basic, but bipolar input bias gives
tens of mV of DC at the outputs from the divider source).

### 3.6 Layout and routing (R3)

- 4HP, one column at X10.0, top to bottom: IN L (J1, Y19.5), IN R (J2, Y33.0),
  LINE (J3, Y46.5), VOL L (RV1, shaft Y62.5), VOL R (RV2, Y81.5), PHONES (J4,
  Y96.0), unshrouded power pin header J5 (pins Y103.54..113.7, 10-pin socket envelope Y99.73..117.51)
  (`geometry.json`, `mechanics.md`). J4 sits as high as RV2 allows so a 10-pin
  socket on J5 clears its B-side pads and stays on the board.
- All SMD parts are on B, in the bands between THT pad rows: the L input row
  above IN L; U1 between the inputs; the R input row below IN R; the line-out
  resistors above LINE; U2 + decoupling + taper loads + headphone build-outs
  between the pots; D1/D2 and the bulk caps standing vertically beside the J5 header.
- F.Cu: +12V lane on the left edge (X1.4), −12V on the right edge (X18.6, for
  the 0.5 mm copper-to-edge rule), each with one short branch per opamp group.
  IN_L runs from J1 T to the J2 TN normal. BUF_L runs down the middle (X12.0) to
  the R7 via and RV1 pin 3; BUF_R runs down the middle (X9.6) to the R8 via, then
  down the left side (X2.7) and under the RV2 tabs to RV2 pin 3.
- B.Cu: all SMD-local nets; HP_L down the right edge (X18.6) and HP_R down the
  left (X2.4) to PHONES, 0.4 mm.
- Both layers carry a whole-board GND pour, with 17 stitching vias. The jack S
  pads, pot pin 1 and the J5 GND pins tie the pours as well.
- `tools/route_plan.py` holds every segment and via (shared ops v1).
  Nothing is autorouted.

## 4. Open items (bench / human)

| # | Item | Status |
|---|---|---|
| A1 | RV09 real dimensions | **Partly closed.** The user's sample (2026-10-19) is B1M linear (the build uses 50k), with no threaded bushing and a 16 mm knurled shaft above the body; the model uses that. Body height is still nominal (6.8 mm): measure shaft tip to PCB seat before ordering panels |
| A2 | Line level and headphone loudness by ear and with a scope | Open (bench) |
| A3 | MC33178 stability into long headphone cables with 10R build-out | Expected fine (600 Ω-rated, unity-stable); bench |
| A4 | Per-part assembly review attestations (land pattern, pin map, ratings) | For the user, as midi (§5) |

## 5. Sourcing

Every assembled part carries `LCSC`, `MPN` and `Manufacturer` (`SOURCING` in
`tools/build_schematic.py`). The shared native audit (`--strict-live --side bottom
--boards 5`, on an export in the ignored `research/`) records:
- all 24 passives and D1/D2 are JLCPCB **Basic** and Economy-eligible;
- U1/U2 are Extended (deliberate) and Economy-eligible;
- MPNs match exactly, every derated voltage/power check passes, and observed
  stock is far above 5-board demand (`sourcing-candidates.json`).

The remaining gates are the human reviews (land pattern, pin mapping, ratings
attestation, capacitor DC-bias/ESR data) and the order-time rechecks. No
`jlcpcb/` export has been made yet.

## 6. References

- Bread Modular `modules/base` at `a960b19` and `ca5f903` (netlists only), RV09
  footprint and `PanelHole_Potentiometer_RV09` (Ø7.2) from
  `opt/footprints/BreadModular_Pots.pretty` (MIT).
- Bread Modular `opt/AudioJacks` (MIT, Barwise): PJ301M-12/PJ366ST footprints and
  models, with the same edits as midi.
- NJM4556A datasheet and DMP8 package drawing (Nisshinbo, rev. 20250306 /
  PI-DMP8-E-B); Bourns PTV09 datasheet (9 mm pot dimensions, reference only).
