# 32bit research and circuit intent (S3 schematic, R3 routing)

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


## 8. S3 / R3: ESP32-S3R8 on the carrier instead of the module (2026-11-15)

Why: no Espressif module is JLCPCB Economic PCBA (live catalog 2026-11-15: every WROOM-1 / 1U / 2 / MINI
listing "Standard only"), and one Standard part makes the whole board Standard. The bare chips are
Economic. User decision 2026-11-15: ESP32-S3R8 + W25Q128JVSIQ + 40 MHz crystal, then route it well.

Circuit (Espressif ESP32-S3 hardware design guidelines and the ESP32-S3-WROOM-1 reference schematic):

- **U1 ESP32-S3R8** (C2913194, QFN-56 7 x 7 mm, 8 MB octal PSRAM in the package on GPIO33-37 / SPICS1,
  3.3 V). With U2 it is the N16R8 module's memory map, so the firmware and `sdkconfig` are unchanged.
- **U2 W25Q128JVSIQ** (C97521, Basic, SOIC-8 208 mil, QE set from the factory) on SPICS0 / SPICLK / SPID /
  SPIQ / SPIWP / SPIHD, supplied from **VDD_SPI** (the chip's own 3.3 V output, C16 1u + C17 100n). R7 0R in
  the clock at the chip, 0603 on purpose: SPIQ runs between its pads, so the clock crosses SPIQ on one layer.
- **Y1 40 MHz**, 3.2 x 2.5 mm, 10 pF load (C5210647), C9 / C10 12p C0G, R6 0R in XTAL_P (place for an
  inductor if harmonics ever matter; they don't without the radio).
- Supply: VDD3P3 (2, 3) and VDDA (55, 56) on +3V3_ESP32 behind FB1 with C6 10u, C12 1u, C5 100n, C13 10n;
  VDD3P3_RTC (20) and VDD3P3_CPU (46) on the +3V3 plane with C14 / C15 100n.
- EN: R4 10k + C7 1u + C8 100n (as before). GPIO0: R8 10k pull-up (new; the BOOT trace runs the length of the board).
- **No radio:** LNA_IN is open, no antenna, matching network or RF keep-out. Firmware must not start
  Wi-Fi / BT. Strapping pins GPIO3 / GPIO45 / GPIO46 are open (internal defaults: SPI boot, VDD_SPI 3.3 V).
- What is lost: the module's tested clock / RF layout and its shield. Nobody has built this circuit here.

R3 routing (manual, batches `research/s3/s01..s06`, DRC after each):

- U1 on B at X109.3 Y134.6, rotated so the flash pins (29-35) face up, I2C / UART / crystal / VDDA (43-56)
  face right, EN / BOOT / CV ADC (4-7) face down and I2S / USB / LED (16-27) face left.
- Flash above the chip: CS / Q / CLK enter the window between its pad columns, WP and D run outside, HD and
  VDD_SPI hop over them on F. C16 at pin 29, C17 at U2 pin 8.
- Right: C15 at pin 46 with its own +3V3 and GND vias; crystal about 3 mm from the chip, XTAL_N over the top of
  the crystal to Y1 pad 3 + C10, XTAL_P through R6 to Y1 pad 1 + C9; the two case pads tied under the crystal.
  VDDA caps C13 at pins 55 / 56, C5 / C12 below pins 2 / 3, fed from FB1 + C6 (left of them) over a 0.4 mm F hop.
- The F bus above the area (USB, EN, +/-12 V, CV, MIDI, codec inputs, BOOT) only lets a via land west of
  X114.2 or east of X118.7. EN drops through a via at Y127.2 to its RC (R4, C7, C8 between the flash and
  the codec) and through a second via to pin 4. BOOT changes to B south of the I2C lines, back to F over
  the crystal and to B again for pin 5 (R8 on the first B piece).
- CV2_ADC now leaves U6 between its pads 6 and 5 so CV1 / CV2 arrive in pin order; rows EN, BOOT, CV1, CV2
  run below the chip.
- Left: I2S DIN / LRCK / DOUT / BCLK and USB D+ / D- take vias above the flash, run west on F above it and
  down the left edge to a via staircase beside the pin column (fan-out lines 0.6 mm apart so every track
  clears the neighbouring via). MCLK stays on B (over the flash and down its west side). LED comes up the
  edge on B from a via below the BUTTON row. C14 at pin 20.
- BUTTON and LED F lanes at the left edge now end below the chip (were at the module's pins).

Result: DRC 0 / unconnected 0 / parity 0, no exclusions; checks in `Code.md`. Open: JLCPCB preview, bench
(crystal start-up, flash boot, PSRAM test, USB download with BOOT / RESET).

## 9. S4: usb-audio S5 carrier + ESP32-S3 MCU board (2026-11-23; drawn and routed, section 9.1)

Why (user, 2026-11-23): 32bit runs `master` in front of loud PA systems. With the same processing in
Ableton, the modules/usb-audio input is silent and the 32bit is audibly noisier, so the difference is
the 32bit audio hardware: ES8388 (about 95 dB) fed from the ESP32's +3V3 through R5 10R, MCLK divided
from the ESP32 PLL. The bypassed-chain floor was not measured; this is a plan, nothing is drawn yet.

User decisions (2026-11-23):

- **Two boards as modules/usb-audio:** the analog carrier of usb-audio S5 and a separate MCU board
  on two 1x10 2.54 mm strips over the carrier F side, vertical USB-C through the panel.
- **MCU board = ESP32-S3** (ESP32-S3R8 + W25Q128JVSIQ + 40 MHz crystal, the section 8 circuit), not
  the CH32V307 board: `master` uses 41-57 % of the ESP32-S3 at 240 MHz, and the CH32V307 has the
  8 MHz I2S limit.
- **No CV inputs, no MIDI in.** Two pots and the audio IO only.
- AMS1117-5.0 for +5VA as on usb-audio (proven quiet there); no TPS7A4700.
- **Two in, two out** (IN L / IN R, OUT L / OUT R, stereo as on usb-audio). What goes where is up
  to the firmware (`master` today: kick + mix in, its mono out on both OUTs).
- **Pots and MODE are firmware controls:** two 50k RV09 pots read by the ESP32 ADC (not in the audio
  path, so the usb-audio per-jack volume pots are dropped), the MODE button and LED on GPIOs. Their
  meaning is set by the firmware; `master` reads none of them yet.

Carrier (copy of usb-audio S5, `modules/usb-audio/tools/circuit_carrier.py`):

- CS4272 (I2C 0x10, clock master from a 24.576 MHz oscillator, 48 kHz), the ESP32 as I2S slave.
  R14 / R16 10k pull-downs on SCLK / LRCK, R48 47k on the DAC data line, MCLK scope pad.
- Inputs: inverting stage + differential ADC drive (NE5532), R49 2.7k VCOM divider. Outputs:
  difference amplifier per channel (NE5532) + 1k 1206 output resistor. The usb-audio IN / OUT volume
  pots come out: unity gain jack to codec and codec to jack (fixed resistors for the 10 Vpp scaling,
  checked when the circuit is drawn).
- POT1 / POT2: 50k RV09 from +3V3 to GND, wiper -> 1k + 100n -> ESP32 ADC1. MODE button to GND
  (internal pull-up) and the MODE LED + series resistor on GPIOs, on the panel side of the carrier.
- +12V_F -> AMS1117-5.0 -> +5VA (codec VA and analog stages only); +12V_F -> 33R 1 W -> AMS1117-3.3
  -> +3V3 (MCU board); +3V3 -> FB1 -> +3V3_C (codec VD / VLC).
- RESET (EN) / BOOT (GPIO0) buttons on the carrier B side; the ESP32-S3 also enters download mode
  over its own USB, so they are for recovery.
- Side power header, M3x10 standoffs MS1 / MS2 above the MCU board, 6HP panel.

MCU board (new, usb-audio MCU board outline 29 x 29.55 mm and strip positions):

- ESP32-S3R8 + W25Q128JVSIQ + 40 MHz crystal + decoupling as section 8; native USB on GPIO19 / 20
  via USBLC6-2SC6 to the vertical HRO USB-C; no radio (LNA_IN open, no antenna keep-out).
- Link: J7 unchanged (+3V3 GND SCLK GND LRCK ADC DAC CODEC_RST GND GND). J6 = 1 +3V3, 2 GND,
  3 POT1, 4 POT2, 5 EN, 6 GPIO0, 7 I2C_SCL, 8 I2C_SDA, 9 MODE, 10 LED (usb-audio: SWDIO / SWCLK /
  NRST / BOOT0 on 3-6, GND on 9 / 10). J6 keeps one GND, J7 has four. POT1 / POT2 on ADC1 GPIOs
  (GPIO1 / GPIO2 as 32bit CV1 / CV2). The pinout differs from the CH32V307 board: the two MCU boards
  are not interchangeable (silk it).

Firmware: `master` keeps the chain and the Web Serial page; the ES8388 setup becomes a CS4272 driver
(I2S slave, 24-bit), shared with modules/usb-audio, which has no CS4272 driver yet either.

Risk: no CS4272 board is built yet. Build usb-audio S5 first (or in the same order) so the codec,
its clocking and the driver are proven on the bench before 32bit depends on them.

Open (plan stage; answered in 9.1): ESP32-S3 current from the carrier +3V3, panel and jack / pot rows.

### 9.1 Result (2026-11-23)

User: "decide it [the ESP32-S3 current] based on the current 32bit and spec sheets. Do the schematics and
do the routing. Add the M3 screws for strength just like in the new USB Audio."

- **+3V3 budget (datasheet, not measured):** ESP32-S3R8 at 240 MHz with the radio off 66..108 mA (datasheet
  v2.2 table 5-9) + flash / in-package PSRAM (~20 mA allowed) + codec VD / VL + oscillator (~20 mA) + LED,
  pots, pull-ups (~5 mA): ~130 mA typical, 180 mA design maximum. The usb-audio pre-drop R1 33R becomes
  **22R 1 W** (0.37 W at 130 mA, 0.71 W at 180 mA); U2 AMS1117-3.3 still sees >= 6.9 V at 180 mA from an
  11.4 V rail. Details in `tools/circuit_carrier.py`.
- **Carrier S4 / R1** (`hardware/32bit.kicad_{sch,pcb}`, `tools/circuit_carrier.py`, copied with its copper from
  the routed usb-audio S5 carrier by `tools/carrier_from_usb_audio.py`, batches `research/s4/b*.py`): volume pots
  out of the audio path, RV1 / RV2 control pots from POT_TOP (R52 2.2k + C42 1u, 3.03 V), MODE SW3, LED
  R53 + D3, RESET / BOOT on B, MS1 / MS2 M3x10 standoffs as usb-audio P2 (coaxial carrier / panel holes,
  `docs/geometry.json` `mount_standoffs`). 102 footprints / 63 nets, 753 tracks / 117 vias; ERC 0, DRC 0
  (all severities) / unconnected 0 / parity 0, no exclusions, no vias in SMD pads, no inner-layer tracks; In2
  +3V3 and +5VA one piece each, In1 one piece + the two pad-tied 1 mm2 slivers usb-audio has. Courtyards >= 1.02 mm
  from the edge, SMD >= 2.03 mm from pot / jack pads (C42 to RV1). Four duplicate stub segments inherited from
  the usb-audio copper removed (b14).
- **J6 as built** (carrier and MCU board): 1 +3V3, 2 GND, 3 EN, 4 BOOT (GPIO0), 5 MODE, 6 LED, 7 I2C_SDA,
  8 I2C_SCL, 9 POT1, 10 POT2. J7 as usb-audio. The plan's J6 order above was changed while placing the carrier.
- **MCU board S1 / R1** (R2 since the fab review, section 9.2; `hardware/32bit-mcu.kicad_{sch,pcb}`, `tools/circuit_mcu.py`, batches `research/s4/m*.py`):
  ESP32-S3R8 + W25Q128JVSIQ + 40 MHz crystal, USBLC6-2SC6 + vertical HRO USB-C (J101 at the usb-audio MCU board
  position, its D+ / D- / VBUS joins copied), 4 layers (F signal + all SMD / In1 GND / In2 +3V3 / B signal).
  27 footprints / 32 nets, 239 tracks / 41 vias; ERC 0, DRC 0 / unconnected 0 / parity 0, no exclusions, no vias
  in SMD pads (two 0.5 mm vias under the U102 body between its pad rows), no inner-layer tracks, In1 / In2 one
  piece each; courtyards >= 1.06 mm from the edge. EN / GPIO0 run as F lanes along the bottom and up the left
  edge; MODE / LED, the I2C pair and the pots go on B to J6; the I2S lines fan out on F to J7; USB D+ / D- on
  F / B to U102 and on B to GPIO20 / GPIO19 (USB full speed). B silk: name, revision and "J6: 32BIT ONLY".
- **GPIOs chosen for the layout** (MCU board; `docs/firmware-pins.md` section S4): I2S slave SCLK GPIO18,
  LRCK GPIO17, DIN (codec SDOUT) GPIO16, DOUT GPIO13 (R105 33R), codec RST GPIO12; I2C SDA GPIO9 / SCL GPIO8
  (R107 / R106 2.2k here); POT1 GPIO7 (ADC1 CH6), POT2 GPIO6 (ADC1 CH5), C112 / C113 100n beside the pins;
  MODE GPIO38, LED GPIO39; USB GPIO19 / 20.
- Shared `check` (both configs, `tools/kicad-project.json`, `tools/kicad-project-mcu.json`): ERC / DRC / parity 0,
  no findings, manifests equal after the S4 export.
- **S4 JLCPCB export (2026-11-23, `../jlcpcb/README.md`):** two separate orders, no panelization (user: the boards
  share no LCSC code, so a panel saves no feeder fees). `main/` carrier 88 parts / 33 rows (bottom Economic, 7
  Extended types) + FR4 panel, `mcu/` 25 parts / 14 rows (top Economic, 4 Extended types). Every code live-checked:
  free stock above the need, minimum purchase 1, no pre-order part; low: USB-C C22464480 414 free, CS4272 1,147.
  `tools/check_usb.py` (usb-audio HS check, re-mapped) flags D+ / D- mismatch (1.1 / 3.5 mm) and ~10 mm of B-side
  USB track over the In2 +3V3 plane: judged fine for ESP32-S3 full-speed USB, not waived, not re-routed.
- Open: CS4272 driver in `master` (shared with usb-audio, no CS4272 board built yet); JLCPCB preview; stock
  recheck before ordering; bench (+3V3 current and U2 / R1 heat, 40 MHz start-up, flash boot, PSRAM, noise floor
  against the usb-audio board); commit.

### 9.2 Fab review (2026-11-23): carrier R2, panel P2, MCU board R2

User: "check all is well and this is FAB ready". Checked from the files (scripts and reports in
`research/fab-review/`, ignored): shared `check` on both boards; the native netlists against the board pads
(carrier 283 pins, MCU board 152; values, footprints, LCSC fields); J6 / J7 against J102 / J103 pin by pin
(net and XY); panel holes against jacks, pot shafts, LED, MODE, standoffs and the USB-C; the pin tables of the
ESP32-S3R8, W25Q128JVSIQ, USBLC6-2SC6 and CS4272 against their datasheets (CS4272: MCLK driven from Y1 with XTI
grounded and XTO open, AD0 low = 0x10, SDOUT 47k down = slave until the firmware sets master); the MCU board's
USB-C land, position, outline and strips against the built modules/usb-audio MCU board (identical); vias in
SMD pads, edge and hand-solder distances, plane pieces; every LCSC code live (free stock, minimum purchase).

Fixed:

- **U2 AMS1117-3.3 heat, carrier R2.** +12V_F is about 11.65 V after D2. U2 drops (11.65 V - 22R x I - 3.3 V) x I
  plus its ground current: 0.71 W at 130 mA, 0.79 W at 180 mA; R1 takes 0.37 / 0.71 W. The usb-audio copper
  left the tab on its bare pad (7.6 mm2) with 0.5 mm tracks, which was enough for the CH32V307. The AMS1117
  datasheet gives 46 to over 90 K/W for SOT-223 depending on the copper, 125 C junction. `research/fab-review/t01.py`
  adds, all on +3V3: six vias under the U2 body (X11.7 / X13.1, Y83.6 / 85.0 / 86.4) and one below the tab
  (X15.5 Y87.8), 0.6 / 0.3 mm, none in a pad; a B zone round the tab (35 mm2, solid on the tab pad); an F zone
  above it in two pieces (16 mm2 over the body vias, 29 mm2 right of the -12V_F track with the C6 / C7 vias).
  The vias land in the In2 +3V3 plane. B silk now `S4 / R2`. ERC 0, DRC 0 (saved fills and refilled) /
  unconnected 0 / parity 0; 753 tracks / 124 vias; In1 one piece + the two slivers, In2 unchanged. Not
  measured. Raising R1 instead only moves the heat: 33R puts 1.07 W into the 1 W resistor at 180 mA.
- **Panel USB-C slot, P2.** Shell 8.94 x 3.16 mm with R1.58 ends at X15 Y24; slot 9.5 x 5.2 mm at Y24.75 with
  R2.6 ends centred at X12.85 / X17.15. The shell's upper corners sit 0.034 mm outside those arcs: the 0.27 mm
  above the shell exists only between the arcs. The 1.5 mm downward extension (usb-audio-max bench fix) made
  the ends rounder and brought this in. 11.0 x 5.2 mm puts the arcs over the shell's own (X12.1 / X17.9):
  0.27 mm round the upper half. `docs/geometry.json`, `tools/build_layout.py panel`, printed panel and panel
  Gerbers redone; panel DRC 0. The regenerated panel file sits at the carrier's sheet origin (the first S4
  panel was written 8 mm higher, with the MCU board's origin); hole positions on the panel are the same.
  modules/usb-audio, usb-audio-max and multi-mix had the same 9.5 mm slot; widened the same way later that
  day (user go-ahead; their `panels/README.md`).

Docs brought to S4: `docs/fit/` (`tools/render_fit.py` was the usb-audio file and pointed at its boards; now it
renders the 32bit stack: `overview.png`, assembly with and without the panel, MCU board, carrier back), ERC /
DRC JSON for both boards and the panel, `docs/32bit-schematic.pdf` + `docs/32bit-mcu-schematic.pdf`, `Code.md`,
`README.md`. The S3 renders are removed.

- **MCU board R2: no hole under 0.3 mm** (user, after the review: "update it to 0.3 or so, I don't want to cost
  extra"). The nine thermal vias in the U101 exposed pad were KiCad's 0.2 mm holes on 0.5 mm pads, the only
  holes under 0.3 mm on the two boards. Drill 0.3 mm now, pads and positions kept (`research/fab-review/t02.py`;
  library footprint and `tools/import_footprints.py` changed with it, `min_through_hole_diameter` 0.3 in the
  project). 239 tracks / 41 vias as before, In1 / In2 one piece each, ERC 0 / DRC 0 / unconnected 0 / parity 0;
  B silk S1 / R2; `mcu/` re-exported, BOM / CPL byte-identical. The review's cost note was too coarse:
  JLCPCB's capability page (read 2026-11-23) charges for 0.2 / 0.25 mm holes only when the via diameter is
  under 0.45 mm, so the 0.2 / 0.5 mm vias on this 4-layer board were inside the free range by that rule; 0.3 mm
  does not depend on it. The paste squares of KiCad's land lie over the nine holes, as before; larger holes
  can take more solder from the exposed pad (the chip's only ground): look at the U101 joint on the first
  board.

Judged, not changed: USB D+ / D- (9.1); SMD parts 0.43 mm
from the J6 / J7 joints on the carrier B side and R105 1.2 mm from a J103 pin on the MCU board; C15 47u 6.3 V
on FILT+; U1 AMS1117-5.0 about 0.4 W on the usb-audio copper; the laptop's USB ground joins the rack ground
when the port is used (a possible hum loop on a PA, bench item).

## 10. ES1: the S3 board with its own codec supply and codec clock (2026-11-23)

User, 2026-11-23, after S4: "Keep [the CS chip]. Now, create another version with the same ES chip but with the
PLL and the separate power supply. So, I can order both and see which is good." ES1 is the "small S4" of the
noise discussion the same day: the S3 / R3 board (ES8388, MIDI, CV inputs, two pots, MODE, back USB-C; the
board that is built) with the two fixes that remove the ESP32-S3 from the codec's supply and clock. It keeps
the ES8388's own floor (about 96 dB dynamic range on the datasheet, against 114 dB for the CS4272); building
both shows how much of the noise was supply / clock and how much the converter.

Its own tree, so S4 stays untouched: `hardware/es/32bit-es.kicad_{pro,sch,pcb}` (own library copy with the
two new lands), `tools/es/` (`build_schematic.py` + `circuit_es.py` = the S3 generator plus the changes below,
`import_footprints.py`, `kicad-project.json`), `docs/es/` (S3 `geometry.json`, schematic PDF),
`panels/es/` (the S3 panel, renamed), `jlcpcb/es/`. Batch scripts and reports in `research/es/` (ignored).

### 10.1 Circuit (ES1 schematic, ERC 0, netlist asserted, 121 parts / 83 nets)

- **Codec supply (U10, C49, C50):** +5V (U8 AMS1117-5.0 output) -> U10 **LP5907MFX-3.3/NOPB** (TI, C80670;
  10 uVrms, 82 dB PSRR at 1 kHz, EN tied to IN, 1u in and out) -> **+3V3_A** -> R5 10R -> +3V3_8388 and the
  S3 codec caps (100u + 3 x 10u + 4 x 100n). R5 stays: it is the S3 RC filter, and it keeps the ~130 uF codec
  bank off the LDO output (LP5907: 1 uF ceramic output cap). S3 fed R5 from the ESP32-S3's +3V3. Codec
  current 59 mW / 3.3 V = 18 mA (datasheet, playback + record): 0.18 V across R5 as on S3, 0.03 W in U10.
- **Codec clock (Y2, C51, R23):** Y2 **11.2896 MHz** CMOS oscillator (YXC OT322511.2896MJBA4SL, C2831381,
  YSO110TR series: 0.7 ps phase jitter, <= 5 mA, pin 1 tri-state tied high) on +3V3 with C51 100n -> R23 33R
  -> ES8388 MCLK. 11.2896 MHz = 256 x 44.1 kHz, so every firmware keeps 44.1 kHz. The ES8388 runs as the
  I2S master (datasheet table 2: MCLK 11.2896 MHz, ADCFsRatio / DACFsRatio 00010 = 256, SCLK = MCLK / 4) and
  drives BCLK / LRCK; the ESP32-S3 is a slave. GPIO21 (S3 MCLK out) is open. The "PLL" of the request: the
  codec clock no longer comes from the ESP32-S3's PLL divider.
- Everything else is S3, same refs and values.

### 10.2 Layout (ES1 / R4 = S3 / R3 + three batches)

- `b01`: board synced to the schematic: I2S_MCLK copper removed (8 items), R5's +3V3 feed (2 tracks + via)
  removed, new parts parked; **thermal vias of U1 (ESP32-S3) and U4 (ES8388) drilled 0.3 mm** (0.2 mm before;
  pads and positions kept, library + `tools/es/import_footprints.py`), `min_through_hole_diameter` 0.3.
- `b02`: clock group in the B pocket left of C30 that the old MCLK run left free: Y2 at (119.1, 123.9), R23
  moved from the I2S resistor stack to (121.85, 124.5) on the MCLK tail into U4.1, C51 at (116.4, 123.9);
  C30 0.2 mm right so R23's courtyard clears it. Y2 VDD / EN tie into the +3V3 track at R4.1; Y2 GND has a via
  at (121.3, 122.75). C51's GND pad reaches the B GND pour only (the F.Cu bundle above the pocket leaves no
  room for a via there).
- `b03` / `b04`: U10 + C49 + C50 in the only free B pocket that holds a SOT-23-5 with the 2 mm hand-solder
  clearance: between the CV jack rows at (113.0, 90.6). +5V from C3 by an F hop; GND vias under U10 and at
  C49. **+3V3_A** (0.3 mm, 43 mm, two vias) from C50 to R5.1: F under the MIDI_RX / BOOT / EN / USB bundle,
  B along y 96.85 under the USB pair, down the right edge beside J3 and RV2. Path from a one-connection
  helper (`research/es/pf.py`), checked by hand. A long run is fine for this net: U10 drives it at low
  impedance and R5 + the codec caps filter it at the codec (RC corner ~12 Hz).
- `b05`: title block, B silk "32bit ES1" under the LED (so the two boards can't be mixed up).
- Result: ERC 0 / DRC 0 (all severities) / unconnected 0 / parity 0, no exclusions; 779 tracks / 136 vias,
  none in or touching an SMD pad; no In1 tracks (the five S3 In2 hop segments unchanged); In1 GND and In2
  +3V3 one piece each. The +3V3_A run splits the B GND pour's largest piece in three (875 / 92 / 82 mm2,
  each via-tied; F pour unchanged). New SMD >= 2.15 mm from pot / jack pads (Y2 to RV2); the four
  user-accepted S3 parts (R5 1.33, C27 1.62, R55 1.63, C46 1.75 mm) unchanged. Smallest drilled hole 0.3 mm.

### 10.3 Firmware

All three firmwares take `BOARD=es1` (`firmware/jumper.sh` -> `CODEC_CLOCK_MASTER=1`): ES8388 register 8 =
0x84 (master, BCLK = MCLK / 4) after the init sequence, I2S0 as slave, no MCLK pin. Default `BOARD=s3` builds
exactly as before. Both builds compile for master, fxrack and polysynth (2026-11-23); not bench-tested.

### 10.4 Open

JLCPCB preview (Y2 and U10 pin 1 / rotation), bench: U10 output, MCLK at the codec pin, I2S lock with the
codec as master, then the comparison the variant exists for (bypassed output floor against the S4 CS4272
board and the usb-audio + Ableton path). If ES1 is quiet enough, the CV / MIDI board stays one board.
