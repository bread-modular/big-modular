# usb-power-45w S8.3: +5 V series disconnect, P1.3 fit placement

> **Development review, not a manufacturing release.** S8.3 replaces the S8.2 SCR crowbar with
> **U23 TPS259470ARPWR**, and powers **U18/U20 from always-on VPD** rather than V3V3.
> 188 references / 83 circuit nets, seven schematic pages; 100.5 × 48 mm four-layer board,
> 50 mm deep, all components on F. The board is **unrouted**. Neither a current/power rating nor
> a guaranteed safe +5 V fault peak is established. Original S7/R3 two-board hardware is unchanged.

Authorized in this review: remove the crowbar and related circuitry, choose a less expensive,
well-stocked JLCPCB part, and fix U20's input-range issue. This does **not** restore the original
three-rail protection architecture: only +5 V gains an output disconnect. MAIN remains the only LED.

## Open / review

| Item | File |
| --- | --- |
| Native project | [hardware/single/usb-power-45w-single.kicad_pro](../hardware/single/usb-power-45w-single.kicad_pro) |
| Schematic, overview + six pages | [PDF](usb-power-45w-single-schematic.pdf) |
| Native schematic BOM | [s8-single/bom.csv](s8-single/bom.csv), test pads excluded; D8/J2/J3 manual |
| Calculations | [calcs.json](s8-single/calcs.json) |
| Independent native pin/field/NC verification | [validation.json](s8-single/validation.json) |
| Final native checks and source hashes | [review-s83.json](s8-single/review-s83.json) |
| Whole-design dated sourcing estimate | [sourcing.json](s8-single/sourcing.json) |
| Live selected/changed-part evidence | [s83-sourcing.json](s8-single/s83-sourcing.json) |
| Placement / mechanical contract | [board-p1.json](s8-single/board-p1.json), [placement.json](s8-single/placement.json), [mechanical.json](s8-single/mechanical.json) |
| Placement drawing | [PDF](s8-single/assembly/usb-power-45w-single-placement.pdf) |
| 3D assembly | [STEP ZIP](s8-single/assembly/usb-power-45w-single-assembly.step.zip), [collision report](s8-single/assembly/assembly-report.json) |
| Unchanged panel | [S8 panel](../panels/front-pcb/usb-power-45w-single-panel.kicad_pcb) |

## +5 V: disconnect rather than discharge the rack

```text
U3 buck / L2 -> P5_RAW ------------------ U23 IN -> OUT -------- +5V -> J2/J3
                   |                       |                     |
            feedback R11/R12        independent OVLO       C35/C60/C73/C74
            C20-C23 + C69-C72        R107+R101 / R102       D23 negative clamp
            + C75/C76                ILM R103+R104
            D3 negative clamp       C68 dVdt
            D21 transient TVS       EN = common RUN
                   |
            U20 raw-OV guard -> OV_N -> common FAULT latch -> U5 input OFF

U23 AUXOFF + FLT + delivered-voltage comparator U18 -> P5_OK -> qualified fault latch
```

The buck's **feedback and mandatory local output capacitors remain upstream**. The header capacitors
are downstream; no component bypasses the disconnect. U23's back-to-back FETs also block reverse
current, but an external supply connected directly to the rack can still overvoltage the rack:
**this is not an external cross-rail miswiring clamp**.

Removed: **Q11, Q12, Q13, U22, R105, R106**, all `CROW_*` nets, SCR-only symbols and the old crowbar
calculations. R101/R102 are reused for OVLO, R103/R104 for ILM, and C68 for dVdt. This avoids needless
reference churn. S8.2's assertion that an overstressed SCR always fails short is withdrawn; the new
design does not depend on it.

### Selected part and cost

**TPS259470ARPWR / JLCPCB C3662799** was observed with **2,525 units in stock**, **$1.2943 at quantity
1–9**, **$1.0696 at 10–29**, and $0.8071 at 100–499 in the public JLCPCB catalog on 2026-11-01.
It is **Extended**, explicitly **Economic/Standard PCBA eligible**, not Basic. Prices exclude
Extended/setup fees, attrition, PCB, manual parts, shipping and taxes; stock is not reserved.
See the exact UTC lookup time, source URL and response hash in the sourcing evidence.
[source](https://jlcpcb.com/partdetail/TexasInstruments-TPS259470ARPWR/C3662799)

Why the **A** version: good stock at low cost, active current limit, and both AUXOFF and FLT outputs.
The compared TPS259470L listing had only 42 units; TPS259474L had good stock but uses a different
circuit-breaker/PG interface. The pin-selectable clamp variant is **not** equivalent: its 5.7 V clamp
option can reach 6.2 V in the threshold specification. The native MPN and pin roles select **470A**, not
472 or 474. [source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

Whole-design sourced-parts estimate is **$21.88**, versus the retained S8.2 snapshot's $21.50 and
S7's $27.12. The protection IC is inexpensive, but the additional capacitor bank consumes some of the
crowbar savings. This total mixes unchanged dated rows with refreshed selected-part rows; it is **not
an all-parts fresh quotation**. Added Basic resistors/capacitors and D23 were live checked. Existing
0.1% precision divider resistors remain Extended; the design therefore does **not** pass a blanket
Basic-only passive policy. No policy exception or order approval is implied.

### Settings and limits

| Setting | S8.3 result / scope |
| --- | --- |
| OVLO divider | R107 510 Ω in series with R101 37 kΩ; R102 10 kΩ; **no intentional filter capacitor** |
| OVLO trip | **5.701 V nominal; 5.585–5.848 V** tolerance screen |
| Current limit | R103 1 kΩ + R104 100 Ω: **3.031 A nominal; 2.674–3.402 A** screen, not a load rating |
| Inrush control | C68 10 nF / 50 V: approximately **0.2 V/ms**, 25 ms to 5 V, typical |
| Overcurrent blanking | ITIMER deliberately NC; no added blanking capacitor |
| Conduction at 2.5 A | Approximately **0.176 W typical / 0.281 W** with 45 mΩ; 71 / 113 mV drop |
| Voltage capability | 2.7–23 V operating, 28 V absolute maximum; D21 protects P5_RAW against fault/ringing energy |
| OVP response | **1.2 µs typical only; no specified maximum** |

OVLO arithmetic includes the 1.183–1.223 V IC threshold, ±0.1 µA input leakage, the existing 0.1% /
25 ppm/C divider parts, and 1% plus 1% drift on the Basic trim. Current-limit arithmetic includes
±10% IC accuracy and 1% plus 1% resistor drift. These are component-parameter screens, not a
qualification of the PCB. [source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

**Fault handling is deliberately explicit:** FLT does **not** report OVLO. AUXOFF does, and is wired
onto `P5_OK` along with FLT and U18. The existing roughly 1 ms bad-status filter and ARMED qualification
then set the common latch. U23 EN follows RUN, so a latched fault requires RESET. Before ARMED, or for
a pulse shorter than the filter, an OVLO-only event can auto-recover. Severe raw overvoltage still
reaches the unmasked U20 preset path even during startup. Neither the A part nor the system is claimed
to latch every arbitrarily short overvoltage pulse. A 470L substitution alone would not solve that:
its OVLO also auto-recovers. [source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

Do not wire AUXOFF directly to `OV_N`: it is normally low during startup and would prevent startup.
Do not put the buck feedback downstream: a disconnected output must not make the buck demand more voltage.

## U20 operating range fixed without another IC

U20 **and U18** retain the LM2901BIDR footprint and sourcing line. Their VCC pins and their existing
**50 V C65/C57 bypass capacitors** now connect to **VPD**, before U5, after F1. All open-collector
outputs still pull up only to **V3V3**; no 20 V signal is presented to the logic.

The old worst-case common-mode ceiling was `3.234 - 2 = 1.234 V`, below `REF_OV(max) = 1.259 V`.
At the conservative **15 V active-system supply screen**, the full-temperature ceiling is **13 V**,
leaving **11.736 V** above reference plus comparator offset. The supply also meets the >=5 V condition
used for the comparator's offset specification. No expensive rail-to-rail comparator is needed.
[source](https://www.ti.com/lit/ds/symlink/lm2901b.pdf)

U21 TLV431B, its bias/stabilizing capacitor, the precision dividers and D22 remain. Nominal U20 guard
trips remain +14.88 V, **P5_RAW +5.83 V**, and −13.64 V; U18 monitors the **delivered** +5 V.

This fixes active-operation headroom, not every sequencing case. D1's listed 35.5 V clamp leaves only
0.5 V below the comparator's 36 V operating maximum; measure actual VPD ringing at the ICs. At power
loss U20 may stay powered after V3V3/reference collapse. D22's room-temperature clamp calculation does
not qualify cold VF, leakage, residual −12 V or replug behavior. Those remain bench gates. The guard
reference's temperature range also limits the overall threshold screen; the comparator's wider
range is not a whole-module temperature rating.

## Capacitance, normal transients and fault sensitivity

+5 V now has **10 × 22 µF upstream** (C20–C23, C69–C72, C75/C76) and **4 × 22 µF downstream**
(C35/C60 at the headers, C73/C74 at the disconnect region). All are the existing 25 V Basic part.
Using the capacitor-study assumptions gives **86.1–193.6 µF upstream** and **34.4–77.4 µF downstream**.
These are assumed bias/tolerance/temperature/aging screens, not measured manufacturer worst-case curves.

The larger upstream bank creates release headroom: for a full 2.5 A load removed instantaneously,
16 switching cycles of unchanged converter current, then current ramping down at `Vo/L`, the
upstream-only estimate is **0.260 V rise**. Add the stacked regulator setpoint corner to get **5.519 V**,
about **66 mV below the lowest U23 trip**. No downstream/rack capacitor credit is taken. This is an
imposed-current calculation, **not a model of the TPS62933F control loop**, and the margin is still
small enough to require real load-release and noise tests.

### Failed-high-side screen: no guaranteed 6 V peak

`calcs.json` → `disconnect.fault_delay_sensitivity` models a hard U3 high-side short, VIN energy,
L2, separate raw/output banks, U23 on-resistance, D21, U20 RC and U5 shutdown. It takes **no credit**
for U23 current-limit/fast-trip action. U23 turn-off is idealized after a chosen delay; output wiring
inductance is separately screened at 100 nH. There is no device transistor model or real layout.

| Case | Delay assumption | Header peak | With separate 100 nH energy estimate |
| --- | --- | --- | --- |
| L2 3.3 µH, 20 V input | 1.2 µs typical | 5.910 V | 5.923 V |
| L2 reduced to 1 µH | 1.2 µs typical | 5.981 V | **6.022 V** |
| L2 3.3 µH | 3 µs sensitivity | **6.333 V** | 6.351 V |
| L2 1 µH | 5 µs sensitivity | **7.777 V** | 7.824 V |
| Half assumed capacitance, 26 V input, L2 1 µH | 3 µs sensitivity | **8.041 V** | 8.122 V |

These intentionally exposed failures of the 6 V screen are **not hidden by the tests**. They show why
an unspecified maximum delay, capacitor behavior and inductance cannot be waved away. The disconnect
is a better isolation architecture, not a proof that every downstream module survives. Before using
valuable modules, validate the maximum header peak against the actual modules' allowable voltage,
including failed regulator, feedback-open, startup, load-release, hot/cold and RESET sequences.

D21 is now **upstream**, where its 6.4–7 V breakdown and approximately 9.2 V rated pulse clamp protect
U23 and absorb stored energy. It is neither a precision 5 V clamp nor rated for a continuously fed
failed converter. U20/U5 must stop the source. TVS pulse duration/temperature and local ringing need
qualification. D23 and C73/C74 address negative output transients; verify U23 OUT's −0.3 V limit and
the permitted short-pulse condition at the actual pins. [source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

### Startup and thermal limitations

The unchanged converter soft-start capacitors are 100 nF. U23 adds a second ramp. Scaling the typical
slew formula by the tabulated charging-current extremes gives a **13–75 ms sensitivity range** to
5 V, not a guaranteed complete startup-time specification. A conservative serial timing sum is about
141 ms against the existing startup-window minimum screen of 309 ms.

The +5 V current/ramp arithmetic leaves only about **0.38 mF additional rack capacitance at a constant
2.5 A** under its chosen corners, before foldback and thermal effects. **Do not publish that as a
rating.** U23 folds current back below about 1.9 V; a constant full-current load from zero volts can
also dissipate several watts during its ramp and prevent startup. Measure actual module load current
versus voltage and start into the real rack. The old converter-only +5 V allowance is no longer the
rack allowance. −12 V retains the approximately 0.40 mF full-load allowance screen and remains a
particularly important startup test. D10's existing thermal issue is unchanged.

## P1.3 fit placement and mechanics

![S8.3 fit placement](s8-single/img/board-p1.png)

The current PCB is a **fit draft**, not a final power-loop layout. It retains all original mechanical
anchors, outline, stackup, rules and retained footprint UUIDs/models. The new TPS259470 footprint is
pinned from **TI RPW0010A drawing 4225183/A**: IN pad 5 and OUT pad 6 are long internal strips, not a
conventional central GND pad. Four corner pads are L-shaped; separate paste apertures follow TI's
0.100 mm stencil example (approximately 93% corner / 82% power-strip coverage). No vias were added.
Final stencil/rotation/assembly preview is still required.

The former crowbar area holds the new disconnect and capacitor bank. U12 shifts 0.8 mm to make room;
R91 and TP11/TP16 move within the free logic/monitor space. D21 moves to the raw-bank region. All fixed
panel and connector parts stay put. **Before routing, tighten the U23 IN/OUT bypass and D21/D23 loops**;
the fit placement currently distributes the larger bank over the front area and D23 remains at the
headers. The lumped calculation is not evidence that those paths are short enough.

Placement screens: all 188 parts on F, no parked parts, no courtyard overlaps, 1 mm edge rule holds
apart from the retained approved panel overhangs, and 2 mm hand-solder clearance around J1/D8/J2/J3
holds. Courtyard fill is about 67.3%. No tracks/vias/zones. Native DRC reports the intentional routing
opens separately; it does not qualify current-path geometry.

- Board depth is Z2..50 from the panel front; 48.4 mm behind the panel rear.
- J2/J3 pin 1 stays at Y76/Y107, Z44. Both outputs share one supply/protection path.
- Existing two B-side printed L brackets, M3 bolts and tool envelopes remain unchanged.
- Mated IDC envelope reaches X18.9, 1.1 mm inside 4HP. A tall strain-relief clip is not approved.
- The shallow 60 mm case still cannot place this board directly over a busboard header.
- The regenerated nominal 3D interference screen has zero overlaps. U23 uses a clearly identified
  **2.1 × 2.1 × 1.0 mm maximum-body proxy**, not a manufacturer STEP model; J1/SW1/L1–L3 also use proxies.

![S8.3 assembly](s8-single/assembly/iso-front.png)

## Reproducibility and verification

Generators remain derived from the untouched S7 circuit. The shared toolkit performs native checks;
its flat edit primitives cannot add the new IC or synchronize nets, so the existing S8 generator and
bounded `place_s8.sync_candidate()` perform those operations on a **separate candidate**. The sync
refuses routed boards, preserves retained UUIDs/models, and verifies the native source placement
against its recorded baseline. It binds the exact project to the temporary board basename so pcbnew
cannot substitute default design rules. No rule/severity/exclusion is relaxed.

```sh
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/usb-power-45w/tools/kicad-project-single.json \
  --reports modules/usb-power-45w/research/<new-check-directory>
python3 -B modules/usb-power-45w/tools/verify_s8.py --netlist <check-directory>/netlist.xml
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
python3 -B modules/usb-power-45w/tools/s8_calcs.py --out <new-report-directory>
```

For candidate tests, set `S8_DESIGN_ROOT` to that candidate module root. Mechanical generation accepts
the same variable and `S8_ASM_WORK` for separate outputs. Native checks include all severities,
exclusions, opens and schematic parity. Tests include incorrect pin roles, reversed/bypassed eFuse
connections, wrong-side feedback/capacitors/TVS, missing status connections, accidental 3.3 V comparator
supply, reference/clamp errors, latch behavior and numerical timestep sensitivity.

**Release gates remain open:** routing/critical-loop placement, regulator stability, measured capacitor
behavior, fault-voltage and restart tests, startup/foldback/thermal tests, connector/cable current and
fit verification, complete live sourcing/Basic-policy disposition, fabrication/CAM and manual assembly
preview. No fabrication files, vendor upload, order or commit are part of this change.
