# 32bit research and circuit intent (S1 schematic, S1 THT placement)

Bread Modular `32bit-5v` (the updated 32bit: ESP32-S3 + ES8388) as a 6HP Eurorack module on a
4-layer carrier. Brief (user, 2026-10-21):

- 6HP, modules/16bit as the inspiration, 4 layers allowed.
- MIDI in on top; two audio inputs and two CV inputs on the top; two outputs at the bottom.
- Two pots, a mode button and an LED.
- USB and BOOT/RESET buttons as in modules/16bit.
- Schematic with nets connected for readability; THT placement to see it; then (user, same day)
  manual divide-and-conquer routing (R1, done: section 6).

Nothing here is bench-tested. LCSC codes are reused from modules/16bit and the BM 32bit-5v BOM;
no live sourcing check was made for this module.

## 1. Bread Modular 32bit-5v baseline (read-only source)

Source: `~/data/projects/bread-modular/modules/32bit-5v` (netlist exported natively from
`32bit-5v.kicad_sch`; firmware `code/32bit/main`).

| Function | Bread Modular 32bit-5v | Firmware |
|---|---|---|
| MCU | ESP32-S3-WROOM-1U-N16R8 on +3V3_ESP32 (FB1 GZ2012D121TF, 100n + 10u); EN 10k/1u/100n + RESET button; IO0 BOOT button | ESP-IDF |
| Codec | ES8388 on +3V3_8388 (10R + 100u, 3 x 10u, 4 x 100n), VREF 10u, VMID 10u + 100n, ADCVREF 10u + 100n, CE = GND (0x10) | `bm_es8388_init_new_bus(I2C_NUM_0, 48, 47)` |
| I2S | IO21 MCLK, IO14 SCLK, IO12 LRCK, IO13 DSDIN, IO11 ASDOUT, each through 33R | `bm_audio.c` |
| I2C | IO47 CCLK, IO48 CDATA, 4.7k pull-ups to +3V3_8388 | |
| Audio | AIN_1/2 header -> LIN1/RIN1 with 100k to VMID (DC coupled); LOUT1/ROUT1 -> 1k -> header | |
| CV | CV1/2 header (100k pull-up to +3V3) -> MCP6002 follower -> 1.5k -> RV1/RV2 50k -> IO9/IO10 | `ADC_CHANNEL_8/9` |
| MIDI | RXD0 (GPIO44) from the INPUT header, TXD0 to the OUTPUT header | `UART_NUM_0`, RX 44 |
| Mode | SW4 IO8 to GND, LED IO18 -> LED -> 1k | `LED_PIN 18` |
| Gates | IO1/IO2 -> 1k -> header | |
| USB | USB-C data only, D+/D- straight to the module, 5.1k CC, 10n shield; VBUS unused | |
| Power | 5 V header -> AP2112K-3.3 | |

## 2. Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Keep the BM core: ESP32-S3-WROOM-1U-N16R8, ES8388 with all BM decoupling/reference parts, BM I2S 33R series, I2C pull-ups, FB1, EN RC, BOOT/RESET, USB-C data only, and BM's GPIO map | BM firmware ports unchanged (except the MIDI inversion, D5) |
| D2 | Power as modules/16bit: ±12 V through B5819W, AMS1117-5.0 -> +5V -> AMS1117-3.3 -> +3V3 | Proven in 16bit. **Thermal limit:** at ~110 mA (ESP32-S3 at 240 MHz, radio never used, codec) U8 drops 6.6 V = ~0.75 W, so it needs a tab patch + thermal vias. Wi-Fi/BT bursts (300-500 mA) are out of scope; the U.FL connector stays unused. User 2026-10-21: the radio is never used (firmware keeps Wi-Fi/BT off), so the linear chain stays |
| D3 | CV1/CV2 = the modules/16bit chain: jack normalled to +5V -> RV1/RV2 50k attenuator -> U7B/U7A follower (±12 V) -> 100k / 56k / 120k level shift, BAT54SW, 1n -> U6B/U6A MCP6002 -> IO1/IO2 (CV1 on the B halves, CV2 on the A halves; ADC pins moved from BM IO9/IO10 in R1, for layout) | Same as BM's behaviour (unpatched = knob, patched = pot scales the CV) but bipolar ±5 V CV safe on 3.3 V ADC pins. The two pots are these attenuators, as on BM |
| D4 | Audio in: 100k / 22k divider (x0.18) -> U7C/U7D follower -> 1u -> 1k -> LIN2/RIN2 (BM LIN1/RIN1; second pair since R1, for layout), 100k to VMID (BM). No IN R normal (user 2026-10-21: the firmware handles mono) | ±5 V -> ±0.9 V (ES8388 ADC full scale ~1 Vrms at 0 dB PGA; clips near ±7.5 V); PGA adds gain for quieter sources. AC coupling because the codec input sits on VMID. The 1k limits clamp current on a ±12 V mis-patch |
| D5 | MIDI in = modules/16bit NPN front end + JP1 (shipped open) -> RXD0 | 1-2 protected (firmware: `uart_set_line_inverse(UART_NUM_0, UART_SIGNAL_RXD_INV)`), 2-3 direct (stock BM firmware) |
| D6 | Audio out: LOUT1/ROUT1 -> BM 1k -> 10u -> 100k to GND -> U5 TL072 gain 3.55 (56k/22k) -> 1k 0.5 W -> jack | ~1 Vrms codec full scale -> ±5 V; the codec output volume trims it. AC coupled (removes VMID). Bench check: full-scale swing (lesson from 16bit's low output) |
| D7 | Op-amps: U7 TL074 (CV A/B + audio-in C/D, all near the top jacks), U5 TL072 (outputs, near the OUT jacks), U6 MCP6002 (CV on +3V3) | One quad where the inputs are, one dual where the outputs are |
| D8 | MODE = 6 x 6 mm THT tact (16bit SW1) on IO8; LED = 3 mm red THT (16bit D1) on IO18 through 1k | BM pins; user's 16bit parts and printed cap |
| D9 | Dropped: TXD0 (BM TX header), IO1/IO2 gate outs, LIN2/RIN2/LOUT2/ROUT2 | Not in the brief; pins open |
| D10 | Footprints: BM ES8388 QFN-28 thermal-via land (model proxy: KiCad 10 QFN-28 4x4 0.4 mm), stock ESP32-S3-WROOM-1U (no 3D model: KiCad 10 ships none, a WROOM-1 proxy would misstate the length), BM RV09, BM K2 switches, BM FB1 on C_0805, BM AudioJacks PJ301M-12; stock for the rest | User preference for BM footprints |

## 3. Circuit (`hardware/32bit.kicad_sch`, ERC 0)

```
POWER  J6 ±12V -> D2/D3 -> ±12V_F; +12V_F -> U8 AMS1117-5.0 -> +5V -> U9 AMS1117-3.3 -> +3V3
ESP32  +3V3 -> FB1 -> +3V3_ESP32 (C5/C6); EN: R4 10k, C7 1u, C8 100n, SW3 RESET; IO0: SW2 BOOT
USB    J7 D+/D- -> U1 USB PHY; R11/R12 5.1k CC; C24 shield; VBUS open
MIDI   J1 T -> R3 100k to +3V3; R1 10k -> Q1 (D4) -> RX_Q (R2 22k); JP1 1 RX_Q / 2 MIDI_RX (RXD0) / 3 MIDI_IN
CV1/2  Jx T (TN = +5V) -> RVx 50k, wiper -> U7B/A -> 100k -> CVx_BUF (56k +3V3, 120k GND, BAT54SW, 1n) -> U6B/A -> IO1/IO2 (R1)
IN L/R J8/J9 T (J9 TN = IN_L) -> 100k/22k -> U7C/D -> 1u -> 1k -> LIN2/RIN2 (R1; 100k to VMID)
CODEC  U4 ES8388: +3V3 -> R5 10R -> +3V3_8388 (C30 100u, C31-33 10u, C34-37 100n); VREF C42,
       VMID C40/C41, ADCVREF C38/C39; I2S via R23-R27 33R; CDATA/CCLK R21/R22 4.7k; CE GND
OUT    LOUT1/ROUT1 -> R50/R55 1k -> C45/C46 10u -> U5A/B (R51/R56 100k bias, 56k/22k) -> R54/R59 1k -> J4/J5
MODE   SW1 IO8 to GND; IO18 -> R20 1k -> D1 -> GND
```

PWR_FLAGs: GND/+12V/-12V at J6, ±12V_F behind D2/D3, +3V3_ESP32 (FB1), +3V3_8388 (R5).

## 4. Placement (S1, `docs/geometry.json`)

6HP panel 30 x 128.5 mm, carrier 29 x 110 mm (as 16bit). Front, top to bottom: MIDI (X14.6 Y17.5),
IN L / IN R (Y32), CV1 / CV2 (Y46.5) at the side edges, P1 / P2 (Y62), OUT L / OUT R (Y99, side edges X5.5 / X24.5 like the top jacks, S2), MODE / LED
in the bottom corners (Y113.5), power header centred at the bottom. B side: USB-C at the top edge with
BOOT / RESET below it, as 16bit. The U1 module zone (courtyard 19.5 x 20.15 mm, X5.25-24.75,
Y71.0-91.15) is reserved between the pot pins and the OUT jack pads (0.6 / 1.6 mm). Every other SMD
part was parked in columns right of the board for group-by-group placement (all placed in R1, section 6).

SMD space is the hard part: the module takes the band where 16bit had its regulators. Plan for the
placement round: codec + audio-in + CV chain in the Y27-70 band (between the jack pads and under the
pot bodies), outputs + U5 between the OUT jacks, U8/U9 beside J6 / under the OUT jack bodies.

## 5. Open

- Thermal: U8 at ~0.75 W (D2). The radio is never used (user 2026-10-21).
- ES8388 full-scale levels (in/out) are datasheet-nominal; bench check gains.
- JLCPCB export: `jlcpcb/` (R2, section 7); stock is a dated web count, recheck before ordering.

## 6. R1 routing (2026-10-21)

Manual divide and conquer on `hardware/32bit.kicad_pcb` (batch scripts `research/r1/b*`, `c*`, `d*`, `e*`;
DRC report per batch). U1 sits left (X10.6), U6 and the ES8388 in the strip beside its right pin row;
the I2S 33R stack sits between the pots. Crossings of the pot row use the RV1/RV2 tab gaps on F:
centre gap D+, D-, EN, -12V, +12V; RV2 gap CV1_BUF, MIDI_RX, LIN, RIN, BOOT (staggered 45° bus to the
pin row between the pots). MIDI front end beside J1; MIDI_RX / BOOT / EN down the left edge on B.
USB-C pad ties as 16bit; D+/D- down the right edge on B. Codec supply (R5, C30-C35) right beside
the codec (user-placed, F01); a 0.4 mm F hop feeds C30 at pins 2/3, and a 0.3 mm In2 hop joins the
pin 16/17 island (C36/C37). Edge rule stays 0.5 mm (1 mm keep-out not required here): U1's left pin row (0.6 mm) and the EN/BUTTON lane beside it, J7, SW2/SW3, the RV1/RV2 tabs and the user-placed codec cluster (C36, C42 and their vias) cannot meet 1 mm. G01 pulled the free-standing items to >= 1 mm copper clearance: C24 + via, D6 + vias, C27 + vias, C46 and the LED run (1 mm test: 69 -> 55 items, all tied to the parts above). ESP32 decoupling / EN RC
in the strip below the module. LED along the bottom edge on F to R20 beside D1.
Firmware-visible changes: `docs/firmware-pins.md`. Result: DRC 0 / unconnected 0 / parity 0.

## 7. R2: 2 mm hand-solder clearance (2026-10-22)

User direction: meet the root `AGENTS.md` 2 mm rule (every SMD pad >= 2.0 mm, copper to copper, from
every jack and pot pad, lugs included). R1 had 35 SMD parts under 2 mm (worst R3 0.25 mm from J1).
Jacks, pots, SW1, D1, J6 and the panel are unchanged. Batch scripts, path helper (`rt.py`, one
connection at a time, each path checked), audit and DRC reports: ignored `research/r2mm/`. Every batch
written to the board with full native DRC + parity.

- Free space: a full-width band Y106.0-108.4 (between the J2/J3 S zones and the pot lugs), the RV1/RV2
  lug gaps (X106.1-108.9 / X121.1-123.9), a 1 mm band Y115.65-116.6 under the lugs, the band
  Y147.4-149.1 between the OUT jack T and TN pads, and a 1 mm strip beside J4/J5 at each edge.
- Top: SW2 (BOOT) turned 90 deg beside SW3 (X109.85 Y62.45); JP1 0.75 mm down, R1 0.3 mm down; MIDI_RX
  leaves JP1 between the SW2 pad columns on an F hop to the left bus. R3 (MIDI pull-up) to X119.0 Y71.0,
  between J1 and J9. R40/R44 in the pockets beside J1's sleeve, R41/C43/R42 and R45/C44/R46 in the
  columns beside U7 (CODEC_RIN via moved off R46's pad); C29 below U7 on a -12V_F F tap.
- Regulators: U8/U9 2.5 mm down (pads in the Y106-108 band), tab patches, pours and the four thermal
  vias moved with U8; C1 / C4 beside them in the band; C3 above the U8 tab. J3's +5V normal now runs
  above the U9 tab.
- CV conditioning: R13/R14 (R16/R17) stacked in the lug gap, D5 (D6) at its foot, R15 + C25 (R18 + C26)
  horizontal in the 1 mm band under the lugs (2.02-2.03 mm, the tightest spots on the board).
- Codec side: U6 0.6 mm up (2.02 mm from J5 T), C40 0.23 mm up/0.5 mm left (user-placed codec cluster,
  moved only for U6's courtyard), R5 0.8 mm right. C27 and R55 in the right edge strip, R58 and C46 in
  the Y148 band, D2 1.6 mm down below J5. R54 0.3 mm right, R59 0.4 mm left.
- ESP32 side: C5, C6 (+3V3_ESP32) and C7, C8, R4 (EN RC) stacked in the 1 mm strip left of J4, FB1 in
  the Y148 band; C5's GND pad ties straight to U1 pin 1 with its own via.

Result: 0 SMD pads under 2 mm (closest U6/R15/R18 2.02 mm, C25/C26 2.03 mm, R5 2.05 mm, R54 2.06 mm).
Native ERC 0; DRC 0 / unconnected 0 / parity 0, no exclusions; no vias in or touching SMD pads; no
tracks on In1; In1 GND and In2 +3V3 one piece each; no dangling ends, zero-length or duplicate
segments; new off-grid points only on pad axes (45 deg bends off 1.27 mm / 0603 pad centres).
Courtyards under 0.5 mm from the edge (copper still >= 0.5 mm, the 32bit edge rule): C6 0.25 mm,
C27/R55 0.30 mm, R5 0.35 mm, besides R1's J7, SW2/SW3 and jacks. The R1 JLCPCB export no longer
matches the board (CPL positions, Gerbers): it needs a new export.

B silk MIDI JP1 labels (2026-10-22, user request, as modules/16bit): "P" beside pad 1 (RX_Q, protected)
and "D" beside pad 3 (MIDI_IN, direct), legend "P=PROT / MIDI JP1 / D=DIRECT" between JP1 and J7
(X116.5 Y65.35-68.15), 0.15 mm stroke, mirrored. Silk only; DRC 0 / 0 / 0 with silk checks included.

User edge-margin moves, option A (2026-10-22): the user moved C6, R5, C27, R55 and C46 in KiCad for
more courtyard-to-edge margin (C6 0.53 mm, C27/R55 0.82 mm, R5 > 1 mm) and chose to keep them over the
2 mm compromise spots (R5 0.39 mm, C27/R55 0.47 mm edge). Accepted 32bit exceptions to the 2 mm
hand-solder rule: R5 1.33 mm from RV2 pad 3, C27 1.62 mm and R55 1.63 mm from J5 T, C46 1.75 mm from
J5 TN. Every other SMD pad >= 2.02 mm. DRC 0 / 0 / 0, no vias in SMD pads, planes one piece.

R2 JLCPCB export (2026-10-22, shared exporter, commands in `jlcpcb/README.md`): carrier ZIP, BOM and
CPL re-exported; BOM byte-identical to R1, 43 CPL rows moved; every CPL row matches its footprint
position and side (90 / 90). PTH drill: 106 routed vias (all 0.3/0.6 mm), 21 x 0.2 mm footprint
thermal vias. Panel re-exported unchanged (only Gerber dates differ). Shared `check` afterwards: ERC 0,
DRC 0 / 0 / 0, manifest equal. Reports in `research/export-r2/`.
