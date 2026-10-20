# VCA-MIX module research

Status: **S4 schematic + P4 placement + R1 routing, finalized** (rev. 2026-10-20). The
native schematic (`hardware/vca-mix.kicad_sch`) has 0 ERC findings. Both 6HP panels
(FR4 and printed) are generated from `geometry.json`. `hardware/vca-mix.kicad_pcb` is
**routed (R1, section 4.1)**: 0 unconnected, parity equal, native DRC = the 9 approved
D10 exclusions only. The shared gate still counts those 9 (D14), so the shared apply
output was copied into `hardware/` with `tools/promote_r1.py` on user direction
(2026-10-20) instead of `pcb promote`. R1 is final on user direction (2026-10-20): the
user accepts the D10 exceptions and verifies the board manually (D14), and the vactrol
build notes are on the footprint silk (D4). Nothing has been bench-tested. The JLCPCB
export (2026-10-20, shared exporter, user direction) is in `jlcpcb/` (`jlcpcb/README.md`);
it is not supplier-accepted.

History (all review feedback): **S2** (2026-10-19) renamed IMIX to VCA-MIX, put the
volume after each VCA with OUT following it, replaced the V2CA LED drive with the
Bread Modular LOW/SVF vactrol driver and moved the vactrols to B on the unchanged BM
VTL5C footprint. **S3/P3** made each channel one panel row with its vactrol behind its
pot (BM SVF style). **S4/P4** (2026-10-20) buffers the audio input and the CV
(inverting, as modules/imix and modules/8bit), drives OUT and MIX through 1 W 2512 1k
resistors (modules/imix R18), moves to Basic TL072 duals (three per channel row, one
for the mix) and puts each VOL knob right **below** its IN/CV/OUT jacks. **R1** routes
P4 (section 4.1).

## 1. Goal

- 6HP Eurorack module with **three channels**. Each channel has a **vactrol VCA**
  (Bread Modular V2CA circuit) with three TS jacks: **IN** (audio), **CV** and
  **OUT**.
- The CURVE knob is gone. The VCA always has V2CA's **CURVE 0** response (the
  punchy one).
- A **volume pot after each VCA** sets the channel level. The per-channel **OUT**
  follows the pot, and all three post-volume channels sum into a **MIX** output
  (the Bread Modular imix mixer).
- The CV drives the vactrol LED through a **vactrol driver** (Bread Modular LOW /
  SVF), so the LED current follows the CV from 0 V with no LED-threshold dead zone.
- With no CV plugged in, a channel's VCA is fully open, so VCA-MIX also works as a
  plain 3-channel mixer.
- Audio inputs and CV inputs are buffered; OUT and MIX are driven through protected
  1 W series resistors, as on our imix and 8bit modules.
- Hand-soldered parts (jacks, pots, vactrols, power header) follow the MIDI module:
  QingPu PJ301M-12 jacks and the Bread Modular pots (Song Huei R0904N 50k tall
  trimmer, `Potentiometer_RV09` footprint) on F, the Chinese
  vactrols on B with the Bread Modular VTL5C footprint (as Bread Modular mounts
  them), all SMD on B for JLCPCB assembly.
- Eurorack ±12 V through a 10-pin header that also takes a 16-pin IDC cable.

## 2. Bread Modular baseline (read-only source)

Netlists were exported with `kicad-cli sch export netlist` into the ignored
`research/bm-ref/` from `~/data/projects/bread-modular/modules/{v2ca,imix,low,svf}`
(BM checkout `a960b19`, not modified).

### 2.1 V2CA 1.0.1: one channel

```
V_IN -> U5A follower -> VTL5C LDR (U1.4-U1.3) -> R3 10k -> U2A(-), R4 10k feedback, U2A(+) = 2.5 V
        U2A out -> R2 1k -> V_OUT                              (gain = -10k / (10k + R_LDR))
CV_IN -> U4A follower -> RV1 50k CURVE (rheostat, pins 1-2) -> R1 330R -> VTL5C LED (U1.2 -> U1.1 = GND)
```

- The supply is a single 5 V rail (MCP6002), with a 2.5 V mid-rail from R5/R6.
- **CURVE** is a rheostat in series with the LED. At **CURVE 0 (0 Ω)** only the
  330 R limits the LED current, which gives the fastest and strongest ("punchiest")
  response. VCA-MIX removes RV1. Its LED drive is the LOW/SVF driver (2.3), whose
  330 R sense resistor gives a comparable current at 5 V CV (7.7 mA vs V2CA's
  ~9 mA) but starts at 0 V instead of at the LED threshold.
- The V2CA output is inverted (one inverting stage).
- The footprint is `BreadModular_MISC:VTL5C`: LED pads at one end, LDR pads at the
  other, 12.7 mm apart.

### 2.2 imix 2.0.0: the mixer (BM's own imix, 4 channels)

```
IN_n -> 22k -> inverting buffer (22k || 100p) -> 100R -> RV 50k (pin 3; pin 1 = V_MID) -> wiper
wipers -> 22k each -> sum (22k || 100p) -> 1k -> MIXOUT
```

The BM CHANGELOG says this version brought inverting buffered inputs for less noise
pickup. VCA-MIX follows our ±12 V port of it (`modules/imix`): 100k inverting input
buffers, a 100k summer and a 1 W 2512 1k output resistor.

### 2.3 LOW and SVF: the vactrol driver

```
LOW: CV (1M pull-down) -> U5B follower -> R3/R4 1M/1M -> U5A(+)
     U5A out -> VAC_POS (LED anodes) ; VAC_NEG (LED cathodes) -> U5A(-) and RV1 50k rheostat + 330R -> GND
SVF: CV (100k pull-up normal) -> RV2 1M attenuator -> U5A follower -> R15/R16 1M/1M -> U5B(+)
     U5B out -> VACTROL_POS ; VACTROL_NEG -> U5B(-) and RV3 50k rheostat + R17 5.1k -> GND
```

The LED sits **inside the op amp's feedback loop**. The op amp raises its output
until the cathode node equals its + input, so I_LED = V(+) / R_sense whatever the
LED's forward voltage is. The current is proportional to CV from 0 V; V2CA's
~2 V dead zone (the LED threshold with a plain series resistor) disappears.
VCA-MIX uses this circuit with a fixed 330 R sense resistor (the rheostats are
trims/ranges on LOW/SVF and are not needed here). In place of the 1M/1M divider, the
inverting CV buffer (gain -0.51) feeds the driver, so the LED loop is referenced to a
negative voltage (section 3.2).

The BM boards mount the VTL5C vactrols on **B** (body behind the board, leads
soldered on F), beside the pots (V2CA U1/U3, LOW U1/U3, SVF U1/U2). All three
use the same `BreadModular_MISC:VTL5C` footprint with a 10.16 x 15.24 mm body
outline.

## 3. Circuit (S4)

### 3.1 What changed from Bread Modular, and why

| Item | Bread Modular | VCA-MIX | Why |
|---|---|---|---|
| Supply | 5 V single rail, 2.5 V reference | ±12 V Eurorack, GND reference | Eurorack levels (±5 V audio, 0..+10 V CV) |
| Op amp | MCP6002 (6 V max) | **TL072CDT** dual (±18 V), 10 per board | ±12 V rails; Basic at JLCPCB; three per channel row keeps each row self-contained |
| Audio input | follower (V2CA) / 22k inverting (imix) | **100k/100k inverting buffer** (∥ 20p) | 100k Eurorack input impedance (modules/imix); the inversion cancels the VCA stage's, so OUT has the input polarity |
| CV input | follower | **100k in, 51k ∥ 20p inverting buffer** (gain -0.51) | review: buffer the CV; the gain sets the LED current range, the 100k is the input impedance |
| CURVE | 50k rheostat + 330R | **removed** | brief: always the punchy CURVE 0 response |
| LED drive | V2CA: follower -> 330R -> LED (dead zone below V_F ≈ 2 V) | **LOW/SVF vactrol driver** fed by the (negative) CV buffer output, 330R sense | review: map the whole CV range onto the vactrol, no dead zone |
| Negative CV | not possible on 5 V | **1N4148W anti-parallel to the LED** | the diode keeps the driver loop closed and holds the LED reverse voltage at ~0.7 V |
| CV unpatched | 0 V (VCA closed) | **TN normal to +12 V via 56k** (I_LED ≈ 12 mA, VCA open) | brief: works as a mixer with no CV |
| Volume | imix: before the mix only | **after the VCA, buffered; OUT follows it** | review: the pot sets the channel level |
| Outputs | 1k (imix) | **1k 1 W 2512** on every OUT and MIX | review: match modules/imix R18; survives a -12 V source patched into an output at +10.5 V (22.5 V² / 1k ≈ 0.51 W) |
| Mix out | sum stage only | 100k summer + **100k/100k inverter** | the channel signal is already non-inverted, so one extra inversion keeps MIX in phase |
| Power entry | 5 V header | 2x5 Eurorack header, B5819W series diode per rail | reverse-cable protection |

### 3.2 One channel (n = 1..3)

Three TL072s per channel, all in the channel's row on the board (section 4):

| TL072 | Section A (pins 1-3) | Section B (pins 5-7) |
|---|---|---|
| Un01 | input buffer | VCA stage |
| Un02 | CV buffer | vactrol driver |
| Un03 | volume follower | spare (grounded follower) |

Un04 is the vactrol.

```
IN n  (J1/J4/J7 tip; TN = GND) -> Rn01 100k -> Un01A(-) ; Rn02 100k || Cn01 20p ; (+) = GND -> BUFn = -IN
BUFn -> LDR (Un04 pins 4-3) -> Rn03 10k -> Un01B(-) ; Rn04 10k feedback ; (+) = GND -> VCAn
VCAn -> Rn10 100R -> RVn pin 3 ; pin 1 = GND ; wiper VOLWn -> Un03A(+) ; Un03A(-) = out = CHOn
CHOn -> Rn05 1k 1 W 2512 -> OUT n (J3/J6/J9 tip)
CHOn -> Rn11 100k -> SUM
CV n (J2/J5/J8 tip) -> Rn08 100k -> Un02A(-) ; Rn06 51k || Cn02 20p ; (+) = GND -> CVBn = -0.51 x CV
TN (CVNn) -> Rn07 56k -> +12V                       (no plug: TN joins the tip, CV normalled to +12 V)
CVBn -> Un02B(+) ; Un02B(-) = LEDAn = LED anode (Un04 pin 2) ; LED cathode (pin 1) = LEDKn = Un02B out
LEDAn -> Rn09 330R -> GND ; Dn01 1N4148W cathode = LEDAn, anode = LEDKn (anti-parallel to the LED)
```

- **Gain** = 10k / (10k + R_LDR), with the input polarity (two inversions): ~0.9-1.0
  with the LED fully on, ~0 in the dark (VTL5C dark resistance is in the MΩ range).
  Then the volume pot scales it.
- **CV law**: the driver holds LEDA at CVB, so I_LED = -CVB / 330 R = 0.51 x CV / 330 R
  = 1.55 mA per volt, from 0 V: 1 V → 1.5 mA, 2.5 V → 3.9 mA, 5 V → 7.7 mA,
  10 V → 15.5 mA, +12 V → 18.5 mA. The current flows GND → Rn09 → LED → the driver
  output, so **positive CV loads -12 V**. Rn09 is the range trim (270 R: 9.4 mA at 5 V).
- **Driver headroom**: at +12 V CV the driver output sits at CVB - V_F ≈ -6.1 - 2.2 =
  -8.3 V while sinking 18.5 mA, inside the TL072's swing on the -11.6 V rail.
- **Negative CV**: CVB goes positive, Dn01 carries the sense current from the driver
  output (now from +12 V), and the LED sees only ~0.7 V reverse. CVB stays within
  ±6.2 V for ±12 V CVs, inside the common-mode range.
- **Unpatched CV**: +12 V → 56k → 100k into the virtual ground gives CVB =
  -12 V x 51k / 156k = -3.9 V and I_LED ≈ 11.9 mA: the VCA is fully open.
- **Bandwidth**: input buffer 100k ∥ 20p ≈ 80 kHz, CV buffer 51k ∥ 20p ≈ 156 kHz.
  DC-coupled throughout, as on Bread Modular, so the VCA also passes CV.
- **OUT n is post-volume** (D1). The follower leaves the pot unloaded, so the
  volume follows the pot's own (linear) law; at full CW OUT n is unity.

### 3.3 Mix bus

```
CHO1-3 -> R111/R211/R311 100k -> SUM -> U401A(-) ; R401 100k || C401 20p ; (+) = GND -> SUMO
SUMO -> R402 100k -> U401B(-) ; R403 100k || C402 20p -> MIXO -> R404 1k 1 W 2512 -> MIX (J11 tip)
```

Unity per channel at full volume, input polarity. Three full-level 10 Vpp inputs at
full volume clip at the TL072's ~±10 V swing; turn the volumes down for hot sums, as
on any unity mixer.

### 3.4 Power

```
J10 pins 9/10 +12V_IN -> D501 B5819W -> +12V (C501 10u; one 100n per TL072 pin 8)
J10 pins 1/2 -12V_IN  -> D502 B5819W -> -12V (C502 10u; one 100n per TL072 pin 4)
J10 pins 3-8 GND
```

- A reversed cable reverse-biases both diodes. Their drop leaves the rails at about
  ±11.6 V.
- PWR_FLAGs: `#FLG01` on GND at the Eurorack entry, and `#FLG02`/`#FLG03` on +12V
  and -12V, which are fed from the connector only through D501/D502 (passive pins
  ERC can't see through). These are the real supply entries, not silencers.

Screening current budget (datasheet typical/max, not measured):

| Load | +12 V typ | +12 V max | -12 V typ | -12 V max |
|---|---:|---:|---:|---:|
| 10 x TL072 (1.4 / 2.5 mA per amplifier, 20 amplifiers) | 28 mA | 50 mA | 28 mA | 50 mA |
| 3 vactrol LEDs, positive CV (unpatched 11.9 mA each; +12 V CV 18.5 mA each), sunk into -12 V | 0 | 0 | 36 mA | 56 mA |
| 3 drivers sourcing the sense current for negative CV (-12 V CV: 18.5 mA each) | 0 | 56 mA | 0 | 0 |
| CV normals (3 x 77 µA) | 0.2 mA | 0.2 mA | 0 | 0 |
| **Total** | **~28 mA** | **~106 mA** | **~64 mA** | **~106 mA** |

+5 V: 0 mA. "typ" is mixer mode (no CV patched). The two max columns can't both
happen on one channel (a CV is either positive or negative). Output loads add their
own current on top.

## 4. Mechanics (P4 placement, `geometry.json`)

| Item | Value |
|---|---|
| Panel | 6HP, 30.0 x 128.5 mm, FR4 1.6 mm (`panels/front-pcb`) or printed 2.0 mm (`panels/front-cad`); rail holes Ø3.2 at (7.5, 3.0)/(7.5, 125.5) |
| Carrier | 29.0 x 110.0 x 1.6 mm, 2 layers, X0.5..29.5, Y9.25..119.25; hangs on the 10 jack nuts only (the R0904N pots are snap-in with a plain shaft and take no nut) |
| Channel rows | One row per channel, 29.0 mm pitch: IN/CV/OUT jacks at Y23.0 / 52.0 / 81.0, then the VOLn pot shaft 13.5 mm **below** them at (15.0, 36.5 / 65.5 / 94.5), right under the CV jack. F courtyards: jacks to their pot 0.4 mm, pot to the next jack row 0.6 mm |
| Jacks | PJ301M-12, unrotated, columns IN X5.25 / CV 15.0 / OUT 24.75 (9.75 mm pitch); **MIX** (15.0, 110.0), 15.5 mm below the row-3 pot |
| Vactrols U104/U204/U304 | **B side, behind their own pot** (Bread Modular SVF style), Bread Modular VTL5C footprint unchanged (courtyard added), at (9.0, pot Y + 1.3), rot 90: body X1.4..16.6. LDR pads (3, 4) at X2.65 beside the pot; LED pads (1, 2) at X15.35, **under the pot body**. Assembly order: vactrol first (leads soldered on F and trimmed flush), then the pot |
| Op amps | B side, three TL072s per row: Un01 (input buffer + VCA) between the IN and CV jacks, Un02 (CV buffer + driver) between CV and OUT, both at row Y + 2.5; Un03 (follower) right of the pot at (24.9, pot Y + 2.4) with the 2512 OUT resistor above it. U401 (mix) at (23.5, 111.0) right of MIX, R404 (2512) left of it. Each TL072 has its two 100n beside its supply pins |
| Power header J10 | B side, horizontal across the top edge, pin 1 (-12 V) at (4.3, 11.0), B silk `-12V`. A 16-pin IDC socket's positions 11-16 overhang to the right (envelope X0.49..25.89, Y7.87..16.67, 2.5 mm above B). Parts under it (D501/D502, C501/C502) are ≤ 1.5 mm tall |
| Panel holes | jack Ø6.2, pot Ø7.2 (BM `PanelHole_Potentiometer_RV09`; 0.6 mm radial clearance around the Ø6.0 R0904N shaft), rail Ø3.2 |
| Pot stack (Z from F.Cu) | Song Huei R0904N, drawing R09N-003 v1.5, tall L = 25: body 6.8 + collar 0.8 → top Z7.6, 2.4 mm under the panel rear (Z10.0); Ø6.0 shaft to Z25.0; knurl Z18.0..25.0. Panel front Z11.6 (FR4) / Z12.0 (print), so the tip is 13.4 / 13.0 mm proud and the knurl starts 6.4 / 6.0 mm above the face |
| Labels | `VCA-MIX`; `IN n` / `CV n` / `OUT n` above each jack row; `VOL n` left of each knob; `MIX`; `BIG MODULAR` |
| 3D fit (nominal) | `docs/fit/fit-report.json` (P4, 2026-10-20): 0 mm³ interference for all 10 jacks and the three pots (R0904N datasheet envelopes) against both panels; board inside the rail gap and panel width; PJ301M-12 thread 2.90 mm (FR4) / 2.50 mm (print) past the panel front. Vactrols have no 3D model and are **not** in the check (D4) |

**Vactrols behind the pots.** As on Bread Modular SVF, each vactrol body sits on B
behind its pot, and the pot body sits over the vactrol's LED leads on F. No position
avoids this overlap: the pot courtyard is 12.8 mm wide and the vactrol pads are
12.7 mm apart, and the vactrol body is wider than the gap between the pot's bracket
tabs. Native DRC therefore reports **9 `pth_inside_courtyard` errors** (per row: the
two LED pads inside the pot courtyard, the pot's left bracket tab inside the vactrol
courtyard). They are the intended stacking. Bread Modular SVF sets this rule to
`ignore`. Here the rule stays at `error`; the user approved exactly these 9 as
per-item native exclusions (D10, 2026-10-20), written by `tools/d10_exclusions.py`. They are the **only** DRC findings on P4/R1.

### 4.1 Routing (R1)

Routed on the P4 placement with external autorouters (user direction, 2026-10-20),
compared on the same board, rules and pours. Driver scripts and raw output are in the
ignored `research/r1/` (`ROUTERS.md`); no router tooling was added to the repository.

| | Freerouting 2.5.0 (repo-pinned runtime) | **TraceMaker 0.10.0** (release, sha256-checked) | Topola (source build) |
|---|---|---|---|
| Unrouted | 0 | **0** | 158 / 165 |
| Vias | 50 | **40** | 0 |
| Track length | ~1.50 m | **~1.08 m** | n/a |
| Below-rule neck-downs | 56 (widened to 0.2 mm by script) | **none** | n/a |
| DRC beyond D10 | none | 3 starved thermals (fixed, below) | 36 violations |

**Picked: TraceMaker** (`--soft-zones --via-cost-mm 12 --no-kb --no-gpu`, GND pours
present while routing), for the shorter, more compact route and fewer vias. Rules were
only ever tightened for the routers (0.25 mm signal, 0.4 mm `Power` class for the
rails in a research copy of the project); the native rules are unchanged.

Cleanup 1 (`research/r1/fix_sleeves.py`): in each row TraceMaker fed Un01 pin 8 with a
second +12V leg running parallel to the trunk, beside the CV jack sleeve. That leg is
replaced by a tee onto the +12V trunk (9 segments out, 3 in). The pours follow
modules/imix: GND on both layers, **solid pad connection**, 0.25 mm clearance, 0.2 mm
minimum width. TraceMaker's route was tested with thermal spokes, and there J2/J5/J8's
B-side sleeve kept only one spoke, because Cn05 (the Un02 100n) sits directly below each
sleeve; a solid connection removes that question without moving parts.

Result: 0.25 mm signals, 0.4 mm rails, 40 vias of 0.6/0.3 mm, 472 track segments.
The copper is frozen in `tools/route_r1.json` (200 polylines from pad centre / via /
tee to pad centre / via, plus the vias), and `tools/route_plan.py` emits it with the two
GND zones as shared `pcb plan/apply` ops v1 (242 operations). Shared apply on the R1 base
(2026-10-20): ERC 0, ref/pin/net parity equal, **0 unconnected**, no new DRC finding;
DRC = the 9 D10 findings only, so the candidate status is `rejected` and `pcb promote`
refuses it. `research/route-cand-r1/` holds it. With the D10 exclusions in the project,
native DRC marks those 9 `excluded`, but the shared apply gate still counts excluded
findings, so `pcb promote` still refuses (D14). On user direction (2026-10-20) the board was
re-planned on the base with the D10 exclusions, applied (`research/route-cand-r1b/`),
and copied into `hardware/` by `tools/promote_r1.py` (promote's model rebinding, no
other change). Native DRC on `hardware/` (`--severity-all --refill-zones
--all-track-errors --schematic-parity`): 0 unconnected, 0 parity, 9 excluded D10, nothing
else; 472 tracks, 40 vias. Nominal 3D fit unchanged (0 mm³).

Final R1 (2026-10-20, after the D4 silk notes): the VTL5C footprint gained three B.SilkS
lines inside its body box, so the base was rebuilt, D10 re-keyed, re-planned, applied
(`research/route-cand-r1c/`) and copied by `tools/promote_r1.py`. Same copper (472
tracks, 40 vias); native DRC on `hardware/`: 0 unconnected, 0 parity, 9 excluded D10,
nothing else (no silk or text-height warning); shared `check`: ERC 0, 0 unconnected,
parity 0, `order_ready` false only for the 9 D10 items. Fit 0 mm³.

## 5. Decisions and open checks

| # | Item | State |
|---|---|---|
| D1 | Per-channel OUT is **after** the volume pot (buffered wiper); MIX sums the post-volume channels | Decided (review 2026-10-19) |
| D2 | Unpatched CV = VCA open (TN normal to +12 V via 56k → 11.9 mA) | Decided (brief: works as a mixer without CV) |
| D3 | **Pot stack**: Song Huei R0904N tall trimmers, snap-in, plain knurled shaft, **no bushing or nut** | **Closed on the datasheet** (section 4). The panel is held by the jack nuts alone. The BM footprint is kept exactly (bracket legs 9.6 mm vs the drawing's 10.6 mm): the user confirmed (2026-10-19) these pots work well in it on their BM builds. Not a physical-fit claim for this board |
| D4 | **Vactrol part**: the Chinese vactrols that fit the Bread Modular VTL5C footprint. LED current 7.7 mA at 5 V CV, 11.9 mA unpatched, 18.5 mA at +12 V CV; LDR range and body height behind the board not modelled | **Handed to the builder (user, 2026-10-20)**: the VTL5C footprint carries B.SilkS notes inside the body box (`SOLDER FIRST`, `TRIM FLUSH`, `LED 18.5mA`); the user solders and checks the part accordingly. **LED rating confirmed by the user (2026-10-20): 40 mA**, so the 18.5 mA worst case keeps 330 R (R109/R209/R309). Not a bench claim |
| D5 | Routing | **R1 final in `hardware/`** (section 4.1), copied past the D14 gate on user direction |
| D6 | Pot taper: linear 50k as Bread Modular | Decided (brief: same pots; user prefers linear for audio too) |
| D7 | Op amp TL072CDT (C6961) is Basic; the 1 W 2512 1k (C54315) is Extended | Accepted (the same trade-off as modules/imix) |
| D8 | CV scaling: inverting buffer gain -0.51, 330 R sense (1.55 mA/V, from 0 V) | Decided (S4). Rn09 is the range trim if the bench vactrols want more or less current |
| D9 | Vactrols on B behind their own pots, Bread Modular SVF style | Decided (review 2026-10-19) |
| D10 | The 9 `pth_inside_courtyard` DRC errors from the vactrol/pot stacking | **Decided 2026-10-20 (user): accept them as 9 per-item native DRC exclusions** in `hardware/vca-mix.kicad_pro`, comment "D10: ...". The rule stays `error` for any other overlap. `tools/d10_exclusions.py` rewrites them from a native DRC report and refuses unless the report holds exactly these 9 pairs; re-run it after every `build_layout.py` (UUIDs change). Verified: native DRC on the R1 base and on the R1 candidate copy marks exactly 9 excluded, nothing else |
| D11 | Audio inputs, CV inputs buffered; OUT/MIX through 1k 1 W 2512 | Decided (review 2026-10-20, as modules/imix / 8bit) |
| D12 | GND pours: both layers, solid pad connection (modules/imix), not thermal relief | Decided for R1 (section 4.1). Jack/pot GND joints need a hotter iron; thermal relief would need a placement change around the CV sleeves |
| D13 | Router: TraceMaker 0.10.0, picked over Freerouting 2.5.0 and Topola on the same board | Decided for R1 (section 4.1) |
| D14 | Shared apply/`check` count excluded findings as findings, so `pcb promote` refuses R1 and `check` reports `order_ready: false` | **Accepted by the user (2026-10-20): ignore for this module, manual verification.** The shared tool is unchanged, so `check` keeps reporting `order_ready: false` for the 9 D10 items. A shared fix would still need a reviewed shared-tool policy (e.g. a plan-bound list of accepted excluded-finding identities) in `opt/kicad-tools/automation/api.py`; not done here because the shared tool documents that exclusions are never waived |

## 6. Sourcing (JLCPCB, dated observations 2026-10-19/20)

From `kicad_tools.py assembly lookup --strict-live`. Full records for the S4 part set
are in [`sourcing-candidates.json`](sourcing-candidates.json) (rebuilt from the saved
lookups by `research/s4/sourcing_doc.py`). Stock is transient and is not a reservation.

| Part | LCSC | MPN | Class |
|---|---|---|---|
| TL072 x10 | C6961 | ST TL072CDT (SO-8) | Basic |
| 1k 1 W 2512 x4 (OUT1-3, MIX) | C54315 | UNI-ROYAL 25121WF1001T4E | Extended |
| 100k / 56k / 51k / 10k / 330 / 100 (0603, 1 %) | C25803 / C23206 / C23196 / C25804 / C23138 / C22775 | UNI-ROYAL 0603WAF… | Basic |
| 20p C0G 0603 | C1648 | Samsung CL10C200JB8NNNC | Basic |
| 100n X7R 0603 | C14663 | YAGEO CC0603KRX7R9BB104 | Basic |
| 10u 25 V X5R 0805 | C15850 | Samsung CL21A106KAYNNNE | Basic |
| 1N4148W SOD-123 | C81598 | ST (Semtech) 1N4148W | Basic |
| B5819W SOD-123 | C8598 | CJ B5819W SL | Basic |

Hand-soldered, not JLCPCB-assembled: 10 x QingPu WQP-PJ301M-12, 3 x Song Huei
R0904N 50k linear tall-trimmer pots (L = 25, knurled), 3 x Chinese VTL5C-type vactrols
(Bread Modular footprint), 1 x 2x5 2.54 mm header.
