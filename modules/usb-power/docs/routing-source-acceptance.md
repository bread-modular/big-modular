# USB-power routing source acceptance — 084 (NOT RELEASED)

**Status: ROUTING SOURCE ACCEPTED — NOT RELEASED. No fabrication or assembly release.**

Canonical PCB routing source is now `hardware/usb-power.kicad_pcb`:

- SHA256 `69a1e329e919ca0f8ddaaec38e30de119fa0d0639823c0017e1675554ff52adc`
- 1,082,046 bytes, byte-identical copy of
  `c83ad5bf30ef8a3c1f2ae3aeb4acf443e35f6db8:modules/usb-power/docs/routing-progress-084/usb-power.kicad_pcb`
- No KiCad edit, no SaveBoard, no routing change, no model-node rewrite, no regeneration.

Independent review: Opus `docs/routing-review-082/REPORT.md` plus
`docs/routing-review-082/receipts/hd1-084/hd1-closure-receipt.json`
(Git commit `a69359228da551e13a40af9de41a2c5f076f2765`, on `main`). Verdict: HD-1 closed,
"Canonical source promotion: PASS" for the 084 PCB **as a NOT RELEASED prototype
source**. Native re-check of that object: ERC 0, DRC 0 violations / 0 unconnected /
0 parity, `source_unchanged: true`; 116 refs / 344 pins / 39 singleton NC nets /
1,110 non-system fields; exact delta vs 081 is only 2 deleted copper blocks
(via `8e4785b7…`, B.Cu stub `b1dbe53d…`).

Frozen and unchanged by this promotion: `usb-power.kicad_pro`
`122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9`,
`usb-power.kicad_sch` `4c3512d8…`, all child sheets, local symbol/footprint
libraries, `fp-lib-table`/`sym-lib-table`, both panel projects and `mechanics/`. See the
resource manifest `docs/routing-source-acceptance.json` for the exact PCB, project,
model and license entries.

## Portable 3D resources (byte-exact PCB kept)

The accepted PCB keeps its `${KIPRJMOD}/_kicad_models/<provider-path-sha256>/…`
references, so exactly its 10 referenced STEP files were copied unmodified from the
locally installed `kicad-packages3d` library (794,646 bytes total). Each copy was
verified against the pinned 075 provider hash and the object SHA; no KiCad library
was bulk-copied and no model path was rewritten. Attribution and locally verified
license terms are in `hardware/_kicad_models/ATTRIBUTION.md`; the supplied notices
themselves (Debian copyright with the full CC-BY-SA 4.0 text and exception, plus the
complete GPL-3) are carried in `hardware/_kicad_models/licenses/` with their SHA256
recorded. Note `D_SMA.step` is GPL-3+ upstream, not CC-BY-SA; it is redistributed
unmodified under those terms.

## Release holds (all still open)

1. L1 mechanical height: **5.40 mm vs 5.10 mm** — user decision required.
2. Explicit JLC acceptance of inner 1 oz copper, plating, drill tolerance and
   unfilled via-in-pad on a PCBA service.
3. Prototype qualification not performed: solder-joint/void integrity, thermal,
   EMI, startup/load and EP-joint bench testing.

## Local verification (this promotion)

- `check --config tools/kicad-project.json --only both` (dry run first, then actual,
  new reports dir under ignored `research/canonical-084-promotion`):
  **ERC 0; DRC 0 violations / 0 unconnected / 0 schematic parity**,
  `source_unchanged: true`, `order_ready: false`.
- All 10 model dependencies resolved from `hardware/_kicad_models/` with the pinned
  provider hashes; PCB stayed `69a1e329…4ff52adc`; PRO stayed `122b817b…529de9`.
- Module test suite run once, unmodified: 133 tests → 34 failures + 8 errors after
  promotion vs 28 failures + 26 errors on pre-promotion HEAD (91 vs 79 passing).
  Only two tests newly fail — both assert the historical 043 via routing contract
  (`test_native_via_disks…`, `test_routing_deletion_and_via_process_changes…`);
  14 previously failing tests now pass because the model resources exist. Three
  `gerbonara` import errors are an environment gap, present before this change.
  No test, baseline, rule or assertion was edited or waived. Full detail:
  `docs/routing-source-acceptance-receipt.json`.

## What is deliberately stale

`jlcpcb/` still holds the historical 043 fabrication/assembly snapshot with
`recovery-status.json` "STALE". No Gerber, BOM, CPL, stencil or ZIP was regenerated
from the 084 source; the old exports do not describe this routed source. Historical
receipts, recovery manifests, `docs/routed-baseline.json` and test assertions were
left untouched, so tests that encode the historical 043 source SHA/counts are
expected to fail until a separate, explicitly approved baseline refresh.
