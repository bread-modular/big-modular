# USB-AUDIO-MAX — 6 in / 8 out USB audio interface, 96 kHz, DC coupled

A Eurorack USB audio interface: a CH32V307 (USB 2.0 High-Speed, USB Audio Class 2) and a TI
PCM3168A 24-bit codec in TDM mode. Six inputs and eight outputs, all DC coupled at about +/-5.9 V,
so CV works too. No level controls. Same two-board build as [USB-AUDIO](../usb-audio/README.md).

| Panel | Circuit |
|---|---|
| **USB** (USB-C through the panel) | MCU board: CH32V307RCT6, USBLC6-2SC6, data only (powered from the rack) |
| **IN 1-6** | 100k -> inverting driver on +5 V (x -0.24) -> PCM3168A VIN+ (single-ended); +/-5.89 V = full scale |
| **OUT 1-8** | PCM3168A VOUT+/- -> difference amplifier on +/-12 V (x 1.467) -> 1k; full scale +/-5.87 V |
| (DC reference) | +5 V analog = the codec's full-scale reference: REF5050 (8 ppm/C) -> LM358 + BCP56 discrete regulator (current-limited), so calibrated CV levels don't drift |
| (+3.3 V digital) | TPS562208 buck in forced-continuous mode (~580 kHz at every load, never in the audio band) behind a 2.2R + ferrite input filter, molded inductor; only the digital rail switches (+12 V ~0.34 A max). ngspice: ~50 uV on +12 V, 0.1 uV on +5 V analog, -142 dBFS at the jacks for USB load bursts |

**Status: S2 schematics, final (carrier + MCU board), native ERC 0 on both.** Panel is 8HP (user
decision); jack layout is open; no PCB, no export, no firmware yet. Every LCSC code re-checked live
on 2026-11-05 (49 codes, all Economic-eligible); JLC stocks the PCM3168APAPR (C529289, Extended, 1517).

| Path | Contents |
|---|---|
| `hardware/` | `usb-audio-max.kicad_{pro,sch}` (carrier), `usb-audio-max-mcu.kicad_{pro,sch}` (MCU board), shared `USBAUDIOMAX.kicad_sym`, `USBAUDIOMAX.pretty` (+ `PROVENANCE.json`), `USBAUDIOMAX.3dshapes` |
| `docs/research.md` | Brief, decisions, levels, buck-vs-audio simulation, circuit, TDM/firmware notes, sourcing, open items |
| `docs/*-schematic.pdf`, `docs/erc/` | Schematic PDFs, native ERC JSON |
| `tools/` | Generators (`circuit_carrier.py`, `circuit_mcu.py` hold the circuits) |

Rebuild (from `modules/usb-audio-max`):

```sh
python3 -B tools/import_footprints.py   # footprint library (pcbnew); reads the Bread Modular AudioJacks/K2
python3 -B tools/build_schematic.py     # both schematics + pinned symbols, netlists asserted
python3 -B tools/build_project.py       # .kicad_pro files (only before hand edits)
kicad-cli sch erc --severity-all --format json -o docs/erc/carrier-erc.json hardware/usb-audio-max.kicad_sch
kicad-cli sch erc --severity-all --format json -o docs/erc/mcu-erc.json hardware/usb-audio-max-mcu.kicad_sch
```

Read [`Code.md`](Code.md) before changing hardware.
