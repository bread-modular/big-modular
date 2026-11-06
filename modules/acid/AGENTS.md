# ACID agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S3 schematic** (`hardware/acid.kicad_sch`, ERC 0, every signal net wired): Bread Modular
  MCO + ENV on one ATtiny1616, BM SVF (two vactrol integrators, RES 500k), all at 3.3 V; 8bit
  MIDI input; AUDIO/CV bypass inputs normalled through U4 TS5A23157 to the MCO mix and the DAC
  envelope; no DRIVE: LP / HP / BP outs, each one TL072 stage + 1k/1k with a 3-pad gain jumper
  JP2 / JP3 / JP4 (Rg 4.7k + 10k + 5.1k): open (shipped) x3.0, 2-3 x3.9, 1-2 x11.1 (S2 gain,
  ~10 Vpp ceiling), research.md 3.6; 0..5 V envelope CV out.
- **R2 = R1 manual routing + the gain-jumper clusters** (`hardware/acid.kicad_pcb`, 4 layers,
  research.md 5, 5.2): every net routed; LP / HP clusters on the left edge strip, BP under the
  RES / CURVE gap, one `*_RG1` link each; vactrols under ATTACK / RELEASE, their 22 stacking findings user-approved and excluded
  by `tools/vactrol_exclusions.py`. KiCad DRC 0 active / 22 excluded / 0 unconnected / parity 0;
  shared gate ERC 0, DRC 22 (counts exclusions), 0 unconnected; no vias in SMD pads.
  The native PCB owns placement and copper: do not rerun `build_layout.py`.
- B silk `GND UPDI` (J11) and MIDI JP1 `D` / `P` + `JP1 D=DIRECT P=PROT` labels (research.md 5.1);
  gain jumpers `M` / `H` at the pads, `LP` / `HP` / `BP`, legend `GAIN: OPEN=x3` / `M=x3.9 H=x11` (5.2).
- 8HP panel `panels/front-pcb/acid-panel.kicad_pcb`, DRC 0.
- **JLCPCB export** in `jlcpcb/` (S3/R2 carrier 2026-11-05, bottom Economic, 98 parts / 27 rows; read
  `jlcpcb/README.md`). Not supplier-accepted, not built. Any board edit needs a re-export.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check. Raw reports
go in the ignored `research/`. Firmware (MCO + ENV merge, REC recorder) in `firmware/` (compiled, not bench-tested; `firmware/README.md`).
