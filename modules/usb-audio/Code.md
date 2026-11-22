# USB-AUDIO contract (S1 schematics, S1 THT placement)

| | |
|---|---|
| KiCad projects | `hardware/usb-audio.kicad_{pro,sch,pcb}` (carrier), `hardware/usb-audio-mcu.kicad_{pro,sch,pcb}` (MCU board); one shared `USBAUDIO` symbol/footprint library |
| Panel | `panels/front-pcb/usb-audio-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| Generators, profiles | `tools/` (`build_schematic.py`, `circuit_carrier.py`, `circuit_mcu.py`, `build_project.py`, `build_layout.py`, `import_footprints.py`, `make_usbc_model.py`, `check_edges.py`, `render_fit.py`, `sexp.py`, `kicad-project.json`, `kicad-project-mcu.json`) |
| Placement / stack contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Evidence | `docs/fit/` (native ERC/DRC JSON, renders), `docs/*-schematic.pdf`, `docs/schematic-symbols.json` |

## Fixed by the brief (user, 2026-10-23)

- 6HP. 2 in / 2 out (CH32V307RCT6 + one codec: CS4270 until S3, CS4272 since S4), 192 kHz target, DC coupled, ±5 V (CV too).
- One pot per jack, a plain 0..1 volume (no gain). Inputs: socket then pot; outputs: pot then socket.
- USB-C on the front panel; BOOT/RESET on the PCB only.
- MCU/USB on a second PCB soldered to the pot board with 2.54 mm pins.
- JLC assembles the SMD (MCU, codec); jacks, pots and the pin strips are hand-soldered.

## Design rules

- Carrier: all SMD on B; MCU board: all SMD on F (each board single-sided assembly). Both 4 layers.
- J6/J7 (carrier) and J102/J103 (MCU board) share XY and pin nets: change them together. The strips
  are in the carrier BOM; J102/J103 are copper only (excluded from BOM/CPL).
- Interface nets (same names on both schematics): `+3V3`, `GND`, `SWDIO`, `SWCLK`, `NRST`, `BOOT0`,
  `I2C_SCL`, `I2C_SDA`, `I2S_SCLK`, `I2S_LRCK`, `I2S_ADC`, `I2S_DAC`, `CODEC_RST`.
- Firmware-visible pins (CH32V307): PB6/PB7 USBHS, PB13/PB12/PB15 I2S2 RX, PB3/PA15/PB5 I2S3 TX,
  PB10/PB11 I2C2, PB14 codec RST, PA9 VBUS sense. Log any change in `docs/research.md`.
- Stack (geometry.json `stack_Z_mm`): header plastic 2.5 mm, MCU board 1.6 mm, USB-C 8.8 mm, panel
  rear at 10 mm. Changing any of them moves the USB-C mouth; it must stay at or in front of the panel
  front minus 0.3 mm.
- Courtyards >= 1.0 mm from `Edge.Cuts` (both boards, `min_copper_edge_clearance` 1.0 mm); SMD pads
  >= 2.0 mm from pot/jack pads (`tools/check_edges.py`). Manual divide-and-conquer routing, no
  autorouters, no vias in SMD pads (root `AGENTS.md`).

## Sources and generators

- `tools/build_schematic.py` + the two circuit tables own both schematics, `USBAUDIO.kicad_sym` and
  `sym-lib-table` (modules/32bit drawing engine). The build asserts nothing dangles and that each
  native netlist equals its circuit table.
- `tools/build_layout.py` places from `docs/geometry.json`, parks the rest and takes nets/values/fields
  from the native netlists. Once SMD placement starts by hand, the boards own placement.
- `tools/import_footprints.py` rebuilds `USBAUDIO.pretty` (stock KiCad, Bread Modular jack/pot/K2,
  and the HRO TYPE-C-31-D-15 land drawn from the manufacturer drawing).

## Verification (S1, 2026-10-23)

- Native ERC `--severity-all`: 0 (carrier), 0 (MCU board).
- Native DRC `--severity-all --schematic-parity --refill-zones`: 0 violations, parity 0 on both boards;
  unconnected 192 (carrier) / 83 (MCU board): nothing routed yet. Panel DRC 0.
- Shared `kicad_tools.py check` (both profiles): ERC 0, DRC 0 violations, parity 0; only the
  unrouted items; `order_ready: false`.
- Courtyards >= 1.02 mm from the edges; closest SMD to a pot/jack pad 3.66 mm.
- Not done (at S1): SMD placement, routing, JLCPCB export / assembly audit, firmware, bench.

## Verification (carrier S2 + R2, 2026-10-24)

- S2: U4 OPA1679 quad -> U4 + U7 OPA1678 duals (+ C31 / C32 decoupling). Native ERC 0.
- R2 routing (`research/route/r2.py`): native DRC 0 violations / 0 unconnected / parity 0, shared
  `check` clean, no vias in SMD pads, no In1 tracks, one 3.1 mm -12V_F In2 hop; In1 GND, In2 +3V3 and
  the In2 +5VA island one piece each. Courtyards >= 1 mm from the edge; closest SMD pad to a pot/jack
  pad 2.03 mm.
- JLCPCB export (2026-10-24, `jlcpcb/README.md`): carrier 72 parts bottom, MCU board 23 parts top,
  live audit: C20-C23 (C0G 0603) and R1 (2512) are Extended R/C, user decision open.
- Not done: firmware, bench.

## Scoped repair (carrier S3/R3, MCU S1/R2)

User authorization: fix USB and R36/R37 only; other review findings deferred for now.
See `docs/usb-output-fix.md` for actual path lengths, geometry, source references,
resistor derating assumptions and the limits of the repair. No fixed/mechanical
placements or MCU pins changed. Carrier R36/R38 and R37/R39 are 2k/0.25 W pairs in
parallel (1k/0.5 W effective); MCU has an explicit JLC04161H-7628 stack, In2 USB GND
island and USB_HS class. Run `tools/check_usb.py` in addition to the shared gate.
Regulator, mute, firmware and other deferred items remain unchanged/unqualified.

## Carrier S4 / P2 / R4 (2026-11-21 / 22), S5 / R5 (2026-11-22)

User direction after two built boards crackled (I2S inputs locking at random bit offsets): power
header to the side, everything lower, two M3x10 standoffs above the MCU board, the codec's successor,
and hardware changes against the fault. The circuit of record is the docstring of
`tools/circuit_carrier.py`; `docs/research.md` section 9 has the decisions.

- **Codec:** CS4272-CZZR (TSSOP-28), differential in / out, I2C control port at **0x10**, master,
  external MCLK from Y1 24.576 MHz (XTI = GND). Firmware-visible change: new register map
  and address; pins on J6 / J7 unchanged.
- **Clock lines:** R14 / R16 10k pull-downs on I2S_SCLK / I2S_LRCK, R48 47k on I2S_DAC, TP1 on MCLK.
  SCLK and LRCK must stay on B from the codec pin into R11 / R12 without a via; R14 sits at J7.3.
- **Dual op-amp (S5):** `DUAL` in `tools/circuit_carrier.py` = NE5532 (NE5532DR C7426, JLCPCB Basic)
  on U4 / U5 / U7, all on +/-12 V. Bipolar inputs: 200 nA typical / 800 nA maximum bias current, so
  a 50k pot at mid travel adds 2.5 mV typical / 10 mV maximum at its follower (datasheet values).
- **Reference (S5):** no buffer op-amp. R49 2.7k from +5VA over R40 510R + R41 2k: VCOM_BUF =
  0.482 x VA (2.41 V), C38 10u + C39 100n to GND; VB_IN = VCOM_BUF x 2/2.51 with **no capacitor**
  (the ratio must hold at every frequency so the reference stays common to AIN+ and AIN-). Nothing
  may load the codec's VCOM pin (25k source, 1 uA).
- **Mechanics:** `docs/geometry.json` (P2). The MCU board file is unchanged and uses
  `mcu_kicad_origin_mm`; `tools/check_edges.py` applies it. MS1 / MS2: carrier hole = panel hole,
  M3x6 screws only.
- **Routing contract (R4):** four F trunks between J6 and the ADC bundle (X4.6 A out, X5.1 -12V_F,
  X5.6 B out, X6.1 +12V_F): no via may sit between X4.3 and X6.5 from Y22 to Y49 except the -12V_F
  one at the bottom. The SDA via at (10.2, 38.37) has 0.22 mm to U8.5, the SCL lane and the R28 via:
  do not move one of them alone. Batches and how to replay them: `research/route-s4/NOTES.md`.
  R5 (`r16.py`): R49 / C38 / C39 in U8's place on B, on U8's +5VA via (6.9, 35.2) and the GND vias
  at (10.9, 30.9) / (11.4, 35.9); VCOM_BUF keeps its X11.5 lane to R40.
- **Verification (S5 / R5):** ERC 0; DRC 0 (all severities) / unconnected 0 / parity 0, no
  exclusions; shared `check` clean with equal manifests on both profiles; `tools/check_edges.py`
  1.01 mm / 2.01 mm; 818 tracks / 114 vias, none in SMD pads, no inner-layer tracks, planes as R4.
  Not built, not measured; no CS4272 firmware yet.
