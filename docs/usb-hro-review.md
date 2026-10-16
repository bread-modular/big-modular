# HRO source / mechanical review — 024 provenance + 025 release

**Bare-PCB release continuation:** source provenance below is retained;025 completes
fabrication and measured-tolerance requirements in [fabrication.md](fabrication.md).
Canonical hardware is authoritative; no commits/main writes/GUI/Bread edits.

## Exact reference and limits

Read-only reference: Bread `modules/32bit-5v/Module32.pretty/HRO-TYPE-C-31-M-12.kicad_mod`, `verification/identity-land-evidence.json` and the HRO drawing. Drawing SHA256 `6ae33d50ac47820114661138dc4e4659f40fdc5d4f485b46685dfec338da1a9e`; sheet 1/1, drawn 2020.12.08; layout tolerance +/-0.05 mm. Original bytes/hashes are in `research/hro-release-024/preservation/`.

- Exact part: HRO **TYPE-C-31-M-12 / C165948**; local footprint `BigModular:HRO-TYPE-C-31-M-12`.
- Retain Bread's twelve rectangular lands, four shell slots and two NPTHs. Wide lands are **0.575 x1.45**, centred at X +/-3.225 and +/-2.45; eight other lands are 0.30 x1.45. All row centres Y=-7.695.
- Drawing explicitly calls four 0.60-wide lands; Bread's 0.575 is within its stated +/-0.05 layout tolerance. **1.45 is the local land length, not an unambiguous drawing-derived length.** This is the user-selected proven local pattern, not a claim of literal manufacturer-layout equivalence.
- Drawing locating-bore label is diameter0.60; molded peg diameter0.50. Local NPTHs remain **0.65**, centres (+/-2.89,-6.25): deliberate extra nominal clearance, not smaller pegs. Nominal diametral peg clearance is0.15; actual molded-part/finished-hole tolerance needs confirmation. Nearest local copper-to-peg-hole edge is **0.396565 mm** against the unchanged0.25 rule.
- Local shell slots: rear0.60 x1.70, front0.60 x1.20; centres X +/-4.32, Y=-6.78/-2.60. Drawing's front recommended slot label is1.40; the retained local1.20 is a documented local deviation. Side-view front tab length0.80 and rear1.10 leave nominal longitudinal insertion allowance; sample/process tolerance acceptance is not proven by DRC.
- Ambiguous vertical0.50/1.64/4.18/5.79 extension-line associations are **not** used to invent a board-edge datum.

## Identity, graphics and process changes

The four pairs share real lands: A1/B12 -> A1; A4/B9 -> A4; A9/B4 -> A9; A12/B1 -> A12. The dedicated13-pin local schematic symbol honestly represents12 signal/power lands + S1 shell. A5=CC1, B5=CC2, S1=GND; four data and two SBU pins remain explicit NC. All197 non-USB native electrical pin identities are unchanged.

Bread supplied **no model, F.Fab body or courtyard**. Added F.Fab nominal body8.94 x7.35 and F.CrtYd land/body envelope; trimmed only off-board silk. HRO has no verified3D model; unreferenced loose STEP was not adopted. The misleading GCT footprint/model is removed from active closure. HRO is marked mixed SMT/contact + plated-through-shell mounting (`through_hole` native type); manual population is not DNP.

Original Bread shell pads included both-side paste. **Removed shell paste only**, keeping copper, drill and both-side mask. The12 SMT lands retain front copper/mask/paste. No relief polygons, peg shrink, fake flags or GCT relief code were imported.

## Datum and fit

Independent side-view anchors are the front shell tab2.60 and rear6.77 from mating face. Local shell-slot rows2.60/6.78 agree to0.01 mm rounding. Using those anchors, retain mouth panel Y33.5 / Z0.8; footprint native origin becomes **(69.25,103.475), rotation0**. Shell slot centres stay at the old carrier positions; SMT row moves0.34 mm toward the rear. Nominal shell height3.26 places its centre at X4.7+1.63=**6.33**; not a borrowed GCT axis.

024 aperture was X4.23 Y28.6 W4.2 H9.8 R0.6.025 enlarges it to
**X3.90 Y28.10 W5.00 H10.80 R0.60**, preserving all other interfaces. Panel9.8 x128.5 x1.6, carrier100.5 x30 x1.6, outline, bracket cutbacks, holes, D10, SW1 and J7 poses stay fixed. Front slot drill-to-edge0.80 / copper-to-edge0.60. Full pad support and existing bracket/nut/tool and LED/switch reservations pass independent native geometry checks.

`hro_fit.py` now checks the full declared fabrication/assembly acceptance budget:
finished boards1.44..1.76mm; walls+/-.10, centre+/-.10 X/Y, radius.50..70;
assembly+/-.10 X/Y, shell width+.15/height+.10, seating+.05 and tilt<=.5deg.
Worst-case rounded-corner clearance0.233458mm. The old aperture fails this same
budget (-0.428610mm), not accepted as an unmodeled0.08mm fit. Registration requires
measurement; loose M3 holes do not guarantee it. Real cable/ABS/LED/sample trial
remains pending, distinct from bare-PCB fabrication readiness.

`docs/assembly.pdf` includes the HRO detail sheet; `docs/usb-fit.pdf` is standalone. Generated SCAD is an explicitly labelled translucent envelope, not an HRO solid; OpenSCAD is unavailable here, so no SCAD engine render/physical-fit approval is claimed.

## Routing and checks

Started from exact routed input `e7e25d1a040b20819c983bb07cf910b98a3aa06ba0c69723f0e9927cfe322eb9`. Only8 USB escape/CC2 segments and1 CC2 via move; the other545 segment/via geometries, all non-USB pads/models/poses, zone boundaries and stack stay unchanged. CC2 via moves to(70.6,94.52) to clear the longer HRO NC land. Final inventory remains421 segments,133 vias,4 zones; continuous In1 GND and isolated eFuse RTN membership are checked.

Inherited five optional DRC and four ERC ignores were **enabled as warnings**, not weakened.
Five four-way schematic junctions were redrawn as paired T junctions (same wires/nets,
no pin or component pose changes) to satisfy the newly enabled four-way check. Missing real hole/J7 assembly courtyards were added; J1/U4/J7 symbol footprint filters now match the exact selected packages. These are nonfabrication metadata/graphics changes, not electrical/layout changes. All133 vias are explicitly filled/capped Type VII as a uniform intended fabrication process; **audited35 positive-area exposed-SMD/paste overlaps plus7 boundary cases; all133 remain the uniform process**. Do not claim all133 individually need filling or call this a commodity unfilled-via board.
