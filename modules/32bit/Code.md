# 32bit contract (S4: carrier S4 / R2, MCU board S1 / R2, panel P2)

| | |
|---|---|
| KiCad projects | `hardware/32bit.kicad_{pro,sch,pcb}` (carrier), `hardware/32bit-mcu.kicad_{pro,sch,pcb}` (MCU board) |
| Panel | `panels/front-pcb/32bit-panel.kicad_{pro,pcb}` (FR4, NPTH only), `panels/front-cad/` (printed) |
| Generators | `tools/build_schematic.py` + `circuit_carrier.py` / `circuit_mcu.py`, `build_project.py`, `import_footprints.py`, `build_layout.py panel`, `carrier_from_usb_audio.py` (one-time S4 start) |
| Shared-tool profiles | `tools/kicad-project.json` (carrier + panel manifest), `tools/kicad-project-mcu.json` |
| Placement and stack contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` section 9 (9.1 result, 9.2 fab review); S1..S3 in sections 1-8 are history |
| Firmware pin map | `docs/firmware-pins.md` |
| Evidence | `docs/fit/` (native ERC / DRC JSON, renders), `docs/32bit-schematic.pdf`, `docs/32bit-mcu-schematic.pdf` |

The S3 contract (one board, ES8388, MIDI, CV inputs) is in git history.

## Fixed by the brief (user, 2026-11-23)

- 32bit runs `master` in front of PA systems, so it takes the audio path of modules/usb-audio S5: **CS4272**
  with its own 24.576 MHz oscillator, NE5532 stages, AMS1117-5.0 +5VA. Two in, two out, DC-coupled.
- **Two boards as modules/usb-audio**: the analog carrier and a separate **ESP32-S3 MCU board** (ESP32-S3R8 +
  W25Q128JVSIQ + 40 MHz crystal) on two 1x10 strips over the carrier F side, vertical **USB-C through the
  panel**. Not the CH32V307 board (CPU load, 8 MHz I2S limit).
- **No CV inputs, no MIDI.** Two 50k pots, a MODE button and an LED are firmware controls on ESP32 GPIOs,
  not in the audio path.
- ESP32-S3 current decided from datasheets (about 130 mA typical, 180 mA design maximum): R1 22R 1 W.
- Two M3x10 standoffs above the MCU board, as modules/usb-audio P2.
- Two separate JLCPCB orders, no panelization (the boards share no part code).

## Design rules

- The carrier keeps the reference designators and the routed copper of the usb-audio S5 carrier. Changes
  to that circuit are listed at the top of `tools/circuit_carrier.py`.
- Link: J6 = 1 +3V3, 2 GND, 3 EN, 4 BOOT, 5 MODE, 6 LED, 7 I2C_SDA, 8 I2C_SCL, 9 POT1, 10 POT2; J7 as
  usb-audio (+3V3, GND, SCLK, GND, LRCK, ADC, DAC, CODEC_RST, GND, GND). J6 differs from usb-audio: the two
  MCU boards are not interchangeable (B silk on both boards).
- The codec is the I2S clock master, the ESP32-S3 the slave. The codec leaves reset as a slave, so
  R14 / R16 / R48 hold the I2S lines low until the firmware has set it up.
- ESP32-S3 circuit after the Espressif hardware design guidelines: decoupling per supply pin, VDD_SPI =
  3.3 V out of the chip for the flash, 10k + 1u on EN, 10k on GPIO0, strapping pins GPIO3 / 45 / 46 open,
  GPIO33-37 and SPICS1 open (PSRAM inside the package), LNA_IN open: the radio is never started.
- USB: data only, VBUS powers nothing. Full speed, so the pair is routed without the high-speed rules
  (`tools/check_usb.py` reports them as failed; judged in `jlcpcb/README.md`).
- Carrier: all SMD on B, jacks / pots / LED / MODE / strips on F, power header upright at the left edge on
  B. MCU board: all SMD on F (faces the panel), nothing on B.
- 4 layers each: F signal / In1 GND / In2 +3V3 (carrier: + a +5VA island) / B signal. No tracks on the
  inner layers. No vias in SMD pads (the ESP32-S3 land's own nine thermal vias are the exception; they are
  drilled 0.3 mm, not KiCad's 0.2 mm: no hole under 0.3 mm on either board, root `AGENTS.md`).
- Heat: U2 AMS1117-3.3 drops 0.7 to 0.8 W. Its tab has a +3V3 patch on B and F and seven vias beside the
  tab into the In2 plane (R2). Keep them when touching that corner.
- Panel: USB-C slot 11.0 x 5.2 mm at X15 Y24.75 (P2). The slot ends must stay over the shell's rounded
  ends; a narrower slot of this height pinches the shell corners.
- Root `AGENTS.md` rules hold: 1 mm edge keep-out, 2 mm from pot / jack pads, manual routing, no
  pre-order parts.

## Sources and generators

- `tools/build_schematic.py` writes both schematics, `32BIT.kicad_sym` and `sym-lib-table` from the two
  circuit tables and asserts the native netlists against them.
- Both boards are routed: the board files own placement and copper. `tools/build_layout.py` is only run
  as `build_layout.py panel` (from `docs/geometry.json`); `build_layout.py mcu` and
  `carrier_from_usb_audio.py --write` would discard the routing.
- After a sourcing change, rebuild the schematic and copy the fields onto the board footprints
  (`jlcpcb/README.md`, Reproduce).
- `panels/front-cad/build_front_panel.py` (FreeCAD, headless) makes the printed panel from the panel PCB.
- `tools/render_fit.py` renders the stack into `docs/fit/`; `tools/check_edges.py` measures courtyards to
  the edge and SMD pads to pot / jack pads.

## Verification (fab review, 2026-11-23)

- Shared `kicad_tools.py check`, both profiles: ERC 0, DRC 0 (all severities), 0 unconnected, parity 0,
  no exclusions, manifests equal after the export; `order_ready: false` as always.
- Native DRC with saved fills and `--refill-zones`: 0 / 0 / 0 on the carrier after R2; panel DRC 0.
- Independent: native netlists equal the board pads (carrier 283 pins / 100 parts, MCU board 152 / 27),
  LCSC fields equal; J6 / J7 equal J102 / J103 in net and position; panel holes on their parts.
- Carrier 753 tracks / 124 vias, MCU board 239 / 41; no via in or touching an SMD pad; In1 one piece (+ two
  pad-tied 1 mm2 slivers on the carrier), In2 +3V3 and +5VA one piece each.
- Courtyards >= 1.02 mm (carrier) / 1.06 mm (MCU board) from the edge; SMD >= 2.03 mm from pot / jack pads.
- All 46 LCSC codes live on 2026-11-23: MPN and package equal, free stock above the need, minimum
  purchase 1.
- Not done: JLCPCB preview (rotations, pin 1), supplier acceptance, build, any measurement. No CS4272
  board has been built yet (modules/usb-audio S5 is the same codec circuit).
