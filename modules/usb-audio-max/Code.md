# USB-AUDIO-MAX contract (S2 schematics, final; S1 placement, 10HP)

| | |
|---|---|
| KiCad projects | `hardware/usb-audio-max.kicad_{pro,sch,pcb}` (carrier), `hardware/usb-audio-max-mcu.kicad_{pro,sch,pcb}` (MCU board); one shared `USBAUDIOMAX` symbol/footprint library; 3D models vendored in `hardware/_kicad_models/` |
| Panel | `panels/front-pcb/usb-audio-max-panel.kicad_{pro,pcb}` (10HP FR4, NPTH only) |
| Generators, profiles | `tools/` (`build_schematic.py`, `circuit_carrier.py`, `circuit_mcu.py`, `build_project.py`, `build_layout.py`, `import_footprints.py`, `check_edges.py`, `fit_density.py`, `render_fit.py`, `sexp.py`, `kicad-project.json`, `kicad-project-mcu.json`) |
| Placement / stack contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Evidence | `docs/erc/` (native ERC JSON), `docs/fit/` (native DRC JSON, renders), `docs/*-schematic.pdf`, `docs/schematic-symbols.json`, `hardware/USBAUDIOMAX.pretty/PROVENANCE.json`; power simulations summarised in `docs/research.md` 2a / D11 (decks in the ignored `research/buck/sim/`) |

## Fixed by the brief (user, 2026-11-05)

- PCM3168A, 6 in / 8 out, up to 96 kHz, DC coupled, no level controls (no pots).
- Same style as modules/usb-audio: CH32V307RCT6 + USB-C on a second PCB soldered to the carrier
  with 2.54 mm strips; JLC assembles the SMD; jacks and strips are hand-soldered.
- Panel (user, 2026-11-06): USB-C at the top; IN 1-6 in two rows of three, OUT 1-8 in three rows of
  three below (ninth spot empty); 10HP because 8HP does not fit without schematic changes
  (`docs/research.md` section 5). No schematic changes for space.

## Design rules

- Carrier: all SMD on B; MCU board: all SMD on F (each board single-sided assembly). Both 4 layers.
- J2/J3 (carrier) and J102/J103 (MCU board) share XY and pin nets: change them together. The strips
  are in the carrier BOM; J102/J103 are copper only (excluded from BOM/CPL).
- Stack (`docs/geometry.json` `stack_Z_mm`, as modules/usb-audio): header plastic 2.5 mm, MCU board
  1.6 mm, USB-C 8.8 mm, panel rear at 10 mm; the USB-C mouth must stay at or in front of the panel
  front minus 0.3 mm. Jacks stay outside the MCU board outline.
- Interface nets (same names on both schematics): `+3V3`, `GND`, `SWDIO`, `SWCLK`, `NRST`, `BOOT0`,
  `I2C_SCL`, `I2C_SDA`, `CODEC_RST`, `I2S_SCLK`, `I2S_LRCK`, `I2S_ADC1`, `I2S_ADC2`, `I2S_DAC1`,
  `I2S_DAC2`. Carrier J2/J3 = MCU board J102/J103: change them together.
- Firmware-visible pins (CH32V307): PB6/PB7 USBHS, PB13/PB12/PB15 I2S2 RX (DOUT1), PB3/PA15/PB5
  I2S3 TX (DIN1), PA5/PA4/PA7/PA6 SPI1 SCK/NSS/MOSI/MISO (DOUT2/DIN2), PB10/PB11 I2C2 (codec 0x44),
  PB14 codec RST, PA9 VBUS sense. Log any change in `docs/research.md`.
- Codec: ADC = TDM clock master, DAC slave on the tied BCK/LRCK; SCKI 24.576 MHz. Firmware must set
  SEAD (single-ended), BYP (HPF off) and REVAD (inverting drivers) for the analog chain to be right.
- Two M3x10 F-F hex standoffs MS1/MS2 (carrier F to panel rear = 10 mm) at the top corners beside the USB-C
  (X5.0 / X45.5, Y13.75) hold the carrier against USB-C plug forces; carrier and panel holes coaxial (`mount_standoffs`), M3x6 screws.
  Keep F copper out of R3.3 and B copper / SMD out of R3.5 around them (B courtyard R3.4).
- Courtyards >= 1.0 mm from `Edge.Cuts`, SMD pads >= 2.0 mm from jack pads, manual
  divide-and-conquer routing, no vias in SMD pads (the codec footprint's own PowerPAD thermal vias
  are the allowed exception) (root `AGENTS.md`).

## Sources and generators

- `tools/build_schematic.py` + the two circuit tables own both schematics, `USBAUDIOMAX.kicad_sym`
  and `sym-lib-table` (modules/usb-audio's engine, plus drawn symbols, property edits and per-unit
  mirroring). The build asserts nothing dangles and that each native netlist equals its circuit table.
- `tools/import_footprints.py` builds `USBAUDIOMAX.pretty` (stock KiCad, Bread Modular jack/K2,
  the HRO USB-C land from modules/usb-audio) and `fp-lib-table`.
- `tools/build_project.py` writes both `.kicad_pro` (modules/32bit settings, 1.0 mm copper-to-edge,
  Power class = rails + power-path nets) and the panel `.kicad_pro`.
- `tools/build_layout.py` places from `docs/geometry.json`, parks the rest and takes nets/values/fields
  from the native netlists (auto net names with a `/` get KiCad's `{slash}` escape). Once SMD
  placement starts by hand, the boards own placement: do not rerun it.
- `tools/check_edges.py` (courtyard to edge >= 1 mm, SMD to jack pads >= 2 mm), `tools/fit_density.py`
  (section 5 fit study), `tools/render_fit.py` (`docs/fit/*.png`).

## Verification (S2, 2026-11-05)

- Native ERC `--severity-all`: 0 (carrier), 0 (MCU board); netlists equal the circuit tables.
- Live JLCPCB lookups of every LCSC code (49, `docs/research.md` section 6).
- ngspice: +3V3 buck ripple and USB load bursts against +12V_F, +5VA, the outputs and the ADC inputs;
  +5VA regulator loop, output impedance, PSRR and current limit (`docs/research.md` 2a, D11). Models,
  not measurements.
- Not done (at S2): panel, placement, routing, DRC, JLCPCB export, firmware, bench.

## Verification (S1 placement, 2026-11-06)

- Schematics unchanged; native ERC `--severity-all` still 0 on both.
- Native DRC `--severity-all --schematic-parity --refill-zones`: 0 violations, parity 0 on both
  boards; unconnected 432 (carrier) / 88 (MCU board): nothing routed. Panel DRC 0.
- Shared `kicad_tools.py check`, both profiles: ERC 0, DRC 0 violations, parity 0, only the unrouted
  items. Its XML ref/pin/net comparison lists only the cosmetic `{slash}` escape on
  `Net-(U9-Trim/NR)` (C17.1, U9.5) and `Net-(U3B-MDO/ADR1/MD1)` (R15.1, U3.44), as modules/usb-power-45w;
  MCU board equal.
- `tools/check_edges.py`: courtyards >= 1.28 mm (carrier) / 1.06 mm (MCU board) from the edges;
  closest SMD pad to a jack pad 5.14 mm (SW2 to J11).
- Panel: 50.5 x 128.5 x 1.6 mm, rail holes X12.58 / X43.06 (2HP case grid phase as
  `case/tools/build_case.py` asserts).
- Not done: SMD placement, routing, JLCPCB export / assembly audit, printed panel, firmware, bench.
