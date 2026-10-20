# 8bit research and circuit intent (S5 schematic, R4 routed carrier)

Bread Modular `8bit` (an ATtiny1616 DAC synth voice on a breadboard module), moved
to a 4HP Eurorack module. The brief:

- Top: a MIDI input and a CV input. CV goes straight to an analog (ADC) pin, with
  protection. The MIDI input has protection that can be switched off, as in MIDI V2.
- Middle: three pots. Pot 3 is either a passive low-pass filter on the audio path
  or an analog input for the MCU, selected with solder jumpers on the back.
- Bottom: the audio output, taken from the DAC, moved to Eurorack level and protected.
- 4HP if possible (it is: `mechanics.md`).
- S2 (user, 2026-10-19): pots are the user's stock only, **50k and 1M** (RV09 as
  `modules/audio-out`); the MODE button is **the Bread Modular 8bit switch** with a
  printed two-part actuator; label the solder jumpers; start routing.
- S3 (user): pot 3 is the passive low-pass only (no ADC option, no jumpers); readable,
  wired schematic.
- S4 (user): buffer the CV with an op-amp at Eurorack input impedance, keep the MCU pin
  safe (MCP6001 on +5 V), and read the full bipolar CV range with headroom (±5.5 V).
- S5 (user, 2026-10-20): the MODE button is a **hand-soldered 6 x 6 mm THT tact
  switch, 7 mm tall** (AliExpress stock goes to 10 mm; 7 mm leaves room for a flange),
  with a one-piece printed cap. Footprint per the user's drawing: 4 pins, 6.5 x 4.5 mm.

Nothing here is bench-tested. Sourcing is a dated catalog observation, not an order.

## 1. Bread Modular 8bit baseline (read-only source)

Source: `~/data/projects/bread-modular/modules/8bit` (VERSION 1.2.1). Netlist exported
natively from `8bit.kicad_sch`; firmware in `code/{helloworld,drums,lfo,supersaw,crash}`.

| Function | Bread Modular 8bit | Firmware |
|---|---|---|
| MCU | ATtiny1616-M (VQFN-20) on `V_SUPPLY` (5 V from the breadboard rail) | 20 MHz |
| MIDI | Pin header `MIDI` straight to **PB3** (USART0 RX); TX on PB2 to the header (MIDI thru) | `Serial` on PB3, no inversion |
| Knobs | RV2/RV3 1M: CV1/CV2 header inputs (100k pull-up to V_SUPPLY) buffered by U3 MCP6002, pot as an attenuator, wiper to **PA1 / PA2** | `PIN_CV1 PA1`, `PIN_CV2 PA2` |
| Filter | **PA6** (DAC) -> RV1 50k (rheostat, pin 3 open) -> C2 100n (to V_MID) -> U1A MCP6002 follower -> R2 1k -> `AUDIO_OUT` (0..4.34 V, unipolar) | `VREF_DAC0REFSEL_4V34`, `DAC0.DATA` |
| Gate | **PA7** -> U1B follower -> R3 1k -> `GATE_OUT` | `GATE_PIN PA7` (output) |
| Mode | SW1 on **PA4** to GND (internal pull-up), LED D1 on **PA5** via 330R | `TOGGLE_PIN PA4`, `TOGGLE_LED PA5` |
| UPDI | PA0 via R1 4.7k | |
| Logger | | `LOGGER_PIN_TX PB4` (output) |

## 2. Decisions

| # | Decision | Why |
|---|---|---|
| E1 | Keep every BM 8bit pin: PA1/PA2 knobs, PA4 button, PA5 LED, PA6 DAC, PB3 RX, PA0 UPDI | BM firmware ports unchanged (apart from the MIDI inversion, E3) |
| E2 | New inputs on ADC0 pins no BM firmware touches: **CV in = PB0 (AIN11)**. PA7 (BM gate, driven as an output) and PB4 (BM logger TX) stay unconnected | A wiper or CV source on PA7/PB4 would fight BM firmware that drives those pins. S2 moved CV from PA3 to PB0: PB0 is on the QFN side facing the CV parts, so the fan-out routes without crossing POT2 |
| E3 | MIDI input = TS jack with the MIDI V2 NPN front end and its 3-pad solder jumper (JP1), **shipped open** | "Like MIDI v2": JP1 1-2 = protected (inverting, firmware `PORT_INVEN` on PB3), 2-3 = direct/unprotected (stock BM firmware). TS because the source is this repo's MIDI module (tip = logic-level MIDI, sleeve = GND) |
| E4 | CV in (S4, §3.2b): level shift R4 56k / R13 51k to +5V / R14 510k to GND, BAT54SW clamp, C9 1n, **U4 MCP6001 follower on +5V** into PB0. Jack tip normalled to GND | User: bipolar Eurorack CV (±5 V) with headroom, op-amp buffer, ~100k input impedance, MCU pin safe. ±5.5 V -> 0..5 V; unpatched = 0 V = mid-scale. A +5 V-only rail-to-rail buffer can't drive PB0 outside 0..5 V, so no clamp is needed after it (a ±12 V op-amp would need its own) |
| E5 | Pots 1 and 2: plain +5V..GND dividers into PA1/PA2, 10n at each pin. No CV attenuator, no op-amp buffer | The CV is a separate jack now (E4); BM's buffered attenuators are not needed |
| E6 | **P1/P2 50k, P3 1M** (linear RV09, user stock, as `modules/audio-out`: no bushing, 16 mm shaft, no nut). BM `Potentiometer_RV09` footprint | Only 50k and 1M exist (user). 50k dividers are the best ADC source (≤12.5k). P3 is the filter rheostat, so it takes the 1M: with **R7 10k** and **C13 1n** the range is 158 Hz..15.9 kHz (the same 1:100 span as BM's 50k/100n) and the DAC never sees less than 10k |
| E7 | Pot 3 is **only the passive low-pass** (§3.3), no jumpers, no ADC | User decision (S3): keep it simple, as BM. S2's F/A jumper bank (JP2-JP5) and PB5 input were removed |
| E8 | Output: TL072 on ±12 V, U3A non-inverting gain 2.2 with an offset from U3B (buffered 3.98 V): 0..4.34 V -> ±4.8 V. DC coupled. 1k series | Eurorack audio level (~10 Vpp), polarity kept and DC coupling so the BM LFO firmware still works. The high-impedance + input leaves the passive filter unloaded |
| E9 | ±12 V each through a B5819W series Schottky (reverse protection); +5V from +12V_F through an HT7550-1 (no dropper) | ~15 mA on +5V: ~0.1 W in the SOT-89. The MIDI module's dropper R20 was for 77 mA |
| E10 | No +5V shunt clamp (MIDI V2 U2/CJ431 not carried over) | Clamp current into +5V is ≤0.2 mA (CV 0.12 mA at +12 V + R3 0.07 mA), far below the MCU's own load, so it cannot pump the rail |
| E11 | MODE button = **generic 6 x 6 x 7 mm THT tact switch** (stock KiCad `SW_PUSH_6mm_H7.3mm`, pins 6.5 x 4.5 mm) on the carrier F side at the BM SW1 net (PA4 to GND), hand-soldered, pressed through the panel by a **one-piece printed cap** (`mechanics.md`). Mode LED 3 mm THT | User (S5, replaces S2's BM K2-1808SN SMD switch + two-part glued actuator): a hand-solderable switch the user can buy. All BM 8bit firmwares use PA4/PA5. 7 mm (not 10 mm) leaves 3 mm under the panel for the cap's captive flange and press-fit socket |
| E12 | Drop BM's gate output (PA7) and MIDI thru (PB2) | Not in the brief; 4HP space |

## 3. Circuit (S1, `hardware/8bit.kicad_sch`, ERC 0)

### 3.1 Power

```
J4 pin 9/10 +12V -> D4 B5819W -> +12V_F -> U3 V+ (C7 100n), C5 10u, U2 HT7550-1 (C4 1u in)
                                          U2 -> +5V (C3 10u out, C2 10u at the MCU, C1 100n)
J4 pin 1/2  -12V <- D5 B5819W <- -12V_F <- U3 V- (C8 100n), C6 10u
```

PWR_FLAGs: `#FLG01` GND (Eurorack entry), `#FLG02` +12V_F and `#FLG03` -12V_F (fed
only through D4/D5, which ERC can't see through). No other flags.

Load estimate: +12 V ~20 mA (MCU ~10 mA, LED ~3 mA, TL072 ~3 mA, dividers), -12 V ~3 mA.

### 3.2 MIDI input (MIDI V2 front end, TS)

```
J1 tip MIDI_IN --+-- R3 100k -- +5V            (idle pull-up)
                 +-- R1 10k -- Q1_B -- Q1 MMBT3904 (E = GND), D2 1N4148W clamp B-E
                 |                       C = RX_Q -- R2 22k -- +5V
                 +------------------------------------------- JP1 pin 3
JP1: pin 1 = RX_Q, pin 2 = RX (PB3), pin 3 = MIDI_IN.  B silk P (pin 1) / D (pin 3).
```

- **JP1 1-2 (P, protected):** Q1 drives PB3. Inverting, so the firmware sets
  `PORT_INVEN` on PB3 (`PORTB.PIN3CTRL |= PORT_INVEN_bm`). Takes 3.3 V and 5 V senders;
  a ±12 V CV/gate cable survives indefinitely (MIDI `docs/research.md` §7.2).
- **JP1 2-3 (D, direct):** MIDI_IN straight to PB3, unprotected, stock BM firmware
  (no inversion). As MIDI V2, R2 sits on RX_Q so PB3 sees only MIDI_IN.
- **Open (as shipped):** PB3 floats; bridge one pair before use. Never both.

### 3.2b CV input (S4: bipolar, buffered)

```
J2 tip CV_IN -- R4 56k --+-- CV_BUF -- U4 MCP6001 + (follower, +5V/GND) -- CV_ADC -- PB0
                         +-- R13 51k -- +5V
                         +-- R14 510k -- GND
                         +-- D3 BAT54SW clamp to GND / +5V,  C9 1n to GND
V(CV_BUF) = 0.4529 x Vin + 2.487 V   (Thevenin 25.4k)
```

- **Range:** -5.49 V -> 0 V, 0 V -> 2.49 V (ADC ~509), +5.55 V -> 5 V. The ±0.5 V of
  headroom over ±5 V keeps the MCP6001 output (rail-to-rail, within ~25 mV of the rails)
  out of its clipping band. The small asymmetry (0.05 V) comes from E24 values: 56k and
  51k are Basic; 510k sets the midpoint (the ideal is 571k; 560k is only Preferred
  Extended).
- **Input impedance:** R4 + R13||R14 = 56k + 46.4k = **102k**, the usual Eurorack value.
- **Reference:** the offset comes from +5V, which is also the ADC reference
  (VDD), so +5V tolerance cancels in the reading.
- **Protection:** a ±12 V mis-patch would pull CV_BUF to +7.9 / -3.0 V; D3 holds it at
  -0.3..+5.3 V with ≤0.21 mA through R4. U4 runs from +5V only, so PB0 can never see more
  than the rail, even at power-up.
- **Filter:** C9 with the 25.4k Thevenin: 6.3 kHz. The follower drives the ADC sample
  capacitor from a low impedance.
- **Unpatched:** the TN switch grounds the tip: 0 V CV, mid-scale.

### 3.3 Pot 3: passive low-pass (as Bread Modular)

```
PA6 DAC -- R7 10k -- DAC_R -- RV3 pin 3 ... RV3 wiper -- FILT -- C13 1n -- GND
RV3 pin 1 open (rheostat, as BM);  FILT -> U3A + input (high-Z, filter unloaded)
```

- **CW = brighter**: 158 Hz (R7 + 1M) .. 15.9 kHz (R7 only).
- S3 dropped the S2 ADC option and its jumpers (JP2-JP5, C12, PB5): knob 3 is the
  filter only, as the user asked. PB5 is spare.
- The rheostat law is linear in R, so most of the sweep sits at the low end (as BM's
  50k/100n); C13 is X7R (no Basic 1 nF C0G found), its voltage coefficient over 0..4.3 V
  is a small cutoff shift.
- R7 keeps the DAC away from a bare capacitor (BM drives 100 nF straight from PA6) and is
  the minimum DAC load (1n at 15.9 kHz is ~10k more).

### 3.4 Output stage

```
FILT --> U3A + ;  U3A - = OUT_FB;  R9 12k OUT_FB->AMP_OUT;  R8 10k OUT_FB->VOFF
+5V -- R10 10k -- VREF_DIV -- R11 39k -- GND, C14 10u;  U3B follower -> VOFF (3.98 V)
AMP_OUT -- R12 1k (1206) -- J3 tip
Vout = 2.2 x FILT - 1.2 x VOFF:  0 V -> -4.78 V, 2.17 V -> 0 V, 4.34 V -> +4.77 V
```

- The offset comes from +5V (HT7550-1 ±2 %), so the output offset error is about
  ±0.1 V. The DAC reference is the internal 4.34 V. C14 filters +5V noise off VOFF (2 Hz).
- Protection: R12 1k limits short/mis-patch current; the TL072 is short-circuit
  limited. A Eurorack source can't exceed ±12 V, which is only one Schottky drop
  outside the op-amp rails. A ±12 V source against a ±4.8 V output puts ≤16.8 V / 0.28 W in R12,
  so R12 is a 0.5 W 1206 (ROHM ESR18EZPF1001, C2074262, 56 % in that fault) and a
  permanent mis-patch is within rating.

### 3.5 MCU, knobs, button, LED

| U1 pin | Port | Net | Use |
|---|---|---|---|
| 20 | PA1 | POT1 | Knob 1 50k (BM `PIN_CV1`), C10 10n |
| 1 | PA2 | POT2 | Knob 2 50k (BM `PIN_CV2`), C11 10n |
| 14 | PB0 | CV_ADC | CV in via U4 (§3.2b) |
| 5 | PA4 | BUTTON | SW1 (6x6 THT tact) to GND, internal pull-up (BM `TOGGLE_PIN`) |
| 6 | PA5 | LED_DRV | R6 1k -> D1 (BM `TOGGLE_LED`) |
| 7 | PA6 | DAC | Audio (R7) |
| 9 | PB5 | - | Spare (unconnected) |
| 11 | PB3 | RX | MIDI (JP1) |
| 19 | PA0 | UPDI_PA0 | R5 4.7k -> J5 UPDI header (pin 1 UPDI, pin 2 GND) |
| 2, 8, 10, 12, 13, 15-18 | PA3, PA7, PB4, PB2, PB1, PC0-PC3 | - | No connect |

## 4. Firmware notes (not part of this hardware task)

- Protected MIDI (JP1 P): add `PORTB.PIN3CTRL |= PORT_INVEN_bm;` after `Serial.begin`.
- CV: `analogRead(PIN_PB0)` reads 0..1023 for -5.5..+5.5 V; 0 V ≈ 509. Bipolar value:
  `analogRead(PIN_PB0) - 509` (≈ 10.8 mV of CV per count). Calibrate the zero per unit
  if it matters (resistor tolerance, ±1 %).
- The DAC must stay at `VREF_DAC0REFSEL_4V34` for the ±4.8 V output scaling.
- BM firmware that drives PA7 (gate) or PB4 (logger) still runs; those pins are open.

## 5. Sourcing (live, 2026-10-19)

Every assembled part has `LCSC`/`MPN`/`Manufacturer` in the schematic
(`SOURCING` in `tools/build_schematic.py`). The live strict lookups are recorded in
`sourcing-candidates.json`. All resistors and capacitors are JLCPCB **Basic** and
Economy-eligible except R12 (ROHM ESR18EZPF1001 C2074262, 0.5 W 1206, Extended by request:
no Basic 0.5 W 1k 1206 was found, and the 0.25 W C4410 fails the mis-patch case); TL072CDT (C6961), B5819W, MMBT3904 and 1N4148W are Basic too. Extended:
ATtiny1616-MNR (C507118), BAT54SWT1G (C78260) and HT7550-1 (C16106, preferred
Extended), the same parts MIDI V2 uses, plus the CV buffer MCP6001T-E/OT (C29429,
Extended). The S4 level-shift resistors are Basic: 56k C23206, 51k C23196, 510k C23192. C13 1 nF is C1588 (Basic, X7R). THT jacks,
pots, LED, switch and headers are hand-soldered and carry no LCSC field. SW1 is a generic
6 x 6 x 7 mm THT tact switch bought by the user (no catalog lookup recorded). The per-part
human review gates are open.

### 3.6 Routing (R4, `tools/route_plan.py`)

2 layers, everything explicit (no autorouter), through the shared plan/apply/promote.

- **F.Cu** carries the long trunks: +5V (LDO via -> left edge X1.4 -> top -> D3/R2/R3 and
  the middle trunk through the pot pin-3 pads RV1 -> RV2),
  UPDI (X1.95 to R5), POT1/POT2 to their wipers, MIDI_IN to JP1, ±12V_F from the power
  entry to U3, FILT to U3, BUTTON and LED_A to SW1 (pad-1 pair linked along Y89.25) and the LED.
- **B.Cu** carries the SMD wiring, the U1 fan-out (0.2 mm), RX (left edge), DAC /
  LED_DRV / BUTTON (right edge), R7 -> RV3 pin 3 and the wiper to the FILT via, and U3.
  U3 is mirrored on B (pins 1-4 on the right): OUT_FB crosses under its body between
  pins 8 and 7 to R8.
- **CV buffer (R3):** U4/R13/R14/C15 sit on B below the RV1 tabs. CV_BUF (F X6.95) runs
  down from C9 and CV_ADC (F X7.65) back up to U1 pin 14, below the F UPDI lane at
  Y35.3. U4's follower feedback runs under its body between the pad columns; +5V comes
  from the RV1 pin 3 pad; U4's GND pin has its own via.
- **SW1 area (R4):** the THT legs come through to B, so the offset divider R10/R11/C14
  moved from under SW1 to the left edge below the RV3 tab (+5V via on the F lane at
  Y76.4, UPDI jogs around it); VREF_DIV runs down B X1.5 past SW1 to U3 pin 5. The RV3
  wiper runs on B between the SW1 pin columns to the FILT via at (7.0, 90.5).
- GND pours on both layers, thermal reliefs (as audio-out R4), 13 stitching vias plus
  the U1 exposed-pad via (as MIDI) and a cathode via for the LED.
- Widths: 0.2 QFN, 0.25 signal, 0.3 +5V, 0.4 ±12V_F, 0.5 at the header. Vias 0.6/0.3.
- The shared tool here was synced to `main` for the thermal-relief zone option
  (`opt/kicad-tools/automation`, 5 files byte-identical to `main`; its tests pass,
  including the native integration set).

## 6. Open items

- **Export and audit**: done 2026-10-19 (`jlcpcb/README.md`). Remaining: the human
  land-pattern/pin-mapping/ratings reviews in `docs/jlcpcb-audit-requirements.json`, the
  JLCPCB placement preview and a live recheck before ordering.
- **Button cap**: measure the bought switch (stem Ø and top height, nominal Ø3.5 at
  Z7.0), tune `socket_D` for the press fit, then print and test-fit (`mechanics.md`).
- **Pots**: the RV09 model is audio-out's nominal user-sample proxy; measure shaft tip to
  PCB seat on a real pot before ordering panels. 3D fit check and printed panel not
  done yet.
- Bench: MIDI front end with this firmware (P and D), CV range/zero and clamp, filter sweep with the
  1M pot, output level/offset, TL072 behaviour with the DAC's step output.
