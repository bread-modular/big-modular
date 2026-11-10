# MULTI-MIX research and circuit intent (S3 schematics, R1 routing)

A digital 4-channel Eurorack mixer in modules/4mix's panel layout widened to 20HP, built on modules/usb-audio-max's
PCM3168A codec, power stage and CH32V307 MCU board. Every knob is read by the MCU, so the mixer can send
its knob positions as MIDI and its channels to a computer over USB.

Brief (user, 2026-11-09, from the design discussion):

- Analog-in / analog-out, mixing in the MCU (digital mixer route, chosen over SSI2164 VCAs).
- 4 channel inputs, 2 return inputs, 2 send outputs. The returns can also come straight from USB audio.
- To the computer: the 4 inputs and the 2 returns (no master: the DAW rebuilds the mix from the stems
  and the MIDI). Channel volume as MIDI channel volume (CC7), the other knobs as CCs.
- External effects stay possible through SEND / RETURN; routing through USB is firmware work for later.
- Knobs through a mux. Same PCB layout as modules/4mix.
- Several units can be chained for more channels (each with its own USB); they must share one clock so
  the stems stay sample-locked, over an internal link. 2x5 IDC ribbon for the link (common in Eurorack).
- Revised the same day: the link is for USB multitrack recording only. Each unit keeps its own MAIN OUT
  and sends (the user mixes the units on an analog mixer), so no audio and no control crosses the link:
  clock only, daisy-chained, headers renamed CLK IN / CLK OUT, still 2x5 IDC ribbons.
- Name: multi-mix. This step: schematics.
- Placement (user, 2026-11-09): 20HP is fine. The MCU board goes where modules/4mix had the MAIN knob and
  the OUT jack; OUT and MAIN then stack one below the other. The MCU board may be miniaturised if needed.
  Read the datasheets and check everything needed; bench tests later.

Nothing here is built, simulated or bench-tested. No firmware exists. Sections 1-8 keep the S1/P3 history;
where S2/S3 changed something the text says so, and section 9 holds the S2/S3 changes and the R1 routing.

## 1. Architecture

```
IN 1-4, RTN A/B (6 x AC-coupled driver) --> PCM3168A ADC 1-6 --TDM 48 kHz--> CH32V307 (MCU board)
SEND A, SEND B, MAIN (3 x diff. amp)    <-- PCM3168A DAC 1-3 <--TDM--------  mix, sends, returns, USB
15 x RV09 (DC dividers) --> 74HC4067 --> MCU ADC (PC0)                        UAC2 6 in / 8 out + USB-MIDI
CLK OUT / CLK IN (2x5 IDC daisy chain): SCKI/BCK/LRCK from the chain master to every slave, clock only
```

| # | Decision | Why |
|---|---|---|
| D1 | Reuse modules/usb-audio-max: power (J8 = its J1, the +5VA LM358/BCP56/REF5050 regulator, FCCM TPS562208 +3V3 buck), PCM3168A with its land, input driver and output difference-amplifier topologies, the CH32V307 MCU board (USB-C, crystal, boot) | Proven schematics, live-sourced parts, one design to maintain. The +5VA precision reference is more than an AC-coupled mixer needs; it stays so both modules share one power design |
| D2 | 48 kHz only (SCKI 24.576 MHz = 512 fS, single-rate TDM, BCK 12.288 MHz): DOUT1 = ADC 1-6, DIN1 = DAC 1-8 | Uses only I2S2 RX / I2S3 TX, the path modules/usb-audio's firmware already runs. usb-audio-max's 96 kHz SPI1 path is untested and SPI1 is not needed. DOUT2 open, DIN2-4 to GND |
| D3 | Inputs AC-coupled (10u into 100k, as modules/4mix D3), driver gain -0.2 (100k / 20k), + input at VCOM_REF | Audio mixer. Full scale +/-7.07 V (14.1 Vpp): 10 Vpp Eurorack audio at -3 dBFS. AC coupling idles the driver at VCOM, so usb-audio-max's VB_IN divider and its buffer (U6D) are not needed (U6D spare) |
| D4 | Outputs: DAC1 SEND A (J1), DAC2 SEND B (J2), DAC3 MAIN OUT (J5) on U7A-C; **DAC4 USB 1 (J9), DAC5 USB 2 (J10)** on a new U8 OPA1678 dual (2026-11-09, user: two outputs the host assigns, e.g. from Ableton); 15k / 27k difference amplifier (gain 1.8, +/-7.2 V), 2 x 2k 1206 = 1k | modules/4mix jacks. Mono MAIN, as modules/4mix (MAIN knob + OUT jack). USB 1/2 are plain host channels (firmware: UAC2 outputs 4/5 straight to DAC4/DAC5). U8 sits by its jacks (bottom right) instead of using the far-away U7D (stays spare). OPA1678IDR C192421 is the code modules/usb-audio and audio-out use; its JLCPCB page was read 2026-11-09 (part listed, stock not shown). DAC6-8 stay open. DC-coupled outputs, no VCOMDA excursion |
| D4a | **Codec channel behind each output (R1 routing, 2026-11-09, user OK):** SEND A = VOUT5 (pins 23/24), SEND B = VOUT3 (27/28), MAIN = VOUT4 (25/26), USB 1 = VOUT1 (31/32), USB 2 = VOUT2 (29/30). Net DACn stays output n (`CODEC_VOUT` in `tools/circuit_carrier.py`) | The U7 outputs leave the west half of the codec's DAC row and the U8 outputs the east half, so the two groups never cross: with VOUT1-3 -> U7 the five U7 tracks had to pass the MS3 standoff keep-out where only one lane fits. Polarity is kept (VOUTn+ -> DACnP). Firmware: write output n's samples into TDM DAC slot CODEC_VOUT[n] |
| D5 | Knobs: 15 x RV09 50k B (modules/4mix references RV1-RV3, RVn01-RVn03) as DC dividers on +3V3_POT, 100n per wiper, 74HC4067 16:1 mux (I15 = GND), COM -> 1k -> MCU PC0 | User: mux. One ADC pin + 4 selects. 100n wipers give the ADC a low source impedance (charge sharing < 0.1 %) and ~1 ms smoothing. Linear pots (user preference); the firmware sets the volume law |
| D6 | Patch detect: all six jack normals on one node NORM (1k to GND), NORM_PROBE (PB0) drives it through 100k with pseudo-random bits (33 mV) | No extra switch pins: the firmware correlates the probe in each ADC channel (~-50 dBFS) to tell patched from unpatched. RTN A/B unpatched -> take the return from USB automatically. A patched jack's normal is open, so the probe never reaches a real signal. Mutable Instruments' "normalization probe" idea, here read through the codec |
| D7 | Clock link on 2x5 keyed IDC (D9, D10, D12, D13) | User: 2x5 IDC. Replaces modules/4mix D5 (2x3 headers so a power cable could not fit): the pinout now survives a Eurorack power cable instead (D10) |
| D8 | MCU board = usb-audio-max's circuit with new pins (section 5). S1: a third 1x10 strip (J114). **S3 (2026-11-10): two 1x12 strips J112/J113, J114 gone, every part on F** (section 9) | S1: the mux, probe and LINK_N pins + supplies did not fit two 1x10 strips. S3: user wanted a single-sided MCU board; tying the I2S3 clock pins to the I2S2 ones on the MCU board and moving the I2C pull-ups there frees enough strip pins for 2 x 12 |

## 2. Levels

| Path | Numbers |
|---|---|
| Input | ADC SE full scale 0.2 x VCC Vrms = +/-1.414 V peak at 5.00 V. Gain -20k/100k = -0.2 -> +/-7.07 V at the jack. Pole 169 kHz (20k / 47p), ADC RC 154 kHz (470R / 2.2n C0G). HPF 0.16 Hz (10u / 100k); the codec HPF can stay on (BYP = 0). Input impedance 100k |
| Output | DAC 8 Vpp differential x 27k/15k = +/-7.2 V (inputs +/-7.07 V: -0.16 dB, trimmed in firmware). Pole 125 kHz. Output impedance 1k |
| Mis-patch | Input: +/-12 V DC passes only as a step through the 10u, the driver clips, VIN stays 0..5 V. Output: 12.6 V into an output at -7.2 V -> 19.8 mA, <= 0.2 W per 2k |
| Latency (estimate, typical delta-sigma filters, not measured) | ~1-1.5 ms jack to jack with 16-frame DMA blocks; external effects through SEND/RTN pass the converters twice |
| Current (estimate from usb-audio-max) | +12 V ~0.3 A max, -12 V ~10 mA |

## 3. Circuit

```
POWER  J8 +/-12V -> D1/D2 -> +/-12V_F; +5VA, +3V3, +3V3_C, +3V3_OSC exactly as usb-audio-max (its docs D7/D11);
       +3V3 -> R62 47R -> +3V3_POT (C48 10u, the 12 channel pots); +3V3 -> R65 47R -> +3V3_POTB (C50 10u, the
       top-row pots RV1-RV3; S3, section 9)
CODEC  U3 PCM3168A unit A: VIN1-6+ <- ADC_IN1-6, VIN- = VCOM_REF, VOUT5/3/4/1/2 +/- -> DAC1-5 P/N (D4a), VOUT6-8 open
       unit B: BCK_C/LRCK_C (BCKAD=BCKDA, LRCKAD=LRCKDA) -> U4 74LVC2G34 -> BCK_B/LRCK_B -> R11/R12 -> I2S_SCLK/LRCK;
       SCKI <- R60 33R <- SCKI_SEL (U11); DOUT1 -> R13 -> I2S_ADC1; DIN1 <- I2S_DAC1 (R110 33R on the MCU board);
       DIN2-4, MODE, ADR0 GND; R15 ADR1, R17 RST pull-down; I2C pull-ups R108/R109 on the MCU board (S2, were
       R18/R19 here); decoupling C11-C15, C20-C30 (usb-audio-max)
IN n   J (TN -> NORM, S = GND) -> C22n 10u -> R20n 100k -> U5A-D (CH1-4) / U6A-B (RTN A/B), + = VCOM_REF,
       R21n 20k || C20n 47p -> R22n 470R -> ADC_INn (C21n 2.2n C0G)      n: 1-4 = J101-J401, 5 = J3, 6 = J4
NORM   NORM_PROBE -> R63 100k -> NORM; R64 1k NORM -> GND
OUT n  DACnN -> R30n 15k -> amp -; DACnP -> R31n 15k -> amp + (R33n 27k || C31n 47p to GND); R32n 27k || C30n 47p;
       -> R34n || R35n 2k 1206 -> jack     n: 1 = J1 SEND A (U7A), 2 = J2 SEND B (U7B), 3 = J5 MAIN OUT (U7C),
       4 = J9 USB 1 (U8A), 5 = J10 USB 2 (U8B); U7D spare (follower at GND); U8 on +/-12V_F, C35/C36 100n
VCOM   U6C: VCOMAD -> R50 100R -> VCOM_REF (C40 10u, C41 100n); U6D spare (follower at VCOM_REF)
KNOBS  RVx pin 3 = +3V3_POT (RV1-RV3: +3V3_POTB), pin 1 = GND, wiper (C701-C715 100n) -> U10 74HC4067 I0-I14;
       I15 = GND; /E = GND;
       S0-S3 = MUX_S0-3; COM -> R61 1k -> POT_ADC
LINK   section 4 (clock only)
STRIPS J12/J13 (2 x 1x12) = MCU board J112/J113 (section 5; S1 had J12-J14, 3 x 1x10); SW1 RESET, SW2 BOOT,
       J15 SWD on the carrier B side
```

Mux order (input = I number): 0 RV101 CH1 VOL, 1 RV102 CH1 SEND A, 2 RV103 CH1 SEND B, 3-5 CH2 (RV201-RV203),
6-8 CH3, 9-11 CH4, 12 RV2 RETURN A level, 13 RV3 RETURN B level, 14 RV1 MAIN, 15 GND.

Native ERC (`--severity-all`) 0 on both schematics (`docs/erc/`); `tools/build_schematic.py` asserts that each
exported netlist equals its circuit table (`tools/circuit_carrier.py`, `tools/circuit_mcu.py`). S3 (2026-11-10,
shared `check` netlist): carrier 232 parts (200 with an LCSC code; the 11 jacks, 15 pots, J6/J7/J8 and the
J12/J13/J15 strips are hand-soldered), MCU board 27 parts (25 with an LCSC code; J112/J113 are the carrier's
strips).

## 4. Clock link (CLK OUT J6 / CLK IN J7)

Purpose: sample-locked USB multitrack recording with several units. Each unit keeps its own USB, its own
MAIN OUT / SEND A / SEND B (mixed on an external analog mixer) and its own knobs/CCs; only the codec clocks
cross the link. Daisy chain: a short 10-way ribbon from a unit's CLK OUT (J6, left edge, B side) to the next unit's
CLK IN (J7, right edge, B side; both at Y58, pin 1 at the top, section 8), so the slaves sit to the
left of the master. The master is the unit whose CLK IN is open; it runs on its own Y1. Every unit drives
the clocks it runs on out of its CLK OUT, so the chain can be any length.

```
 Unit 3 (slave)        Unit 2 (slave)        Unit 1 (MASTER, Y1)
[CLK OUT] [CLK IN]<---[CLK OUT] [CLK IN]<---[CLK OUT] [CLK IN] open
```

| Pin | Net | CLK OUT (J6, to the next unit) | CLK IN (J7, from the upstream unit) | Power cable plugged in by mistake |
|---|---|---|---|---|
| 1 | DET | R82 4.7k to GND (tells the next unit it is linked) | R83 10k -> LINK_N (R84 100k pull-up, D3 BAT54S clamp) | -12 V: 2.6 mA in R82 / 1.5 mA into D3 |
| 2 | NC | | | -12 V on nothing |
| 3, 5, 8 | GND | GND | GND | GND |
| 4 | SCKI | U14A -> R72 150R (out) | -> U11 In1 (R76 100k pull-down) | GND: buffer output into 150R, 22 mA |
| 6 | BCK | U12A -> R70 150R (out) | -> U13A (R77 pull-down) | GND |
| 7 | LRCK | U12B -> R71 150R (out) | -> U13B (R78 pull-down) | GND |
| 9, 10 | NC | | | +12 V on nothing |

| # | Decision | Why |
|---|---|---|
| D9 | Hardware clock switching on LINK_N (low = CLK IN connected = clock slave): U11 74LVC1G97 as a 2:1 mux (In2 = LINK_N: high -> Y1, low -> link SCKI; Diodes DS35127 function table) feeds the codec SCKI; U13 74LVC2G125 (/OE = LINK_N) drives the link BCK/LRCK onto BCK_C/LRCK_C through R74/R75 100R. The MCU only reads LINK_N (PB1) and leaves the codec in slave mode (its reset default, section 6a F4) | No MCU pin for the switch, no glitch at run time. Firmware rule: read LINK_N with the codec in reset; while LINK_N is low never set the ADC to master (R74/R75 limit a fight to 16 mA). ADC and DAC reset to slave (F4), so only a chain master writes MSAD. Do not hot-plug the ribbon |
| D10 | Every line that leaves the board is buffered (U12/U14A 74LVC2G34) behind 150R; DET sits on a power-cable -12 V pin behind 4.7k / 10k + BAT54S; pins 2, 9, 10 unused; pin 8 GND | Survives a Eurorack power cable in either keyed header: pins 1-2 see -12 V, 3-8 GND, 9-10 +12 V. 150R ~ the ribbon impedance with GND neighbours (source termination), 22 mA into a short. SCKI between two GNDs (3, 5), LRCK beside GND 8. Keyed box headers + "CLK - NOT POWER" silk at placement |
| D11 | Dropped (2026-11-09): no audio or control on the link | The user mixes the units' MAIN OUTs on an analog mixer, so the expander bus sums (USART2 DATA, pin 8) and the USART1 CTRL line (pin 2) are gone: U14B spare (input to GND), R73/R79/R80/R81 and R85-R87/D4/D5 removed, J13.8 = GND, J13.9 and J14.9-10 spare. PA2/PA3/PA9/PA10 are free, and the APB1/APB2 baud-rate question is moot |
| D12 | Clocks (SCKI + BCK + LRCK) shared, not just SCKI | Same rate and the same frame: all codecs sample on the same LRCK edge (+ a few ns per hop), so stems from several units stay sample-locked; each unit's UAC2 feedback endpoint reports the same rate. macOS aggregate device with drift correction off; Windows needs ASIO4ALL or one device. Each unit's USB serial from the CH32V307 unique ID, so the host tells them apart. A possible fixed offset between the devices (USB start-up) is constant, found with one click test |
| D13 | Daisy chain: a slave repeats the link clocks out of its CLK OUT (U14A SCKI_SEL, U12 BCK_B/LRCK_B) | Any number of units, no master/slave jumper. Each hop adds ~10-15 ns (buffers + ribbon) against a 20.8 us frame. SCKI passes one gate fewer per hop than BCK/LRCK (U11 vs U13 + U4), so their phase shifts a few ns per hop: allowed, the PCM3168A needs no phase relationship between SCKI and BCK/LRCK, only a fixed frequency ratio (TI SBAS452A 9.4.5; checked 2026-11-09). What limits the chain is the BCK duty cycle (section 6a, F2). **Up to 4 units (16 inputs + 8 returns) until a bench test proves more.** The master must be powered; the 74LVC parts have Ioff, so an unpowered unit is not back-fed from the ribbon |

Firmware outline (not written; datasheet rules in section 6a): one composite USB device per unit (UAC2 6 in / 8 out + USB-MIDI); the 4 inputs
and 2 returns go to the host pre-fader (VOL arrives as CC7, so it is not applied twice); host channels 1-2 can
feed RETURN A/B (automatically when the return jack is unpatched, D6); knob scan with hysteresis (7-bit CC,
14-bit CC7/CC39 optional); per-channel SEND A/B post-fader; MAIN = channels + returns x levels x MAIN.
Clock slave (LINK_N low at boot): leave the codec ADC and DAC in slave mode (the reset default) and never
write MSAD/MSDA. Clock master: write MSAD = master 512 fS (DAC stays slave on the same BCK/LRCK).

## 5. MCU board pins (CH32V307RCT6, LQFP64)

S3 pin map (2026-11-10; `tools/circuit_mcu.py` `MCU_PINS` is the source). Unchanged from usb-audio-max: USB
PB6/PB7, HSE PD0/PD1 (Y101 8 MHz, 3225 since S3), I2C2 PB10/PB11, SWD, BOOT0/BOOT1, NRST. SPI1 is not used
(PA4-PA7 free).

| Pin | Function | Net | Strip |
|---|---|---|---|
| PB12 (33), PB13 (34) | I2S2 WS / CK (slave) | I2S_LRCK / I2S_SCLK | J113.10 / J113.9 |
| PA15 (50), PB3 (55) | I2S3 WS / CK (slave) | tied to I2S_LRCK / I2S_SCLK on the MCU board (S3) | - |
| PB15 (36) | I2S2 SD, slave **TX** (S2, was RX) | I2S_DAC1_SRC -> R110 33R -> I2S_DAC1 (codec DIN1) | J113.5 |
| PB14 (35) | SPI2_MISO (input unless used) | on PB15's node before R110 (SPI-slave TX fallback, 6a F1) | - |
| PB5 (57) | I2S3 SD, slave **RX** (S2, was TX) = SPI3_MOSI | I2S_ADC1 (codec DOUT1 through R13) | J112.5 |
| PB10 (29), PB11 (30) | I2C2 | I2C_SCL / I2C_SDA, pull-ups R108/R109 2.2k on the MCU board (S2) | J113.6 / J113.7 |
| PC0 (8) | GPIO out | CODEC_RST (S2; S1 PB14) | J112.6 |
| PC1 (9) | ADC_IN11 | POT_ADC (S2; S1 PC0) | J112.7 |
| PC2 (10), PC3 (11), PA0 (14), PA1 (15) | GPIO out | MUX_S0-S3 (S2; S1 PC6-PC9) | J112.8-11 |
| PA8 (41) | GPIO / TIM1_CH1 (timer-driven PRBS) | NORM_PROBE (S2; S1 PB0) | J113.12 |
| PA2 (16) | GPIO in | LINK_N, low = clock slave (S3; S1 PB1) | J112.12 |
| PC11 (52) | GPIO in | VBUS_DET (R103/R104 divider) | - |
| PA13 (46), PA14 (49) | SWD | SWDIO / SWCLK -> carrier J15 | J113.2 / J113.1 |
| NRST (7), BOOT0 (60) | | carrier SW1 RESET / SW2 BOOT | J112.2 / J112.1 |

Free: PC6-PC9, PB0, PB1, PA3, PA9-PA12, PB4, PC13 and PA4-PA7.

SPI-slave fallback (datasheet review F1): the CH32V307 rates I2S CK at 8 MHz max but SPI slave at 72 MHz, and
I2S2/I2S3 share their pins with SPI2/SPI3. RX already lands on PB5 = SPI3_MOSI (slave in); a slave transmits
on MISO, so PB14 = SPI2_MISO is tied to PB15 before R110 (only one of the two may drive; the other stays an
input). S1 had the mirror image (RX on PB15, PB4 tied to PB5).

Strips, S3 (carrier J12/J13 = MCU J112/J113, 1x12, pin 1 at the top, panel X73.5 / X96.7, Y14.92-42.86):

| Pin | J12 / J112 (west) | J13 / J113 (east) |
|---|---|---|
| 1 | BOOT0 | SWCLK |
| 2 | NRST | SWDIO |
| 3 | +3V3 | +3V3 |
| 4 | GND | GND |
| 5 | I2S_ADC1 | I2S_DAC1 |
| 6 | CODEC_RST | I2C_SCL |
| 7 | POT_ADC | I2C_SDA |
| 8 | MUX_S0 | GND |
| 9 | MUX_S1 | I2S_SCLK |
| 10 | MUX_S2 | I2S_LRCK |
| 11 | MUX_S3 | GND |
| 12 | LINK_N | NORM_PROBE |

Each strip pin faces its codec pin or its carrier part: the west strip carries what goes west and south (pot
mux, DOUT1, reset), the east strip what runs down the clock corridor east of the codec.

## 6. Sourcing (JLCPCB live lookups 2026-11-09, `research/sourcing/`; stock is not reserved)

New in this module (all Economic-eligible):

| Part | LCSC | Class | Stock |
|---|---|---|---|
| 74HC4067PW,118 (Nexperia, TSSOP-24) | C179326 | Extended | 24290 |
| 74LVC1G97DW-7 (Diodes, SOT-363) | C460532 | Extended | 4253 |
| SN74LVC2G125DCTR (TI, SSOP-8 DCT) | C206035 | Extended | 4768 |
| BAT54S,215 (Nexperia, SOT-23) | C47546 | Extended | 300978 |
| 20k / 27k / 4.7k / 47R 0603 (UNI-ROYAL) | C4184 / C22967 / C23162 / C23182 | Basic | > 600k |

Re-checked the same day: PCM3168APAPR C529289 (1513, shared with usb-audio-max), OPA1679IDR C2878631 (2842),
24.576 MHz OT2EL C5203547 (6493), TPS562208 C91301, REF5050A C27804, SN74LVC2G34 C14461, BCP56-16 C92221,
MWSA0402S C408337, CH32V307RCT6 C2988083 (1873), TYPE-C-31-D-15 C22464480 (450), USBLC6-2SC6 C7519. All other
R/C codes are usb-audio-max's (2026-11-05). 44 carrier codes + 12 MCU codes (unchanged by dropping D11: every
removed part's code is still used elsewhere).

## 6a. Datasheet review (2026-11-09)

Read for this module's new and changed paths (PDFs in the ignored `research/datasheets/`): TI SBAS452A
(PCM3168A), WCH CH32V303/305/307/317 datasheet V3.9 and reference manual V2.5, Diodes DS35127 Rev 7-2
(74LVC1G97), TI SCES204Q (SN74LVC2G125), SCES359J (SN74LVC2G34), TI SCHS209D (CD74HC4067: the Nexperia
74HC4067 sheet would not download; same HC 2-6 V family and pinout). The power stage, codec land, input
drivers and output amplifiers are modules/usb-audio-max's and were reviewed there.

Findings that change something or must be carried:

| # | Finding | Source | Action |
|---|---|---|---|
| F1 | **The CH32V307 rates I2S CK at 8 MHz max (master and slave)**; TDM at 48 kHz runs BCK at 12.288 MHz (+54 %). The SPI port is rated to 72 MHz in slave mode (data setup/hold 4 ns, output valid 10 ns). modules/usb-audio(-max) assumed "no I2S timing table"; V3.9 has one | CH32V DS V3.9 Tables 4-28, 4-29 | MCU board: a MISO pin tied to the TX data pin (S1: PB4 on PB5; **S2/S3: PB14 = SPI2_MISO on PB15 before R110**, section 5; ERC 0). Firmware tries I2S2/I2S3 slaves first; if they fail at 12.288 MHz it uses SPI2/SPI3 slaves on the same pins (S3: RX PB5 = SPI3_MOSI, TX PB14), framed from LRCK. Bench item. The same limit applies to modules/usb-audio and modules/usb-audio-max (not changed here) |
| F2 | ADC slave timing in TDM: BCKAD high and low >= 35 ns, cycle >= 75 ns. At 12.288 MHz the nominal half period is 40.7 ns: a slave unit has 5.7 ns of duty-cycle budget for the link buffers and ribbon (each hop passes U12, U13 and U4). A PCM3168A master only promises BCK duty 40-60 % (32.6 ns), though its BCK = SCKI / 2 should be close to 50 % | SBAS452A 8.10, 8.11 | Keeps D13's 4-unit limit; bench: measure BCK high/low at the last unit of a 4-unit chain. If it fails: share SCKI only and run every codec as its own master (rate-locked, frames offset by a constant < 1 sample; drops U13 and the BCK/LRCK lines), a schematic change for the user |
| F3 | No phase relationship needed between SCKI and BCK/LRCK, only a fixed ratio; > +/-2 BCK drift halts and resyncs | SBAS452A 9.4.5 | D13 datasheet item closed |
| F4 | ADC and DAC both reset to **slave** (MSAD/MSDA defaults). In slave units the firmware writes nothing; masters write MSAD = 512 fS | SBAS452A Table 13 | Firmware rule (section 4); the U13/codec fight in D9 can only come from a firmware bug |
| F5 | MODE = DGND is I2C; the mode pins are sampled when the internal reset is released, which needs SCKI. Internal reset ends 3846 SCKI cycles after RST high; without synchronous BCK/LRCK the codec waits in power-down and starts by itself once they arrive | SBAS452A 9.3.6, Table 6 | Firmware: a slave can release RST before its master runs; no ordering between units needed |
| F6 | If SCKI stops, the DAC outputs **hold their last value** (DC-coupled outputs keep it) | SBAS452A 9.4.5 | Only if the chain master loses power while slaves run (one Eurorack supply: not expected). Firmware: on lost LRCK, mute by RST |
| F7 | Single-ended ADC input: full scale 0.2 x VCC Vrms (1.414 V peak at 5 V), VINx- to VCOMAD; **SEAD resets to differential** | SBAS452A 9.3.1, Table 13 | Firmware writes SEAD[6:1] = single-ended at init |
| F8 | TDM single rate needs SCKI = 512 fS and BCK = 256 fS, DOUT1/DIN1 only; SCKI 40-60 % duty, >= 10 ns high/low | SBAS452A Table 11, 8.6 | Matches D2. Y1 runs on every unit (also slaves), harmless |
| F9 | 74LVC1G97: IN2 low -> Y = IN1, IN2 high -> Y = IN0; Schmitt inputs, Ioff, tpd <= 5.1 ns at 3.3 V | DS35127 function table | U11 as drawn: LINK_N high -> Y1, low -> link SCKI. OK |
| F10 | SN74LVC2G125 (DCT: 1 1OE, 2 1A, 3 2Y, 4 GND, 5 2A, 6 1Y, 7 2OE, 8 VCC) and SN74LVC2G34 (DCK: 1 1A, 2 GND, 3 2A, 4 2Y, 5 VCC, 6 1Y): Ioff, +/-50 mA absolute output current, +/-24 mA at 3.3 V | SCES204Q, SCES359J | Pinouts as drawn. A power-cable short through 150R draws ~20 mA per output: inside the ratings |
| F11 | 74HC4067 at 3.3 V: VIH ~0.7 VCC (2.3 V, MCU drives 3.3 V); RON ~100-250 ohm (specified at 4.5 V: 160-200); off leakage <= 0.8 uA at 25 C; CCOM 50 pF | SCHS209D 8, 13 | The 100n wiper caps swamp RON, leakage and CCOM (charge sharing < 0.1 %); wipers stay below VCC (+3V3_POT < +3V3) |
| F12 | CH32V307 ADC: fADC <= 14 MHz, RAIN <= 50k at 55.5 cycles, CADC 8 pF; pins PC0 = ADC_IN10 (8), PB0/PB1 (26/27, not 5 V tolerant), PC6-PC9 (37-40), PB4 = SPI3_MISO (56) | CH32V DS V3.9 Table 3-1, 4-42/4-43 | Pin table re-checked for S3 (section 5): PC1 = ADC_IN11 (9), PA2 (16), PA8 (41), PC2/PC3/PA0/PA1 (10/11/14/15), PB14 = SPI2_MISO (35). LINK_N (S3: PA2, an analog-capable pin, treated as not 5 V tolerant): worst case +12 V on CLK IN pin 1 lifts it to ~3.6 V through 10k + BAT54S (~0.9 mA in the clamp), at the pin's VDD + 0.3 V limit |

## 7. Open

- Placement and routing are done (section 9, R1). Not done: fab review, JLCPCB export, panel re-check against
  the built boards.
- Firmware: everything (UAC2 + USB-MIDI composite, codec init per F4/F7, I2S or SPI-slave TDM (F1), mixer,
  knob scan, NORM probe correlation, unique USB serial per unit).
- Bench: I2S slave at 12.288 MHz (F1, else SPI slaves), BCK duty at the last of 4 units (F2), codec slave mode on
  the link clocks, sample lock in a macOS aggregate device, SCKI through U11 (jitter), patch-detect threshold,
  pot noise / CC stability, latency, thermal (codec, Q1).
- DAC6-8 are still free (open) for a later stereo MAIN or headphone variant; jacks and an amplifier would be needed.

## 8. Panel and P1 placement (20HP, 2026-11-09)

User: 20HP; the MCU board takes modules/4mix's MAIN knob + OUT jack spot (top right); OUT and MAIN stack one
below the other; the MCU board may be miniaturised if needed. Geometry contract `docs/geometry.json`; boards
written by `tools/build_layout.py` (THT, back-side parts, standoffs, MCU board outline; SMD parked right of
each board; unrouted).

| # | Decision | Why |
|---|---|---|
| P1 | Panel 101.3 x 128.5 (20HP), carrier 100 x 110 (X0.65-100.65, Y9.25-119.25), 4 layers, all SMD on B. Rail holes X12.58 / X93.86 | modules/4mix + 10 mm; holes 16HP apart on the 2HP grid (4MIX rule) |
| P2 | Channel strips = modules/4mix P6 re-centred (+5.08): columns X20.17 / 40.49 / 60.81 / 81.13, rows IN 47 / A 65.5 / B 84 / VOL 106, 18 mm big-knob reserve; MS1/MS2 X30.41 / 71.05 Y114; J8 power bottom right (pin 1 X90.11 Y116.08) | Same panel feel and references as 4MIX |
| P3 | Top line Y16.6 jacks / Y30 pots: SEND A X6.6, SEND B X20, RTN A X33.5 over LVL A, RTN B X48.5 over LVL B, **OUT X63.5 over MAIN**, then the MCU board | User layout. Pot columns at 15 mm pitch (4MIX 17): courtyard gaps 2.1 mm, small knobs 4.0 mm apart |
| P4 | MCU board **not miniaturised**: modules/usb-audio-max's 29.0 x 29.55 outline at X70.6-99.6, Y10-39.55; J112 X73.5, J113 X96.7, **J114 X92.89** (3.81 mm inboard of J113: two 1x10 courtyards may not overlap at 2.54 mm), pin 1 Y13. USB-C at X84.1 Y16 (1.0 mm left of the board centre to clear J114: courtyards 0.72 mm), U101 zone X77.0-90.5 Y25-38.5 | It fits: RV1 courtyard 0.66 mm left of the outline, IN4 jack courtyard 1.18 mm below, outline 1.05 mm inside the carrier edge. Same stack Z as usb-audio-max (USB-C 1.3 mm proud). The carrier's J12-J14 share the holes |
| P5 | Panel USB-C slot 9.5 x 3.7 at X84.1 Y16 ("USB" label) | usb-audio-max slot |
| P6 | J6 CLK OUT (X6.7) / J7 CLK IN (X94.6) keyed 2x5 box headers on B, both Y60, pin 1 at the top; silk "CLK OUT/IN - NOT POWER" | Side margins below the top line (4MIX's EXP spots are too small for box headers and J7's is under the MCU strips). Level, so a slave's J7 is ~13 mm from its master's J6: short ribbon |
| P7 | **MS3**, third M3x10 standoff at X95 Y45 (right margin just below the MCU board) | As usb-audio-max's USB-C standoffs: a plug pushed into the panel loads the MCU board and the carrier's top-right corner; no room beside the USB-C itself. Optional: drop it if the user prefers |
| P8 | J15 SWD (pin 1 X75 Y42.5), SW1 RESET (X69 Y44), SW2 BOOT (X69 Y49) on B below the MCU board between the IN3 and IN4 jacks | Short NRST/BOOT0/SWD runs to J12; J15's tails come through on F clear of the MCU board and the jack bodies; SW pads 4.18 mm from the closest pot pad (RV1) |

Checks (build assertions + native): every placed courtyard >= 1 mm from the edge (closest 1.075 mm, the top-row
jacks); no F courtyard under the MCU board; SMD pads >= 2 mm from pot/jack pads (4.18 mm); panel labels clear of
nuts, knobs, bolt heads and the USB slot; big-knob circles clear. Native DRC with parity (`research/drc/`):
carrier and MCU board 0 violations / parity 0 (496 and 93 unconnected: unrouted), panel 0. Shared `check`
(`research/check-p1b-*`): ERC 0, DRC 0 violations, parity 0, the same opens. Renders `research/render/*-p1*.png`.

### P2 rework (2026-11-09)

User: spread the channels into the side space, two screws around the MCU board like modules/usb-audio-max, and
move the returns and master a bit away from the sends. P1 decisions stand except where replaced here.

| # | Decision | Why |
|---|---|---|
| P2a | Channel columns **X17.9 / 39.7 / 61.5 / 83.3** (21.8 mm pitch, 4MIX 20.32); row labels IN/A/B/VOL at X4.8; MS1/MS2 midway between the VOL knobs (X28.8 / 72.4, Y114) | Uses the empty side margins: 8.9 / 9.0 mm front margins outside the big-knob circles. Wider is blocked by J6/J7: each box header's courtyard is 1.02-1.1 mm from the edge and 0.12 mm from the SEND A pot lug pads (RV102/RV402); the build now asserts no foreign through-hole pad under a B box header |
| P2b | Top line regrouped: SEND A X6.6, SEND B **X18.1** (11.5 mm), 17.4 mm gap, RTN A/LVL A **X35.5**, RTN B/LVL B **X49.5**, OUT/MAIN X63.5 (14 mm) | Visible send / return+master grouping. MAIN cannot move right (0.66 mm from the MCU board, which is 1.05 mm inside the carrier edge) and SEND A sits at the left keep-out, so the gap comes from tighter pitches: jack nuts 2.3 mm apart, pot courtyards 1.09 mm, small knobs 3.0 mm |
| P2c | **MS3 X74.1 / MS4 X96.1, Y43.5**: two M3x10 standoffs at the MCU board's lower corners, mirror images about its centre X85.1 (replaces P7's single MS3 at X95 Y45); panel holes H29-H32 | User: two screws around the MCU board as on usb-audio-max. Its spot beside the USB-C is not free at 20HP (RV1 on the left, the carrier edge on the right): a top pair needs ~15 mm more width, about 23-24HP. Hexes 0.77 mm below the MCU board outline; MS4's B keep-out 1.0 mm from the edge. The top-row jack nuts (J5 at X63.5) still hold the area left of the USB-C |
| P2d | J6 CLK OUT X6.65 / J7 CLK IN X94.55, both **Y58**; J8 power one pitch right (pin 1 X92.65 Y116.08, IDC16 envelope X90.12-97.72) | J6/J7 clear MS4's B keep-out and stay level; J7 0.1 mm inboard keeps its pin-1 silk arrow inside the edge. J8 and the IDC16 socket clear the RV401 lugs (1.4 mm) |
| P2e | J15 SWD pin 1 X71.5 Y49.2, SW1 RESET X77 Y49.5, SW2 BOOT X77 Y55 (B), SWD label below J15 | Between IN3 and IN4, below MS3; SW pads 2.13 mm from the IN4 jack pads |

Checks (build assertions + native, `research/drc/*-p2.json`, `research/check-p2-*`): courtyards >= 1 mm from the
edge (closest J6 1.025 mm); no F courtyard under the MCU board (MS3/MS4 hexes 0.625 mm, RV1 0.665 mm); SMD
>= 2 mm from pot/jack pads (2.13 mm); no through-hole pad under J6/J7/J8 (0.115 / 0.115 / 1.395 mm); panel
labels and knobs clear (closest label 0.47 mm, small knobs 3.0 mm apart). Native DRC with parity: carrier 0
violations / parity 0 / 496 opens, MCU board 0 / 0 / 93 opens (unrouted, MCU board unchanged), panel 0. Shared
`check`: ERC 0, DRC 0, parity 0, the same opens. Renders `research/render/*-p2.png`.

### P3 rework (2026-11-09)

User: remove the two corner screws (MS3/MS4); move the MCU board a bit down and put one screw on top (that is
enough); do not move the pots down; shorten the MCU board or cut it out (4 layers allowed); two DAC outputs from
USB, assigned in the DAW, in the very corner; the IDC sockets are on the other side (B), so their space can be
used on the front. P1/P2 decisions stand except where replaced here.

| # | Decision | Why |
|---|---|---|
| P3a | MS3/MS4 at the MCU board's lower corners removed; **one MS3 at X84.1 Y13.75**, centred above the USB-C (panel hole H33; H31/H32 = MS1/MS2) | In line with the plug force. As high as the 1 mm keep-out allows (B keep-out R3.5 exactly 1.0 mm from the top edge); panel bolt head 3.15 mm above the USB slot, inside the rail gap (top Y11.0) |
| P3b | MCU board **moved down 7.7 mm**, outline X70.6-99.6 Y17.7-45.0 with a **10.6 x 4.8 mm notch** (X78.0-88.6 below Y40.2) over the IN4 jack; 27.3 mm tall; still 4 layers. J12-J14 = J112-J114 pin 1 at Y20.0 (were Y13), running down the legs beside the jack. USB-C J101 at X84.1 **Y21** (panel slot moves with it), U101 zone unchanged (X77.0-90.5, Y25-38.5) | MS3 hex 0.65 mm above the board; notch edges 0.51 mm from the IN4 courtyard; MAIN (RV1) still 0.665 mm left. Pots and jacks did not move. The notch's inside corners get the router radius (<= 0.3 mm of material, still clear) |
| P3c | **USB 1 (J9) X94.85 Y82.1, USB 2 (J10) X94.85 Y96.3**, bottom-right side margin, labels above each | The bottom-right corner over J8 and its IDC16 socket (both on B). J10 as low as the J8 pads allow (S pad 1.24 mm copper gap to the J8 pin 9/10 pads); the CH4 VOL big-knob circle stops the panel nuts lower (1.5 mm clear). Courtyards 1.025 mm from the edge, 0.34 mm from the RV403/RV401 courtyards, J9/J10 0.1 mm apart; nuts 1.6 mm from the CH4 SEND B knob |

Notes: J10's TN/S pins come through under the IDC16 power socket envelope on B (socket bottom 2.5 mm above B on
J8's plastic): trim those two leads to <= 1.5 mm. The MCU board lost the free corners beside the USB-C (about
40 mm2 net after the legs): the ~20 small parts (U102, Y101 5032 crystal, C101-C111, R101-R108) have to fit in the
1.7 mm column between J112 and U101, the 1.2 mm strip between the USB-C and U101, the 1.7 mm strip below U101 and
the leg ends. That is tight on F only; if it does not close at placement, the fallbacks are a 3225 8 MHz crystal
(schematic change) or 0402 passives on the MCU board's B side (2.5 mm under it; two-sided assembly). Not decided.

Checks (build assertions + native, `research/drc/*-p3.json`, `research/check-p3-*`): courtyards >= 1 mm from the
edge (closest J9/J10/J6 1.025 mm); no F courtyard under the notched MCU board (IN4 0.525 mm, MS3 0.625 mm, RV1
0.665 mm); SMD >= 2 mm from pot/jack pads (2.13 mm); no THT pad under J6/J7/J8 (0.115 / 0.115 / 0.295 mm, J10);
panel labels and knobs clear (closest label 0.47 mm). Native ERC 0 both (carrier 233 parts / 152 nets). Native DRC
with parity: carrier 0 violations / parity 0 / 499 opens, MCU board 0 / 0 / 93 opens (unrouted), panel 0. Shared
`check`: ERC 0, DRC 0, parity 0, the same opens. Renders `research/render/*-p3.png`.

## 9. S2 / S3 schematics and R1 routing (2026-11-10)

User: start and finish the routing, change part placements as needed; only the through-hole parts stay where
they are. Later the same day: the MCU board must be single-sided; extend it to the top of the main board with
a cut-out for the screw, move the SWD pins elsewhere, move the strips up for more room.

### Schematic changes

| # | Change | Why |
|---|---|---|
| S2a | MCU pins re-assigned to the side of the LQFP each strip sits on (section 5): I2S2 = TX to DIN1, I2S3 = RX from DOUT1, CODEC_RST PC0, POT_ADC PC1, MUX_S0-3 PC2/PC3/PA0/PA1, NORM_PROBE PA8, VBUS_DET PC11 | Chosen while routing the MCU board so each signal leaves the LQFP on the side of its strip. Any GPIO/ADC pin works (firmware does not exist yet); the SPI-slave fallback moved with the data pins (PB14 on PB15) |
| S2b | I2C pull-ups (R108/R109 2.2k) and the DIN1 series resistor (R110 33R, at the source) moved to the MCU board; carrier R18/R19/old R65 removed | Parts at the driver, fewer carrier parts in the codec corner |
| S3a | **Two 1x12 strips** J12/J112 (X73.5) and J13/J113 (X96.7), pin 1 at Y14.92; J14/J114 removed. I2S3 CK/WS tied to I2S2 CK/WS on the MCU board, so BCK and LRCK use one strip pin each; LINK_N on PA2 | User: single-sided MCU board with the strips moved up. Dropping the centre strip frees 3.8 mm beside the MCU and opens a 6 mm clock corridor east of the codec on the carrier |
| S3b | MCU board outline: X70.6-99.6, Y10.25-45.7, with a 7.6 x 7.45 mm notch for MS3 at the top (X80.3-87.9 down to Y17.7) and the IN4-jack notch (X78.0-88.6 below Y40.2); **all 25 SMD parts on F**, crystal Y101 now 3225 | User: extend to the carrier top with a cut-out for the screw. MS3 hex 0.45 mm from the notch, IN4 courtyard 0.505 mm, RV1 0.645 mm; outline 1.0 mm inside the carrier edge. USB-C unchanged (X84.1 Y21), so the panel did not change |
| S3c | J15 SWD moved to the carrier B side at X93.3 (pin 1 +3V3 Y22.54, SWDIO, SWCLK, GND upwards, between J13 and the codec); SW2 BOOT (X69.5 Y12.2) and SW1 RESET (X77.5 Y12.2) at the carrier top edge on B | User: move the SWD pins. Short runs to J13.1/2 and J12.1/2 |
| S3d | **R65 47R + C50 10u = +3V3_POTB** feeds the top-row pots RV1-RV3 (LVL A, LVL B, MAIN); the other twelve stay on R62/C48 (+3V3_POT) | The N-S +3V3_POT link from the channel pots to the top row was a wall across the E-W analog fan; a second filter under the top row removes it. Same 340 Hz corner; the wipers stay below +3V3 |

Generators (`tools/circuit_*.py`, `build_schematic.py`, `import_footprints.py`) carry all of it; ERC 0 on both,
netlists asserted. `tools/build_layout.py` and its P3 description of the MCU outline are history: it must not be
rerun (it would park the SMD parts again); `docs/geometry.json` was updated by hand to S3.

### R1 routing (manual, divide and conquer, straight on the boards)

Batches are scripts in the ignored `research/route/` (`mcu/m10-m17.py`, `carrier/*.py`), one net or one local
group each, native DRC + parity after each; a one-connection path finder was used on a `/tmp` copy for single
links and every path was inspected and re-entered by hand. No autorouter.

- **Layers.** Carrier: F signal (only THT parts there: long runs, the analog fan, the clock and mux lanes),
  In1 solid GND (no tracks), In2 +3V3 plane with a +5VA island (codec, input drivers, a finger down to the
  regulator) and two +3V3_C islands (clock corridor, strip west of the codec), B signal + all 200 SMD parts.
  MCU board: F signal + all parts, In1 GND, In2 +3V3, B signal.
- **Floorplan.** Codec U3 on B under the MCU board between the strips; clock logic (U4, U13) in a corridor east
  of the codec with F lanes N-S and B crossers E-W; SCKI mux U11 and the CLK OUT buffers SW of it; input drivers
  U5/U6 between the IN jacks; U7 by SEND A/B, U8 by USB 1/2; mux U10 central among the channel pots; power entry (D1/D2) by J8, the +5VA
  regulator (Q1, R1/R2) bottom centre, the +3V3 buck (U2/L1) on the west edge.
- **Crossings.** The digital pot lines (J12.7-11 -> U10) run N-S on B lanes X63.8-65.4 east of IN3, the analog
  fan and the CLK OUT bus run E-W on F. CLK OUT (LRCK/BCK/SCKI, R70-R72 -> J6) is three F tracks Y52-61 across
  the board to vias west of U10, then B to J6.
- **NORM** (jack-normal node) links J401.TN to J301.TN with six vias: each hop crosses one of those walls. It is
  a DC patch-detect net (33 mV probe), so the vias cost nothing.
- **W_VOL4** (the last net): R62 moved from in front of U10 pin 22 to below U10; pin 22 leaves east, hops to F
  past C49 and returns to B under R2's body (2512, B side) to C710.
- **DAC mapping** D4a still holds (set during this routing).

Checks (2026-11-10, `research/drc/carrier-s04f4b.json`, `research/check-r1-carrier`, `research/check-r1-mcu`):

| Check | Carrier | MCU board |
|---|---|---|
| Native ERC `--severity-all` | 0 | 0 |
| Native DRC `--severity-all`, zones refilled | 0 violations, 0 exclusions | 0 violations, 0 exclusions |
| Unconnected | 0 | 0 |
| Schematic parity | 0 | 0 |
| Vias in SMD pads | 0 (codec thermal vias only) | 0 |
| Tracks on In1 | 0 | 0 |
| Courtyards to the edge | >= 1.00 mm (C8 1.00, J10 1.03, J6 1.03) | - |
| SMD pads to pot/jack pads | none under 2 mm | - |
| Copper | 1873 track segments, 288 vias | 253 segments, 55 vias |

Plane pieces (filled polygons): +5VA island one piece, both +3V3_C islands one piece each, Q1 heatsink pour one
piece. In1 GND: one plane + four 2.4-2.6 mm2 fragments between the pins of J6, J7 and J8, each tied to its GND
pins by spokes. In2 +3V3: one plane + four fragments: two 0.95 mm2 slivers on J12.3 (+3V3, spoke-tied) and the
pads of two +3V3 vias that sit inside the +5VA island, (52.1, 76.05) under U10 and (78.9, 45.1), both fed by
tracks, not by the plane.

Shared `check`: MCU board no findings. Carrier: ERC 0 / DRC 0 / unconnected 0 / parity 0, and its extra
ref/pin/net comparison lists four name-only differences, `Net-(U9-Trim/NR)` and `Net-(U3B-MDO/ADR1/MD1)`
against the PCB's `{slash}` spelling of the same nets (KiCad escapes `/` in pin-derived net names on the
board; native parity is 0), plus the three reference-less standoffs. Both were there at P1-P3; not waived,
fixed only by naming those two nets in the schematic.

Open after R1: fab review, JLCPCB export, firmware, bench.
