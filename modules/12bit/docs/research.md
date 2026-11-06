# 12bit research and circuit intent (S2 schematic, P3 placement, R1 routing)

modules/8bit (an ATtiny1616 DAC voice) moved to an STM32G071C8T6, whose two 12-bit DAC
channels give two outputs, on a 6HP module. Brief (user, 2026-11-06):

- The ATtiny1616 is low on stock; use the **STM32G071C8T6** (12-bit DAC, two channels).
- New module **12bit**, **6HP**.
- **Two audio outputs**, so the firmware can use them in different ways.
- **Remove the low-pass filter**: knob 3 (the 8bit passive LPF rheostat) becomes a plain
  knob read by the MCU.
- Add a **gate output** if it fits (S1 had one).
- **Schematic and THT placement only. No routing.**

S2/P2 follow-up (user, 2026-11-06):

- **Remove the gate output.**
- Move the **power header** from the bottom edge to the right.
- Move the **output jacks** as low as possible.
- Swap P3 and MODE, with **MODE, LED and P3 on one row**.
- Space P1/P2 and P3 further from the jacks, for more room.

P3 follow-up (user, 2026-11-06):

- Move the P3 row a bit down, then centre the whole pot block between the jack rows.

R1 follow-up (user, 2026-11-06): **start routing and export to JLC.**

Nothing here is bench-tested. Sourcing is a dated catalog observation, not an order.

## 1. Baseline: modules/8bit (S5/R4)

Kept from 8bit: the TS MIDI input with the MIDI V2 NPN front end and the JP1 bypass
(shipped open), the bipolar buffered CV input, three RV09 knobs, the 6 x 6 x 7 mm THT MODE
switch with its printed cap, the 3 mm mode LED, the Eurorack power entry (series
B5819W Schottkys), the 0.5 W 1206 output resistors and a TL07x output stage on ±12 V.

## 2. Decisions

| # | Decision | Why |
|---|---|---|
| T1 | **STM32G071C8T6** (LQFP-48, C529341, Extended, Economy-eligible, 4969 in stock 2026-11-06) on **+3V3** | User choice. Two 12-bit DACs (PA4/PA5), 12-bit ADC, 64 MHz M0+. LQFP-48 is hand-reworkable |
| T2 | Schematic symbol = stock KiCad `STM32G081CBTx`, renamed `STM32G071C8Tx` (Value/Datasheet/Description edited, recorded in `docs/schematic-symbols.json`) | KiCad 10 ships no STM32G071CxT symbol. The G081 is the G071 die plus AES with the same STM32G0x1 LQFP-48 pinout. **Review item:** check the pin table against ST DS12232 before export |
| T3 | Pin map: PA4 DAC1_OUT1 = OUT 1, PA5 DAC1_OUT2 = OUT 2; ADC PA0 = CV, PA1 = P1, PA6 = P2, PA7 = P3; **PB7 USART1_RX** = MIDI; PB4 = MODE (internal pull-up); PB5 = LED (TIM3_CH2 PWM); PA13/PA14 SWD; PF2 NRST. Everything else is a no-connect | PA10 (the other USART1_RX) carries the UCPD1 dead-battery pull-down (DBCC2) at reset, which would fight the MIDI pull-up. PB5 PWM sets the LED brightness |
| T4 | MIDI = 8bit front end at 3.3 V (R1 100k / R3 22k pull-ups to +3V3). JP1 1-2 = protected (Q1 inverts: firmware sets USART1 `CR2.RXINV`), 2-3 = direct | As 8bit/16bit. **Review item:** confirm PB7 is 5 V tolerant (FT) in DS12232 before using direct mode with a 5 V sender |
| T5 | CV in = 8bit S4 topology with the modules/16bit D5 values: R4 100k, R5 56k to +3V3, R6 120k to GND, D5 BAT54SW, C5 1n, **U2 MCP6001** follower on +3V3 -> PA0 | ±5 V CV with headroom: -5.9..+6.0 V -> 0..3.3 V, 0 V = 1.63 V, Zin 138k. U2 on +3V3 keeps PA0 inside the rail |
| T6 | **P1/P2/P3 = 50k linear RV09 dividers** (+3V3..GND) into PA1/PA6/PA7, 10n at each wiper | User: no low-pass, knob 3 is an MCU knob. 50k is the user's ADC pot (stock: 50k / 500k / 1M) |
| T7 | **VREF+ = +3V3 through FB1** (600 R ferrite, 0603) with 1u + 100n at pin 5. No VREFBUF | One reference for the DACs, the ADC, the knobs and the output offset (VOFF is a +3V3 divider), so the zero and the knob range track the LDO. FB1's ~0.45 R DCR drops < 0.5 mV at the DAC reference current. VREFBUF (2.0/2.5 V) would need the knobs fed from VREF+ and firmware set-up before anything works |
| T8 | Outputs: TL074 on ±12 V. **U4A/U4B** non-inverting x3.4 (Rf 24k / Rg 10k) with -2.4 x VOFF; **VOFF 2.33 V** from R14 10k / R15 24k + C17 10u, buffered by **U4C**. 1k + 4.7n (34 kHz) in front of each + input. 1k 0.5 W 1206 (ROHM ESR18, as 8bit R12) to each jack. DC coupled | DAC with output buffer on (firmware default for driving a load) swings 0.2..3.1 V -> -4.9..+4.9 V; buffer off 0..3.3 V -> -5.6..+5.6 V (still inside the TL074 swing). DAC mid-scale 1.64 V -> 0 V (offset error ~20 mV). The 34 kHz RC only smooths the DAC steps; it is not a tone filter (the 8bit knob LPF is gone, as asked). DC coupling keeps every option open: stereo, two voices, audio + CV/LFO/envelope |
| T9 | **No gate output** (S2). U4D is a grounded follower (+ to GND, output to -); PB1 is a no-connect | User removed the S1 gate (PB1 -> U4D x1.5 -> J3). Grounding the spare section keeps it from oscillating or rail-sticking |
| T10 | Power: ±12 V through B5819W series Schottkys; **HT7533-1** (C14289, Basic) from +12V_F -> +3V3 | As modules/hats. Load ~20 mA on +3V3 (MCU ~8 mA, DAC, LED, MCP6001, knobs): ~0.17 W in the SOT-89 |
| T11 | No crystal: HSI16 | ±1 % is inside the 31.25 kbaud UART tolerance; audio timing from a timer on HSI is fine for a synth voice. PC14/PC15/PF0/PF1 stay open, so a crystal could not be added later without a re-layout |
| T12 | Programming: **J6 1x5 2.54 mm SWD header** on B: 1 +3V3 (sense), 2 SWDIO, 3 SWCLK, 4 GND, 5 NRST; C14 100n on NRST | Pins 1-4 as modules/usb-audio J8; NRST added for ST-Link "connect under reset". Program with the module on Eurorack power; don't power it from the probe |
| T13 | 6HP, two columns X7.95 / X22.05 (§4) | modules/hats grid, moved 0.2 mm inward so the RV09 courtyards meet the 1 mm edge rule |
| T15 | P3 rows: P1/P2 Y52.2, MODE + LED + P3 Y79.2 (P2: Y45 / Y69), OUT 1/2 Y110.4; power header upright at the right edge (rot 180 on B, pin 1 bottom) between P3 and OUT 2 | User. The MODE switch turns 90 deg (square body; courtyard 7.6 mm wide) and the LED turns 90 deg (pads along Y) so switch (X6.5), LED (X12.85) and P3 (X22.05) fit one row: courtyard gaps 0.33 / 0.53 mm. P3 (user): row pitch 27 mm and the pot block centred on the panel between the jack centres (Y21 / Y110.4, mid Y65.7). The 16-pin IDC envelope (Y77.91..103.31) now covers the RV3 lugs and pins 2/3 (a 10-pin socket still covers pins 2/3); the socket sits 2.5 mm above B, so those leads are trimmed to <= 2 mm |
| T14 | **R1 routing** (user, 2026-11-06), manual divide and conquer, four batches; JLC export | Superseded the P1-P3 "no routing". See `Code.md` R1 for the group layout. DAC1/DAC2 leave the mirrored LQFP in the opposite order to U4 pins 3/5, so DAC2 takes one F hop; no schematic change |

## 3. Circuit (`hardware/12bit.kicad_sch`, ERC 0)

```
POWER  J5 +12V -> D2 B5819W -> +12V_F (U4 V+, C1 10u, U1 HT7533-1 via C3 1u) -> +3V3 (C4 10u)
       J5 -12V -> D3 B5819W -> -12V_F (U4 V-, C2 10u)
MIDI   J1 T -> R1 100k to +3V3; R2 10k -> Q1 MMBT3904 (D4 1N4148W clamp) -> RX_Q (R3 22k to +3V3)
       JP1: 1 RX_Q / 2 MIDI_RX (PB7) / 3 MIDI_IN
CV     J2 T (TN = GND) -> R4 100k -> CV_BUF (R5 56k +3V3, R6 120k GND, D5 BAT54SW, C5 1n)
       -> U2 MCP6001 follower -> CV_ADC (PA0)
KNOBS  RV1/RV2/RV3 50k +3V3 dividers -> POT1 (PA1) / POT2 (PA6) / POT3 (PA7), C7/C8/C9 10n
MCU    U3 STM32G071C8T6: VDD + VBAT = +3V3 (C12 100n, C13 4.7u); VREF+ = VREFP (FB1 from +3V3,
       C10 1u, C11 100n); NRST (C14 100n, J6 pin 5); SWD J6
OUT n  DACn (PA4/PA5) -> R8/R9 1k -> DACn_F (C15/C16 4.7n) -> U4A/U4B + ; Rf R10/R12 24k, Rg R11/R13 10k
       to VOFF -> OUTn_AMP -> R16/R17 1k 0.5 W -> J3 / J4
VOFF   +3V3 -> R14 10k -> VOFF_DIV (R15 24k, C17 10u) -> U4C follower -> VOFF (2.33 V)
SPARE  U4D + = GND, - = output (U4D_OUT)
MODE   SW1 PB4 to GND; PB5 -> R7 1k -> D1 3 mm red -> GND
```

- Output transfer: `Vout = 3.4 x V(DAC) - 2.4 x 2.329 V`; 1.644 V -> 0 V, 0.2 V -> -4.91 V,
  3.1 V -> +4.95 V (0 V -> -5.59 V, 3.3 V -> +5.63 V unbuffered). VOFF and the DAC reference
  both come from +3V3, so LDO tolerance moves the zero by < 20 mV.
- Mis-patch: a ±12 V source on an output puts at most ~17 V / 0.29 W across its 1k
  (0.5 W rated). The TL074 output is short-circuit limited.
- PWR_FLAGs: GND, +12V, -12V at J5; +12V_F, -12V_F behind D2/D3. No others.
- 58 components / 36 named nets; 46 JLC-assembled SMD parts on B (JP1 copper only), all R/C
  JLCPCB Basic except the two 0.5 W 1206 1k (ESR18, Extended, as 8bit).

## 4. Placement P3 (`docs/geometry.json`, renders `docs/fit/`)

6HP panel 30.0 x 128.5 mm; carrier 29 x 110 mm (X 0.5..29.5, Y 9.25..119.25), 4 copper
layers (planned F / In1 GND / In2 +3V3 / B), `min_copper_edge_clearance` 1.0 mm.

| Panel Y | Left | Right |
|---|---|---|
| 21 | J1 MIDI (X7.95) | J2 CV (X22.05) |
| 52.2 | RV1 P1 (X7.95) | RV2 P2 (X22.05) |
| 79.2 | SW1 MODE (X6.5, rot 90) + D1 LED (X12.85, rot 90) | RV3 P3 (X22.05) |
| 87.9..98.1 | J6 SWD on B at the left edge (X3.4) | |
| 89.3..99.5 | | J5 Eurorack power on B, upright at the right edge (X23.8 / X26.34), pin 1 (-12 V) at the bottom |
| 110.4 | J3 OUT 1 (X7.95) | J4 OUT 2 (X22.05) |

The pot block is centred between the jack rows on the panel: pot rows Y52.2 / Y79.2 are both
31.2 mm from their jack row (mid Y65.7). Courtyard gaps: MIDI/CV to P1/P2 18.2 mm, P1/P2 to
row 3 13.2 mm, RV3 to OUT 1/2 16.2 mm (P2: 11.0 / 10.2 / 26.4). The B side between the jack
rows and the pot rows, between the pot rows and left of J5 below row 3 (X5.5..20.6,
Y84..104) is free for the MCU and its groups. Closest THT pads: RV3 pin 3 to J5 pin 9,
2.74 mm centre to centre.

Panel labels: `12BIT`, `MIDI`, `CV`, `P1`, `P2`, `MODE`, `P3`, `OUT 1`, `OUT 2`,
`BIG MODULAR` (moved to Y117.6 under the outputs). Holes: jack Ø6.2, pot Ø7.2, button Ø4.2,
LED Ø3.2.

Measured (`research/edge_check.py`): every THT courtyard >= 1.0 mm from Edge.Cuts (closest
RV1/RV2/RV3 1.02 mm, J3/J4 1.03 mm, J6 1.11 mm, J5 1.35 mm; P3 re-measured). No SMD is on the board yet,
so the 2 mm hand-solder rule has nothing to measure. Native DRC on the carrier: 0
violations, parity 0, 130 unconnected (nothing routed); panel DRC 0/0.

## 5. Open items

- **Done (R1)**: STM32G071 LQFP-48 pin table checked against DS12232 Table 12 (T2) and PB7 is
  FT_fa (T4), so JP1 direct mode with a 5 V sender is allowed by the datasheet. PA14 is also
  BOOT0: leave the factory option bytes (nBOOT_SEL) so the SWCLK line does not select the boot
  mode. Still open: DAC buffered range and VREF+ current (T7/T8).
- **Routing**: done (R1). Bench items: +3V3 ripple at the DAC reference, output offset
  (VOFF) and DAC step smoothing, MIDI in both JP1 positions.
- **Firmware**: none yet. Needs a toolchain under `opt/` (no STM32 tools exist in the repo)
  and ports of the 8bit apps to two DAC channels and three knobs.
- **Sourcing**: lookups recorded in `docs/sourcing-candidates.json`; MCU and TL074 rechecked at
  export (`jlcpcb/README.md`). FB1 C1002 still unresolved by the exact lookup.
  The MCU stock (4969) is the reason for the change: watch it.
- **Mechanics**: printed panel and 3D fit not made; the MODE cap is the 8bit part.
