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
- **P4/R3 10HP re-layout** (`hardware/acid.kicad_pcb`, 4 layers, research.md 5.3, user 2026-11-06):
  MIDI / AUDIO / CV jacks on top, ENV OUT on the bottom row beside BP, ATTACK / RELEASE 4 mm lower,
  REC LED right of the REC button, RES / CURVE on the outer pot columns, J10 moved up beside FREQ.
  Board stripped and re-routed by hand group by group (one-connection helper in `research/r3/`).
  Every net routed; vactrols under ATTACK / RELEASE, their 22 stacking findings user-approved and
  excluded by `tools/vactrol_exclusions.py`. KiCad DRC 0 active / 22 excluded / 0 unconnected / parity 0;
  shared gate ERC 0, DRC 22 (counts exclusions), 0 unconnected, ref/pin/net parity equal; no vias in
  SMD pads, no In1 tracks, In1 / In2 one piece each. The native PCB owns placement and copper:
  run `build_layout.py --panel-only` only.
- B silk `UPDI` / `GND` (J11) and MIDI JP1 `D` / `P` + `JP1 D=DIRECT P=PROT` labels;
  gain jumpers `M` / `H` at the pads, `LP` / `HP` / `BP`, legend `GAIN: OPEN=x3` / `M=x3.9 H=x11`.
- 10HP panel `panels/front-pcb/acid-panel.kicad_pcb` (50.5 mm, rail holes X12.58 / X43.06), DRC 0.
- R3 via cleanup (2026-11-06): one net at a time ripped and re-routed with a high via cost, kept
  only when DRC stayed clean: 156 -> 140 vias (ENV_CV 8 -> 2, MODE_SW 5 -> 1, AIN_BUF / HP_RG1 2 -> 0).
- **JLCPCB export** in `jlcpcb/` is the S3/R3 10HP set (2026-11-06, `jlcpcb/README.md`): bottom
  Economic, 98 parts / 27 rows. U2 switched to ATTINY1616-MF C5227638 (same die/package, 125 C grade, 240 in stock; C507118 had 3), fields only.
  Not supplier-accepted, not built.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check. Raw reports
go in the ignored `research/`. Firmware (MCO + ENV merge, REC recorder) in `firmware/` (compiled, not bench-tested; `firmware/README.md`).
