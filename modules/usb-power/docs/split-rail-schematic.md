# SR1 schematic handoff — review required, PCB NOT synchronized

**Scope:** workspace056, schematic-only per latest steering. Supervisor starts a separate Opus schematic review, presents schematics/findings to the user, and **waits for explicit user ACK before any PCB/synchronization/routing work**. No review delegation was initiated here. No commit/merge/push, other-workspace access, GUI, orders or fabrication export.

Native root and seven child sheets, local symbol, generator, BOM and pin audit now describe SR1. **131 electrical references, 24 additions, no removed references; 397 native component pins including43 NCs.** Only7 existing pin assignments change: U4.8->GND and U4.23/D2.1/C8.1/C10.1/R12.1/#FLG06.1->POS_DORMANT. A new real rectified-source flag #FLG09 declares L5/D29 PRAW; no arbitrary power flags.

Both PCB files and project rules are byte-identical to this workspace's HEAD. No duplicate-property UUID repair was run; the24 duplicate IDs remain for the later PCB worker. A standalone TI RTE library footprint was added solely to resolve the schematic's footprint reference/ERC warning; **no board file was edited/saved, placed or routed**. PCB fit,3D model/thermal copper/vias and routing are NOT accepted. Existing footprint/model dependencies were not stripped. Old `jlcpcb/` remains the untouched **STALE** historical snapshot.

## Actual selected circuit

- CH224A requests9V; TPS26600 R8+R79+R80=6.04k (~1.986755A nominal), unchanged. Both TPS54302 bucks, independent P5, connectors/UI/panel/stack unchanged.
- VPROT -> **U14 TPS55340RTER/C169167** -> PRAW -> unchanged exact **TPS7A4700RGWR** -> P12.
- MID -> U4 TPS65131 negative channel -> NRAW -> unchanged exact **TPS7A3301RGWR** -> N12. U4 ENP8 independently grounded; ENN10 unchanged. VIN/INN only MID/filtered MID, never9V.
- L2/D2/C8/R12/R75/R13/C10/C13 and positive feedback/sense are retained on **POS_DORMANT**, passively precharged from MID, with no output port or PRAW connection. J7 parallel pins continue sharing one rail each.

| References | Exact values / parts | Purpose |
|---|---|---|
| U14 | TPS55340RTER, C169167, Extended/Economy observed | RTE16: SW1/15/16, VIN2, EN3, SS4, SYNC5 GND, AGND6, COMP7, FB8, FREQ9, reserved10/14 GND, PGND11/12/13, EP17 GND |
| L5 | MDA1040-6R8M, C2847552,6.8uH±20% | Same exact family as L1/L4;4.0mm max body height; manufacturer table Isat11A/typ12.2A >7.75A switch fault maximum; not relabeled guaranteed hot-lot minima |
| D29 | SS34, C8678, SMA,3A/40V | Anode2 SW, cathode1 PRAW; passive path remains when EN is low |
| R86 / R87 | RT0603BRD07100KL C122538 / RT0603BRD0710KL C95204 | 100k/10k, both0.1%25ppm/K; **PRAW13.519V nominal** |
| R88 / R90 | 0603WAF1003T5E C25803 /0603WAF2002T5E C4184 | Basic100k+20k frequency resistor;400.21kHz nominal |
| R89 / C86 / C87 | 470R C23179 /1u50V0805 C28323 /100p50V C0G C14858 | Basic Type-II compensation; initial1k/510R candidates exceeded14kHz screen, corrected to470R |
| C85 / C88 | 100n50V X7R C14663 | Soft start (~30ms typical) / local VIN HF bypass |
| C77–80 / C82–84 | C12891 CL31A226KAHNNNE22u25V1206 | Four local PRAW output / three local VPROT input parts |
| R14 / R60 | CPF0805B1M4E1 C4193812 /0603WAF1502T5E C22809 | 1.4M0.1%25ppm +15k Basic upper negative divider |
| R15 / R76 | RT0603BRD07120KL C705720 /0603WAF1001T5E C21190 | 120k0.1%25ppm +1k Basic lower to VREF; **NRAW-14.185083V nominal** |
| R72 / R83 / R73 / R74 | RT0603BRD0790K9L C728600 /0603WAF0000T5E C21189 /0603WAF1201T5E C22765 /RT0603BRD0710KL C95204 | 90.9k precision +0R +1.2k Basic /10k precision; **N12-11.996750V nominal**, not derated to-11.95V |
| C73 / C74 / C75–76 / C81 | C12891 | Fourth N12 output / fifth negative LDO input / two additional local U4 NRAW / local MID supplement |
| C62 |10n pads retained, **DNP** | TI TPS7A33 §8.1.4 permits operation without CFF; noise/PSRR tradeoff, not a proven cure |

All newly added/changed ordinary R/C selections are evidenced Basic+Economy except the six precise feedback refs R14/R15/R72/R74/R86/R87. R12 is an inherited seventh precision exception on the dormant channel. Live bounded records are in `split-rail-catalog.json`; historical catalog fields are not overwritten merely to update URLs.

**Additional inherited sourcing gap, not waived:** exact retained R6/C23250, C10/C501829 and C11/C519375 were freshly observed **Extended, not Basic**, although Economy eligible. Their values/MPNs/footprints remain unchanged. This revision does not claim the entire BOM is Basic compliant; disposition belongs in Opus review, not an unrequested blanket substitution. R84/R85 and R73 missing Economy observations were closed by exact live C23193/C22765 lookup, without changing their parts. No stock allocation/order/assembly-service acceptance is claimed.

## Screen results and review cautions

Reproducible independent tolerance/TCR/ref/offset/sign enumeration: `tools/split_rail_budget.py` -> `split-rail-schematic-budget.json`.

- PRAW full-ref/100K/±100nA sensitivity DC13.150..13.892V; allocated100mV dip gives **13.050V**, above the separate13.0V positive-LDO accuracy-input condition. ±100nA is not a guaranteed full-temperature TPS55340 IFB bound.
- NRAW at ±100nA: magnitude DC13.487236..14.879277V; trough13.387236V; peak**14.979277V**. Maximum N12 target magnitude12.386251V gives **1.000986V headroom: only0.9855mV reserve over1V**. At ±50nA, headroom1.071476V. These are conditional prototype screens, NOT robust guaranteed envelopes.
- VREF divider load9.6838..10.3600uA, nominal10.0248uA. TI specifies1.200..1.225V at10uA; no separate maximum-drive/load-regulation guarantee was found. Near-test loading is not proof of accuracy across that load range. No80uA divider is used.
- A bounded R60=13/15/16/18k comparison is retained.16k would balance margins, but the exact observed16k codes were Extended/Preferred Extended, not Basic. Selected15k passes the explicit screen; the tiny margin is left visible for review, not hidden by raising NRAW.
- MID peak5.418152V <5.5V. MID peak +NRAW peak +0.55V diode +2V allocated ringing =22.947429V, leaving1.052571V below24V. Ringing has not been measured.
- Combined typical DC-bias ×0.90 tolerance ×0.85 temperature ×0.95 aging ×0.83423 low-AC sensitivity: IN+/OUT+/IN-/OUT-=**11.348/20.013/12.887/12.681uF**. Positive output margin is particularly thin (13nF over20uF). U4 local NRAW7.732uF; boost local output11.348uF; boost local input13.345uF. These are **not guaranteed combined manufacturer minima**; lot/biased AC measurements remain necessary.
- TI-derived CCM model:256 corners, crossover370..13247Hz, below14kHz/RHPZ/5/fsw/10 screens; model phase margin41.5..106.2deg, not a measured stability acceptance. Uses typical15mohm current-sense/10Mohm error-amplifier resistance; C86 effective0.5..1.15uF is a sensitivity allowance. Frequency312.96..523.37kHz is scaled sensitivity, not a guaranteed120k table bound.
- **Abrupt400mA load step is NOT shown to stay within100mV**: the broad consistent CCM corner estimate reaches1.179V. Thus the DC headroom screen does not guarantee uninterrupted regulation under full-load steps. Review/bench must set slew/load-step limits and verify startup/DCM/loop response.

## Conditional power / thermal budget

7mA per raw rail, explicitly an allowance, not a guaranteed maximum. Nominal/adverse efficiencies: boost/bucks90/85%, inverter80/70%; source9/8.55V,0.15V wiring,0.25ohm eFuse,0.15W auxiliaries.1.85A is a planning allocation, not a newly guaranteed current-limit minimum.

| P12 / N12 mA (nominal output W) | Input A at P5=100mA, nominal/adverse | Input A at P5=250mA, nominal/adverse |
|---|---:|---:|
|600/0 (7.2/0)|1.164/1.359|1.265/1.484|
|800/0 (9.6/0)|1.531/1.792|1.635/**1.920**|
|0/250 (0/3.0)|0.677/0.902|0.775/1.023|
|**400/200 (4.8/2.4)**|**1.278/1.587**|**1.379/1.713**|
|500/200 (6.0/2.4)|1.461/1.805|1.565/**1.933**|
|600/150 (7.2/1.8)|1.525/**1.856**|1.629/**1.985**|

P5 nominal output is0.50/1.25W respectively. JSON includes all standalone/simultaneous input watts, eFuse allocation, LDO losses/thermal-resistance ceilings and inverter peak estimates. **+400/-200mA is only a conditional objective**, not a supply rating; high-positive priority must fit both input and actual board thermal budgets. Standalone ceilings cannot be added. No heatsink or thermal copper has been implemented in this stage.

## Startup, faults and later layout

EN follows VPROT and U12 EN remains PRAW: no active sequencer, output disconnect, monotonic rail order or synchronous shutdown guarantee. Passive L5/D29 precharge is approximately VPROT minus Vf, including when boost EN is low. The eFuse C3 remains100n; input+raw nominal bulk340uF gives~0.393A typical slew load before converter demand. Including possible P12 charging and tolerance/fast slew gives~0.952A adverse charge screen, **before running loads**. SS100n limits switching ramp, not passive inrush. Full-load startup/foldback recovery, retry/unplug, raw/output shorts, FB-open overvoltage, backdrive and negative FB/NR/OUT-to-IN absolute limits remain unmeasured. External active supplies at J7 are prohibited. D27/D28 are discharge paths, not isolation or proof of0.3V differential protection.

Later PCB worker must independently verify the new RTE local footprint/3D, front-only fit/height, critical SW/rectifier/cap loop, Kelvin FB, AGND/PGND join, ordinary0.300mm thermal vias, LDO ground copper, fixed interfaces/stack/panel and full native parity/DRC. No automatic or silent router fallback. **Do not start until Opus review and explicit user ACK.**

## Gates, commands and continuity

**11 focused tests pass**, including native all-severity ERC0 (warnings/exclusions included, ignored_checks empty), exact native XML397 pins/43 NCs, independent manufacturer-role/net checks, all131 schematic/BOM/footprint pin maps, source delta, deterministic regeneration and byte-preserved PCBs/rules/unaffected four sheets. `split-rail-schematic-receipt.json` records hashes and findings.

Shared flat-sheet inspector rejects hierarchical ports: `Only flat wire/local-label sheets supported; hierarchy, buses, global/hierarchical labels rejected`. No shared-tool modification/bypass. Existing `native_sheet_patch` and module generator implement the authorized electrical edit. Common `check --only erc` runs native hierarchy/ERC; its overall status can remain `findings` because the deliberately old PCB fails separate ref/net parity. **No PCB parity claim.**

```sh
python3 -B modules/usb-power/tools/build_project.py --schematic-only --output NEW_DIRECTORY
python3 -B -m unittest discover -s modules/usb-power/tests -p test_split_rail_schematic.py -v
python3 -B modules/usb-power/tools/split_rail_budget.py --output NEW_BUDGET.json
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power/tools/kicad-project.json --only erc --reports NEW_REPORT_DIRECTORY
```

One-shot `--split-rail-revision` is only for the pre-SR1 schematic, not replay after promotion. No full module/PCB/CAM suite was run under this narrowed scope; old integrated-release tests/assertions and `ldo_budget.py` still describe the historical043 PCB and must not be reported as current SR1 evidence. Frozen recovery/release manifests and historical proofs are unchanged. Follow the current focused test/JSON, not old receipt numbers.

Manufacturer inputs: TI TPS55340 SLVSBD4E PDF SHA256 `e579aa4fcb549eab29e889f7f6dcbd0fd88cac2647082c65f102e411c3f666ca`; TPS65131 SLVS493E SHA256 `e8360b9509047317416cfd9163a09d8cdf5c8accbd4e702ad6a43292ef48e0ed`; existing accepted Samsung exact-MPN curve. Sources: https://www.ti.com/lit/ds/symlink/tps55340.pdf and https://www.ti.com/lit/ds/symlink/tps65131.pdf. All waveform/noise/PSRR/thermal/loop/start-stop qualifications remain open.

## Final native schematic images

- [root](/uploads/b150b8c7-7074-4af3-9345-ede267962f52.webp)
- [boost](/uploads/5cf1f000-c119-414e-93a3-c46bb756884b.webp)
- [negative](/uploads/a0da7486-7d9c-4f6c-a57e-1cd78e9a0eed.webp)
- [quiet](/uploads/694020bc-6912-4a4d-9670-4dddc6ed810c.webp)
