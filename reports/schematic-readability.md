# Three-subsheet readability revision — validation

**Presentation-only change. NOT operational validation, PCB completion or fabrication approval.**

The previous A1 circuit is now an A4 navigation overview and three A3 functional circuit sheets. The existing 88 real components, values, part numbers, pin assignments, no-connects and all 97 symbol/pin UUID sets (including ERC flags) are retained. All edits are in the isolated Big Modular workspace; no commit, PCB synchronization, routing or Bread Modular modification was performed.

## Delivered reading material

- [Schematic PDF](../docs/schematic.pdf): four pages; the first three internal PDF navigation links lead to pages 2, 3 and 4.
- [Sheet guide](../docs/schematic-guide.md): each page's purpose, interfaces, reading conventions and safe regeneration commands.
- [Component guide](../docs/component-guide.md): all 88 real BOM references, grouped by function, including operating rationale and unresolved limits.
- [Machine-readable audit](schematic-readability.json): exact net-name mapping, hashes, counts and limitations.

## Executed checks

| Check | Result |
| --- | --- |
| Hierarchy | One overview, three referenced children, no orphan/duplicate circuit sheets; 11 matched sheet-pin/child-port links |
| Real inventory | 88 components: 22 input/protection, 35 conversion, 31 output |
| Native before/after comparison | **All 288 exported pin memberships and 72 exact net-member sets preserved**, including singleton/unconnected nets and off-board J2 in the XML export |
| Component fields | Native common-tool component records exactly equal before/after |
| UUID identity | All 97 placed symbols and their pin UUIDs unchanged; hierarchy paths intentionally change |
| Native net namespace | 39 full names acquire functional-sheet prefixes; original leaf names remain unique, no nets merged or split |
| Local labels | Reduced from **192 to 81** over the whole drawing set; 11 explicit hierarchical labels added |
| Geometric connectivity | 297 pin records including flags/NC inspected; 260 connected real pins checked against the retained intended audit |
| Independent pin/net spot checks | 65 retained hardcoded assertions |
| Visible interstage paths | 20 original wire/hierarchy paths checked; one remote PRE_P-to-U5 continuation explicitly retained as label-mediated |
| Visible local paths | **57** additional wire-only checks for feedback, filtering, enables, protection, LDO networks and bleeders |
| Native installed-environment ERC | **0 errors, 0 warnings**, full severity; [JSON](erc.json), [text](erc.rpt) |
| Native isolated/private ERC | **68 existing footprint-library configuration warnings before and after**, no electrical errors; retained without exclusions |
| Native save/reload | Force-saved the entire hierarchy on a separate disposable copy, freshly exported and rechecked; exact component/hierarchy/net equality, 0 installed-environment ERC findings |
| PDF | Four pages, A4/A3/A3/A3; converted link targets checked with Poppler; all page layouts rasterized and visually inspected |
| Tests | `python3 -B -m unittest discover -s tests -v`: **12 passed** |
| Existing project verifier | 260 connected pins, 65 spot checks, 57 local wire paths, 20 interstage paths plus one named continuation, 28 voltage/PG/RUN cases, 8 NPTH geometry checks: passed |
| Protected artifacts | 14 tracked files hash-identical to baseline: both PCBs, both project files, pinned symbol/footprint libraries and tables, BOM, intended pin audit, assembly documents and mechanics document |
| Diff whitespace | `git diff --check`: passed |

The geometric graph and intended inventory remain supplemental evidence, not substitutes for native KiCad netlisting/ERC or an independent electrical design review. The before/after net-member comparison uses the imported common toolkit; it does not compare only leaf strings or silently discard singleton/NC nets. Raw full-namespace differences are retained separately from the electrical-equivalence assertion.

## Why the two ERC results differ

The common checker stages a private project with an isolated configuration. That configuration does not include six installed standard footprint libraries used by the circuit inventory:

- Capacitor_SMD: 32 warnings.
- Resistor_SMD: 31 warnings.
- Package_SO: 2 warnings.
- Package_TO_SOT_SMD, Package_SON and Package_DFN_QFN: one each.

These are the same 68 warning categories/descriptions in the before and after runs. The direct installed-environment CLI resolves those standard libraries and reports zero findings. Neither result was obtained by changing an ERC rule, suppression, exclusion, pin electrical type or project library. **The private checker still reports `findings`, not a clean/full hardware result.**

## PCB boundary and known failures

Both boards are byte-for-byte unchanged, with zero tracks, vias and zones. The carrier has only J1 as an electrical footprint; J2 remains off-board. Fresh geometry assertions passed, but DRC was not rerun for unchanged boards. The existing carrier findings (four physical clearances and six unrouted items), panel mechanical limitations and all electrical qualification blockers remain.

The common check also retains **failed native XML-to-PCB parity**: 86 missing electrical references, four extra mechanical references, 255 missing pins and 17 net-name mismatches. Full details are preserved below. The hierarchy change does not authorize updating/synchronizing either PCB or suppressing those findings. Future authorized PCB synchronization must account for the new hierarchical paths/names as well as completing the circuit placement.

The documentation also corrects two overstatements without changing the circuit: U3 PG is high-impedance in shutdown/UVLO, and U5's 6.52 V is a divider-selection target rather than its 0.808 V-reference typical estimate. The component guide cites the manufacturer documentation for both.

## Retained native evidence

The [readability-native directory](readability-native/) contains:

- `before-netlist.xml`, `after-netlist.xml`, `reloaded-netlist.xml`: actual complete native XML exports.
- `before-erc.json`, `after-erc.json`: full private native findings.
- `before-summary.json`, `after-summary.json`: source hashes, command records/stdout/stderr, warnings, parity and source-preservation results.
- `reloaded-erc.json`: native ERC on the saved/reloaded private copy.
- `native-hierarchy-delta.json`: exact common-tool full-name/hierarchy comparison. It correctly reports inequality because the hierarchy intentionally changed.
- `reload-delta.json`: common-tool exact save/reload comparison, `equal: true`.

The machine-readable readability audit records hashes of these files and the delivered schematic/PDF. Temporary layout iterations and raster previews remain in ignored `research/`; they are not alternate hardware deliverables. Native KiCad may create an ignored local `.kicad_prl` view-state file; this is not a PCB, library, project-rule or circuit change.

## Reproduce current checks

Use a **new** reports destination for the common checker. Its findings exit status is expected for this intentionally incomplete carrier and the isolated footprint-library warnings.

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
python3 -B opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --reports research/new-readability-check --only erc
python3 -B -m unittest discover -s tests -v
/usr/bin/python3 -B tools/verify_project.py
pdfinfo -f 1 -l 4 docs/schematic.pdf
git diff --check
```

The verifier reads the delivered native netlist/PDF and refreshes its threshold/geometry audit reports. To validate a newly changed schematic, first regenerate those exports with the commands in README. To generate a schematic-only candidate without changing the boards, use `build_project.py --schematic-only --output NEW_DIRECTORY`; the unflagged legacy builder remains broader and must not be used casually.
