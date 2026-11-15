# MOTION agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- **S1 schematic** (`hardware/motion.kicad_sch`, ERC 0, wired with power symbols; user
  brief 2026-11-15): 6HP motion recorder. ATtiny1616 at 5 V reads four 50k knobs
  (PA1 / PA2 / PA6 / PA7), records them straight into an **MB85RC256V** I2C FRAM (0x50,
  ~81 s per knob, always saved) and plays four tracks through an **MCP4728** quad 12-bit
  I2C DAC (0x60, VREF = VDD = +5VA). TL074: Vout = 2 x Vdac - (+5VA) = -5..+5 V per
  output, 160 Hz low-pass in front, 1k series. REC and RANGE tact buttons (PC0 / PC1),
  six LEDs through 10k on TCA0 PWM pins (four motion LEDs, REC, RANGE). The range
  (0..+5 V / -5..+5 V) is firmware only. HT7550-1 +5V, +5VA behind 10R / 10u.
- **P1 placement + R1 routing** (`docs/geometry.json`, `hardware/motion.kicad_pcb`,
  29 x 110 mm, **2 layers**; user go-ahead 2026-11-15): knobs zigzag at Y18 / 34.5 / 51 /
  67.5 (X7.95 left, X22.05 right), each motion LED in the opposite column of its knob's
  row; REC / RANGE LEDs Y79, buttons Y85.5; OUT 1 / 2 Y96.25, OUT 3 / 4 Y110.4; power
  header J5 on B between OUT 3 and OUT 4, UPDI J6 on B at the left edge. All 52 SMD parts
  on B: power entry between the jack rows, HT7550 between RV1 and RV3, TL074 + filters
  right of RV3, DAC, FRAM and MCU between RV3 / RV4 and the buttons. Long knob, LED and
  output runs on F. 402 tracks / 89 vias (37 GND stitching), GND pours on F and B (solid
  on SMD pads, thermal reliefs on THT pads).
- **Checks:** shared `check` `no_findings_in_requested_checks`, manifest equal: ERC 0 /
  DRC 0 / unconnected 0 / parity 0, ref/pin/net parity equal, no exclusions. One GND net
  by the independent `research/r1/gndnet.py` check; the pours are in pieces (F 22, B 20),
  all via-tied. No via in an SMD pad except one ground via in the U2 exposed pad. SMD
  pads >= 2.025 mm from pot / jack pads, courtyards >= 1.015 mm and track copper >= 1.1 mm
  from the edge.
- **S1 symbol note:** MCP4728 pin 5 is named `RDY_~{BSY}` (stock `RDY/~{BSY}`): the slash
  made the shared ref/pin/net parity differ on that unused pin. Generator patched too.
- **JLCPCB export** in `jlcpcb/` (carrier bottom Economic, 52 parts / 15 rows, 5 Extended
  part types + HT7550 Preferred Extended; 6HP panel), not supplier-accepted, not built.
- Renders in `docs/fit/` (`overview.png`, `carrier-back.png`).
- Open: JLCPCB preview / DFM; `docs/jlcpcb-audit-requirements.json` (requirements audit
  not written); firmware; printed button caps; bench. The route came from a
  one-connection path helper and has had no second review.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. `tools/build_layout.py`
refuses the routed carrier: the native PCB owns placement and copper (manual divide-and-conquer, root `AGENTS.md`). Bread
Modular is read-only. No merges, pushes, orders or uploads.
