# USB-AUDIO research and circuit intent (S1 schematics, S1 THT placement)

A 6HP Eurorack USB audio interface: 2 in / 2 out, DC-coupled ±5 V (audio and CV), 24-bit /
192 kHz, USB Audio Class 2 over USB 2.0 High-Speed. Brief (user, 2026-10-23):

- 2 x 2 with the older, proven chips (CH32V307 + one CS4270). A 4 x 4 CH32H417 version may follow later.
- 192 kHz is the target. DC coupled. Signals are basic Eurorack ±5 V, CV in that range too.
- 6HP. Each jack has a pot that is a plain 0..1 volume control (no gain). Panel rows:
  inputs = socket, pot; outputs = pot, socket.
- USB-C on the front panel. BOOT/RESET only on the PCB (pull the module to flash).
- The USB/MCU part may be a separate PCB soldered to the pot board with 2.54 mm pins.
- JLC places the MCU and codec; the user hand-solders jacks, pots and the 2.54 mm headers.

Nothing here is bench-tested. The firmware (UAC2 on the CH32V307, I2S slave on two ports) does
not exist yet and is the biggest risk.

## 1. Architecture

```
USB-C (panel) -- MCU board: CH32V307RCT6 USBHS (PB6/PB7), I2S2 RX + I2S3 TX (slaves), I2C2
                     | J102/J103 = carrier J6/J7 (2 x 1x10 2.54 mm strips)
carrier: CS4270 (I2S master, Y1 24.576 MHz) -- 2 x input chain, 2 x output chain, power, BOOT/RESET, SWD
```

| # | Decision | Why |
|---|---|---|
| D1 | CH32V307RCT6 (LQFP-64) | USB 2.0 HS with the PHY inside; Full-Speed parts (ESP32-S3, STM32F103) cannot carry 192 kHz stereo 24-bit (1152 B/ms > 1023 B/ms FS iso). 2 I2S ports = 1 stereo in + 1 stereo out |
| D2 | CS4270 (TSSOP-24), I2C control-port mode, master, quad speed | 105 dB DR, 192 kHz. Master: MCLK/LRCK 128 -> 24.576 MHz / 128 = 192 kHz, SCLK = 64 Fs = 12.288 MHz; both CH32V307 I2S ports run as slaves on the same SCLK/LRCK (I2S2 receives SDOUT, I2S3 sends SDIN). 96/48 kHz via MCLK_FREQ (÷2/÷4) with the same oscillator. 44.1 kHz family would need a second oscillator (not fitted). **Cirrus lists the CS4270 as discontinued**; JLC had 1389 in stock on 2026-10-23 |
| D3 | Two boards | The MCU board sits on the carrier F side (between carrier and panel) so a vertical USB-C reaches the panel; each board is single-sided SMD (carrier B, MCU board F). Section 5 |
| D4 | DC coupling | ADC: CS4270 HPF, then freeze (register 04h bits 7/6 = ADC_HPF_FRZ_A/B) after it settles with the inputs at 0 V, so real DC passes. DAC: AOUT is DC coupled into a high-Z op-amp input (AOUT DC load max 10 µA, so no inverting stage on AOUT) |
| D5 | Input = jack (TN to GND) -> 50k pot (0..1) -> 1k -> U4A/B follower (±12 V) -> U6A/B inverting driver on +5VA | Follower keeps the pot linear; the driver's single 5 V supply means AIN can never leave 0..5 V on a ±12 V mis-patch (CS4270 AIN abs max -0.7..VA+0.7) |
| D6 | Output = AOUT -> 470R/1n C0G -> U5A/B gain 3.2 (Rg to VREF_OUT) -> 50k pot -> U4C/D follower -> 1k -> jack | 0.65 x VA = 3.25 Vpp DAC full scale -> ±5.2 V; follower = low output impedance at any pot setting |
| D7 | References from the codec's own VQ (VA/2): U6C buffer -> VB_IN divider; U6D -> VREF_OUT | VQ is 25k / 1 µA max, so buffered; tracking VQ removes VA tolerance from the zero point. Residual offsets are calibrated in firmware (as the ES-8) |
| D8 | Op-amps OPA1679 (quad) x 2 + OPA1678 (dual) | Low noise / distortion audio parts; rail-to-rail output on 5 V (U6). Both in JLC stock |
| D9 | Power: ±12 V -> B5819W; +12V_F -> AMS1117-5.0 -> +5VA (codec VA, U6); +12V_F -> 33R 1 W -> AMS1117-3.3 -> +3V3 (MCU board, oscillator, I2C); +3V3 -> FB1 -> +3V3_C (codec VD/VLC) | CS4270 needs VA 4.75-5.25 V. The 33R pre-drop shares the 3.3 V regulator's heat (100 mA: 0.33 W + 0.54 W) |
| D10 | USB: data only, VBUS -> 10k/20k -> PA9 (sense), CC 5.1k, USBLC6-2SC6 ESD, 8 MHz HSE | Self-powered device: connect the D+ pull-up only while a host is there. The ROM bootloader also enumerates on PB6/PB7 |
| D11 | BOOT (BOOT0 to +3V3) / RESET (NRST to GND) K2 switches and a 1x4 SWD header on the carrier B side | The MCU board faces the panel, so nothing on it is reachable; hold BOOT, press RESET, flash with `wchisp`/WCHISPTool over the panel USB-C |

## 2. Levels

| Path | Numbers |
|---|---|
| Input | gain -5.1k/20k = -0.255; +input at VB_IN = VQ x 20/25.1 so 0 V in -> VQ at AIN. ADC full scale 0.56 x VA = 2.8 Vpp -> **±5.49 V at the jack** (pot at max). ADC_INV_A/B (reg 05h) restores the polarity |
| Output | gain 1 + 22k/10k = 3.2; Rg to VREF_OUT = VQ x (1 + 10k/22k) = 3.64 V so VQ at AOUT -> 0 V out. DAC full scale 3.25 Vpp (0.6-0.7 x VA) -> **±5.2 V** (±4.8..5.6 V over the datasheet spread) |
| Power-up | Popguard holds AOUT at 0 V for 1045 samples, then ramps to VQ over ~0.4 s: DC-coupled outputs start near -8 V and settle to 0 V. Note for the user; a MUTE-pin relay/switch could be added later |
| Load | CS4270 AOUT sees 470R + 1n + an op-amp input (no DC load). AIN source 220R (< 1k for best THD+N), 2.2n C0G reservoir |

## 3. Circuit

```
POWER  J1 ±12V -> D2/D1 -> ±12V_F; U1 AMS1117-5.0 -> +5VA; R1 33R -> U2 AMS1117-3.3 -> +3V3; FB1 -> +3V3_C
CODEC  U3 CS4270: VA +5VA (C10 1u, C11 100n); VD/VLC +3V3_C (C12-C14); FILT+ C15 47u/C16 100n; VQ C17 10u/C18 100n
       Y1 24.576 MHz -> R10 33R -> MCLK; SCLK/LRCK -> R11/R12 33R -> I2S_SCLK/I2S_LRCK; SDOUT -> R13 -> I2S_ADC
       (R15 47k pull-down = stand-alone slave if never configured); SDIN <- I2S_DAC; I2C 0x48 (R16 47k AD0,
       AD1/AD2 GND), R18/R19 2.2k pull-ups; RST <- CODEC_RST (R17 10k pull-down)
IN 1/2 J2/J3 T (TN GND) -> RV1/RV2 50k -> R20/R21 1k -> U4A/B -> R22/R23 20k -> U6A/B (R24/R25 5.1k, + VB_IN)
       -> R26/R27 220R -> AINA/AINB (C20/C21 2.2n C0G)
OUT1/2 AOUTA/B -> R30/R31 470R (C22/C23 1n C0G) -> U5A/B (R32/R33 10k to VREF_OUT, R34/R35 22k)
       -> RV3/RV4 50k -> U4C/D -> R36/R37 1k 1206 -> J4/J5
REFS   U6C: VQ -> R40 5.1k / R41 20k (C24) = VB_IN; U6D: VQ x (1 + R43 10k / R42 22k) = VREF_OUT
LINK   J6: +3V3 GND SWDIO SWCLK NRST BOOT0 SCL SDA GND GND; J7: +3V3 GND SCLK GND LRCK ADC DAC CODEC_RST GND GND
       (1x10 strips: the user stocks 1x10 headers, 2026-10-24; pin 10 is an extra GND on both. J6/J7 and
       J102/J103 swapped in place on both boards; carrier R18/R19 moved down and the R20/R21/C26/C27 column
       0.475 mm left to clear pin 10)
       SW1 RESET, SW2 BOOT, J8 SWD (+3V3 SWDIO SWCLK GND)
MCU    U101 CH32V307RCT6: PB6/PB7 USBHS via U102 USBLC6-2SC6 to J101; PB13/PB12/PB15 I2S2 RX;
       PB3/PA15/PB5 (R108 33R) I2S3 TX; PB10/PB11 I2C2; PB14 CODEC_RST; PA9 VBUS_DET (R103/R104);
       Y101 8 MHz (C101/C102 33p); NRST R105/C111; BOOT0 R106, BOOT1 R107 pull-downs; C103-C110 decoupling
```

Native ERC (`--severity-all`) 0 on both schematics; the generator asserts the exported netlist equals
the circuit tables (`tools/circuit_carrier.py`, `tools/circuit_mcu.py`).

## 4. Placement (S1, `docs/geometry.json`)

6HP panel 30 x 128.5 mm. Carrier 29 x 110 mm (as modules/32bit), MCU board 29 x 27 mm (X0.5-29.5,
Y10-37). Columns X8 / X22 (pot courtyards 1.05 mm from the carrier edge).

| Row | Y | Left (X8) | Right (X22) |
|---|---|---|---|
| USB | 16 | USB-C slot centred at X15 | |
| IN 1 | 46 | J2 jack | RV1 pot |
| IN 2 | 62 | J3 jack | RV2 pot |
| OUT 1 | 79 | RV3 pot | J4 jack |
| OUT 2 | 95 | RV4 pot | J5 jack |

B side: J1 power (bottom centre, as 32bit), J8 SWD beside it (X24), SW1 RESET / SW2 BOOT bottom-left.
Every other SMD part is parked right of each board for group-by-group placement; the U101 LQFP-64
zone is reserved on the MCU board (X8.65-21.35, Y22.15-34.85). Courtyards >= 1.0 mm from both edges
(closest: pots 1.02 mm, header strips 1.06 mm). Closest SMD (SW1) to a pot/jack pad: 3.66 mm.

## 5. Stack and USB-C

| Z (mm, carrier F.Cu = 0) | |
|---|---|
| 0-2.5 | J6/J7 header plastic on the carrier |
| 2.5-4.1 | MCU board (1.6 mm, all parts on top) |
| 4.1-12.9 | HRO TYPE-C-31-D-15 vertical USB-C, H = 8.8 mm |
| 10.0 / 11.6 | panel rear / front (jack boss height, 1.6 mm FR4) |

A USB-C plug only seats if the receptacle mouth is at most ~0.3 mm behind the panel front
(receptacle depth 6.20 mm vs plug shell 6.51-6.65 mm), so the mouth stands **1.3 mm proud** of the
panel through a 9.5 x 3.7 mm obround slot. The same land takes D-15A/B/C/D (9.3/10/10.5/12.4 mm);
a 1.0 mm MCU board would make it 0.7 mm proud. Footprint drawn from the HRO drawing (2023-10-27,
recommended layout): 16 pads 1.59 x 0.50 at 1.00 mm, plated leg slots 0.50 x 1.20 (drawing 0.45);
the two plastic-peg holes sit 0.14 mm past their neighbour leg slots, closer than any fab hole rule,
so each peg + leg pair is one 0.95 x 2.24 mm plated slot. Shell = GND (the drawing overlaps the legs
with the corner GND pads). 3D model: envelope proxy (`tools/make_usbc_model.py`).

Mechanics: plug insertion (5-20 N) pushes the MCU board onto the header plastic and the carrier,
which hangs on the four jack nuts; the panel slot takes side loads. Header pins stand 4.4 mm above
the MCU board (Z 8.5, below the panel rear).

## 6. Sourcing (JLCPCB live lookups, 2026-10-23; stock is not reserved)

| Part | LCSC | Class | Stock |
|---|---|---|---|
| CH32V307RCT6 | C2988083 | Extended | 578 |
| CS4270-CZZR | C1323229 | Extended | 1389 (Cirrus: discontinued) |
| OPA1679IDR / OPA1678IDR | C2878631 / C192421 | Extended | 1011 / 10549 |
| YXC 24.576 MHz 3225 oscillator | C5203547 | Extended | 4030 |
| HRO TYPE-C-31-D-15 | C22464480 | Extended | 471 |
| USBLC6-2SC6 | C7519 | Extended | 38112 |
| 8 MHz crystal X50328MSB2GI | C115962 | Basic | 243364 |
| C0G 2.2n / 1n 0603 | C33353 / C163508 | Extended | 5851 / 446393 |
| 33R 2512 1 W | C53728 | Extended | 69379 |
| K2-1808SN-A4SW-01 | C92589 | Extended | 10340 |

R/C (except the C0G and 2512 parts), AMS1117, B5819W are Basic. Basic/Economic eligibility for the
assembly is not audited yet (no BOM/CPL export at S1).

## 7. Open

- SMD placement and manual routing of both boards (root `AGENTS.md`): codec + references under the
  pots between the rows, input chains beside the IN jacks, output chains beside the OUT jacks,
  regulators near J1; MCU board: U101 in its zone, Y101 close, USB pair on F over In1 GND with
  90 ohm differential (net class USB_HS) and vias only at the ends.
- Firmware: UAC2 (TinyUSB USBHS port), two I2S slave DMA streams, async feedback endpoint,
  CS4270 init (RST after MCLK, PDN within 1045 LRCK periods, FM = quad master, ADC_INV, HPF freeze),
  DC calibration table.
- Bench: 192 kHz I2S slave timing on the CH32V307 (no I2S timing table in its datasheet), output
  power-up transient, thermal of U2/R1.
