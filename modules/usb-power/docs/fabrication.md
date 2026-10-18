# LDO-R1 prototype bare-PCB fabrication contract

> Migration recovery: source/electrical content below is retained checkpoint evidence.
> `jlcpcb/` is the current manufacturing export generated from this tree.
> Run commands from `modules/usb-power`; shared `opt/` stays at repo root. See
> [migration-recovery.md](migration-recovery.md) for current checks and Astra handoff.

This release is **bare-PCB artwork ready with JLCPCB standard settings**, not an assembled-product qualification, supplier acceptance or purchasing approval.
Canonical files are `hardware/usb-power.kicad_pcb` and `hardware/usb-power-panel.kicad_pcb`.
The carrier uses JLC standard 0.300 mm through vias with the default "Tented" via
covering; no filled, capped or other paid via process is specified.

## Carrier — independent four-layer order

- Finished outline **100.50 x 30.00 mm**, including the existing two front cutbacks.
  Machine to Edge.Cuts **centreline**, not the outside of its 0.05 mm plotted stroke.
  Overall routed edge location tolerance +/-0.10 mm; no V-score, castellation,
  edge plating or countersinks. Remove burrs without changing the profile.
- **JLCPCB standard 4-layer stack JLC04161H-7628**, FR4 Tg155 (JLC default),
  1.6 mm, outer 1 oz / inner 0.5 oz; no paid stack/copper/material options.
  Standard JLC thickness tolerance applies (+/-10%, 1.44..1.76 mm).
- Native design stack, top to bottom (mm): F.Mask .010 / F.Cu .035 /
  7628 prepreg .2104 / In1.Cu .0152 / core 1.065 / In2.Cu .0152 / 7628 prepreg .2104 /
  B.Cu .035 / B.Mask .010 = **1.606 nominal** (JLC published values).
  Outer copper includes plating. Not a controlled-impedance order. No impedance requirement; epsilon/loss values in native metadata are
  planning values, not tested material properties. No layer substitutions/reordering.
- **HASL (with lead)** finish, JLC default. Lead-free HASL / ENIG are paid options
  only if needed (e.g. flatness for the 0.5 mm pitch HRO USB-C). Green mask both
  sides, white legend (JLC default). Mask apertures as supplied.
- All **207 through vias** (0.300 mm drill, 0.50..0.65 mm pad) are **JLC standard
  vias, "Tented" via covering** (JLC default). No plugging, epoxy fill, copper cap
  or VIPPO. Do NOT fill or plug the component holes or the four USB shell slots.
- Native and independent CAM audit identify **93** via barrels with positive-area intersection of exposed
  SMD copper and **92** intersecting paste. Another **6** touch/lie within1um of a
  pad/paste boundary (separately recorded; not called positive overlap). These are
  reported as prototype assembly risk: an ordinary via barrel inside an exposed or
  thermal pad can wick solder or leave an unfilled void, and mask tenting does not
  seal that hole. Inspect and validate such joints in prototype assembly; this is
  not a fabrication reject and no fill/cap process is required.
  `via-audit.json` identifies every barrel/affected pad and its filled/capped flags.
  `via-process.tsv` lists all 207 vias in KiCad X/Y-down and CAM X/Y-up coordinates.
  Excellon alone does not encode any fill/cap requirement; none is specified here.
- All drill/slot/hole tolerances are **JLC standard capabilities**; no tighter
  project tolerances are requested (vias have no specified bore tolerance; PTH
  +0.13/-0.08 mm). Component PTH .900 / 1.000 mm. HRO shell slots .600 mm wide,
  1.700 mm (rear, two) and 1.200 mm (front, two) long; keep as slots, not drills.
- NPTH: two HRO locator .650 mm, two switch locator .900 mm, two 2.500 mm
  strain-relief and two 3.200 mm mounting holes; JLC standard tolerances.
- JLC standard 4-layer quality and flying-probe/E-test. eFuse RTN **must NOT join**
  main GND (verify against supplied IPC-D-356).

## Passive panel — separate independent order

- Finished outline **9.80 x 128.50 mm**, JLC standard **2-layer FR4 Tg135, 1.6 mm
  (+/-10%)**, black mask (free standard colour), white front legend, finish per JLC
  default (no exposed copper remains, so it has no effect).
  Copper Gerbers are intentionally empty, so all copper is etched away; native stack
  copper thicknesses are zero. No plated holes, no electrical assembly.
- Six NPTHs: five 3.200 +/- .100 mm and one LED 3.600 +/- .100 mm. Existing locations
  unchanged. Location to profile +/-0.10 mm per axis. Empty PTH file is intentional.
- USB opening: panel coordinates **X3.90 Y28.10 W5.00 H10.80 R0.60 mm**.
  Centre X6.40,Y33.50; W and H +/-0.20 mm (each wall +/-0.10), centre location
  relative to panel datum +/-0.10 mm each axis; radius 0.50..0.70 mm. The whole
  through-thickness profile must meet these bounds, including taper/burrs.
  Outer profile edge deviation +/-0.10 mm. No countersinking, edge plating or scoring.
- Do not silently enlarge mounting/LED/retry holes, shift brackets or alter the
  outer rectangle. Native aperture is independently checked in Gerber centreline
  geometry, not inferred solely from this document.

## Toleranced aperture fit and assembly limits

Compared with 024: X -0.33, Y -0.50, W +0.80, H +1.00 mm; R unchanged. The frozen
carrier, D10/SW1/J7/brackets, panel overall and all non-USB openings are unchanged.
Worst-case signed rounded-corner clearance is **0.233458 mm**, versus a **negative**
clearance for the old opening under the SAME complete acceptance budget.

Budget is additive, not RSS: BOTH finished-board thicknesses +/-0.16 mm; machined
wall +/-0.10, aperture centre +/-0.10 X/Y, maximum radius .70; HRO shell width +.15
and height +.10; seating +.05 X; measured assembled registration +/-0.10 X/Y;
squareness <=.5 degrees plus .02 mm projected sweep through the thickest panel;
in-plane angular registration <=.5 degrees adds .040 mm X / .016 mm Y at shell corners.
Carrier back-face is the mounting datum, so full carrier thickness deviation moves
the connector face in X. Panel thickness changes mouth Z and the tilt sweep.
Mouth recess is .42..1.18 mm; ahead of panel rear .58..1.02 mm. Worst panel-edge
ligament .60 mm. See generated `usb-fit.json`, SVG/PDF and independent negative tests.
**Assembly registration is an acceptance condition, not guaranteed by loose M3 holes.**
Actual cable/overmould/full insertion, HRO sample fit, formed LED leads and printed
ABS bracket shrinkage/strength require an assembled trial. These are not concealed
as completed tests and are not a reason to confuse bare-PCB artwork with a product.

## Tooling and narrowly scoped gaps

Read canonical `../../opt/kicad-tools/skills/kicad-workflow/SKILL.md`, `kicad_tools.py --help`,
`export --help`, `pcb --help` and actual native CLI help first. Common `check` remains
mandatory for private all-severity ERC/DRC/native parity. The unchanged common
`export` always creates assembly BOM/CPL and includes paste in its fabrication ZIP;
`--pcb-only` means fields from PCB, NOT a bare-PCB-only mode. It strips X2/net attrs
and offers no IPC-D-356/job/process-aware bare-PCB package or actual-CAM renderer.
Do not run its assembly pipeline and pretend the unreviewed CSV is qualified.

Use the shared `opt/kicad-tools/jlcpcb/export.py` exporter and `kicad_tools.py check`.
There is no module-local release orchestrator, CAM parser or renderer: the module
does not duplicate the shared toolkit. The shared exporter creates the Gerbers,
drills, BOM and CPL; `kicad_tools.py check` provides private all-severity ERC/DRC
and native parity. No installs into main, Bread or system Python. No uploads,
orders or assembly CSVs.
Native metadata normalization is recorded: remove volatile timestamps; correct
job size from verified Edge.Cuts centreline (KiCad includes the .05 stroke); omit
misleading auto-derived zero inner-clearance fields and non-fabrication paste stack
entries from the bare-PCB job, retaining unchanged native design rules in source.
No CAM coordinates, apertures, drills or net attributes are changed.
Gerbonara 1.6.3 needs a small region-attribute adapter: its native parser already
reads X2 attributes but fails to attach them to Region objects. The adapter copies
that parsed dictionary at G36/G37; geometry parsing/rendering remains unchanged.
Excellon plating is verified from native file/tool X2 comments because Gerbonara
does not populate its plating property for these comments. Its G90-after-header
notice is retained and reconciled with absolute coordinate matching. Excellon
3-decimal output quantization is bounded to0.000501mm; no hole can be dropped or
matched twice. IPC-D-356 uses checked unique shortened aliases plus a full-name map. A standard
ZIP metadata epoch is used solely for reproducible bytes, not as a fabrication date.
Paste is a separate **ASSEMBLY-STENCIL-SUPPORT-ONLY** archive, not a stencil-order
approval (thickness/reduction/reflow process still needs assembly review).

JLC standard "Tented" via covering is the specified via treatment; no fill,
plug or copper-cap process is ordered. Tenting is artwork-defined and does
not seal a barrel that lies inside an exposed pad. The specific limits above are this
project's requirements, not supplier acceptance.
Standard 1.6 mm +/-10% thickness is used as an explicit acceptance bound, not an
unqualified exact 1.6 mm assumption. [source](https://www.viasion.com/pcb-manufacturing-tolerances/)
Gerbonara provides actual Gerber/Excellon/IPC-356 parsing and SVG primitives.
[source](https://gerbolyze.gitlab.io/gerbonara/)

## LDO-R1 capacitor and single-side assembly requirements

Exact CL31A226KAHNNNE / C12891 banks: IN+4, OUT+6, IN-4, OUT-3.
Manufacturer typical bias data with 0.9 tolerance x0.85 temperature x0.95 aging
allowance screens to 12.592 /23.990 /12.592 /11.995uF at14.8 /12.4 /14.8 /12.4V.
These are **screening estimates, not guaranteed or measured minima**. No unreviewed
substitutions. X5R body temperature <=85C; lot/bias/temperature, input ringing,
load-step stability, startup/reverse/shutdown, noise/PSRR and thermal tests remain.

All C63-C66 and C67 are FRONT. All components are on F.Cu: zero B.Cu footprints and
zero B.Paste component apertures. B.Cu routing/mask/copper and drill layers remain
part of the bare PCB. Single-side prototype assembly; no Economy PCBA qualification.
No assembly BOM/CPL is supplied; root BOM.csv is design identity only, not an
order/allocation file. The separate stencil-support ZIP carries the actual F.Paste
component apertures; B.Paste is intentionally empty. No stencil thickness, reduction
or reflow approval is implied.

The fixed carrier datum X2.5..4.1mm, brackets, panel, harness envelope and all THT
tail projections are retained by the 0.60mm panel-feature shift. Native placement
and assembly-height checks are in `mechanics.json` and `assembly-geometry.json`;
this is a dimensioned fit check, not an assembled sample test. The panel outline,
bracket/rail holes and legend are retained; the USB aperture, LED hole and reset
hole move -0.60mm in X with the carrier.

The old HRO-R1 release archive was retired together with the `production/`
directory. The manufacturing-export location is `jlcpcb/`, regenerated from the
current sources with the shared `opt/kicad-tools/jlcpcb/export.py`; the historical
043 snapshot was removed. No supplier upload or order was made here. Supervisor
reviews/merges; no commit/push.
