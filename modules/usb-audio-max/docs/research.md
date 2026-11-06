# USB-AUDIO-MAX research and circuit intent (S2 schematics)

A Eurorack USB audio interface: 6 in / 8 out, DC-coupled (audio and CV), 24-bit, up to 96 kHz,
USB Audio Class 2 over USB 2.0 High-Speed. Brief (user, 2026-11-05):

- Based on the TI PCM3168A (6-in / 8-out codec), named usb-audio-max, same style as
  modules/usb-audio (CH32V307 MCU board on 2.54 mm strips, carrier with jacks, SMD by JLC).
- No level controls on inputs or outputs. DC coupled. 96 kHz is enough.
- Check that JLC has the codec; draw the schematics. Placement, panel and routing come later.

Nothing here is built or bench-tested. The MCU board pins keep modules/usb-audio's I2S2/I2S3 use
and add SPI1 for the second TDM line pair (section 4: the 96 kHz firmware path is the main risk).

Schematic revisions (all 2026-11-05, user decisions): S1 first draft (+5VA AMS1117-5.0, then
LT3045 + REF5050 for the DC outputs; +3V3 TPS562208 buck); S1.1 +5VA from REF5050 + LM358 + BCP56
(cost); S1.2 +3V3 from 3 x 68R + AMS1117-3.3; **S2 (final schematics)**: +3V3 back on the TPS562208
FCCM buck behind an input filter, checked against the audio in ngspice (section 2a), every LCSC code
re-checked live, drawings tidied (no overlapping texts). The MCU board circuit is unchanged since S1
(S2 is a drawing tidy).

## 1. Architecture

```
USB-C (panel) -- MCU board: CH32V307RCT6 USBHS, I2S2 RX + I2S3 TX + SPI1 (slaves), I2C2
                     | J102/J103 = carrier J2/J3 (2 x 1x10 2.54 mm strips)
carrier: PCM3168A (ADC = TDM clock master, SCKI 24.576 MHz) -- 6 x input driver, 8 x difference
         amplifier, power (precision linear +5VA, FCCM buck +3V3), BOOT/RESET, SWD
```

| # | Decision | Why |
|---|---|---|
| D1 | PCM3168APAPR (HTQFP-64 PowerPAD), I2C control (MODE = DGND), address 0x44 | 6 ADC (8-96 kHz) + 8 DAC (8-192 kHz), TDM output so the CH32V307 needs only 2 data lines each way at 96 kHz. JLC C529289, Extended, Economic-eligible, 1517 in stock (2026-11-05, S2 re-check) |
| D2 | ADC master in 24-bit I2S-mode TDM; BCKDA/LRCKDA tied to BCKAD/LRCKAD (DAC slave) | One clock domain. SCKI 24.576 MHz = 256 fS at 96 kHz (dual rate, BCK 128 fS) or 512 fS at 48 kHz (single rate, BCK 256 fS): BCK is 12.288 MHz in both, the same rate modules/usb-audio's firmware already runs. TI SBAS452A: TDM single rate uses DOUT1/DIN1, dual rate DOUT1/2 and DIN1/2 |
| D3 | ADC single-ended mode (SEAD = 1), HPF bypassed (BYP = 111) | One 5 V op-amp per input keeps the input chain of modules/usb-audio (inverting driver, bias from the codec's mid-rail). SE costs 3 dB (104 vs 107 dB DR); DC passes with the HPF off. VINx- terminated with (buffered) VCOMAD, as datasheet 9.3.1 allows |
| D4 | Input: jack (TN = GND) -> 100k -> inverting driver on +5VA (24k, 47p) -> 470R / 2.2n C0G -> VINn+; VINn- = VCOM_REF | 100k input impedance (Eurorack norm, no pot to buffer). A 5 V single supply means VIN can never leave 0..5 V; for a +/-12 V patch the inverting node stays at 1.7..2.4 V, so no clamp diodes conduct |
| D5 | Output: difference amplifier on +/-12 V per DAC (15k in, 22k \|\| 47p feedback, 22k \|\| 47p to GND) -> 2 x 2k 1206 (1k, 0.5 W) -> jack | Removes VCOMDA without coupling capacitors (DC coupled). Both DAC pins move together at power-up, mute and power-save (all go to VCOMDA or AGND), so the outputs stay near 0 V: no CS4270-style -8 V start-up excursion. 15k meets the datasheet DC-load minimum (1 + 0.9G)/(1 + G) x 15k = 14.1k at G = 1.467. Output network as the usb-audio R36/R38 repair |
| D6 | References: U6C buffers VCOMAD -> VCOM_BUF -> 100R / 10u -> VCOM_REF; VCOM_BUF -> 24k / 100k (10u) -> U6D -> VB_IN | VCOMAD is 10k / 1 uA max. The VB divider has the input stage's own Rf/Rin ratio, so 0 V in = VCOM at VINn+ independent of the +5VA tolerance |
| D7 | Power: +12V_F -> 2 x 33R 2512 in parallel -> discrete LM358 + BCP56 regulator (REF5050 reference, D11) -> +5VA (codec VCC, input op-amps: every analog rail stays linear). +12V_F -> FB2 GZ2012D121TF + R3 2.2R -> V3_IN (C6/C7 10u 1206 50 V, C8 100n; R4 100k to EN) -> U2 TPS562208 (FCCM) -> L1 4.7u Sunlord MWSA0402S (molded) -> +3V3 (C9/C10 22u, C5 100n; R5 33k / R20 10k = 3.30 V) -> FB1 -> +3V3_C (codec VDD, U4) -> R21 10R / C43 10u -> +3V3_OSC (Y1). S2 (user, 2026-11-05): the buck again (S1.2 had 3 x 68R + AMS1117-3.3), kept away from the audio | +3V3 carries ~200 / 250 mA (typ / max: codec VDD 106-130 mA + MCU board ~100 mA). Linear from 12 V that is ~1.7-2.2 W of heat (S1.2); the buck takes ~0.9 W from +12 V. Audio: only the digital rail switches. The TPS562208 is the forced-continuous (FCCM) variant, so it runs at a pseudo-fixed ~580 kHz at every load and never pulse-skips down into the audio band (the TPS562201 Eco-mode variant lowers its frequency with the load, TI SLVSD91D 6.3.2: do not substitute). FB2 + R3 with C6/C7 is a resistor-damped filter (~5 kHz, no LC peak) that keeps the switching current off +12V_F and the Eurorack bus; its output impedance (<= 2.6 ohm) stays far below the buck's ~130 ohm negative input impedance, so the buck loop is unaffected. L1 is molded (shielded). FB1 and R21/C43 filter the codec VDD and the oscillator. Values inside TI's table for 3.3 V (33.2k / 10k, L 3.3-4.7 uH, 20-68 uF; 2 x 22u 0805 = ~26 uF at 3.3 V). Results in section 2a. +12 V ~0.28 A typ / ~0.34 A max |
| D8 | U4 SN74LVC2G34 buffers BCK/LRCK to the MCU board | In master mode the codec clock pins are rated 20 pF and TI asks for light loads (12.1.10); three MCU pins each plus the header would exceed that |
| D9 | MCU board: modules/usb-audio MCU S1 + SPI1 (PA4 NSS = LRCK, PA5 SCK = BCK, PA6 MISO -> R109 33R -> DIN2, PA7 MOSI <- DOUT2) | I2S2 RX (DOUT1) and I2S3 TX (DIN1) stay on the pins that work today. CODEC_RST stays on PB14. 10 header pins carry the extra lines: CODEC_RST moves to J2.9, J3 = +3V3 GND BCK GND LRCK ADC1 DAC1 ADC2 DAC2 GND |
| D11 | DC reference (2026-11-05, user: add what the DC outputs need; S1.1 same day, user: replace the ~$8.9 LT3045 with REF5050 + LM358 + NPN): U9 REF5050A (0.1 %, 8 ppm/C max) -> R6 10k / C19 1u (16 Hz, 10 ms soft start) -> V5_SET -> U1A LM358 (+12V_F) -> R9 150R -> Q1 BCP56-16 emitter follower (collector V5_IN) -> R8 2.2R -> +5VA. Feedback R7 10k from +5VA (Kelvin at the codec, equals R6 so the bias currents cancel); PI compensation C37 22n + R16 47k from the U1A output to its - input. Q2 MMBT3904 across R8 pulls the Q1 base: current limit ~0.3-0.35 A. Unused U1B is a follower at GND | +5VA is the converters' reference: DAC full scale 1.6 x VCC, ADC 0.2 x VCC, VCOM 0.5 x VCC. With an AMS1117 (0.5 % temperature stability, 0.3 % / 1000 h, typ) a 5 V CV would drift up to ~30 mV (~35 cents at 1 V/oct), which per-channel calibration cannot remove. Now: REF 8 ppm/C max; LM358 offset <= 7 mV (9 mV over temperature) is fixed and calibrated out, its drift 7 uV/C typ (~1.4 ppm/C of 5 V); bias-current offset <= 0.5 mV. Loop in ngspice (S2; Nexperia BCP56-16, National LM358 macro and 2N3904 models, `research/buck/sim/reg5va.py`; S1.1 used a hand nodal model): 170 cases over 8-250 mA, 8-100 uF on +5VA (16.6 uF effective as drawn), hFE 70-250, LM358 GBW 0.5-2 x the macro and ESR 2-50 mOhm give phase margin >= 78 deg, gain margin >= 26 dB, crossover 1-29 kHz; Zout <= 0.76 ohm (peak near 1 kHz); PSRR from +12V_F 50 dB at 100 Hz, 47-49 dB at 1-8 kHz, 53 dB at 580 kHz. A 50 -> 200 mA load step dips 91 mV and is still ~22 mV low 2 ms later (PI tail); the +5VA load is near constant, so this is not a working case. Noise ~6 uV rms (LM358 40 nV/rtHz over the loop). Q1 <= 0.70 W at 12.6 V (worst at 195 mA): SOT-223 with >= 1 cm2 tab copper. No thermal shutdown: a sustained +5VA short sits at the Q2 limit (ngspice 0.35 A: Q2 also sinks the LM358's ~40 mA output current) with Q1 ~1.8-2 W (over its 1.35 W rating) and R1/R2 ~1.0 W each, so it protects start-up and brief faults only. Cost ~$1.2 (C7950 Basic, C92221, C20526 Basic, C144499) instead of ~$8.9 for the S1 LT3045 + REF5050. Bench: scope the +5VA step response and check the limit point |
| D10 | Op-amps OPA1679 x 4 (U5/U6 on +5VA, U7/U8 on +/-12 V) | As modules/usb-audio U6: low noise, rail-to-rail output on 5 V. 16 sections: 6 drivers, 2 references, 8 outputs |

## 2. Levels and accuracy

| Path | Numbers |
|---|---|
| Input | ADC SE full scale 0.2 x VCC Vrms = +/-1.414 V peak at 5.00 V. Gain -24k/100k = -0.24 -> **+/-5.89 V at the jack** (11.8 Vpp). VB_IN = VCOM x 100/124 = 2.016 V. REVAD = 1 restores the polarity. Pole 141 kHz (24k / 47p), ADC RC 154 kHz (470R / 2.2n C0G). Input impedance 100k |
| Output | DAC full scale 1.6 x VCC = 8 Vpp differential. Gain 22k/15k = 1.467 -> **+/-5.87 V** (matches the input to -0.04 dB, both track +5VA). Pole 154 kHz. Output impedance 1k |
| Noise (estimate) | Input stage ~24 nV/rtHz at the ADC (24k, 100k x 0.24, op-amp x 1.24): ~3.4 uVrms in 20 kHz = 109 dB below full scale, against the ADC's 104 dB SE: ~103 dB total. Not measured |
| DC | Datasheet bipolar zero error +/-1 % FSR typ for ADC (HPF bypassed) and DAC; 1 % resistors in the difference amplifiers add up to ~+/-60 mV worst case from the 2.5 V common mode. Per-channel offset (and gain) calibration in firmware, as planned for modules/usb-audio |
| DC stability | +5VA from D11: the reference drifts <= 8 ppm/C (max), i.e. < 0.25 mV/C at full scale, plus the LM358 offset drift (7 uV/C typ). Difference-amplifier ratio drift (1 % 0603, same type on both legs) and the PCM3168A's own zero drift are not specified; measure on the bench after calibration |
| Mis-patch | Input: +/-12 V on a jack -> 120 uA through the 100k, driver output clips at a rail, VIN stays within 0..5 V. Output: 12.6 V into an output at -5.9 V -> 18.5 mA, <= 0.17 W per 2k resistor |

## 2a. +3V3 buck against the audio (ngspice 45.2, S2)

Method: ngspice transient of a behavioural TPS562208 (D-CAP2 adaptive on-time, FCCM, 140 / 84 mOhm
FETs, 1 ms soft start) with the real L1 and capacitors (DC-bias derated, ESR/ESL), the Eurorack
bus (0.1 ohm + 0.5 uH), D2, the input filter, the MCU-board and codec loads. Its input-current and
switch-node spectra drive AC models of the +12V_F network, the +5VA regulator (vendor models, D11),
the OPA1679 output stages (datasheet PSRR curve) and the ADC input network. Decks and results:
`research/buck/sim/` (local, ignored; `out/final-summary.json`). It is not TI's model and not a
measurement, and layout coupling (stray magnetic field, ground currents) is not in it: the layout
rules in section 7 cover that.

| Path (12 V bus, 250 mA on +3V3; 11.4-12.6 V and no load checked too) | Result |
|---|---|
| Switching frequency | 532-537 kHz in the model at every line and load, including no load (FCCM; TI: ~580 kHz) |
| +12V_F (output op-amps, +5VA regulator, U9) | 50 uV rms of switching harmonics with FB2 + R3 (1.9 mV rms without a filter, 60 uV with R3 alone) |
| Eurorack bus | 0.03 mA rms of switching current back into the bus (1 mA without the filter) |
| +5VA | 0.12 uV rms |
| Output jacks | 2.3 uV rms at 535 kHz and up: above the audio band, -128 dB below full scale |
| ADC inputs (aliasing) | worst switching harmonic -183 dBFS |
| +3V3 / +3V3_C / +3V3_OSC | 2.2 mV / 0.06 mV / 0.2 uV peak at the switching frequency |
| Input-filter stability | filter output impedance <= 2.6 ohm against the buck's ~130 ohm negative input impedance |
| Audio band: USB load bursts | MCU-board current stepping 30 mA p-p at the 8 kHz microframe rate (pessimistic): 0.78 mV at 8 kHz on +12V_F with the buck, 0.58 mV with the S1.2 LDO (its 22.7R pre-drop and 10u filtered a little more). That is -142 dBFS at the jacks (LDO: -144), 2.8 uV on +5VA (-125 dBc of full-scale DAC gain modulation) and 0.07 mV on +3V3_OSC: both versions sit ~30 dB below the codec's own noise |

## 3. Circuit

```
POWER  J1 +/-12V -> D2/D1 B5819W -> +/-12V_F; R1||R2 2 x 33R 2512 -> V5_IN (C3) -> Q1 BCP56-16 -> R8 2.2R -> +5VA
       (C20-C25 at the codec, C31/C32 at U5/U6); Q2 MMBT3904 across R8 -> Q1 base (current limit); U9 REF5050A
       (C16 in, C17 NR, C18 out) -> R6 10k -> V5_SET (C19 1u) -> U1A LM358 + ; R7 10k +5VA -> U1A - ;
       C37 22n + R16 47k U1A out -> - ; U1A -> R9 150R -> Q1 base; U1B follower at GND; C38 U1 V+ (+12V_F)
       FB2 GZ2012D121TF -> R3 2.2R -> V3_IN (C6/C7 10u 1206 50 V, C8 100n; R4 100k -> EN) -> U2 TPS562208
       (C4 100n VBST-SW) -> L1 4.7u MWSA0402S -> +3V3 (C9/C10 22u, C5 100n; R5 33k / R20 10k -> VFB);
       FB1 -> +3V3_C; R21 10R -> +3V3_OSC (C43 10u)
CODEC  U3 PCM3168A unit A: VIN1-6+ <- ADC_IN1-6; VIN1-6- = VCOM_REF; VCOMAD C11, VCOMDA C12, VREFAD1 C13/C14,
       VREFAD2 C15 (10u each, datasheet 12.1.4-12.1.5); VOUT1-8 +/- -> DACnP/DACnN
       unit B: Y1 24.576 MHz -> R10 33R -> SCKI; BCKAD=BCKDA, LRCKAD=LRCKDA -> U4 74LVC2G34 -> R11/R12 33R ->
       I2S_SCLK/I2S_LRCK; DOUT1/DOUT2 -> R13/R14 33R -> I2S_ADC1/2; DIN1/DIN2 <- I2S_DAC1/2; DIN3/4, MODE,
       MS/ADR0 to GND, MDO/ADR1 via R15 10k to GND; SDA/SCL (R18/R19 2.2k to +3V3); RST <- CODEC_RST (R17 10k
       pull-down); DOUT3/OVF/ZERO open. VCC pins 1u each (C20-C23) + 2 x 10u (C24/C25), VDD 1u each (C26/C27)
       + 10u (C28); Y1 C29, U4 C30; PowerPAD to GND
IN n   J1n T (TN, S = GND) -> R20n 100k -> U5A-D / U6A-B (- input; + = VB_IN; R21n 24k || C20n 47p)
       -> R22n 470R -> ADC_INn (C21n 2.2n C0G)
OUT n  DACnN -> R30n 15k -> U7/U8 - (R32n 22k || C30n 47p to the output); DACnP -> R31n 15k -> + (R33n 22k
       || C31n 47p to GND) -> R34n || R35n 2k 1206 -> J2n T
REFS   U6C: VCOMAD -> VCOM_BUF -> R50 100R -> VCOM_REF (C40 10u, C41 100n); R51 24k / R52 100k (C42 10u) -> U6D
       -> VB_IN
LINK   J2: +3V3 GND SWDIO SWCLK NRST BOOT0 SCL SDA CODEC_RST GND; J3: +3V3 GND SCLK GND LRCK ADC1 DAC1 ADC2 DAC2 GND
       SW1 RESET, SW2 BOOT, J4 SWD (+3V3 SWDIO SWCLK GND)
MCU    U101 CH32V307RCT6 as modules/usb-audio MCU S1, plus PA4 (LRCK), PA5 (BCK), PA6 -> R109 33R -> I2S_DAC2,
       PA7 <- I2S_ADC2; J102.9 = CODEC_RST; J103 as carrier J3
```

Native ERC (`--severity-all`) 0 on both schematics (`docs/erc/`); the generator asserts that the
exported netlist equals the circuit tables (`tools/circuit_carrier.py`, `tools/circuit_mcu.py`).
Carrier 197 parts / 127 nets (179 with an LCSC code; the 18 jacks, headers and strips are
hand-soldered), MCU board 26 parts / 28 nets (24 with an LCSC code; J102/J103 are the carrier's
strips). Every placed footprint is in `hardware/USBAUDIOMAX.pretty`.

The PCM3168A symbol is drawn by `tools/build_schematic.py` from the datasheet pin table (KiCad ships
none): unit A analog, unit B interface/control/supplies, pin 65 = PowerPAD.

## 4. TDM link and firmware notes (not done)

| Rate | Codec | Lines |
|---|---|---|
| 48 kHz | SCKI 512 fS, single rate, BCK 256 fS | DOUT1 = ADC1-6 (slots 1-6 of 8), DIN1 = DAC1-8 |
| 96 kHz | SCKI 256 fS, dual rate, BCK 128 fS | DOUT1 = ADC1-4, DOUT2 = ADC5-6 (+2 empty), DIN1 = DAC1-4, DIN2 = DAC5-8 |

- 48 kHz uses only I2S2 RX and I2S3 TX, exactly as modules/usb-audio's firmware (I2S slave, 32-bit
  slots, started on a WS edge, then free-running): 8 slots per frame instead of 2.
- 96 kHz also needs SPI1 as a full-duplex slave. Its hardware NSS = LRCK (I2S-mode TDM: LRCK low
  for slots 1-2) frames the first half of each frame; to keep it running through slots 3-4 the
  firmware can switch to software NSS (SSM = 1, SSI = 0) during the first LRCK-low half (5.2 us).
  This is plausible on the STM32F1-style SPI but **untested on the CH32V307: bench it first**. If it
  fails, SPI1 with plain NSS still carries ADC5-6 and DAC5-6 at 96 kHz (DAC7-8 then only at 48 kHz).
- Rate switch at run time (user direction 2026-11-05; settle on the bench): SPI1 has its own pins
  (PA4-PA7), separate from I2S2/I2S3, so no hardware change is needed. 48 kHz: I2S2 RX + I2S3 TX
  only, SPI1 off and PA6 driven low (DIN2 unused). 96 kHz: same I2S setup plus SPI1 for line 2.
  On a UAC2 rate change: stop DMA, hold the codec in mute, rewrite MSAD/MSDA over I2C, restart the
  ports on a WS edge, and remap the TDM slots (table above).
- Codec init: RST high after SCKI runs; OVF (the reset-done pulse) is not wired, so wait a fixed
  delay (> 4096 SCKI = 167 us, plus margin); then MSAD = 100
  (256 fS) or 010 (512 fS), FMTAD = 110, FMTDA = 0110, SEAD = 111111, BYP = 111, REVAD = 111111.
  Supply order is free (datasheet 9.3.6); +3V3 is up in ~1 ms, +5VA follows V5_SET in ~10 ms, and R17
  holds RST low until the firmware releases it.
- Firmware FIFOs (2026-11-05 sizing, modules/usb-audio): 8 ch x 96 kHz fits the 64 KiB RAM with
  12 KiB FIFOs and static block buffers; 6/8 channels need slightly less.

## 5. Panel

14 jacks and the USB-C slot, no pots. **8HP** (user decision, 2026-11-05), three jack columns (IN 1-6 in two rows of
three, OUT 1-8 below in three rows), MCU board and USB-C at the top as modules/usb-audio. 6HP would
need 7-8 rows of two jacks (~8.5 mm pitch): too tight with the MCU board under the top 40 mm.
Not decided: jack order, labels. Placement, panel and routing follow the root `AGENTS.md` rules.

## 6. Sourcing (JLCPCB live lookups, 2026-11-05; stock is not reserved)

S2 re-check of every LCSC code on both schematics (49 codes, 16:5x UTC):
`research/sourcing-s2/` (ignored, local; C1562 by keyword search, its exact-code lookup is
ambiguous). Earlier raw lookups: `research/sourcing-2026-11-05.json`, `research/ldo-search/`,
`research/buck/`. 33 codes are Basic, 16 Extended; all Economic-eligible.

| Part | LCSC | Class | Stock |
|---|---|---|---|
| PCM3168APAPR | C529289 | Extended (Economic) | 1517 |
| TPS562208DDCR (FCCM buck) | C91301 | Extended (Economic) | 69740 ($0.09) |
| MWSA0402S-4R7MT (Sunlord molded 4.7 uH, Isat 3 A, 105 mOhm) | C408337 | Extended (Economic) | 39722 ($0.15) |
| GZ2012D121TF ferrite (FB1, FB2) | C5671 | Extended (Economic) | 40039 |
| AC1206FR-072R2L 2.2R 1206 (R3, R8) | C144499 | Extended (Economic) | 77908 |
| REF5050AIDR | C27804 | Extended (Economic) | 16819 ($1.09) |
| BCP56-16,115 (Nexperia) | C92221 | Extended (Economic) | 53453 |
| 33R 2512 1 W (R1, R2) | C53728 | Extended (Economic) | 48348 |
| SN74LVC2G34DCKR | C14461 | Extended (Economic) | 26770 |
| OPA1679IDR | C2878631 | Extended (Economic) | 3015 |
| YXC 24.576 MHz 3225 oscillator | C5203547 | Extended (Economic) | 3536 |
| C0G 2.2n 0603 | C33353 | Extended (Economic) | 2759 |
| K2-1808SN-A4SW-01 | C92589 | Extended (Economic) | 12297 |
| CH32V307RCT6 / TYPE-C-31-D-15 / USBLC6-2SC6 | C2988083 / C22464480 / C7519 | Extended (Economic) | 607 / 464 / 30195 |
| LM358DR2G / MMBT3904 | C7950 / C20526 | Basic | 558663 / 2741014 |

Every other R/C (incl. the buck's 10u 1206 50 V C13585, 22u 0805 C45783, 33k C4216 and 10R C22859),
the B5819W and the 8 MHz crystal are Basic. Not an order or a stock reservation.

## 7. Open

- Jack layout on the 8HP panel (section 5), then placement and manual divide-and-conquer routing of both
  boards (root `AGENTS.md`). Codec: PowerPAD to the GND plane with the footprint's 36 thermal vias
  (~1.2 W); TI PAP land pattern to check against the KiCad Texas PAP0064 footprint (mask 5 x 5 mm).
  Q1 BCP56 (<= 0.70 W: >= 1 cm2 tab copper on V5_IN) and R1/R2 need copper; Q2 away from Q1;
  R7 (+5VA sense) and C19's ground side Kelvin-routed to the codec VCC/AGND.
- Buck layout (what keeps section 2a true): U2, L1 and C4-C10 in the power corner by J1, away from the
  input stages, the codec's analog pins and Y1; the C6/C8 - U2 VIN/GND loop as small as possible on one
  side with GND vias at the caps; short, small SW node; nothing routed under L1; the R5/R20 VFB divider
  and R5's +3V3 sense on the quiet side, away from SW; solid GND under the buck with its currents kept
  local (no analog return path through the power corner); FB1 at the codec VDD caps, R21/C43 at Y1.
- Firmware: UAC2 descriptors for 6 in / 8 out, codec init (section 4), TDM slot mapping, SPI1 path,
  DC calibration table.
- Bench: SPI1 NSS switch, 12.288 MHz capture margins, thermal (codec, Q1, R1/R2), +5VA loop (step response,
  current-limit point), +3V3 switching frequency and ripple, an output noise spectrum while USB streams
  (the 8 kHz microframe tone and the ~580 kHz harmonics).
- Current draw: +12 V ~0.28 A typ / ~0.34 A max, -12 V ~20 mA (estimate from datasheet maxima).
