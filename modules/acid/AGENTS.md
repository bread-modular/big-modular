# ACID agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S2 schematic** (`hardware/acid.kicad_sch`, ERC 0, every signal net wired): Bread Modular
  MCO + ENV on one ATtiny1616, BM SVF (two vactrol integrators, RES 500k), all at 3.3 V; 8bit
  MIDI input; AUDIO/CV bypass inputs normalled through U4 TS5A23157 to the MCO mix and the DAC
  envelope; no DRIVE: LP / HP / BP outs, each one TL072 x22.3 stage + 1k/1k (x11.1, ~10 Vpp
  ceiling); 0..5 V envelope CV out.
- **R1 manual routing done** (`hardware/acid.kicad_pcb`, 4 layers, research.md 5): every net
  routed; vactrols under ATTACK / RELEASE, their 22 stacking findings user-approved and excluded
  by `tools/vactrol_exclusions.py`. KiCad DRC 0 active / 22 excluded / 0 unconnected / parity 0;
  shared gate ERC 0, DRC 22 (counts exclusions), 0 unconnected; no vias in SMD pads.
  The native PCB owns placement and copper: do not rerun `build_layout.py`.
- B silk `GND UPDI` (J11) and MIDI JP1 `D` / `P` + `JP1 D=DIRECT P=PROT` labels (research.md 5.1).
- 8HP panel `panels/front-pcb/acid-panel.kicad_pcb`, DRC 0.
- **JLCPCB export** in `jlcpcb/` (2026-10-23, bottom Economic, 92 parts / 27 rows; read
  `jlcpcb/README.md`). Not supplier-accepted, not built. Any board edit needs a re-export.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check. Raw reports
go in the ignored `research/`. Firmware (MCO + ENV merge, REC) is not written yet.
