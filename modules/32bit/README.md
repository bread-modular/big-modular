# 32bit — ESP32-S3 + CS4272 stereo audio processor (6HP)

S4 (2026-11-23): two boards. The **carrier** is the modules/usb-audio S5 analog board (CS4272 codec with
its own 24.576 MHz clock, NE5532 input / output stages, AMS1117 +5VA, DC-coupled ±5 V, 2 in / 2 out) with
two control pots, a MODE button and an LED in place of the volume pots. The **MCU board** (ESP32-S3R8,
8 MB PSRAM inside, W25Q128JVSIQ 16 MB flash, 40 MHz crystal) is soldered on two 1x10 strips over the
carrier's front side and carries the USB-C, which comes out through the front panel. Two M3x10 standoffs
above the MCU board take the plug forces. It runs the `master` end-of-chain processor in front of PA
systems; the reason for the codec change is in `docs/research.md` section 9. The S3 design (one board,
ES8388, MIDI and CV inputs, USB-C on the back) is in git history.

| Panel (top to bottom) | Circuit |
|---|---|
| **USB** (USB-C) | MCU board J101 -> USBLC6-2SC6 -> ESP32-S3 GPIO19 / 20 (USB Serial/JTAG: Web Serial, console, firmware download). Data only, VBUS powers nothing |
| **IN L**, **IN R** | jack -> 1k -> NE5532 follower -> OPA1679 differential drive on +5VA -> CS4272 ADC (±5.5 V full scale, 100k input) |
| **P1**, **P2** | 50k RV09 from a filtered 3.03 V -> ESP32-S3 ADC1 (GPIO7 / GPIO6). Firmware controls, not in the audio path |
| LED, **MODE** | 3 mm red LED on GPIO39 (1k), 6 x 6 mm tact switch on GPIO38 (to GND) |
| **OUT L**, **OUT R** | CS4272 DAC (differential) -> NE5532 difference amplifier (±12 V) -> 1k -> jack (±5.3 V full scale) |

The ESP32-S3 is the I2S slave of the codec (SCLK GPIO18, LRCK GPIO17, data GPIO16 / GPIO13) and sets it
up over I2C (0x10, GPIO9 / GPIO8). Full pin map: [`docs/firmware-pins.md`](docs/firmware-pins.md).

Power: Eurorack 10-pin, ±12 V through series Schottkys; +12 V -> AMS1117-5.0 -> +5VA (codec analog side);
+12 V -> 22R 1 W -> AMS1117-3.3 -> +3V3 (MCU board, codec digital side behind a ferrite). About 130 mA
on +3V3 (datasheet estimate), so roughly 0.2 A from +12 V and 20 mA from -12 V; not measured. RESET and
BOOT buttons are on the carrier's back.

**Status: carrier S4 / R2 + MCU board S1 / R2, both hand-routed, 4 layers; panel P2. ERC 0, DRC 0,
0 unconnected, parity 0 on both boards. JLCPCB export in [`jlcpcb/`](jlcpcb/README.md) (two orders:
carrier 88 parts bottom side + panel, MCU board 25 parts top side, Economic PCBA). Fab-reviewed
2026-11-23; not supplier-accepted, not built.** The `master` firmware still needs its CS4272 driver.

| Path | Contents |
|---|---|
| `hardware/` | `32bit.kicad_{pro,sch,pcb}` (29 x 110 mm carrier) and `32bit-mcu.kicad_{pro,sch,pcb}` (29 x 29.55 mm MCU board), pinned symbols / footprints (`32BIT.kicad_sym`, `32BIT.pretty` + `PROVENANCE.json`, `32BIT.3dshapes`) |
| `panels/front-pcb/32bit-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, USB-C slot, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `docs/research.md` | Decisions and circuit notes; section 9 is S4, 9.2 the fab review |
| `docs/geometry.json` | 6HP panel, placement and stack contract |
| `docs/32bit-schematic.pdf`, `docs/32bit-mcu-schematic.pdf`, `docs/fit/` | Schematic PDFs; native ERC / DRC JSON; assembly renders |
| `jlcpcb/` | JLCPCB Gerbers, BOM, CPL, upload map and sourcing notes |
| `firmware/` | `master`, `fxrack`, `polysynth` (ESP-IDF); see `firmware/README.md` |
| `tools/` | Generators (`circuit_carrier.py`, `circuit_mcu.py` hold the circuit tables), checks and the shared-tool profiles |

Checks (from `modules/32bit`):

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --reports research/check-NEW
python3 -B ../../opt/kicad-tools/kicad_tools.py check --config tools/kicad-project-mcu.json --reports research/check-mcu-NEW
python3 -B tools/check_edges.py     # courtyards to the edge, SMD to pot / jack pads
python3 -B tools/render_fit.py      # docs/fit/ renders of the stack
```

Both boards are routed by hand: `tools/build_layout.py` only rebuilds the panel now (`build_layout.py panel`).
Read [`Code.md`](Code.md) before changing hardware.
