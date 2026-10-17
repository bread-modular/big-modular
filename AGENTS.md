# Current checkpoint override

The exact 037 basic-passive correction is accepted in canonical `hardware/`: exact
R4/R8/R36 series networks with R77-R82, C10 0402 4.5p, and D10 DNP (footprint/pads
retained, not fitted or purchased). D10 is not a manual purchased part.
Source/native ERC/DRC/warnings/exclusions/opens/parity are zero; production/ldo-r1
is re-exported from this frozen source, including the JLC assembly BOM/CPL.

# Agent entry point

Read Code.md. For KiCad read opt/kicad-tools/skills/kicad-workflow/SKILL.md;
for sourcing/assembly also read skills/jlcpcb-assembly/SKILL.md and jlcpcb docs.
Common-tool-first; inspect actual CLI help. Do not strip dependencies or weaken rules.

Current task: finish LDO-R1 prototype capacitor correction, preserve closed routing,
verify and export fresh bare-PCB release in the assigned isolated workspace.
Latest user authorization supersedes historical source-only/no-export restrictions.
Canonical hardware now contains the reviewed LDO board, not the old64-part carrier.
Read docs/ldo-handoff.md and docs/ldo-revision.md. Historical HRO-R1 stays untouched.
Current via override: ordinary 0.300 mm plated through vias, solder-mask tented where
artwork permits; no IPC-4761 fill/planarization/copper-cap add-on.
Current assembly override: all components on F.Cu (single-side); no B.Cu electrical
footprints and no B.Paste component apertures. B.Cu routing/mask/drill layers remain.

No advisor/delegation, commit, merge, push, main writes, GUI, orders or vendor uploads.
Supervisor reviews/merges the workspace; assistant does not merge. Workspace028
and Bread Modular are read-only. No arbitrary raw-rail/current guarantee changes.
