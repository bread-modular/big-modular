# 8bit mechanics and 4HP fit (S5 placement, R4 routing)

**Verdict: the module fits 4HP** on the nominal footprints and courtyards (native DRC 0
at all severities on the routed carrier). It is not yet a 3D-checked fit: no
interference run yet (`research.md` §6). The printed FreeCAD panel (`panels/front-cad/`,
2.0 mm) is generated but not test-printed.

Frame, origin and conventions are those of `modules/midi` (`geometry.json` `frame`):
panel origin at the upper-left corner seen from the front, X across, Y down, mm;
KiCad position = (100, 50) + panel XY on both boards. The carrier's F side faces the
panel, so the KiCad top view is the front view. All numbers come from
[`geometry.json`](geometry.json).

## Stack

| Item | Value |
|---|---|
| Panel | 4HP, 20.0 x 128.5 mm, FR4 1.6 mm (`panels/front-pcb/8bit-panel.kicad_pcb`). Rail holes Ø3.2 at (12.58, 3.0) and (12.58, 125.5) (Doepfer X7.5 moved 1HP right, as midi) |
| Carrier PCB | 19.0 x 110.0 x 1.6 mm, 2 layers, X 0.5..19.5, Y 9.25..119.25 (as `modules/midi`) |
| Fixing | The three jack bushings and nuts (J1, J2, J3). The pots are soldered only |
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

## Front (F): hand-soldered parts, one column at X 10.0

| Part | Panel XY | Notes |
|---|---|---|
| J1 MIDI IN (PJ301M-12, TS) | (10.0, 17.5) | rotated 270° as `modules/midi` (S pad toward the left edge) |
| J2 CV IN (PJ301M-12) | (10.0, 30.0) | tip normalled to GND (TN) |
| RV1 / RV2 (50k) / RV3 (1M) | shafts (10.0, 43.5 / 58.5 / 73.5) | 15 mm pitch; pins 7.5 mm below each shaft, pin 1 on the left. Knobs up to ~11 mm |
| SW1 MODE (6x6 THT tact) | (7.0, 87.0) | stock `SW_PUSH_6mm_H7.3mm`, rotated 180°: pad 1 pair (BUTTON) on the lower row Y89.25, pad 2 pair (GND) Y84.75; legs X 3.75 / 10.25 |
| D1 MODE LED (3 mm) | (15.5, 87.0) | |
| J3 OUT (PJ301M-12) | (10.0, 100.0) | |

Panel labels (1.2 mm, above each control): `MIDI`, `CV`, `P1`, `P2`, `P3`, `MODE`,
`OUT`; title `8BIT` (2.5 mm) and `BIG MODULAR`. Holes: jack Ø6.2, pot Ø7.2, LED Ø3.2,
button Ø4.2.

## Back (B): SMD for JLC assembly, plus headers

| Band | Parts |
|---|---|
| Top edge | B silk `8BIT S5` and the JP1 legend `JP1 MIDI IN: P=PROTECTED D=DIRECT` |
| J1/J2 | MIDI front end: JP1 at the left edge (`P` / `D`), R2, Q1, R1, R3, D2 |
| J2 row / J2-RV1 | R4 between the J2 TN and T pads; C9, D3 BAT54SW; U1 ATtiny1616 at (10.0, 38.3), C1 (right), GND via in the exposed pad |
| Below the RV1 tabs (Y45.5-49.8) | CV buffer: R14 (5.6, 48.4), U4 MCP6001 (10.6, 47.6), R13 (13.4, 47.3), C15 (14.9, 47.3) |
| RV1/RV2, RV2/RV3 | C2 (+5V bulk) and C10 under RV1; C11 above RV2 |
| Under RV3 | Left edge below the RV3 tab: R10/R11/C14 offset divider. R7 (DAC series, to RV3 pin 3); the wiper runs between the SW1 legs to the FILT via. Right: R6 |
| U3 (Y 91.8..97.2) | U3 TL072 at (10.0, 94.5), mirrored (pins 1-4 on the right): R9, C13 right; C7, R8 left; C8 below; R12 1206 at the right edge |
| Bottom zone (Y 104..119) | As `modules/midi`: J4 2x5 Eurorack power (pin 1 -12 V at the bottom, B silk `-12V`), R5 + J5 UPDI on the left (B silk `UPDI`), D4 + U2 HT7550-1 + C3/C4 right of J4, C5/C6 at the right edge, D5 at the bottom edge (-12V_F pad toward C6) |

References are on the Fab layers (as `modules/midi`).

### Power header and 16-pin IDC cables

Identical to `modules/midi` (`geometry.json` `power_header`): J4 is vertical with pin 1
at the bottom, so a 16-pin IDC socket's positions 11-16 overhang upward over the board
(envelope X4.8..12.4, Y94.4..119.8, 2.5 mm above B, drawn on `Dwgs.User`). It covers
the lower half of U3 (SOIC-8, 1.75 mm tall) and C8, below the 2.5 mm socket floor.
Keep the J3 jack leads clipped to ≤1.5 mm.

## Not yet verified

- 3D interference against the panel (pot proxy and button cap exist); test-print the panel
  (`panels/front-cad/`, generated, not printed).
- The jack STEP model is marked "Untested" upstream (as `modules/midi`); the pot model
  is a nominal proxy of the user's sample; SW1 uses the stock 7.3 mm model (the bought part is 7.0 mm).
- Cap test print, press fit and feel.
