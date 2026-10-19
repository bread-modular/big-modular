# 8bit mechanics and 4HP fit (S4 placement, R3 routing)

**Verdict: the module fits 4HP** on the nominal footprints and courtyards (native DRC 0
at all severities on the routed carrier). It is not yet a 3D-checked fit: no
interference run and no printed (FreeCAD) panel yet (`research.md` §6).

Frame, origin and conventions are those of `modules/midi` (`geometry.json` `frame`):
panel origin at the upper-left corner seen from the front, X across, Y down, mm;
KiCad position = (100, 50) + panel XY on both boards. The carrier's F side faces the
panel, so the KiCad top view is the front view. All numbers come from
[`geometry.json`](geometry.json).

## Stack

| Item | Value |
|---|---|
| Panel | 4HP, 20.0 x 128.5 mm, FR4 1.6 mm (`panels/front-pcb/8bit-panel.kicad_pcb`). Rail holes Ø3.2 at (7.5, 3.0) and (7.5, 125.5) |
| Carrier PCB | 19.0 x 110.0 x 1.6 mm, 2 layers, X 0.5..19.5, Y 9.25..119.25 (as `modules/midi`) |
| Fixing | The three jack bushings and nuts (J1, J2, J3). The pots are soldered only |
| Panel rear seat | Z 10.0 above carrier F.Cu (PJ301M-12 boss top, as `modules/midi`) |
| Pots | User RV09 stock (as `modules/audio-out`): no threaded bushing, no nut, body 6.8 mm (nominal), 1 mm collar, Ø6 knurled shaft to Z 22.8 = **11.2 mm past the FR4 front** for a push-on knob. Panel hole Ø7.2. 3D proxy `hardware/8BIT.3dshapes/RV09_proxy.step` (copied from audio-out) |
| LED | 3 mm THT, body bottom Z 6.3: dome flush with the FR4 front (as `modules/midi`) |
| Button | SW1 = BM K2-1808SN-A4SW-01 SMD tact on the carrier F side, top Z 2.5. Two-part printed actuator through a Ø4.2 panel hole (below) |

## MODE button actuator (`panels/button-actuator/`)

The switch top is 7.5 mm below the panel rear, so a printed extender presses it. It is
two parts, glued through the panel hole, so it is captive and prints without supports:

| Part | Shape (carrier Z) | Print |
|---|---|---|
| **Plunger** (behind the panel) | Ø2.4 foot Z 2.5..4.5 resting on the switch button; Ø7.0 body Z 4.5..9.7 (wider than the hole, so it can't leave through the front); Ø3.9 blind socket from the top, 3 mm deep | Socket face down (foot up) |
| **Cap** (in front) | Ø3.6 stem Z 6.7..13.0 through the Ø4.2 hole; Ø8.0 finger cap Z 13.0..15.5, 0.4 mm top chamfer | Cap face down (stem up) |

- Assembly: put the plunger on SW1, mount the panel, push the cap stem through the hole
  into the socket until it bottoms, and glue it (a drop of CA glue in the socket).
  Bottoming the stem sets the length, so no shimming is needed.
- Gaps (nominal): plunger 0.3 mm behind the panel rear; cap 1.4 mm (FR4) / 1.0 mm
  (2.0 mm print) proud of the panel front. Switch travel is ~0.25 mm, so pressing the cap
  reaches the switch long before the cap hits the panel.
- The generator asserts these gaps, both captive diameters, the stem/hole/socket
  clearances, the foot on the 4.2 x 3.25 mm switch top, and ≥1 mm from the plunger to
  the LED, RV3 and J3 bodies. FDM holes print undersize: ream the socket (Ø3.9) and the
  panel hole (Ø4.2) if the stem binds.
- Common practice for SMD tact switches behind a panel is a printed button extender:
  a flanged plunger held by the panel, with a separate cap (glue or press fit). The
  flange-plus-cap pair here is that pattern. Not test-printed yet.

## Front (F): hand-soldered parts, one column at X 10.0

| Part | Panel XY | Notes |
|---|---|---|
| J1 MIDI IN (PJ301M-12, TS) | (10.0, 17.5) | rotated 270° as `modules/midi` (S pad toward the left edge) |
| J2 CV IN (PJ301M-12) | (10.0, 30.0) | tip normalled to GND (TN) |
| RV1 / RV2 (50k) / RV3 (1M) | shafts (10.0, 43.5 / 58.5 / 73.5) | 15 mm pitch; pins 7.5 mm below each shaft, pin 1 on the left. Knobs up to ~11 mm |
| SW1 MODE (SMD, F side) | (7.0, 87.0) | rotated 180°: pad 1 (BUTTON) on the lower row |
| D1 MODE LED (3 mm) | (15.5, 87.0) | |
| J3 OUT (PJ301M-12) | (10.0, 100.0) | |

Panel labels (1.2 mm, above each control): `MIDI`, `CV`, `P1`, `P2`, `P3`, `MODE`,
`OUT`; title `8BIT` (2.5 mm) and `BIG MODULAR`. Holes: jack Ø6.2, pot Ø7.2, LED Ø3.2,
button Ø4.2.

## Back (B): SMD for JLC assembly, plus headers

| Band | Parts |
|---|---|
| Top edge | B silk `8BIT S4` and the JP1 legend `JP1 MIDI IN: P=PROTECTED D=DIRECT` |
| J1/J2 | MIDI front end: JP1 at the left edge (`P` / `D`), R2, Q1, R1, R3, D2 |
| J2 row / J2-RV1 | R4 between the J2 TN and T pads; C9, D3 BAT54SW; U1 ATtiny1616 at (10.0, 38.3), C1 (right), GND via in the exposed pad |
| Below the RV1 tabs (Y45.5-49.8) | CV buffer: R14 (5.6, 48.4), U4 MCP6001 (10.6, 47.6), R13 (13.4, 47.3), C15 (14.9, 47.3) |
| RV1/RV2, RV2/RV3 | C2 (+5V bulk) and C10 under RV1; C11 above RV2 |
| Under RV3 | R7 (DAC series, to RV3 pin 3); the wiper runs down to the FILT via. Left: R10/R11/C14 offset divider. Right: R6 |
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

- 3D interference against the panel (pot proxy and actuator now exist), printed panel.
- The jack STEP model is marked "Untested" upstream (as `modules/midi`); the pot model
  is a nominal proxy of the user's sample; SW1 has no 3D model.
- Actuator test print and feel.
