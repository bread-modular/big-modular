# usb-power-45w — manufacturing export (S9.5 / R4, second prototype)

Re-exported on 2026-11-26 from the S9.5 schematic and the R4 board with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter (user: "Export for JLC"). Against the S9.4 / R2 set this export has:

- **No D10** (SS1060 input blocker; it ran hot in the first-board load test) and no TP3: U5 IN sits on the VPD pour
  ([`docs/design.md`](../docs/design.md) S9.5 / R3).
- **U2 thermal copper** (R4): 24 more vias by U2 and its caps, the B.Cu GND pour under U2 grown 493 -> 650 mm²
  ([`docs/routing/README.md`](../docs/routing/README.md) R4).
- **Three pre-order parts swapped** for in-stock ones (fields only, same land, pins and function; see Parts below).
- **Zones refilled** before the export: the saved R4 fills were one refill short of converged (+4.75 mm² on four pours
  around U2; a second refill is byte-identical). No other board change.
- **`min_through_hole_diameter` 0.2 -> 0.3 mm** in the project (root `AGENTS.md` holes rule); DRC still 0.

This is a complete prototype export, **not a supplier-accepted release** and not bench-qualified.
Never hand-edit these files: change the sources, then re-export with the commands below.

History: S9.4 / R2 export 2026-11-16 (CH224A supply limiter removed); R1 generated 2026-11-06. Both are in git history.

## Contents

| Path | Data |
|---|---|
| `usb-power-45w-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `usb-power-45w-panel-gerbers.zip` | 4HP FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (F.Cu, In1 GND, In2 VIN/+3V3, B.Cu, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in `carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `usb-power-45w-gerbers.zip` | 4 layers, FR4, 1.6 mm, 100.5 x 48.0 mm, JLC standard stack-up JLC04161H-7628 (the board's stack-up), 1 oz outer / 0.5 oz inner, HASL, **tented vias** (all 337 are 0.3/0.6 mm through vias, none in a pad; no POFV, no resin fill). **Smallest hole 0.3 mm** (PTH drill file T1, the vias): no small-hole surcharge. No `JLCJLCJLCJLC` marker: pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Top side only.** 148 parts in 59 BOM rows, every row with LCSC, MPN and manufacturer. J1 (USB-C, SMD pins + 4 THT shell lugs) is in the CPL and must be machine-fitted |
| Front panel PCB | `usb-power-45w-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 20.0 x 128.5 mm (4HP), no copper, no assembly; 6 NPTH holes plus the USB-C aperture in the outline |

### Hand-fitted after delivery (BOM rows, not in the CPL)

| Refs | Part | Note |
|---|---|---|
| J2, J3 | Wurth 61201021621, 2x5 shrouded IDC header, 2.54 mm | Front-side THT, two parallel outputs. Pin 1/2 = -12 V (`1 / -12V / RED` silk and the key), 3-8 GND, 9/10 +12 V |
| D8 | 3 mm red LED (MAIN), owner stock | Front-side THT, leads formed 90° so the lens sits in the panel hole (axis 2.0 mm above F.Cu); form it in a jig with the panel |

J2/J3/D8 carry `in_pos_files no` in the schematic (`tools/build_s8.py` `NOT_PLACED`) and
`exclude_from_pos_files` on the board, so the exporter drops them from both CSVs
(`carrier/export-report.json`, `excluded`). The 25 test pads (TP1-TP30) are copper only.

## Parts (live catalog, 2026-11-26 12:52-12:54 UTC, 5 boards)

Read-only public lookup with the shared auditor, every code with `--strict-live` (`research/export-r4/audit2/`, ignored;
raw responses in `cache/`, table in `free-stock-2026-11-26.json`). The whole-design audit `docs/design/sourcing.json`
was re-run live the same day (no failures, no missing / zero-stock / unpriced code).

- **59 codes / 148 placements: 32 Basic, 27 Extended** (one setup fee each), all Economic-eligible
  (`componentProductType` 0). Extended R/C, as in the S9.2 policy: R2 C122538, R3/R94/R98 C95204, R93/R99 C860071
  (0.1 % divider resistors) and R109 C393095 (18 mΩ Kelvin shunt).
- **No pre-order part** (root `AGENTS.md`): for every code the free stock `canPresaleNumber` is >= placements x 5 +
  the catalog's attrition (`lossNumber`) and `minPurchaseNum` is 1.
- **Three codes swapped for this export** because they were pre-order only (fields changed in `tools/circuit_s8.py`
  `R0603_01` / `S95_SOURCING`, the schematic regenerated and the same fields set on the board footprints; no copper,
  pin or net change, ERC / DRC / parity unchanged, `verify_s8.py` validation identical):

  | Refs | Was (pre-order) | Now | Why it is the same part |
  |---|---|---|---|
  | R93, R99 | C326736 YAGEO RT0603BRD07110KL (listed 2,660, free -137, minimum 293) | **C860071 YAGEO RT0603BRB07110KL** (free 4,491, min 1) | Same RT series, 110k 0.1 %, 0603; 10 ppm/°C instead of 25 (tighter) |
  | U10, U11 | C19653 TI TPS3808G01DBVR (listed 1, free -291, minimum 26) | **C702161 TI TPS3808G01DBVT** (free 30, min 1) | Same TI device and SOT-23-6 (DBV), 250-piece reel instead of 3000 |
  | U15 | C7836 TI SN74LVC1G17DBVR (listed 30, free -2,296, minimum 67) | **C151394 Diodes 74LVC1G17W5-7** (free 464, min 1) | Single Schmitt buffer, 1.65-5.5 V, SOT25 = SOT-23-5; pins 1 NC, 2 A, 3 GND, 4 Y, 5 VCC (Diodes DS35124 Rev. 7-2, page 1), the TI DBV pinout |

- **Lowest free stock, recheck right before ordering:** U10/U11 TPS3808G01DBVT C702161: **30** (needs 10 for 5
  boards), U15 C151394: 464, SW1 TL3340AF160QG C2886925: 670, U9 TPS7A1633 C181239: 900, U14 SN74HC20 C2867684: 1,131.
  Stock is a dated observation, not a reservation.

The audit exits non-zero, as for the other modules: its only failure is the exporter's generic "not a DRC or assembly
approval" warning, which it never waives. That is expected, not a catalog failure.

## Source identity

Taken from `source-sha256.json` (kicad-cli 10.0.8); the shared `check` re-hashes them and fails on drift.

- Carrier PCB `ad220172ef138775864c1eff32493d8413ee84a593f3f74090e5b09e161befae`.
- Carrier project `432eb5245f251b6e66562b52bd39ede036f448231277c4b3e1dd6cc3aa71525e`.
- Root schematic `2935b62a0c9f1ef4a41a0639339b993bcaaca55397d2b17c8f36261dce4a261a` (+ five sheets; the swapped
  parts are on `04_fault_reset.kicad_sch` (U10, U11, U15) and `05_outputs_status.kicad_sch` (R93, R99)).
- Panel PCB `ce77533392472726fd9ddf08db1a1aab53a8648c25dd9a7890b3a8b45fd9820f` (unchanged).
- Panel project `6fb70c36157f4e827990f7ca0fea610b02d36e1849cad032b590d9ed15ddea90` (unchanged).

## Reproduce

From `modules/usb-power-45w`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-power-45w --schematic usb-power-45w.kicad_sch \
  --include-through-hole --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/usb-power-45w-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board usb-power-45w-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/usb-power-45w-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/usb-power-45w-gerbers.zip jlcpcb/panel/usb-power-45w-panel-gerbers.zip jlcpcb/
```

`--include-through-hole` is needed for J1 (its footprint type is through-hole because of the shell
lugs; marking it SMD raises a native `footprint_type_mismatch` warning). Delete the unpacked Gerbers
first if layers change. The catalog audit is:

```sh
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --bom modules/usb-power-45w/jlcpcb/carrier/bom.csv \
  --cpl modules/usb-power-45w/jlcpcb/carrier/positions.csv \
  --export-report modules/usb-power-45w/jlcpcb/carrier/export-report.json \
  --boards 5 --side top --strict-live --max-requests 64)
```

## Checks done for this export

- **Shared `check`** after the re-export (`research/export-r4/native-final/`, ignored): ERC 0 errors, 4 warnings (KiCad
  10.0.8 `same_local_global_label` on power symbols, also on the S9.4 tree; not from this change); DRC 0 violations,
  0 warnings, 0 exclusions, **0 unconnected**, schematic parity 0, exact ref/pin/net parity; manifest equal
  (10 sources, exports byte-identical). 176 refs / 80 nets; D10 and TP3 are in neither the BOM nor the CPL.
- **Zones:** refilled natively and saved before the export; a further refill is byte-identical. In1 GND one piece,
  In2 VIN (+ its finger zone) and +3V3 one piece each, no track on In1.
- **Vias:** 337, all 0.3/0.6 mm, tented; none in or touching an SMD pad (pcbnew check + `tools/check_s8_board.py`).
  `check_s8_board.py` fails the same five contract items as R4 (`min_widths`, `thermal.R109.force_copper`,
  `thermal.U2.In1`, `thermal.U2.VIN_area`, `thermal.U2.VOUT_area`), reviewed as acceptable for this prototype, not waived.
- **Carrier drill:** PTH 337 x 0.3 (vias) + 20 x 1.1 (J2/J3) + 2 x 0.9 (D8) + 4 plated 0.6 mm slots (J1 shell
  lugs); NPTH 2 x 0.65 (J1 pegs), 2 x 0.9 (SW1 pegs), 2 x 3.2 (M3 bracket holes). **Smallest tool 0.3 mm.**
- **Panel:** sources unchanged, native DRC 0 / 0. NPTH 4 x 3.2 (rail and bracket holes), 3.2 (RESET), 3.6 (MAIN LED);
  the USB-C aperture is an Edge.Cuts cut-out. Printed panel (`panels/front-cad/`) regenerated headless: same STL,
  checks pass (STEP / FCStd differ only in their timestamps, left at the committed files).
- **BOM/CPL:** 148 parts, 59 rows, every CPL row `top`; no missing part number.
- **Tests:** `python3 -B -m unittest discover -s tools -p 'test_*.py'`: 79 run, the same two accepted failures as R3/R4
  (`test_plane_vias_widths_and_cleanup`, `test_placement_rules`; `research/export-r4/s96/tests-final.log`).
- **Edge / hand-solder:** no part moved since R2: no copper within 1.0 mm of the edge except the user-approved J1/SW1
  front lugs (0.55 mm rule); courtyards >= 1.355 mm (L3) except the approved J1/SW1/D8 panel overhangs;
  every SMD pad >= 2.01 mm from the J1/D8/J2/J3 hand-solder pads.

## Status and order gates (not done here)

1. **Placement preview** in JLCPCB's top view, every rotation, and in particular: J1 (the KiCad anchor
   is the receptacle front lip, 3.7 mm forward of the body centre: check that JLCPCB's model lands on
   the pads), U2 (VQFN-HR-21, pin 1 and the bar orientation), U1 (ESSOP-10), U4 (SO-PowerPAD-8), U5
   (HTSSOP-20), U9 (HVSSOP-8), U10/U11 (SOT-23-6), U12-U14/U18/U20 (SOIC-14), U15 (SOT-23-5, now the
   Diodes part: pin 1 on pin 1), U21, Q1, Q4-Q16 (SOT-23), the cathode bands of D1/D2/D4/D24/D26 and
   D15/D22/D25/D27/D28, SW1.
2. **Edge rails:** J1 overhangs the front edge by 1.2 mm and parts sit 1.3-2 mm from the edges; accept
   JLCPCB-added rails if the assembly review asks for them.
3. **Live recheck** right before ordering: free stock and minimum purchase (U10/U11 C702161 first: 30 free), class, attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench (post-prototype acceptance tests in `docs/design/routing-notes.md` section 2):** S1-S4
   start-up on a strict 3 A PD source, TH-1 (U2/R109), TH-2 (U5 at 3 A input; D10 is gone), TH-3 (U4), CC-1,
   KS-1, IN-1..IN-3, CL-1, EMI-1, HDR-1. The copper/thermal contract items still open in
   `tools/check_s8_board.py` are listed in `docs/routing/README.md`; they were reviewed as acceptable
   for this first prototype, not waived.
