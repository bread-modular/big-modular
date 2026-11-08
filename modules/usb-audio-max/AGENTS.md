# USB-AUDIO-MAX agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S2 schematics, final** (2026-11-05), ERC 0 both: carrier `hardware/usb-audio-max.kicad_sch` (±12 V power,
  2 x 33R + discrete LM358/BCP56 regulator (REF5050 reference, MMBT3904 current limit) -> +5VA (precision DC
  reference for every channel), FB2 + 2.2R input filter -> TPS562208 FCCM buck (~580 kHz at every load, molded
  inductor) -> +3V3 (user: buck again in S2; ngspice in `docs/research.md` 2a), PCM3168A as TDM clock master with
  SCKI 24.576 MHz, 6 DC-coupled inputs (100k -> OPA1679 inverting driver on +5VA, single-ended ADC),
  8 DC-coupled outputs (OPA1679 difference amplifiers on ±12 V, 2 x 2k), VCOM/VB references, BOOT/RESET,
  SWD, MCU-board headers J2/J3) and MCU board `hardware/usb-audio-max-mcu.kicad_sch` (modules/usb-audio
  MCU S1 + SPI1 on PA4-PA7 for the second TDM line pair; J102/J103; circuit unchanged since S1). Every LCSC
  code re-checked live (49, all Economic-eligible).
- Footprint library built (`tools/import_footprints.py`; pcbnew gives new UUIDs on every run, geometry and
  sources pinned in `PROVENANCE.json`).
- **S1 placement, 10HP** (2026-11-06; user: USB-C on top, IN 1-6 in two rows of three, OUT 1-8 in three rows,
  ninth spot empty, no schematic changes, 10HP if 8HP is too tight). Fit study in `docs/research.md`
  section 5 (`tools/fit_density.py`): 8HP 64 % SMD density with no room for the SOIC-14s between the jack
  columns, 10HP 45 % (as modules/usb-audio). `tools/build_layout.py` built the carrier
  `hardware/usb-audio-max.kicad_pcb` (49.5 x 110 mm, 4 layers: 14 jacks, J1 power in the ninth spot, J2/J3
  strips, J4 SWD + BOOT/RESET top left on B; every other SMD part parked right of the board), the MCU board
  `hardware/usb-audio-max-mcu.kicad_pcb` (modules/usb-audio's 29 x 29.55 mm outline, centred: USB-C and
  J102/J103 placed, rest parked) and the panel `panels/front-pcb/usb-audio-max-panel.kicad_pcb`.
  Native DRC 0 violations / parity 0 on both boards (432 / 88 unconnected: nothing routed), panel DRC 0;
  courtyards >= 1.06 mm from the edges. Nothing routed, no export, no firmware.
- **R1 routing done, both boards** (2026-11-07, manual divide and conquer, batches `research/route/c_b*.py` +
  `mcu_b*.py`, `research/route/build.sh` rebuilds the carrier, notes in `research/route/PLAN-codec.md`):
  native DRC 0 / unconnected 0 / parity 0 on both; no vias in SMD pads, no In1 tracks, courtyards >= 1 mm
  from the edge, SMD >= 2 mm from jack pads (closest 2.03 mm). Carrier In2: +12V_F plane, +5VA island over
  the codec/input stage with a finger to the regulator (R7 Kelvin trace), two small +3V3_C islands (codec, U4).
  The shared check's independent ref/pin/net parity flags 4 pins on `Net-(U9-Trim/NR)` /
  `Net-(U3B-MDO/ADR1/MD1)` ("/" vs "{slash}" escaping, same nets).
- **Standoffs** (2026-11-08, user: USB-C push support, modules/usb-audio needed a printed brace; user: at the
  top around the USB port): two M3x10 F-F hex standoffs MS1/MS2 at the top corners, X5.0 / X45.5, Y13.75,
  level with the USB-C (`docs/geometry.json` `mount_standoffs`; board-only, NPTH 3.2, F courtyard R3.3,
  B courtyard R3.4, no F copper inside R3.3 / no B copper inside R3.5), coaxial panel holes H20/H21.
  Batch `research/route/c_b30_standoffs_top.py` (checks `check_b30.py`, `check_b30_mech.py`, panel
  `panel_b30_holes.py`): left J4 SWD down 5.1, SW1/SW2 down 2.56/1.06 (RESET/BOOT/SWD B silk vertical), Y1 right
  1.0, C29 upright beside R21, C28 (codec VDD 10u) next to the +3V3_C via by J2 (the left-edge +3V3_C feed is
  gone); right the buck core L1/U2/C6/C7/C8/R3/R4/R5/R20 rigidly down 2.3 with its copper, C9/C10 left 0.5,
  C5 under C10, C4 left of L1, R13 upright by J3, FB2 below the core (FB2-R3 link on F at X48.5), +3V3 sense,
  VCOM_REF jog and V3_IN hop re-routed. Carrier DRC 0 / unconnected 0 / parity 0, shared check ERC/DRC 0,
  courtyards >= 1.0 mm from the edge (`tools/check_edges.py`), SMD >= 2.03 mm from jack pads, no vias in
  SMD pads, no In1 tracks, In2 planes one piece; panel DRC 0.
- **Fab-review fixes + JLCPCB export** (2026-11-08, user: fix the review findings and export; review in
  `research/fab-review-2026-11-08/REVIEW.md`, fix scripts and reports in `research/fab-fix/`):
  F1 MCU board pours refilled and saved (the saved fills had 48 clearance errors; the exporter plots the
  saved fills) and the JLC04161H-7628 stackup block recorded (copied from modules/usb-audio's MCU board);
  F2 Q1 BCP56 collector copper: `/V5_IN` pours `Q1_HEATSINK` on B (around the tab, 33.3 mm2 filled) and F
  (under J27/Q1, 131.4 mm2 filled), solid pad connection, 8 new 0.6/0.3 thermal vias beside (not in) the
  tab, tied to it by short 0.6 mm B tracks (KiCad re-nets track-less vias inside the In1 GND plane to GND);
  F3 U3 footprint renamed `PCM3168A_HTQFP-64-1EP_10x10mm_P0.5mm_EP8x8mm_Mask7.4x7.4mm_ThermalVias`
  (`tools/import_footprints.py` `pcm3168a_land`, applied to the pinned library + the placed U3, schematic
  footprint fields and `tools/build_schematic.py` updated): mask 5 x 5 -> 7.4 x 7.4 mm over the 7.25 x
  7.00 mm PowerPAD, 25 round 1.15 mm paste apertures between the thermal holes (51 % of the PowerPAD),
  thermal holes solid to the planes. Shared check: ERC 0, DRC 0 (incl. warnings), unconnected 0, native
  parity 0 on both; saved-fill DRC (no refill) 0 on both; only the known 4-pin `{slash}` escape in the
  XML ref/pin/net comparison (carrier). JLCPCB sets in `jlcpcb/main/` (carrier + panel) and `jlcpcb/mcu/`
  (`jlcpcb/README.md`), not supplier-accepted, not built.
- Open (pre-routing note kept for history): group-by-group SMD placement and manual routing of both boards (floorplan proposal and buck layout
  rules in `docs/research.md` sections 5 and 7); firmware (96 kHz SPI1 path is untested on the CH32V307).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` (carrier) and
`tools/kicad-project-mcu.json` (MCU board) for doctor/check. Raw reports go in the ignored
`research/`. Placement and routing are manual, group by group, straight on the boards (root
`AGENTS.md`); once that starts, do not rerun `tools/build_layout.py`. No merges, pushes, orders or
uploads.
