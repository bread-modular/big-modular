# Routing checkpoint 078 — native connectivity complete; NOT RELEASED

Stopped at the user's hard batch boundary. One best physically checked PCB is retained here. Canonical hardware is untouched; no fabrication exports, GUI, advisor, commit, order or upload.

Candidate SHA-256: `23e57358417eb9d9187a7419537295b744b52e7174cbc743de4ab12b85c0735e`.
Resume source 076 SHA: `2482301aa94d465a2fd8657f95d511d8167a2dde9c58943f032694273220c340`.

## Exact final evidence
- Native DRC **23 errors (all opens) / 15 warnings → 0 errors / 0 warnings / 0 opens / 0 exclusions / 0 schematic-parity findings**.
- Native ERC **0 errors / 0 warnings → 0 / 0**; exclusions zero.
- Independent exact parity **116 refs / 344 pins / 39 explicit NCs / 1,110 schematic-owned fields PASS**, including DNP, native field identity/content, pin/net identity, hierarchy and unchanged frozen native XML identities.
- Fixed J1/J7/SW1/D10, four mounts, all outline/drawings, four-layer stack, front-only placement and no B.Paste component pads preserved. L1=C357250 and L4/L5=C207852 retained. Frozen dependencies/rules unchanged; no ignored DRC rules or ERC/DRC exclusions.
- Added **140 tracks + 36 ordinary 0.30/0.65 mm routing vias**, plus **18 exact restored original thermal vias**. Removed 28 obsolete/replaced copper UUIDs and modified eight existing tracks. Complete before/after UUID/native geometry/reason audit: `routing-ops.json`.
- Only nonfixed C5, C68, C93, R9, R15 and R84 moved. R15/C93 are now local to U3 feedback; C68 common VPROT/system-GND bulk moved beside U5, C5 adjusted for clearance. U3's NRAW local return/decoupling remains separate from system ground. All fields/parts/pin assignments unchanged.

## Copper completed
Explicit hand-routing covers NRAW distribution C71→U13 and converter bank; U3 EN/EN_LO and local FB/divider/feedforward; U14 C88 supply and C84 return; C91/C92 common protected supply and system-ground joins; C73 N12/return; +5 SW/BOOT/FB/divider/sense. PRAW pin16 feed was rerouted around restored U12 EP barrels. One obstructing RTN return was deliberately rerouted on F.Cu; RTN was never renamed GND.

Main added distribution is 1.0–1.5 mm with 2–3 parallel barrels at principal power transitions. The bounded NRAW corridor includes a **0.75 mm × 1.8 mm neck** between existing RTN/shutdown vias. +5 SW has a short 0.50 mm pin escape, 0.85 mm local trunk and 1.40 mm landing; cap returns typically 0.8–1.2 mm; quiet signals 0.25–0.40 mm. These are geometry facts, not qualified ampacity/stability/noise claims. Final power-loop/neck/return review remains required.

## Corrected ordinary-prototype thermal strategy
Restored **nine original EP vias each for U12 and U13**, exact UUID/net/position/0.30 mm drill/0.60 mm diameter/process serialization from preserved `routing-checkpoint-sr2/usb-power.kicad_pcb`, cross-checked against 075 `evidence/thermal05-audit.json` removal records. All **16 external thermal vias** remain unchanged. U12 inner spoke entries were recentered onto the exact original offset barrel; outer clearances and the one 0.50 mm spoke width remain.

Native filled-geometry evidence confirms all nine restored barrels per EP directly enter the system-GND EP and the same In1 GND region (about 2,041.98 mm²), plus local In2 GND. F.GND regions remain **25.5923 / 23.0394 mm²**, containing only four of eight external-via centers each. Original direct EP→plane paths are restored; **thermal-performance/nonregression qualification is NOT claimed**. Historical stored and final refilled comparisons are in `thermal-paths.json`.

The frozen fabrication contract permits ordinary unfilled/uncapped in-pad barrels; it does not require paid fill/cap or make these an automatic bare-fab reject. Tenting does not seal exposed-pad holes. The older 075 41-entry exposed-SMD-hole inventory remains a process-review input, not a blanket-removal instruction. This pass also records **17 new routing vias intersecting numbered SMD copper**, with exact affected refs/pads in `exact-parity.json`; none is an additional thermal-EP intersection beyond the authorized 18 restorations. Manufacturer PCBA review, prototype joint/void/wicking inspection and thermal testing remain mandatory; website information does not establish assembly acceptance.

## Integrity trap caught and repaired
The strict dependency-hash assertion caught standalone native save replacing the research companion `.kicad_pro` with defaults, including five ignored warnings and lost schematic/ERC metadata. Those early trial results and the first final check are **superseded**, not accepted evidence. Exact 075 project bytes were restored (SHA `122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9`), seven newly exposed endpoint warnings were physically repaired, then native refill/save and a fresh common full ERC/DRC/field/parity check passed under the frozen project. The final project remains byte-identical; see the restoration receipt embedded in `native-check-receipt.json` and `exact-parity.json`. No shared-tool patch or gate weakening.

## Resume without repackaging dependencies
Use 075's existing materializer with an exclusively NEW research destination, then replace ONLY the PCB with this checkpoint:

```sh
python3 -B modules/usb-power/docs/routing-progress-075/materialize_resume.py --output modules/usb-power/research/NEW-review-078
cp modules/usb-power/docs/routing-progress-078/usb-power.kicad_pcb modules/usb-power/research/NEW-review-078/usb-power.kicad_pcb
sha256sum modules/usb-power/research/NEW-review-078/usb-power.kicad_pcb
```

075 closure: `DEPENDENCIES.json` SHA `e056507eb0d7808f102186036c46688c69e8f2090e4831c2ea94ae9522b7bf6e`; `CHECKPOINT.json` SHA `f64516722696030e1a8366876a8835df461580fd33e3e04fa95c08d9f2a65ae0`. The helper's RESTORE receipt describes its original 075 PCB, not the replacement. Preserve the frozen project after any native save and independently recheck all hashes before trusting findings.

## Remaining release gates
Fresh independent Opus engineering/final approval; physical power-loop and current-neck review; manufacturer PCBA acceptance and joint/thermal/startup/load qualification; L1 **5.40 mm versus 5.10 mm** enclosure decision; explicit inner 1 oz and tighter drill/plating contract acceptance. No paid fill/cap, part, stack, tolerance, rule, exclusion or test change. No canonical promotion or fab export. Existing native/exact evidence only was preserved at the batch boundary; no new engineering is queued in this chat.
