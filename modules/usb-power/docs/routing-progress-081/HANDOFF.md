# Focused PCB checkpoint 081 — native clean, NOT RELEASED

Candidate SHA-256: `4e4f19a16956be529fd3b08f75de34ff992bf712747fe9da94c303b5080a77db`.
Source: exact 078 `23e57358417eb9d9187a7419537295b744b52e7174cbc743de4ab12b85c0735e`, restored using 075's existing materializer into new `research/focused-081`, then replacing only its PCB. The corrected 080 report and actual pad coordinates were used; the withdrawn pin map was not used.

One PCB plus compact audit/receipts is retained. No schematic/circuit/part/rule/test/exclusion/stack/fixed-mechanical change; no canonical promotion, fabrication exports, GUI, advisor, commit, orders or vendor uploads. The interrupted response had already completed the physical edits; recovery reused and rechecked that candidate rather than replaying mutations.

## Native and independent checks

- Fresh all-severity native ERC: **0 errors / 0 warnings / 0 exclusions**.
- Fresh native DRC with refill, all-track-errors and schematic/field parity: **0 errors / 0 warnings / 0 opens / 0 exclusions / 0 parity findings**. The source 078 baseline was also zero throughout.
- Independent native XML/PCB comparison: **116 refs / 344 pins / 39 explicit NCs / 1,110 schematic-owned fields**, including DNP C93/C62/D10. Field UUID/name/text, pad UUID/pin/net, symbol paths and hierarchy preserved; fresh recovery XML semantics match the earlier final and source XML.
- Every 075 dependency remains byte-identical, including project SHA `122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9`. No ignored rule severities or ERC/DRC exclusions. Native save was followed by exact project restoration/hash assertions before trusted checks. Final refill/save itself did not change this project hash.
- Fixed J1/J7/SW1/D10, four mounts, all drawings/outline, setup/layers/stack and zone definitions preserved. All components front; no B.Paste component pads. L1=C357250 and L4/L5=C207852 unchanged.

## R1 — actual boost hot loop

U14 remains TPS55340RTER: SW 1/15/16; PGND 11/12/13; EP17 at (129.80,84.40), all ground pins on the existing `/GND` net.

The new cell uses D29 at (131.40,78.00), 180 degrees, and C78 at (132.10,81.10), 180 degrees. D29.2 is SW at (129.40,78.00); D29.1 is PRAW at (133.40,78.00). C78.1 PRAW is (133.575,81.10); C78.2 GND is (130.625,81.10). Diode polarity, capacitor identity/value and all pin nets are unchanged.

Explicit external copper legs, verified by native pad/track containment:

- U14.15 (129.55,83.00) -> (129.55,82.20) -> (129.20,81.85) -> (129.20,79.20) -> D29.2. Short 0.24 mm lead neck, 0.45 mm escape and **1.0 mm local SW trunk**; L5 feed is 1.2 mm F.Cu. U14.1/.16 are joined on F.Cu.
- D29.1 -> C78.1: **3.105 mm, 1.2 mm F.Cu**, no vias.
- C78.2 -> (130.55,82.00) -> U14.13: **1.903 mm, 0.5 mm F.Cu**. Parallel 0.8 mm local return reaches U14.12; U14.11 and AGND/EP have direct same-layer connections.
- Remote PRAW bank distribution branches only after C78's local output terminal; its via transitions are not in this selected local commutation path.

The corrected 080 report quoted approximately 42.9 mm² / 30.6 mm. Re-measuring explicit, recorded copper-contained paths consistently gives **43.0675 -> 15.42875 mm²**, **31.16254 -> 18.11958 mm**, and **four -> zero via-group transitions**. This is about **64% less projected area** and **42% less projected length**, all F.Cu external copper. **The aspirational <10 mm² target was not reached.** This is not a claim of optimal placement; fixed retained package/courtyard spacing and the bounded batch constrained this attempt.

Area is a planar projection with declared straight component pad-to-pad and internal-chip closures; it is not a fabricated graph-area result, simulated current distribution or inductance measurement. Through-board Z lengths are excluded from both projections. Full vertices/method are in `exact-parity.json`.

## R2 — sense and In1 return

Removed In1 sense UUIDs `31bbfd34` and `fcc10d1c`. R86 now senses the local C78 output through a **1.1 mm / 0.8 mm F.Cu landing**, then **0.25 mm In2.Cu** from (133.575,82.20) through (134.30,82.925) to (134.30,83.20), then the existing F.Cu route to R86.1. This is Kelvin-like at local Cout; the short landing also carries remote distribution, not a wholly independent four-wire tap.

The new local C78.2-to-U14.13 return is inside the same refilled In1 GND island at **41/41 samples**. The removed sense no longer cuts that return. Do not mistake this for a claim of an entirely hole-free old remote diagonal: the old diagonal still has 4/41 samples outside fill at other copper clearances, now away from the local loop. R86/R87/R89/C86/C87 and 18 quiet-network/ground-return copper UUIDs remain exact, including the separate ground transition at (132.00,90.00).

## R3 — two fine-lead dogbones

- U3.5 NINV_EN via `f73a597f`: (133.60,97.10) -> **(131.95,96.64)** on ordinary under-body land. F escape **1.227 mm x 0.30 mm**; hole-to-original-lead copper edge gap **0.351 mm**.
- U5.2 FIVE_SW via `c367cdcc`: (106.8625,95.15) -> **(105.95,95.15)**. F escape **0.9125 mm x 0.50 mm**, then existing 0.85 mm SW trunk; hole-to-lead copper gap **0.100 mm**.
- Both remain ordinary **0.30 mm drill / 0.60 mm diameter** vias. Neither hole intersects any numbered SMD pad. Only these two selected barrel diameters were reduced for local clearance, not a global resizing policy. Nearby U5 NRAW copper was shifted while retaining 1.5 mm width and P5 sense detoured on B.Cu as required for clearance.

## R4 — U14 EP thermal geometry

Added four ordinary GND vias, **0.30 mm drill / 0.60 mm diameter**, on a 0.80 mm-pitch square: x=129.40/130.20, y=84.00/84.80. They fit inside the unchanged 1.68 mm EP with **0.14 mm minimum annulus-to-square-pad-edge margin**. Each annulus perimeter (64 native samples) is inside both EP copper and the **same refilled In1 GND island, 2,045.478 mm²**. Nearest foreign-copper clearance across the four barrels/layers is **0.454 mm on F.Cu**, and at least **1.3069 mm on the inner/back layers**; full native DRC additionally checks every layer/rule. Local In2/B GND fill is not claimed at these barrels.

All **9 original EP + 8 external vias per LDO** are retained by exact native serialization and explicit UUID identity, not radius-based guesses. Twelve vias were added overall (four EP + eight routing), nine removed, four relocated; all newly added drill/SMD intersections are the four authorized U14 EP holes, none a fine lead.

TI recommends thermal vias under the PowerPAD to internal GND and direct same-layer ground connections. Its package example uses 0.2 mm holes and recommends filling/plugging/tenting under paste; this 0.30/0.60 mm prototype adaptation is **not** exact replication or a sealed-hole claim. [source](https://www.ti.com/lit/ds/symlink/tps55340.pdf)

The existing prototype contract permits ordinary unfilled/uncapped EP vias. No paid fill/cap was enabled; tenting applies only where mask artwork permits and does not seal exposed EP holes. Manufacturer PCBA acceptance, wicking/void/joint inspection and bench thermal performance remain unqualified.

## F2 — actual drill gap

Moved only EF_MODE via `687cf235` from (79.40,87.475) to (79.25,87.475), updating its attached endpoints. OV_SET `ee0541ca` at (79.85,86.825) is unchanged. Actual circular-hole edge gap **0.490569 -> 0.584590 mm**. Independent whole-board different-net hole audit minimum is **0.553302 mm**, with **zero pairs below 0.50 mm**. No rule was weakened and no other component in this cell moved.

## Audit and handoff

Only nonfixed **D29, C78, C84, R88, R90** changed placement. `routing-ops.json` records 53 added / 51 removed / 12 modified tracks, 12 added / 9 removed / 4 modified vias, and the five footprints, with UUID/net/geometry/reason/hash pairs. Shared inspect/plan/apply was attempted first: the EP-only common apply correctly rejected four newly exposed endpoint warnings. The user-authorized narrow native exception used unchanged shared `validate/perform` for supported operations and pcbnew only for unsupported existing-via/track-endpoint updates; those warnings were physically corrected. No forked tool or patched gate.

See `native-check-receipt.json`, raw `after-erc.json` / `after-drc.json`, `exact-parity.json`, `physical-audit.json`, and `RESTORE.md`. Temporary operations, diagnostics and PNG renders remain under ignored `research/`; no dependency repackaging.

Private render previews (PNG source rendered with existing KiCad CLI; chat transcodes to WebP): [top](/uploads/81ba71ac-b84e-46f6-9aa0-07fd5f8c65e6.webp), [boost close-up](/uploads/90acbb50-2080-4f5e-9689-f65f7090f191.webp). Unmodeled package bodies are not absent parts; renders are not mechanical qualification.

## Remaining release conditions

**NOT RELEASED / not JLC-ready.** Fresh independent Opus delta review remains pending and was not invoked in this no-advisor run; reviewers must use the final SHA above and assess the actual 15.43 mm² loop, short shared Cout sense landing and ordinary EP process. L1 **5.40 vs 5.10 mm** enclosure decision remains with the user. Explicit inner-1-oz, plating, drill/tolerance and unfilled-in-pad PCBA service acceptance, plus thermal/EMI/startup/load and EP-joint bench qualification remain mandatory. These holds did not prevent the PCB-resolvable changes above. No canonical promotion or fabrication export is authorized by this handoff.
