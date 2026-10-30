# usb-power-45w: design notes (S2 schematic)

Goal: a USB-C PD Eurorack supply that can use **at least 45 W**. The current
`modules/usb-power` takes 9 V and goes boost/inverter -> LDOs (about 15 W). This one
asks the charger for **20 V** and makes +12 V, -12 V and +5 V straight from it with
switchers: no boost and no LDOs.

S2 changes from S1 (user review 2026-10-30):

- **eFuse in front, small VBUS capacitance.** A cheap TPS259470A eFuse (one of the
  parts the user proposed) now sits between the PD input and every bulk capacitor.
  VBUS sees only about 2 uF when the cable goes in.
- **All three converters run in forced PWM** at a fixed frequency at every load.
  S1's LMR33630 and TPS54360B drop into pulse skipping at light load, and that can
  bring switching bursts down into the audio band. +12V and +5V now use the TPS62933F
  (1.2 MHz and about 2.0 MHz) and -12V uses the LMR38020F (about 790 kHz).

```
USB-C --VBUS--> F1 5 A --> VPD --> U5 TPS259470A eFuse --> VIN (20 V) --+--> U2 TPS62933F buck -----> +12V
  CC1/CC2 -> U1 CH224A (asks for 20 V, powered from VPD)                 +--> U3 TPS62933F buck -----> +5V
  D1 SMBJ20A, C1 + C2 = 2 uF on VPD                                      +--> U4 LMR38020F inverting -> -12V
  U5: on 17.6-25.3 V only, VIN ramp 2 V/ms, limit 4.1 A, auto-retry           (IC ground = -12V; EN from +12V via Q1)
  U5 AUXOFF -> EN_P: U2/U3 start only after VIN has ramped
Outputs: J2 + J3 16-pin box headers in parallel, bulk caps, SS34 clamps, LEDs
Panel: SW1 RESET on U5 EN/UVLO, D8 red 3 mm +5V power LED
```

All parts were checked live in the JLCPCB catalog on 2026-10-30/31 (`opt/kicad-tools/jlcpcb/assembly.py
search/lookup --strict-live`). Catalog stock is not a reservation. Every R/C is
**Basic**. The ICs, inductors, fuse, TVS, SS34, MMBT3906, electrolytics and USB-C are
**Extended** (each adds the usual JLC Extended setup fee). The full list is in
`docs/bom.csv`, exported from the native schematic fields.

## Input and eFuse

| Item | Choice | Why |
|---|---|---|
| PD sink | U1 CH224A (C42459160), CFG1 = R1 120k to GND | WCH CH224 datasheet V2.0 table 5-1: 120k asks for 20 V. It runs from VPD, ahead of the eFuse, because it has to negotiate while the eFuse is still off |
| Connector | J1 HRO TYPE-C-31-M-12 (C165948) | Same part as usb-power. Catalog rating 5 A / 20 V |
| Fuse | F1 0466005.NRHF 5 A 1206 (C57525) | Back-up only: U5 limits at about 4 A first |
| TVS | D1 SMBJ20A (C10213) | 20 V stand-off, 22.2 V minimum breakdown, so it stays off at the 21 V PD maximum. Lower than S1's SMBJ22A because the eFuse's absolute maximum is 28 V |
| eFuse | U5 TPS259470ARPWR (C3662799, about $0.71 at LCSC / $1.29 at JLC qty 1) | 2.7-23 V, 28 mOhm, adjustable UVLO and OVLO, dVdt ramp, active current limit, auto-retry. The A (auto-retry) version: it retries by itself; SW1 RESET adds a manual off/restart |

**VBUS capacitance.** The Type-C spec allows a sink about 10 uF on VBUS at attach.
Here VBUS only sees C1 (CH224A, 1 uF) and C2 (eFuse input, 1 uF), about 2 uF. Every
other capacitor (C5 47 uF electrolytic and all the converter input ceramics, about
75 uF effective at 20 V) sits behind U5 and is charged slowly.

**Window (R2 100k / R3 2.2k / R4 5.1k, one divider on EN/UVLO and OVLO).** U5 thresholds
are 1.20 V rising and 1.09 V falling (1.183-1.223 V):

- on above VPD = 1.2 x 107.3 / 7.3 = **17.6 V** (18.0 V worst case); off below 16.0 V
- cut off above VPD = 1.2 x 107.3 / 5.1 = **25.3 V** (24.9 V minimum); back on below 22.9 V

A 20 V contract (19-21 V) always passes. A 5 / 9 / 12 / 15 V contract, a charger
without a 20 V profile or a plain 5 V port leaves **everything off**. OVLO keeps a
faulty charger above 25 V away from the converters (TPS62933 recommended max 30 V).
As in usb-power, seeing 20 V does not prove the charger can supply 45 W: use a
20 V PD charger rated 45 W or more.

**Inrush (C3 1 nF on dVdt).** Slew = 2000 / 1000 pF = 2 V/ms (datasheet eq. 4; the dVdt
charge current is 0.81-3.82 uA, so 0.8-3.8 V/ms). VIN rises from 0 to 20 V in about
10 ms, and the inrush into about 75 uF is about 75 uF x 2 V/ms = **0.15 A**. The
converters do not load VIN during the ramp (next paragraph), so this is the whole
start-up current the charger sees.

**Start order.** U5 AUXOFF is an open drain that stays low until VIN is in the window
and the ramp is done. It holds EN_P (U2 and U3 enable) low, so the bucks start only once
VIN is up. Then R6 100k / R7 10k set EN_P = VIN / 11 = 1.8 V (TPS62933 EN threshold
1.21-1.28 V, EN max 5.5 V; AUXOFF max 6.5 V). -12V follows +12V through Q1.

**Current limit (R5 820).** I_LIM = 3334 / 820 = **4.1 A** (+/-10 %, 3.7 A minimum). That
is above the 3 A a 60 W charger gives. U5 is the board's short-circuit and overload
protection; on a 45 W charger the charger's own limit acts first. C4 10 nF lets
overloads pass for 1.51 V x 10 nF / 1.8 uA = 8 ms before U5 turns off. It then retries
by itself. At 3 A, U5 drops about 0.1 V and dissipates 0.25-0.4 W.

FLT is left open: it is an open drain rated to 6.5 V, and there is no low-voltage rail
that stays up during a fault to pull it up to.

## Rails

| Rail | Converter | Parts | Output set point |
|---|---|---|---|
| +12V | U2 TPS62933FDRLR (C5219272), sync, 3 A, FCCM, **1.2 MHz** (RT to GND) | L1 SLO1040H6R8MTT 6.8 uH (C207852, Isat 10 A); 2 x 10 uF/50 V + 100 nF in; SS 22 nF (~3 ms); 4 x 22 uF/25 V out | R8 47k / R9 3.3k: 0.8 V x 15.24 = **12.19 V** |
| +5V | U3 TPS62933FDRLR, sync, 3 A, FCCM, **~2.0 MHz** (RT R10 10k) | L2 SLO1040H3R3MTT 3.3 uH (C207850, Isat 16 A); same caps | R11 68k / R12 13k: 0.8 V x 6.23 = **4.98 V** |
| -12V | U4 LMR38020FDDAR (C5149193), 80 V, 2 A, sync, FPWM, inverting buck-boost, **~790 kHz** (RT R13 33k) | L3 SLO1040H150MTT 15 uH (C182184, Isat 7 A); 2 x 10 uF/50 V + 100 nF across VIN and -12V, 10 uF VIN to GND; 5 x 22 uF out | R14 100k / R15 9.1k: 1.0 V x 11.99 = **11.99 V** |

The FB resistors are 1 % E24 Basic values. +12V comes out 1.6 % high (12.19 V) because
the exact 140k / 10k pair is not a Basic part. That is well inside Eurorack's +/-5 %.

**Frequencies.**

- TPS62933 RT: f = 17293 x RT^-0.942 kHz (datasheet eq. 2), so 10k gives about 1.98 MHz.
  RT to GND gives 1.2 MHz (1.0-1.35 MHz).
- LMR38020 RT: datasheet table 8-1 (34.8k = 750 kHz, 25.5k = 1 MHz), so 33k gives about
  790 kHz. The LMR38020 oscillator tolerance is wide (-18 / +24 % at 525 kHz).
- All three converters are free-running, not synchronised. The fundamentals are set
  well apart (0.79 / 1.2 / 2.0 MHz) so they can't beat against each other in the
  audio band. Some higher harmonic pairs could still land close once the tolerances
  add up. That needs checking on the bench.
- Forced PWM means none of them skips pulses at light load. This is the bigger
  audible-noise fix than the frequency itself.

**+12V and +5V (TPS62933F).**

| Rail | Inductor ripple | Peak at 2.5 A | Device limit |
|---|---|---|---|
| +12V | (20 - 12) x 0.6 / (1.2 MHz x 6.8 uH) = 0.59 A | 2.8 A | high side 4.2 A min, low side 2.9 A min |
| +5V | 15 x 0.25 / (1.98 MHz x 3.3 uH) = 0.57 A | 2.8 A | same |

- Inductors are scaled from TI table 10-2 (12 uH at 500 kHz for 12 V; 3.3 uH at
  1.2 MHz for 5 V).
- +5V on-time at 2 MHz is about 126 ns, above the 70 ns minimum.
- Both inductors saturate well above the high-side current limit.

**Heat.** The TPS62933 is a small SOT-583 with no exposed pad (60 C/W on TI's 2-layer
2 oz EVM). At +12V 2.5 A and 1.2 MHz the estimate is about 0.9 W in the IC, so
roughly 55 C above ambient. That's fine, but the PCB needs wide copper on VIN, GND and
SW. It is the first thing to measure. If it runs hot, set RT floating (500 kHz) on U2.

**-12V inverter (U4 LMR38020F).**

- The IC's ground (pin 1 and the pad) is the -12V node. L3 goes from SW to system GND.
  The part is synchronous, so the S1 catch diode is gone.
- Voltage on U4 and the VIN-to-(-12V) caps: VIN + 12 V = 32 V, or 37 V at the 25 V
  OVLO. That is fine for the 80 V part and the 50 V caps.
- Duty cycle: D = 12 / 32 = 0.375-0.385.
- Inductor current: average = Iout / (1 - D) = 1.63 A at 1 A out. Ripple =
  20 V x 0.385 / (790 kHz x 15 uH) = 0.65 A, so the peak is 1.95 A.
- Limits: high side 2.6 A minimum, low side (valley) 1.8 A minimum. That allows about
  1.3 A out before current limit, so the rail is rated **1.0 A**.
- Right-half-plane zero at 1 A: 12 ohm x (0.615)^2 / (2 pi x 15 uH x 0.385) = about
  125 kHz. U4 is internally compensated. 5 x 22 uF plus the 100 uF electrolytic keeps
  the crossover low, but loop stability in the inverting setup is a bench item.
- Enable (as in S1): Q1 (MMBT3906, emitter on +12V, base 100k to GND) feeds R17 100k /
  R18 20k into EN_N, so EN = (V+12 - V-12) / 6. U4 starts when +12V passes about 8 V
  (EN 1.1-1.4 V), runs with EN at about 4 V (maximum VIN + 0.3 V), and stops as soon
  as +12V goes. -12V never runs alone.

**Output side** (unchanged from S1).

- J2 and J3 are hand-soldered 16-pin box headers, in parallel with the Doepfer pinout
  (1-2 -12V, 3-8 GND, 9-10 +12V, 11-12 +5V; CV/GATE open). Use both cables above
  about 1.5 A per rail.
- Each rail has a 100 uF / 35 V electrolytic, an SS34 clamp and a red LED.

**Front panel (S3, as `modules/usb-power`)**

- SW1 TL3340AF160QG (C2886925, Extended, Economy eligible; same part and footprint as
  usb-power SW1). Contacts 1 + 3 to EF_UV, contact 2 to GND, case floating. Pressed,
  it holds U5 EN/UVLO at 0 V: U5 shuts down, VIN and EN_P fall and all three rails go
  off. Released, EN/UVLO is back at 20 x 7.3 / 107.3 = 1.36 V (above the 1.2 V
  threshold), so U5 clears any fault, ramps VIN again and the rails start in order.
  Only works inside the 17.6-25.3 V window. Pressed current: 20 V / 100k = 0.2 mA
  (switch rated 50 mA / 12 V; the node sits at about 1.4 V).
- D8 red 3 mm THT LED (usb-power D10 footprint, leads formed 90 degrees, hand-soldered,
  no LCSC) from +5V through R22 1k: about 3 mA. Shows +5V present only. The three
  0603 rail LEDs D5-D7 stay on the board.

## Power budget

Per-rail design maximum: **+12V 2.5 A, +5V 2.5 A, -12V 1.0 A**. The charger limits
the total:

| Charger | Input | About this much out, all rails together |
|---|---|---|
| 45 W (20 V / 2.25 A) | 45 W | 39 W |
| 60 W (20 V / 3 A) | 60 W | 52 W |

These assume roughly 91 % (+12V), 86 % (+5V) and 84 % (-12V) efficiency. That is a
few points below S1 because of the higher frequencies and forced PWM. The numbers are
estimates, not measurements. Example: a case drawing +12V 1.5 A, -12V 0.8 A and
+5V 0.5 A uses 30.1 W out, about 35 W in.

## Not done / open

- **PCB:** not started. Keep the hot loops short: VIN caps to the IC pins, and for U4
  the VIN-to-(-12V) cap loop. Use a solid GND plane, make the -12V node under U4 a
  copper island, and give U2/U3 wide copper for heat. Footprints are pinned in
  `hardware/USBPOWER45.pretty`. The U5 RPW0010A land pattern is hand-made from the TI
  example board layout (4225183/A). Check it against the datasheet before ordering.
- **Not measured:** noise and ripple (no LDOs: expect switcher ripple of a few tens of
  mV p-p at the headers before module filtering), converter interaction, -12V loop
  stability, thermals (U2 first), start-up with real case loads, and EMI. None of it
  has been prototyped.
