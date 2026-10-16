# HRO bare-PCB fabrication contract — HRO-R1

This release is **bare-PCB artwork ready with the required fabrication process**,
not an assembled-product qualification, supplier acceptance or purchasing approval.
Canonical files are `hardware/big_modular.kicad_pcb` and `hardware/front_panel.kicad_pcb`.
Do not manufacture the carrier as an ordinary unfilled/tented-via board.

## Carrier — independent four-layer order

- Finished outline **100.50 x 30.00 mm**, including the existing two front cutbacks.
  Machine to Edge.Cuts **centreline**, not the outside of its 0.05 mm plotted stroke.
  Overall routed edge location tolerance +/-0.10 mm; no V-score, castellation,
  edge plating or countersinks. Remove burrs without changing the profile.
- **FR4, Tg >=170 C**, nominal finished thickness **1.60 mm, acceptance 1.44..1.76 mm**,
  including copper, finish and mask at representative coated seating areas.
  Manufacturer must select actual laminate/prepreg pressing to meet this limit.
- Explicit design stack, top to bottom (mm): F.Mask .010 / F.Cu .035 /
  prepreg .200 / In1.Cu .035 / core 1.040 / In2.Cu .035 / prepreg .200 /
  B.Cu .035 / B.Mask .010 = **1.600 nominal**. Same values in native board/job.
  All four copper layers are nominal 35 um finished, minimum 28 um. Outer copper
  includes plating; cap plating is not an extra uniform board layer. Dielectric
  thicknesses are design targets, not a supplier-approved stack or controlled-impedance
  construction. No impedance requirement; epsilon/loss values in native metadata are
  planning values, not tested material properties. No layer substitutions/reordering.
- **ENIG** exposed copper, nickel 3..6 um and immersion gold 0.05..0.10 um;
  green solder mask both sides, white legend. Mask apertures as supplied; do not
  expand them or delete narrow dams without review. Finished mask registration to
  copper <=0.05 mm each axis. Minimum retained dam target 0.10 mm.
- All **133 through vias**, the **0.300 mm ViaDrill tool** in the PTH file, require
  **IPC-4761 Type VII: nonconductive epoxy filling, planarization, copper capping
  on BOTH sides**, followed by the specified surface finish/mask. Copper cap minimum
  15 um; local dimple or protrusion <=25 um. These numerical limits are project
  acceptance requirements, not a quotation of every IPC clause. Plated barrel
  copper minimum 20 um. Provide fabricator process confirmation and sample/coupon
  evidence for fill/cap quality. No solder-mask plugging, ordinary tenting, or open
  via substitution. Do NOT fill the component holes or the four USB shell slots.
- Native and independent CAM audit identify **35** via barrels with positive-area intersection of exposed
  SMD copper and **35** intersecting paste. Another **7** touch/lie within1um of a
  pad/paste boundary (separately recorded; not called positive overlap). All remaining
  vias get the same uniform
  process for unambiguous fabrication; they are not each claimed to require VIP.
  `via-audit.json` identifies every barrel/affected pad. `via-process.tsv` identifies
  the entire required fill/cap population in KiCad X/Y-down and CAM X/Y-up coordinates.
  Excellon alone does not encode epoxy/cap requirements; THESE NOTES ARE MANDATORY.
- Via 0.300 mm is the nominal plated bore before filling (accepted bore 0.25..0.35 mm);
  it is NOT a finished open hole. Component PTH diameters: .900 and 1.000 +/-0.075 mm.
  HRO shell slots: finished **.600 +/- .050 mm width**, lengths **1.700 +/- .100 mm**
  (rear, two) and **1.200 +/- .100 mm** (front, two). G85 endpoints are cutter-centre
  travel, so subtract tool diameter from total slot length to obtain travel.
  Do not shrink/remap shell slots to circular drills.
- NPTH: two HRO locator holes **.650 +.050/-0 mm**; two switch locator holes
  .900 +/- .050 mm; two 2.500 +/- .100 mm strain-relief holes; two 3.200 +/- .100 mm
  mounting holes. Hole/slot location to copper +/-0.075 mm per axis; to routed
  profile +/-0.10 mm per axis. No plated treatment of NPTHs.
- Fabricate to IPC-6012 Class 2 workmanship unless an explicitly approved contract
  says otherwise. Perform 100% electrical continuity/isolation test against supplied
  IPC-D-356 + full-name net map; eFuse RTN **must NOT join** main GND. Manufacturer
  coupon/process tests are requirements, not tests already performed here.

## Passive panel — separate independent order

- Finished outline **9.80 x 128.50 mm**, thickness **1.60 mm, acceptance 1.44..1.76 mm**.
  FR4 Tg>=170 C, nominal dielectric 1.580 mm + black mask .010 mm each side.
  **NO retained copper, no plated holes, no electrical assembly, no metal finish.**
  The two logical KiCad copper layers and their supplied Gerbers are intentionally
  empty; native stack copper thicknesses are zero. Use unclad laminate, or remove
  all initial cladding and choose the substrate to achieve finished thickness.
  No residual copper sheet/rings are permitted. White front legend; back legend empty.
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

Read canonical `opt/kicad-tools/skills/kicad-workflow/SKILL.md`, `kicad_tools.py --help`,
`export --help`, `pcb --help` and actual native CLI help first. Common `check` remains
mandatory for private all-severity ERC/DRC/native parity. The unchanged common
`export` always creates assembly BOM/CPL and includes paste in its fabrication ZIP;
`--pcb-only` means fields from PCB, NOT a bare-PCB-only mode. It strips X2/net attrs
and offers no IPC-D-356/job/process-aware bare-PCB package or actual-CAM renderer.
Do not run its assembly pipeline and pretend the unreviewed CSV is qualified.

`tools/release_hro.py` is therefore narrow release orchestration: it REUSES the
common exporter's `stage_cli_project` / `run_cli`, calls actual KiCad Gerber/drill/
IPC-D-356 exporters, and packages their artwork. It does not redraw/route boards or
implement a Gerber parser/renderer. `tools/check_hro_cam.py` uses pinned **Gerbonara**
for actual Gerber/Excellon parsing and SVG rendering, and Shapely for geometric
comparison, not a native-board preview. Optional local environment only:

```sh
/usr/bin/python3 -m venv --system-site-packages research/hro-cam-venv
research/hro-cam-venv/bin/python -m pip install -r tools/cam-requirements.txt
research/hro-cam-venv/bin/python -B tools/release_hro.py --output research/new-hro-release --reports research/new-hro-native
```

No installs into main, Bread or system Python. No uploads, orders or assembly CSVs.
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

The Type VII filled/capped distinction is supported by fabricator guidance; the
specific limits above are this project's requirements, not supplier acceptance.
[source](https://www.viasion.com/pcb-via-plugging/)
Standard 1.6 mm +/-10% thickness is used as an explicit acceptance bound, not an
unqualified exact 1.6 mm assumption. [source](https://www.viasion.com/pcb-manufacturing-tolerances/)
Gerbonara provides actual Gerber/Excellon/IPC-356 parsing and SVG primitives.
[source](https://gerbolyze.gitlab.io/gerbonara/)
