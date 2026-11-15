# MOTION — 4-knob motion recorder (6HP)

Four knobs, four CV outputs. Hold **REC** and move a knob: its motion is recorded and
then loops on that knob's output. With a take playing, the knob moves the take up or
down. Hold REC for 5 s without moving a knob to erase every take. **±5V** switches all
four outputs between 0..+5 V and -5..+5 V.

| Panel (top to bottom) | Circuit |
|---|---|
| Knobs **1-4**, zigzag, each with its motion LED beside it | 50k linear dividers into the ATtiny1616 ADC; LEDs on PWM pins through 10k |
| **REC** LED + button (left), **±5V** LED + button (right) | 6 x 6 mm THT tact switches with the `modules/8bit` printed cap; LED on = -5..+5 V |
| **OUT 1-4** | MCP4728 12-bit DAC -> 160 Hz low-pass -> TL074 (gain 2 around +5VA) -> 1k; DC coupled |

- Takes are recorded straight into an MB85RC256V I2C FRAM (~81 s per knob), so they are
  kept through power-off with no save step.
- Power: Eurorack 10-pin header on the back between the lower jacks (a 16-pin IDC fits),
  ±12 V through series Schottkys, +5 V from an HT7550-1. UPDI on a 2-pin header.

**Status: S1 schematic + R1 hand-routed 2-layer carrier, JLCPCB export in `jlcpcb/`;
no firmware, not built.** ERC 0; DRC 0 / unconnected 0 / parity 0 (`docs/fit/`).

| Path | Contents |
|---|---|
| `hardware/` | KiCad project `motion.kicad_{pro,sch,pcb}` (29 x 110 mm carrier, 2 layers, routed, SMD on the back), pinned symbols, footprints and models |
| `panels/front-pcb/motion-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, silkscreen labels |
| `docs/research.md` | Brief, chip choice, decisions, circuit, sourcing, open items |
| `docs/geometry.json` | Placement and panel contract |
| `docs/motion-schematic.pdf`, `docs/fit/` | Schematic PDF; native ERC/DRC JSON and renders (`overview.png`) |
| `tools/` | Generators and the shared-tool profile `kicad-project.json` |
| `jlcpcb/` | Upload-ready carrier + panel Gerbers, BOM and CPL (`jlcpcb/README.md`) |
