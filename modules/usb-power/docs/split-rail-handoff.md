# Split-rail revision — BLOCKED / NOT IMPLEMENTED

Main-derived workspace 050; base `26306b089fbd9207a83ad69c4157fb701266ade5`.
**No native hardware, libraries, BOM, generators, rules, baseline assertions or
shipping files changed.** This is an admission/baseline handoff, not a completed
split-rail source revision. `jlcpcb/` remains its untouched STALE historical snapshot.

Supervisor now assigns bounded shared-resource dependency support to Sol, then a
fresh implementation context. Opus is also permitted for KiCad. No shared-opt
changes, dependency removal/bypass, advisor, delegation, commit/merge/push, GUI or
vendor upload was performed. Initial discovery accidentally listed sibling AGENTS
paths; no sibling file contents were read/copied. Engineering inputs were current
workspace main and the focused main handoffs, never the paused passive workspace.

## Exact admission failure and independent environment issue

```sh
python3 -B opt/kicad-tools/kicad_tools.py pcb inspect --config modules/usb-power/tools/kicad-project.json
```

Actual stdout:

```json
{"schema_version":1,"status":"error","error":"3D models, embedded files and images are unsupported dependencies; fail closed","accepted":false}
```

`opt/kicad-tools/automation/api.py:90`, `_closure()`, rejects `model`,
`embedded_files`, and `image` nodes in PCB/footprint dependencies. This blocks the
**common PCB edit admission path**, not native KiCad ERC/DRC. Planning/application
use this closure too. Models/assets/rules must be preserved in the shared fix.

Independent issue: `tools/release_hro.py --help` fails through
`check_hro_cam.py:10`, `ModuleNotFoundError: No module named 'gerbonara'`.
Both pinned `gerbonara==1.6.3` and `shapely==2.1.2` are absent; see
`tools/cam-requirements.txt`. This affects CAM/release and three existing tests,
**not core native checks**. No installation or test/dependency removal attempted.
Inherited pcbnew `PROPERTY_ENUM(): No enum choices defined` diagnostics remain
visible but did not prevent baseline native/mechanical verification.

## Actual fresh baseline findings — unchanged 043 hardware ONLY

- Common check: `no_findings_in_requested_checks`, source unchanged, errors `[]`.
  ERC **0**, DRC **0**, opens **0**, schematic parity **0**, including warnings,
  exclusions, all-track-errors and refill-in-memory. Exact XML/PCB ref/pin/net equal.
- Independent source verifier passes **107 components, 334 native pins including
  43 NCs, 642 PCB/BOM/schematic field comparisons**. Freshly executed existing
  budget retains the **0.178019 V negative headroom FAIL**; no old saved
  `dc-budget.json` was treated as fresh, and no bench symptom was diagnosed.
- Full project verifier exit **0**: electrical/physical/mechanical/front-side/
  stack/access/routing checks pass. Carrier **111 footprints (107 electrical +4
  mechanical), 585 tracks, 207 ordinary 0.300 mm vias, 8 zones, 0 backside parts**.
  Panel has six mechanical footprints, no routes/zones; separate native panel
  DRC **0 violations /0 opens**, all severities.
- Entire module suite: **114 run, 111 pass, 3 import errors, 0 assertion failures/
  skips**. Failing methods: `test_drill_precision_is_bounded_and_dropped_slot_rejected`,
  `test_gerbonara_region_attribute_adapter_preserves_geometry`,
  `test_open_outline_rejected_by_actual_CAM_checker`; all missing Gerbonara.
- Fresh baseline top render inspected, **not a new layout**:
  `/uploads/2b0e2bba-474b-486b-a0ba-ed59e7849f01.webp`.
  Native seven-page SVG export succeeded, but no new-design visual acceptance.

Raw results: `research/split-rail/`. Persisted compact results, source/artifact
hashes and conditional arithmetic: `docs/split-rail-blocker-evidence.json`.

## Numeric design plan and what is NOT yet selected

Architecture: unchanged CH224A 9 V / TPS26600 **6.04 kohm, 1.986755 A nominal**;
no 3 A increase. VPROT directly → **TPS55340RTER / C169167** → PRAW → exact
TPS7A4700RGWR. Existing MID TPS54302 → TPS65131 negative → exact TPS7A3301RGWR.
Independent TPS54302 P5 unchanged; preserve P12/N12/P5 and shared J7 pins.

TPS55340 RTE mapping: SW **1/15/16**, VIN **2**, EN **3**, SS **4**, SYNC **5**
to GND, AGND **6**, COMP **7**, FB **8**, FREQ **9**, reserved **10/14 grounded**,
PGND **11/12/13**, EP to AGND. Fresh common catalog: Extended, independently
Economy eligible; no stock/order promise. Local footprint/model integration NOT done.
Source: https://www.ti.com/lit/ds/symlink/tps55340.pdf

**Positive value-level planning choice: 13.924570 V**, upper **10k+330 ohm**, lower
**1k**, targeting Basic parts; exact resistor sourcing not yet audited. Independent
1%/100ppm/100K factors `[0.9801,1.0201]`, TPS55340 reference **1.204–1.254 V**,
±100nA sensitivity, ±0.100V ripple/transient allocation give trough/peak
**13.052617 /14.837547 V**. ±100nA is a sensitivity, NOT a guaranteed full-temperature
bias bound: TPS55340 specifies 20nA max only at25C. This is the lowest inspected
small network retaining a separate50mV planning reserve over13V, not a global optimum.

**Reject 12.8V:** even ideal nominal is below `12.300+0.450+0.100=12.850V`.
Separately TPS7A4700 ±2.5% accuracy requires VIN>=VOUT(nom)+1V=**13V**, not merely
passing the dropout test. Candidate has0.752617V headroom to12.300V, but only
52.617mV over that accuracy-input condition. Effective positive COUT>=20uF including
AC sensitivity must be checked; allocations are not guaranteed ripple bounds.
Source: https://www.ti.com/lit/ds/symlink/tps7a47.pdf (electrical table).

**Negative exact setpoint remains UNRESOLVED.** Trial raw upper150k precision+24k
Basic / lower15k precision (+0..0.1ohm link), with final upper90.9k precision+1.2k
Basic (+link) / lower10k precision: raw nominal14.0708V, DC13.474297–14.664960V;
final11.611808–12.386251V. At±100nA raw-FB sensitivity, headroom after0.1V dip is
**0.988046V: reject against the1V screen**. Precision factors were
`[0.9965025,1.0035025]`; no exact precision parts or exception approval claimed.
Do not install this trial or simply raise NRAW. Close lower-impedance feedback,
raw peak<15V, MIDpeak<5.5V and switch differential<24V with explicit ringing margin.

Keep U4 ENP grounded independently of ENN; retain disabled-positive LC/diode/FB/cap
on an isolated precharged node, never PRAW. VIN/INN remain MID; PSN/PSP unchanged.
C62 DNP is a diagnostic option, not a claimed cure. Plan minimal C12891 additions
at U13 OUT/IN and local U4 after DC/AC/temp/tolerance screening. No actual parts/
placements changed. No inductor/diode/compensation/frequency/EN/SS selection is final.

## Conditional power/thermal estimates — NOT implemented ratings

Positive uses the value-level plan above. Negative **14.2V nominal/14.9V adverse
are budget allocations, NOT a selected divider**. Efficiencies: boost/bucks90/85%,
inverter80/70%; source9/8.55V, wiring0.15V, hot eFuse0.25ohm, auxiliaries0.15W.
**7mA overhead per raw rail**: replaces old positive2mA allowance because TPS7A47
lists6.1mA typical at1A; neither overhead is a guaranteed full-temperature maximum.
All rows reserve **P5=100mA /0.5W**. 1.85A is an illustrative allocation, not a
new guaranteed eFuse minimum.

| +12/-12 mA | + / - output W | Input A nominal/adverse | Assessment |
|---|---|---|---|
| 800/0 |9.6/0|1.576/1.899|standalone adverse allocation fails|
| 0/250 |0/3.0|0.678/0.898|input fits; inverter/thermal unqualified|
| 400/200 |4.8/2.4|1.300/1.636|conditional simultaneous planning point|
| 800/150 |9.6/1.8|1.948/2.412|aspiration unaccepted; nominal already >1.85A screen|

+800mA positive-LDO loss **1.637/2.614W**, requiring effective theta<=**45.8/28.7C/W**
at50C ambient/125C junction boundary, before margin. +400mA: **0.867/1.359W**,
theta<=**86.5/55.2C/W**. No EP copper/via thermal improvement was made/measured.
Converter/eFuse heat, enclosure coupling and X5R<=85C remain separate limits.
Standalone limits cannot be added. Full-load startup/precharge/EN/eFuse retry and
shutdown/backdrive remain unclosed; this arithmetic proves no sequencing guarantee.

## Exact continuation commands / remaining scope

Commands already run; continuation must choose NEW report directories:

```sh
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power/tools/kicad-project.json --reports modules/usb-power/research/split-rail/baseline-native
python3 -B modules/usb-power/tools/verify_ldo_source.py --reports modules/usb-power/research/split-rail/baseline-native --output modules/usb-power/research/split-rail/baseline-independent.json
python3 -B modules/usb-power/tools/verify_project.py --netlist modules/usb-power/research/split-rail/baseline-native/netlist.xml --output modules/usb-power/research/split-rail/baseline-project.json
python3 -B -m unittest discover -s modules/usb-power/tests -v
```

After shared admission is fixed, fresh implementation still owns exact sourcing,
inductor fault saturation (TPS55340 max switch limit7.75A, not existing4.97A-Isat
part), diode, local caps, compensation/frequency/EN/SS/inrush, negative correction,
schematic/library/3D/BOM/generator/test synchronization, manual critical routing,
EP thermal spreading, and new native/independent gates. Preserve front assembly,
ordinary0.300mm unfilled/uncapped vias, B.Cu routing, mechanical envelope, D10 DNP,
R32 fitted/no D11/D12. No current contract was rewritten to pretend implementation;
authorized topology changes supersede migration-only preservation when actually
made, while frozen receipts stay intact. Release/CAM remains a separate fresh chat
using the existing pipeline. No new source, bench, thermal or order qualification.
