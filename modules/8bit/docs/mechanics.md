# 8bit mechanics and 6HP fit (S6 placement, R1 routing)

**Verdict: the module fits 6HP with room to spare** on the nominal footprints and courtyards
(native DRC 0 at all severities on the routed carrier, 1 mm edge keep-out and 2 mm
hand-solder clearance met). It is not yet a 3D-checked fit: no interference run yet
(`research.md` §6). The printed FreeCAD panel (`panels/front-cad/`, 2.0 mm) is generated
but not test-printed.

Frame, origin and conventions are those of `modules/midi` (`geometry.json` `frame`):
panel origin at the upper-left corner seen from the front, X across, Y down, mm;
KiCad position = (100, 50) + panel XY on both boards. The carrier's F side faces the
panel, so the KiCad top view is the front view. All numbers come from
[`geometry.json`](geometry.json).

## Stack

| Item | Value |
|---|---|
| Panel | 6HP, 30.0 x 128.5 mm, FR4 1.6 mm (`panels/front-pcb/8bit-panel.kicad_pcb`). Rail holes Ø3.2 at (12.58, 3.0) and (12.58, 125.5), as `modules/12bit` |
| Carrier PCB | 29.0 x 110.0 x 1.6 mm, 2 layers, X 0.5..29.5, Y 9.25..119.25 (as `modules/12bit`) |
| Fixing | The four jack bushings and nuts (J1, J2, J3, J6). The pots are soldered only |
| Panel rear seat | Z 10.0 above carrier F.Cu (PJ301M-12 boss top, as `modules/midi`) |
| Pots | User RV09 stock (as `modules/audio-out`): no threaded bushing, no nut, body 6.8 mm (nominal), 1 mm collar, Ø6 knurled shaft to Z 22.8 = **11.2 mm past the FR4 front** for a push-on knob. Panel hole Ø7.2. 3D proxy `hardware/8BIT.3dshapes/RV09_proxy.step` (copied from audio-out) |
| LED | 3 mm THT, body bottom Z 6.3: dome flush with the FR4 front (as `modules/midi`) |
| Button | SW1 = 6 x 6 mm THT tact, 7 mm tall, on the carrier F side: body to Z 3.1, tapered stem (Ø3.4 at the body to Ø3.2 at the top, measured) to Z 7.0. One-piece printed cap through a Ø4.2 panel hole (below) |

## MODE button cap (`panels/button-actuator/`)

The stem top is 3.0 mm below the panel rear. One printed part bridges it, no glue, printed
socket-down without supports:

| Feature | Shape (carrier Z) |
|---|---|
| **Socket** | Ø3.4 blind hole Z 4.5..7.0, press-fit over the tapered stem (Ø3.33..3.2 in the grip zone, Ø3.3 nominal); the stem top bottoms in it (sets the height) |
| **Flange** | Ø7.0 Z 4.5..8.5: wider than the Ø4.2 hole, so it is captive behind the panel; 1.4 mm above the switch body, 1.5 mm below the panel rear |
| **Tip** | Ø3.6 Z 8.5..13.5 through the Ø4.2 panel hole |

- Assembly: solder SW1, press the cap onto the stem, fit the panel over the tip.
- Gaps (nominal): flange 1.5 mm behind the panel rear (the first cut had 0.3 mm: a
  tightened panel pressed the flange and held the switch on); tip 1.9 mm (FR4) / 1.5 mm
  (2.0 mm print) proud of the panel front. Switch travel is ~0.25 mm.
- The generator asserts these gaps, the captive flange, the socket grip (2.5 mm) and roof,
  the tip clearance and ≥1 mm from the flange to the LED, RV3 and J3 bodies. FDM holes
  print undersize: measure the bought stem and tune `socket_D` for a firm press fit.
  Not test-printed yet.

## Front (F): hand-soldered parts, two columns X 7.95 / X 22.05

User order, 2026-11-14: MIDI and CV on one line, the knobs spread over the middle, the
MODE (record) button and its LED on the row above the outputs, the outputs as low as the
1 mm edge keep-out allows.

| Row (panel Y) | Left, X 7.95 | Right, X 22.05 |
|---|---|---|
| 17.5 | J1 MIDI IN (PJ301M-12, TS) | J2 CV IN (PJ301M-12, tip normalled to GND) |
| 37.5 | RV1 P1 (50k) | |
| 57.5 | | RV2 P2 (50k) |
| 77.5 | RV3 P3 (50k, PB5) | (J4 power header behind, B side) |
| 97.5 | SW1 MODE (6x6 THT tact): pad 1 pair (BUTTON) Y95.25, pad 2 pair (GND) Y99.75, legs X4.70 / X11.20 | D1 MODE LED (3 mm) |
| 110.4 | J3 OUT (DAC) | J6 GATE |

- Rows on a 20 mm pitch (the jack-to-knob spacing of `modules/mcc`); neighbouring knobs
  are 24.5 mm apart centre to centre, so wide knobs fit. Pot pins sit 7.5 mm below each
  shaft, pin 1 on the left.
- The output row is as low as it goes: the J3/J6 courtyards end 1.02 mm above the bottom
  edge. The RV09 courtyards keep 1.015 mm to the side edges (RV1, the closest courtyard).
- Jacks at rotation 0: T pad 4.92 mm above the bushing centre, TN 3.38 mm and S 6.48 mm
  below it.

Panel labels (1.2 mm, above each control): `MIDI`, `CV`, `P1`, `P2`, `P3`, `MODE`,
`OUT`, `GATE`; title `8BIT` (2.5 mm) and `BIG MODULAR`. Holes: jack Ø6.2, pot Ø7.2,
LED Ø3.2, button Ø4.2.

**LFO panel** (`panels/front-pcb/8bit-lfo-panel.kicad_pcb`, `geometry.json` `lfo_panel`,
for `firmware/lfo`, no MIDI): the same holes without the J1 MIDI jack hole and the RV3
shaft hole; labels `RATE` (P1) and `WAVE` (P2) instead of `P1`/`P2`, no `MIDI` / `P3`,
`REC` instead of `MODE`, and `LFO` (2.5 mm) at the empty P3 spot. Build notes: **don't
fit J1 or RV3** (no panel holes; the MIDI input parts behind J1 can stay, the firmware
never enables the UART, and PB5 is not read). S6 needs **no wire bridge**: RV3 is only
an ADC knob now, the DAC reaches the output amplifier directly. GATE stays (the LFO
firmware drives PA7).

**4HP LFO panel for the old S5/R4 carrier** (user direction 2026-11-23;
`panels/front-pcb/8bit-lfo-4hp-panel.kicad_pcb`, `geometry.json` `lfo_4hp_panel`): 20.0 x
128.5 mm, the old 4HP hole contract (git `ec1ebe8^`, one control column at X10.0): MIDI
J1 Y17.5, CV J2 Y30.0, RATE RV1 Y43.5, WAVE RV2 Y58.5, REC SW1 (X7.0) + LED D1 (X15.5)
at Y87.0, OUT J3 Y100.0, rail holes X12.58. It replaces the old 4HP LFO panel (git
`ec1ebe8^`, no MIDI hole): the **J1 MIDI jack hole is kept**, so a board with J1 fitted
takes it; `firmware/lfo` still reads no MIDI. RV3 stays out (`LFO` at its spot): on the
4HP board the DAC runs through RV3's passive low-pass, so without RV3 **bridge RV3 pin 3
to its wiper pad (pin 2)** (as the knob fully CW).

## Back (B): SMD for JLC assembly, plus headers

Placed by hand, group by group with the routing (root `AGENTS.md`); the native PCB owns it.

| Band (panel Y) | Parts |
|---|---|
| 10..25, between J1 and J2 | MIDI front end in one column at X~13: R3, R1, D2, Q1, R2, JP1 (vertical, `P` at the top pad, `D` at the bottom pad) |
| 27..35, under J2 | CV input: R4, R13, D3 BAT54SW, C9, R14, U4 MCP6002 (SOIC-8), C15 |
| 38..44, right edge | J5 UPDI header (pin 1 UPDI on top, B silk `UPDI` / `GND`) and R5 |
| 46..52, right half | B silk `8BIT S6` and the JP1 legend `JP1 MIDI IN: P=PROTECTED D=DIRECT` |
| 69..77 | +5 V regulator: U2 HT7550-1, C4, C3, C5; D4 above the J4 +12 V pins |
| 79..91 | U1 ATtiny1616 at (17.8, 84.5) with C1, C2, the knob caps C10 / C11 / C12 and the gate pull-down R7; J4 2x5 power header at the right edge (pin 1 at (23.8, 90.5), -12 V at the bottom, B silk `-12V`) |
| 93..101 | D5, C6 (-12 V entry), R6 (LED), offset divider R10 / R11 / C14 |
| 103..117, between J3 and J6 | U3 TL074 at (15.0, 109.5), C7 / C8 at its supply pins, R9 / R8 below it; R12 (OUT, left edge strip) and R15 (GATE, right edge strip), both 1206 |

References are on the Fab layers (as `modules/midi`).

### Measured clearances (R1)

| Check | Closest |
|---|---|
| Courtyard to board edge (>= 1.0) | RV1 1.015 mm |
| SMD pad to pot/jack pad (>= 2.0) | C7.2 - J3 tip 2.245 mm |
| SMD pad to other THT pad | D5.2 - D1.2 1.10 mm (LED) |
| Via to SMD pad (never inside) | 0.20 mm (U3 pin 12) |
| Copper to edge | native DRC rule, 1.0 mm |

### Power header and 16-pin IDC cables

As `modules/12bit` (`geometry.json` `power_header`): J4 stands upright at the right edge
with pins 1/2 (-12 V) at the bottom (Y90.5) and 9/10 (+12 V) at the top (Y80.34). A
16-pin IDC socket's positions 11-16 overhang upward over the board, never past an edge
(envelope X20.67..29.47, Y68.91..94.31, 2.5 mm above B). No THT lead sits under it: the
RV2 pins end 3.0 mm above, the LED pads start 1.0 mm below. The SMD under it (D4, D5, C5, C1, C2 and
the ends of C3 / C4 / C6: 0805 / 0603 capacitors and SOD-123 diodes) is at most ~1.35 mm tall.

## Not yet verified

- 3D interference against the panel (pot proxy and button cap exist); test-print the panel
  (`panels/front-cad/`, generated, not printed).
- The jack STEP model is marked "Untested" upstream (as `modules/midi`); the pot model
  is a nominal proxy of the user's sample; SW1 uses the stock 7.3 mm model (the bought part is 7.0 mm).
- Cap test print, press fit and feel.
