# Requested TS-1166VW-type footprint — pattern checked, assembly blocked

> **Retired alternative:** the user has chosen the earlier **TL3340AF160QG SMT**
> switch instead. A4.2 installs that part and retains 2HP / plain L brackets.
> The analysis, historical height preference and test results below describe the
> rejected THT proposal, not the current part selection or active SW1.


## Delivered / deliberately not promoted

- Added `BigModular:SW_TS1166VW_RightAngle_THT_P4.50_P7.00_Row2.50mm` from the
  **uploaded recommended PCB layout**: signal pitch4.5, support pitch7.0,
  row offset2.5, plated drills1.0 /1.5, copper diameters2.0 /2.6.
- All four solderable legs are through-hole. Signal numbering1/2 is a local
  convention; MP1/MP2 are separate unassigned support pads, not assumed ground.
- Selected **4.3H provisionally** for a recessed reset; H is along the actuator,
  **not PCB-normal body height**. Actual axial datum still needs a sample.
- Native library loads successfully; reviewed native plot is
  [`docs/ts1166-footprint.svg`](../docs/ts1166-footprint.svg). No borrowed 3D model.
  Courtyard is explicitly provisional; no invented dimensioned body contour.
- Updated [buying guide](../docs/parts-buying-guide.md),
  [detailed switch analysis](../docs/ts1166-switch.md), README and mechanical
  guidance. The user screenshot has no product URL; no exact seller link, LCSC
  code, DigiKey equivalent, stock or delivery claim was invented.
- **Not installed:** the normal projection is7.1±0.1mm versus only5.1mm available
  beyond the present component face. Nominal extremity X11.8 exceeds the9.8mm
  panel by2.0mm. Changing H does not clear that interference.
- The installed MJTP1117 is explicitly labeled an **old layout placeholder**,
  not the user's current part choice. Existing board/panel/brackets were not
  silently repositioned or widened. The new part requires a mechanical decision.

## Source disagreement retained

The uploaded image specifies2.50mm between rows. An externally found PDF named
TS-1166VW specifies2.15mm, also consistent with its3.65−1.5 dimensions. It was
visually reviewed and retained by URL/hash in `ts1166/source-evidence.json`.
It was **not** substituted for the user's drawing. Seller/sample confirmation is
mandatory; the same model name does not guarantee the same mounting pattern.
[source](https://taoic.oss-cn-hangzhou.aliyuncs.com/7159/product/MXBESIJIA_1591957457000.pdf)

## Executed evidence

| Check | Result / limit |
|---|---|
| Native footprint loading and pad inspection | 4 pads, exact coordinates, PTH, drill/copper dimensions, both copper/mask sides, no paste, support nets unassigned |
| Analytic annular rings / nearest pad gap | 0.50/0.55mm rings; 0.49508mm minimum nominal gap |
| Isolated coupon native DRC | **0 violations, 0 opens**; coupon only, no circuit or 3D-fit claim |
| New regression tests | **8 passed**, including negative2.15-row, old5mm signal pitch, old1.3mm support drill and collapsed-support-number cases |
| Stem-height check | H4.3/5/6/7/20 all retain the same2.0mm lateral overhang in this assembly |
| Full suite | **36 passed / 2 failed (38 total)**; independent schematic byte-baseline drift described below, not suppressed |
| Existing board and drawing regeneration tests | Passed; active A4.1 geometries still reproduce, no TS-1166 promotion |
| Shared private current native check | Exit1 findings;68 ERC warnings,4 USB clearance violations,16 opens,115 native parity findings; `order_ready=false` |
| Shared private check source protection | `source_unchanged=true` for that check; historical source drift is separately preserved |
| Whitespace | `git diff --check` passed |

Evidence files:
- `ts1166/pattern-and-fit.json`
- `ts1166/coupon-drc.json`
- `ts1166/footprint-tests.txt` and `ts1166/full-tests.txt`
- `ts1166/source-boundary.json`
- `ts1166/native-current/summary.json` and raw native logs

## Unrelated source drift observed, not reverted

At the initial doctor inspection, the circuit source hashes still matched the
prior A4.1 check. During this task, the root schematic, three subsheets and
`big_modular.kicad_pro` changed outside the footprint work. The schematic text is
now reserialized to a different native version/format. This task did not write
those files; their changes were preserved, not reverted or folded into new hash
baselines. Their author/process and full semantic equivalence were not asserted.

The two failures are:
- `test_deterministic_candidate_mode_preserves_all_sources`: regenerated
  schematic bytes differ from the currently saved source.
- `test_original_circuit_and_usb_are_unchanged`: historical schematic SHA-256
  mismatch (fails on input-protection sheet before the USB comparison).

The **active main PCB remains byte-identical** to the prior native check, and
current native geometry/USB AST checks pass. No routing, fabrication upload,
purchase or commit was made. No Bread Modular files were modified. The isolated
pattern passing DRC never establishes that this switch fits the module.
