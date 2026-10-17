> **Current status: PCB ROUTING SOURCE ACCEPTED — NOT RELEASED.** Canonical
> `hardware/usb-power.kicad_pcb` is the byte-exact 084 PCB
> `69a1e329e919ca0f8ddaaec38e30de119fa0d0639823c0017e1675554ff52adc` (independent
> Opus PASS, `docs/routing-review-082/REPORT.md`, HD-1 closed). Source, resources,
> hashes and release holds: `docs/routing-source-acceptance.md` and `.json`.
> No fabrication/assembly release: `jlcpcb/` exports remain STALE and are not
> regenerated. Open holds: L1 5.40 vs 5.10 mm user decision; explicit JLC inner-1-oz/
> plating/drill/unfilled-in-pad PCBA acceptance; joint/void/thermal/EMI/startup/load
> bench qualification. The older "585 tracks / 207 vias / 043 routing" inventory below
> is historical; the current routed source is 721 track segments + 251 through vias
> (972 native `GetTracks` objects, vias included). Historical
> recovery and release receipts stay frozen.

# usb-power agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/migration-recovery.md`. Paths in module instructions are module-relative.

## Accepted checkpoint (preserve, do not redesign)

Canonical sources are `hardware/usb-power.kicad_{pro,sch,pcb}` and
`hardware/usb-power-panel.kicad_{pro,pcb}`, with all six child sheets/local libraries.
They recover the latest accepted **043 / Basic-capacitor closure** from this repo's
`8f3c5000b88a09a22e3b49ce209ca87bbc9aeefe` tree, not the older 043 branch base.
107 electrical + 4 mechanical footprints; 585 tracks, 207 ordinary 0.300 mm vias,
8 zones. C5/C18 and C68-C72 use the accepted exact local 22u C12891 plan.
D10 stays DNP: footprint/pads retained, not fitted or purchased; R32 stays fitted.

Preserve circuit values, native schematic presentation/UUIDs, routing, interfaces,
LDOs, outline, stack, brackets and Basic/Economy sourcing requirements. All components
are front-side; no B.Cu electrical footprints or B.Paste component apertures.
B.Cu routing/mask/drill layers remain. Ordinary unfilled/uncapped vias, artwork-defined
mask tenting; no special fill/planarization/copper-cap process.

## Recovery/release boundaries

This migration is file/path recovery only. Do not replay circuit migration,
regeneration or routing. Native electrical/PCB repair and new fabrication export
belong to Astra's separate handoff. No claim of new fabrication exports: `jlcpcb/`
is the sole shipping-set location, currently an intact **STALE recovered snapshot**.
`production/` is retired, not an active archive; historical integrity tests use Git
objects. Read `jlcpcb/README.md` before any release work.

Shared tools/skills stay at root `../../opt/`; never copy them into this module.
Read `../../opt/kicad-tools/skills/kicad-workflow/SKILL.md`, and for sourcing/export
also `../../opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md` and shared JLCPCB docs.
Common-tool-first; inspect actual help. No stripped dependencies, weakened tests,
ignored rules, exclusions, fake power flags or hidden native findings.

Work only in the assigned isolated workspace. No advisor/delegation, commit, merge,
push, main writes, other-workspace access, GUI, orders or vendor uploads. Supervisor
reviews/merges. Bench/thermal/startup/order qualification is NOT claimed; negative
full-temperature 1 A dropout remains a disclosed FAIL, not waived by migration.
