# usb-power-45w — manufacturing export (S9.4 / R2, second prototype)

Re-exported on 2026-11-16 from the S9.4 schematic and the R2 board with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter (user: "Do the JLC export"). R2 removes the CH224A supply limiter
(Q2/Q3/R23/R27/D9/D11, TP2): on the first S9.3-10P / R1 board Q2 (BCX53, SOT89) had emitter and base swapped on its land
(Nexperia numbers the leads 3-2-1), so the CH224A never got its supply and the board stayed at 5 V. U1 and C1 now sit
straight on VPD, as in the WCH reference and as the bench-proven TP1-TP2 wire on the R1 board
([`docs/design.md`](../docs/design.md)). A board built from the R1 export works with that wire and a re-plug.
This is a complete prototype export, **not a supplier-accepted release** and not bench-qualified.
Never hand-edit these files: change the sources, then re-export with the commands below.

R1 history: generated 2026-11-06, re-exported the same day after D1 SMBJ22A was re-sourced to Littelfuse C224015.

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
| Carrier PCB | `usb-power-45w-gerbers.zip` | 4 layers, FR4, 1.6 mm, 100.5 x 48.0 mm, JLC standard stack-up JLC04161H-7628 (the board's stack-up), 1 oz outer / 0.5 oz inner, HASL, **tented vias** (all 314 are 0.3/0.6 mm through vias, none in a pad; no POFV, no resin fill). No `JLCJLCJLCJLC` marker: pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Top side only.** 149 parts in 60 BOM rows, every row with LCSC, MPN and manufacturer. J1 (USB-C, SMD pins + 4 THT shell lugs) is in the CPL and must be machine-fitted |
| Front panel PCB | `usb-power-45w-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 20.0 x 128.5 mm (4HP), no copper, no assembly; 6 NPTH holes plus the USB-C aperture in the outline |

### Hand-fitted after delivery (BOM rows, not in the CPL)

| Refs | Part | Note |
|---|---|---|
| J2, J3 | Wurth 61201021621, 2x5 shrouded IDC header, 2.54 mm | Front-side THT, two parallel outputs. Pin 1/2 = -12 V (`1 / -12V / RED` silk and the key), 3-8 GND, 9/10 +12 V |
| D8 | 3 mm red LED (MAIN), owner stock | Front-side THT, leads formed 90° so the lens sits in the panel hole (axis 2.0 mm above F.Cu); form it in a jig with the panel |

J2/J3/D8 carry `in_pos_files no` in the schematic (`tools/build_s8.py` `NOT_PLACED`) and
`exclude_from_pos_files` on the board, so the exporter drops them from both CSVs
(`carrier/export-report.json`, `excluded`). The 27 test pads (TP1-TP30) are copper only.

## Parts (live catalog, 2026-11-06 06:51 UTC, 5 boards; R1 BOM, not re-run for R2)

Read-only public lookup with the shared auditor (`research/fab254-05-d1/audit/`, ignored):
64 codes / 155 placements (R1), every code resolves to its MPN and package and is Economy-eligible.
C1623 (C85, 470n) needed the MPN search (its short code prefix truncates the exact lookup):
Basic, 1,072,190 in stock, 06:49 UTC (`docs/design/sourcing.json`, whole-design live audit 06:48–06:51 UTC).

- R2 drops four codes (BCX53 C47787, SMAZ24-13-F C155317, 33R C23140, 10k 1206 C17902) and one placement each
  of MMBT3906 C53444 and SS34 C8678: 60 codes / 149 placements. The class split below is the R1 count.
- **34 Basic codes**, **30 Extended** (one setup fee each). Extended R/C, as in the S9.2 policy:
  R2 C122538, R3/R94/R98 C95204, R93/R99 C326736 (0.1 % divider resistors) and R109 C393095
  (18 mΩ Kelvin shunt).
- **D1 SMBJ22A is Littelfuse C224015** (Extended, Economy-eligible, 1,947 in stock), replacing RUILON C10214
  (59 in stock). Same MPN, DO-214AA, on the same `D_SMB` land as the Littelfuse D24/D26. Littelfuse
  datasheet (rev. JC.07/04/25 v4): VR 22 V, VBR 24.4–26.9 V at 1 mA, VC 35.5 V at 16.9 A, IR 1 µA. These are
  the rows the calculations already used. Its minimum pads (2.16 x 2.26 mm, gap ≤ 2.74 mm) fit the 2.5 x 2.3 mm
  pads with a 1.8 mm gap, and the cathode band is on pad 1 (VPD). C10214 stays a valid fallback.
- **Lowest stock, recheck before ordering:** U9 TPS7A1633 C181239: 406, U10/U11 TPS3808 C19653: 613,
  L1 SLO1040H6R8MTT C207852: 719, U5 TPS16630 C1849461: 904, SW1 TL3340AF160QG C2886925: 1,410.
  Stock is a dated observation, not a reservation.

The audit exits non-zero, as for the other modules: there is no requirements/review file, so the
per-part review rows stay `unknown`. That is expected, not a catalog failure.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `378dbec87cb895c4ecec38764eb04d0fe5f77b596b3edb274fcf064a9c12dc97`.
- Carrier project `2d81a5ce479df571c2a80e2e95a3509a98a4fc5ea1e9cefec43d8c5901930004`.
- Root schematic `675de8f983ffbe1a7cf59d5eeb407d5fd90ccf3418074b8abc4ed1baa39b3f4e` (+ five sheets; U1/C1 and D1 are on
  `01_usb_input.kicad_sch`, `56734d060db40ba5e3e7db7ff1fc42d5601be474fd7eab0678bc963c45160d35`).
- Panel PCB `ce77533392472726fd9ddf08db1a1aab53a8648c25dd9a7890b3a8b45fd9820f`.
- Panel project `6fb70c36157f4e827990f7ca0fea610b02d36e1849cad032b590d9ed15ddea90`.

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

- **Shared `check`** after the R2 re-export (`research/export-r2/native-post/`, ignored): ERC 0; DRC 0 violations,
  0 warnings, 0 exclusions, **0 unconnected**, schematic parity 0; manifest equal (10 sources, exports
  byte-identical). R2: 178 refs / 81 nets; none of Q2/Q3/R23/R27/D9/D11/TP2 is in the BOM or CPL. The panel
  sources are unchanged; its Gerbers/drills differ from R1 only in their date lines.
- R1 (2026-11-06, `research/fab254-05-d1/native/`): 185 refs / 84 nets, same results.
- **Zones:** a refill on a scratch copy is byte-identical to the saved board, so the exported pours
  are current. In1 GND one piece, In2 VIN and +3V3 one piece each, no track on In1.
- **Vias:** 314 (R2), all 0.3/0.6 mm, tented; none in or touching a pad (`tools/check_s8_board.py`).
- **Carrier drill:** PTH 314 x 0.3 (vias) + 20 x 1.1 (J2/J3) + 2 x 0.9 (D8) + 4 plated 0.6 mm
  slots (J1 shell lugs); NPTH 2 x 0.65 (J1 pegs), 2 x 0.9 (SW1 pegs), 2 x 3.2 (M3 bracket holes).
- **Panel:** native DRC 0 / 0. NPTH 4 x 3.2 (rail and bracket holes), 3.2 (RESET), 3.6 (MAIN LED);
  the USB-C aperture is an Edge.Cuts cut-out.
- **BOM/CPL:** 149 parts, 60 rows, every CPL row `top`; no missing part number.
- **Edge / hand-solder:** no copper within 1.0 mm of the edge except the user-approved J1/SW1 front
  lugs (0.55 mm rule); courtyards >= 1.355 mm (L3) except the approved J1/SW1/D8 panel overhangs;
  every SMD pad >= 2.01 mm from the J1/D8/J2/J3 hand-solder pads.

## Status and order gates (not done here)

1. **Placement preview** in JLCPCB's top view, every rotation, and in particular: J1 (the KiCad anchor
   is the receptacle front lip, 3.7 mm forward of the body centre: check that JLCPCB's model lands on
   the pads), U2 (VQFN-HR-21, pin 1 and the bar orientation), U1 (ESSOP-10), U4 (SO-PowerPAD-8), U5
   (HTSSOP-20), U9 (HVSSOP-8), U10/U11 (SOT-23-6), U12-U14/U18/U20 (SOIC-14), U15 (SOT-23-5), U21,
   Q1, Q4-Q16 (SOT-23), the cathode bands of D1/D2/D4/D10/D24/D26 and D15/D22/D25/D27/D28,
   SW1.
2. **Edge rails:** J1 overhangs the front edge by 1.2 mm and parts sit 1.3-2 mm from the edges; accept
   JLCPCB-added rails if the assembly review asks for them.
3. **Live recheck** right before ordering: stock (U9 C181239 and U10/U11 C19653 first), class, attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench (post-prototype acceptance tests in `docs/design/routing-notes.md` section 2):** S1-S4
   start-up on a strict 3 A PD source, TH-1 (U2/R109), TH-2 (D10/U5 at 3 A input), TH-3 (U4), CC-1,
   KS-1, IN-1..IN-3, CL-1, EMI-1, HDR-1. The copper/thermal contract items still open in
   `tools/check_s8_board.py` are listed in `docs/routing/README.md`; they were reviewed as acceptable
   for this first prototype, not waived.
