# 8bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- **S6 schematic, 6HP** (`hardware/8bit.kicad_sch`, ERC 0, fully wired with power symbols; user direction
  2026-11-14): Bread Modular 8bit on Eurorack. TS MIDI in with the MIDI V2 NPN front end and JP1 bypass
  (shipped open), protected bipolar CV in (±5.5 V -> 0..5 V, 102k, MCP6002 follower on +5V, U4A; U4B a grounded spare) to PB0,
  **three 50k knobs on the ADC** (PA1 / PA2 / **PB5**; the BM passive low-pass on knob 3 is gone, the DAC
  drives the output amp directly), 6x6x7 mm THT MODE (record) switch + LED, **TL074**: ±4.8 V DAC output,
  VOFF buffer, **GATE out** (PA7, the BM `GATE_PIN`, 0 / +5 V follower + 1k) and a parked spare; ±12 V
  Schottky protection, HT7550-1 +5V.
- **Panel order** (`docs/geometry.json`): MIDI + CV on one row (Y17.5), P1 / P2 / P3 zigzag on a 20 mm
  pitch (Y37.5 left, Y57.5 right, Y77.5 left), MODE + LED row (Y97.5), OUT + GATE row at the bottom
  (Y110.4); two columns X7.95 / X22.05; power header J4 upright at the right edge, UPDI J5 at the right edge.
- **R1 manual divide-and-conquer routing** (`hardware/8bit.kicad_pcb`, 29 x 110 mm, 2 layers, all SMD on
  B, F and B GND pours): shared `check` ERC 0 / DRC 0 / unconnected 0 / parity 0, no exclusions; 258
  tracks / 32 vias, no vias in SMD pads (closest 0.20 mm), SMD >= 2 mm from pot/jack pads (closest
  C7-J3 2.245 mm), courtyards >= 1.015 mm from the edge (RV1), copper-edge rule 1.0 mm; F pour one piece,
  B pour one piece + two pad-tied fragments under U1 (2.6 mm² EP, 0.4 mm² at C1). 6HP FR4 panel and LFO
  panel DRC 0. The native PCB owns placement and copper (the old 4HP `tools/route_plan.py` is removed).
- **JLCPCB export** in `jlcpcb/` (S6/R1, 2026-11-14, after a fab review that needed no board change):
  carrier 2 layers, bottom Economic, 38 parts / 24 rows, 6HP panel + optional LFO panel; shared `check`
  `no_findings_in_requested_checks` with the manifest equal. Live audit 2026-11-14: all codes resolve;
  Extended = R12/R15 (0.5 W 1206, the audit's one hard fail, intentional), U1, **U3 TL074CDR**, D3;
  U2 and U4 Preferred Extended. Not supplier-accepted, not built (`jlcpcb/README.md` order gates).
- **U4 MCP6001 -> MCP6002** (user, 2026-11-14): MCP6002T-I/SN C7377 is JLCPCB Preferred Extended (no
  feeder fee; live audit 2026-11-14T15:36Z, stock 67,081), as Bread Modular 8bit. U4 is now SOIC-8 below
  the CV cluster (B, 120.0 / 85.6), C15 beside its pin 8; local re-route only, the rest of R1 untouched;
  carrier re-exported (still 38 parts / 24 rows).
- `firmware/`: BM `drums`, `supersaw`, `crash`, `lfo` (see `firmware/README.md`), compiled for the BM pin
  map, not bench-tested. All four already drive PA7 (`GATE_PIN`), so the GATE jack works unchanged;
  **none reads P3 (PB5) yet**. The LFO panel variant omits J1 and RV3 (not fitted; no wire bridge needed
  on S6).
- Printed panels (`panels/front-cad/`) and the MODE cap (`panels/button-actuator/`) regenerated for
  6HP; not test-printed.
- Open: JLCPCB preview + part reviews + live recheck before ordering, firmware use of P3, cap
  press-fit/test print, pot measurement, bench (`docs/research.md` §6).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. The routed native PCB owns
placement and copper: changes are explicit manual edits to the board in small batches
(root `AGENTS.md` routing rules), never an autorouter and never a `build_layout.py`
rerun over the routed carrier (`build_layout.py panels` rebuilds only the panels).
Bread Modular is read-only. No merges, pushes, orders or uploads.
