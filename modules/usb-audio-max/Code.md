# USB-AUDIO-MAX contract (S2 schematics, final)

| | |
|---|---|
| KiCad projects | `hardware/usb-audio-max.kicad_{pro,sch}` (carrier), `hardware/usb-audio-max-mcu.kicad_{pro,sch}` (MCU board); one shared `USBAUDIOMAX` symbol/footprint library. No PCBs yet |
| Generators, profiles | `tools/` (`build_schematic.py`, `circuit_carrier.py`, `circuit_mcu.py`, `build_project.py`, `import_footprints.py`, `sexp.py`) |
| Circuit intent and decisions | `docs/research.md` |
| Evidence | `docs/erc/` (native ERC JSON), `docs/*-schematic.pdf`, `docs/schematic-symbols.json`, `hardware/USBAUDIOMAX.pretty/PROVENANCE.json`; power simulations summarised in `docs/research.md` 2a / D11 (decks in the ignored `research/buck/sim/`) |

## Fixed by the brief (user, 2026-11-05)

- PCM3168A, 6 in / 8 out, up to 96 kHz, DC coupled, no level controls (no pots).
- Same style as modules/usb-audio: CH32V307RCT6 + USB-C on a second PCB soldered to the carrier
  with 2.54 mm strips; JLC assembles the SMD; jacks and strips are hand-soldered.

## Design rules

- Interface nets (same names on both schematics): `+3V3`, `GND`, `SWDIO`, `SWCLK`, `NRST`, `BOOT0`,
  `I2C_SCL`, `I2C_SDA`, `CODEC_RST`, `I2S_SCLK`, `I2S_LRCK`, `I2S_ADC1`, `I2S_ADC2`, `I2S_DAC1`,
  `I2S_DAC2`. Carrier J2/J3 = MCU board J102/J103: change them together.
- Firmware-visible pins (CH32V307): PB6/PB7 USBHS, PB13/PB12/PB15 I2S2 RX (DOUT1), PB3/PA15/PB5
  I2S3 TX (DIN1), PA5/PA4/PA7/PA6 SPI1 SCK/NSS/MOSI/MISO (DOUT2/DIN2), PB10/PB11 I2C2 (codec 0x44),
  PB14 codec RST, PA9 VBUS sense. Log any change in `docs/research.md`.
- Codec: ADC = TDM clock master, DAC slave on the tied BCK/LRCK; SCKI 24.576 MHz. Firmware must set
  SEAD (single-ended), BYP (HPF off) and REVAD (inverting drivers) for the analog chain to be right.
- Courtyards >= 1.0 mm from `Edge.Cuts`, SMD pads >= 2.0 mm from jack pads, manual
  divide-and-conquer routing, no vias in SMD pads (the codec footprint's own PowerPAD thermal vias
  are the allowed exception) (root `AGENTS.md`).

## Sources and generators

- `tools/build_schematic.py` + the two circuit tables own both schematics, `USBAUDIOMAX.kicad_sym`
  and `sym-lib-table` (modules/usb-audio's engine, plus drawn symbols, property edits and per-unit
  mirroring). The build asserts nothing dangles and that each native netlist equals its circuit table.
- `tools/import_footprints.py` builds `USBAUDIOMAX.pretty` (stock KiCad, Bread Modular jack/K2,
  the HRO USB-C land from modules/usb-audio) and `fp-lib-table`.
- `tools/build_project.py` writes both `.kicad_pro` (modules/32bit settings, 1.0 mm copper-to-edge).

## Verification (S2, 2026-11-05)

- Native ERC `--severity-all`: 0 (carrier), 0 (MCU board); netlists equal the circuit tables.
- Live JLCPCB lookups of every LCSC code (49, `docs/research.md` section 6).
- ngspice: +3V3 buck ripple and USB load bursts against +12V_F, +5VA, the outputs and the ADC inputs;
  +5VA regulator loop, output impedance, PSRR and current limit (`docs/research.md` 2a, D11). Models,
  not measurements.
- Not done: panel design (8HP decided), placement, routing, DRC, JLCPCB export, firmware, bench.
