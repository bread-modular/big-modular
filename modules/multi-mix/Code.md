# MULTI-MIX contract (S3 schematics, R1 routing)

| | |
|---|---|
| KiCad projects | `hardware/multi-mix.kicad_{pro,sch,pcb}` (carrier), `hardware/multi-mix-mcu.kicad_{pro,sch,pcb}` (MCU board), `panels/front-pcb/multi-mix-panel.kicad_{pro,pcb}` (20HP panel); one shared `MULTIMIX` symbol/footprint library |
| Generators, profiles | `tools/` (`build_schematic.py`, `circuit_carrier.py`, `circuit_mcu.py`, `build_project.py`, `build_layout.py`, `import_footprints.py`, `sexp.py`, `kicad-project.json`, `kicad-project-mcu.json`) |
| Geometry contract | `docs/geometry.json` (panel frame, 20HP; S3, hand-edited since routing) |
| Circuit intent and decisions | `docs/research.md` (MCU pins and strip maps: section 5; datasheet review: 6a; placement: 8; S2/S3 changes and R1 routing: 9) |
| Evidence | `docs/erc/` (native ERC JSON), `docs/*-schematic.pdf`, `docs/schematic-symbols.json`, `hardware/MULTIMIX.pretty/PROVENANCE.json` |

## Fixed by the brief (user, 2026-11-09)

- Digital mixer: analog I/O through a PCM3168A, mixing, sends and returns in the CH32V307.
- 4 channel inputs, 2 returns, SEND A / SEND B outputs (+ MAIN OUT, mono, as modules/4mix) and two host-assigned
  USB 1 / USB 2 outputs (DAC4/DAC5, bottom-right corner, user 2026-11-09); returns can come
  from USB. To the host: the 4 inputs and 2 returns, no master. VOL as MIDI CC7, the other knobs as CCs.
- Knobs through a mux. modules/4mix's panel layout (jack/pot references kept), widened to 20HP (user,
  2026-11-09): the MCU board takes 4MIX's MAIN/OUT spot, OUT stacks over MAIN.
- Units daisy-chain on an internal 2x5 IDC clock link (CLK OUT -> next unit's CLK IN) that shares the codec
  clocks only, for sample-locked USB multitrack recording; each unit keeps its own USB and its own outputs
  (no audio or control on the link, user 2026-11-09).

## Design rules

- Carrier: all SMD on B (as modules/4mix and usb-audio-max); MCU board: every part on F, nothing on B (user,
  2026-11-10). 4 layers both.
- J12/J13 (carrier) and J112/J113 (MCU board), 2 x 1x12, share XY and pin nets: change them together.
- Interface nets (same names on both schematics): `+3V3`, `GND`, `SWDIO`, `SWCLK`, `NRST`, `BOOT0`, `I2C_SCL`,
  `I2C_SDA`, `CODEC_RST`, `I2S_SCLK`, `I2S_LRCK`, `I2S_ADC1`, `I2S_DAC1`, `POT_ADC`, `MUX_S0`-`MUX_S3`,
  `NORM_PROBE`, `LINK_N`. No spare strip pins.
- Firmware-visible pins: `docs/research.md` section 5. 48 kHz only (DOUT1/DIN1). LINK_N low = clock slave: the
  codec ADC must stay in slave mode then (its reset default). PB14 and PB15 share the DAC1 source node (I2S or
  SPI-slave TX, `docs/research.md` 6a F1): only one may drive. PA15/PB3 are tied to PB12/PB13 (LRCK/BCK) on the
  MCU board. Log any pin change in `docs/research.md`.
- Placement: `docs/geometry.json` records the panel-located parts (jacks, pots, J6/J7/J8, J12/J13 = J112/J113,
  J15/SW1/SW2, MS1-MS3, USB-C, notched MCU outline). **`tools/build_layout.py` must not be rerun**: both boards
  are placed and routed by hand (it still describes P3 and would park every SMD part).
- Routed boards: the through-hole parts are fixed (user); SMD parts and copper may move with a reason. Carrier
  In1 is GND with no tracks; In2 is +3V3 with a +5VA island and two +3V3_C islands: a +3V3 via inside the +5VA
  island has no plane and needs a track. F carries the E-W analog fan and CLK OUT bus, B the N-S mux lanes.
- CLK OUT (J6) / CLK IN (J7) pinout (`docs/research.md` section 4) must stay Eurorack-power-cable safe:
  only the 4.7k/10k-protected DET on pins 1-2, GND or buffered + 150R clocks on 3-8, nothing on 9-10.
- Root `AGENTS.md` placement/routing rules (1 mm edge keep-out, 2 mm hand-solder clearance, no vias in SMD
  pads except the codec's own thermal vias, manual divide-and-conquer routing).

## Sources and generators

- `tools/build_schematic.py` + the two circuit tables own both schematics, `MULTIMIX.kicad_sym` and
  `sym-lib-table` (modules/usb-audio-max's engine). The build asserts nothing dangles and that each native
  netlist equals its circuit table.
- `tools/import_footprints.py` builds `MULTIMIX.pretty` (stock KiCad, Bread Modular jack/RV09/K2, the PCM3168A
  land and HRO USB-C from usb-audio-max) and `fp-lib-table`.
- `tools/build_project.py` writes both `.kicad_pro` (modules/32bit settings, 1.0 mm copper-to-edge, Power class).

## Verification (S1 + P1, 2026-11-09)

- Native ERC `--severity-all`: 0 (carrier, 212 parts / 140 nets), 0 (MCU board, 26 parts / 32 nets); netlists
  equal the circuit tables (build assertion). Re-run after the clock-only link change (D11 dropped).
- Live JLCPCB lookups of the new codes and the key reused ones (`docs/research.md` section 6).
- Rendered and inspected (`docs/*-schematic.pdf`).
- P1 placement (`docs/research.md` section 8): build assertions (1 mm edge keep-out, closest 1.075 mm; nothing
  under the MCU board; SMD >= 2 mm from pot/jack pads, 4.18 mm; panel label/knob clearances); native DRC with
  parity: carrier and MCU board 0 violations / parity 0 (opens only: unrouted), panel 0; shared `check` ERC 0 /
  DRC 0 / parity 0 + the same opens. Datasheet review (`docs/research.md` 6a) added PB4 to the MCU board (ERC 0).
- P2 rework (`docs/research.md` section 8, P2a-P2e): same checks plus no through-hole pad under the B box
  headers; closest edge 1.025 mm, SMD to pot/jack pad 2.13 mm; carrier 0 / parity 0 / 496 opens, MCU board
  0 / 0 / 93, panel 0; shared `check` ERC 0 / DRC 0 / parity 0.
- P3 rework (`docs/research.md` section 8, P3a-P3c): one MS3 above the USB-C, MCU board 7.7 mm lower with a
  notch over IN4, USB 1/2 jacks + U8; ERC 0 both (carrier 233 parts / 152 nets); closest edge 1.025 mm; carrier
  0 / parity 0 / 499 opens, MCU board 0 / 0 / 93, panel 0; shared `check` ERC 0 / DRC 0 / parity 0.
- **S3 + R1 (2026-11-10, `docs/research.md` section 9):** single-sided MCU board extended to the carrier top
  (MS3 notch), two 1x12 strips, J15/SW1/SW2 moved, R65/C50 +3V3_POTB; all SMD placed and both boards routed by
  hand. Native ERC 0 both (carrier 232 parts, MCU board 27). Native DRC `--severity-all` with parity, zones
  refilled: carrier 0 violations / 0 unconnected / parity 0, MCU board 0 / 0 / 0, no exclusions. No vias in SMD
  pads, no In1 tracks, courtyards >= 1.00 mm from the edge, SMD >= 2 mm from pot/jack pads, MCU outline clear of
  the carrier's F courtyards (MS3 0.45 mm, IN4 0.505 mm, RV1 0.645 mm). Planes one piece each apart from
  spoke-tied header-pin fragments and two track-fed +3V3 via pads inside the +5VA island. Shared `check`
  (`research/check-r1-*`): MCU board no findings; carrier ERC/DRC/parity 0 plus four name-only `/` vs `{slash}`
  differences on two pin-named nets and the three reference-less standoffs (present since P1, not waived).
- Not done: fab review, JLCPCB export, panel re-check, firmware, bench.
