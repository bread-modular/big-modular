# Audio Out mechanics and 4HP fit (P4 placement, R4 routing)

**Verdict: the module fits 4HP.** The verdict is nominal, from models: no physical
jack, pot or printed-panel trial has been done, and the pot model follows the
user's sample with a nominal body height.

Frame: as `modules/midi`. Panel origin at the upper-left corner seen from the
front, X across, Y down, mm. KiCad position = (100, 50) + panel XY on both
boards. The carrier's F side faces the panel. All numbers come from
[`geometry.json`](geometry.json). The nominal 3D check is in
[`fit/fit-report.json`](fit/fit-report.json), from `tools/fit_assembly.sh`.

## Stack

| Item | Value |
|---|---|
| Panel | 4HP, 20.0 x 128.5 mm. FR4 1.6 mm (`panels/front-pcb`) or printed 2.0 mm (`panels/front-cad`) |
| Rail holes | Ø3.2 at (12.58, 3.0) and (12.58, 125.5) (Doepfer X7.5 moved 1HP right), as midi |
| Carrier PCB | 19.0 x 110.0 x 1.6 mm, 2 layers, X 0.5..19.5, Y 9.25..119.25 |
| Fixing | The carrier hangs on the four jack bushings and nuts, as midi. The pots are soldered only |
| Panel rear seat | Z 10.0 above carrier F.Cu (top of the jack boss) |
| Jack thread past panel front | PJ301M-12: 2.90 mm (FR4) / 2.50 mm (print). PJ366ST: 4.36 / 3.96 mm |
| Pot (user sample, body nominal) | RV09 with no threaded bushing: body 6.8 mm (nominal), 1 mm collar, Ø6 knurled shaft 16 mm above the body to Z 22.8: **11.2 mm** of shaft past the FR4 front (10.8 mm print) for a push-on knob. No pot nut |
| Depth behind panel rear | 20.2 mm to the J5 pin tips; add ~8 mm for the IDC plug and cable bend |
| Interference | 0.0 mm³ for J1-J4 and RV1/RV2 against both panel variants (nominal models) |

## Front (F): hand-soldered THT

| Ref | Part | Position | Panel hole |
|---|---|---|---|
| J1 | PJ301M-12, IN L | (10.0, 19.5) | Ø6.2 |
| J2 | PJ301M-12, IN R (TN normalled to IN L) | (10.0, 33.0) | Ø6.2 |
| J3 | PJ366ST, LINE (T = L, R = R) | (10.0, 46.5) | Ø6.2 |
| RV1 | RV09 50k, VOL L | shaft (10.0, 62.5) | Ø7.2 |
| RV2 | RV09 50k, VOL R | shaft (10.0, 81.5) | Ø7.2 |
| J4 | PJ366ST, PHONES (T = L, R = R) | (10.0, 96.0) | Ø6.2 |

- Jacks are rotated 270° as midi (S pad toward the left edge). Pots sit at
  rotation 0 with their pins 7.5 mm below the shaft.
- Jack pitch is 13.5 mm. Pot pitch is 19 mm (knobs up to ~15 mm). PHONES is
  14.5 mm below VOL R, as high as the RV2 courtyard allows (J4 courtyard
  Y90.71, RV2 Y90.69). That leaves room for a 10-pin socket on J5 below it.
- Panel labels: `AUDIO OUT`, `IN` with `L`/`R` beside the input jacks, `LINE`,
  `VOL L` above the first knob, `VOL R` between the knobs, `PHONES` above its
  jack, `BIG MODULAR`.

## Back (B): SMD for JLC assembly, plus headers

| Band | Parts |
|---|---|
| Top edge / IN L | B silk `AUDIO OUT V1.0`; L input row: R1 1k, C1 1u, R3 47k, R5 56k |
| IN L / IN R | U1 OPA1678, C5/C6 100n |
| IN R / LINE | R input row: R2, C2, R4, R6; R7/R8 100R line build-out above the LINE pads |
| Between the pots (under the RV2 body) | U2 MC33178, C7/C8 100n, C9/C10 10u, R9/R10 15k taper loads, R11/R12 10R headphone build-out |
| Bottom | **J5** unshrouded 2x5 pin header (10-pin cable), vertical, pin 1 (-12 V) at the bottom (8.73, 113.7), B silk `-12V`; D1 + C3 (+12 V) standing vertically left of the header, D2 + C4 (-12 V) right of it |

### Power header: unshrouded 2x5 pin header, 10-pin cable

J5 is a plain 2x5 2.54 mm pin header with no box (the user's part; KiCad
`PinHeader_2x05_P2.54mm_Vertical`), centred: columns X8.73/X11.27, rows Y103.54
(pins 9/10, +12 V) to Y113.7 (pins 1/2, -12 V). Its pads are the same as the
earlier keyed box header's, so the copper is unchanged.

Nothing keys the cable: fit a 10-pin IDC socket with the red stripe (-12 V) at
the bottom, next to the B silk `-12V`. The 10-pin socket envelope is
X6.2..13.8, Y99.73..117.51 (as midi: 3.81 mm past the end pin centres). Its
bottom stays on the board (Y119.25) and inside the rail gap (Y120.5); its top is
2.4 mm below the J4 B-side pads (Y97.3). `tools/build_layout.py` asserts both,
and that no other pad sits under it.

Use a 10-to-16 cable on a 16-pin bus. A 16-pin socket aligned at pin 1 would
reach Y92.1 and sit over the PHONES (J4) leads; the board is not changed for it
(user, 2026-10-19).

## Assembly notes

1. JLC assembles the B-side SMD. Hand-solder J5, the pots and the jacks.
2. Mount the panel on the jack nuts before soldering the jacks and pots, so the
   jack bushings and pot shafts line up with the holes.
3. Clip jack and pot leads on B to ≤1.5 mm. They share the back with SMD parts.
4. J5 has no key: plug the 10-pin cable with its red stripe at the bottom,
   next to the B silk `-12V`.

## Not yet verified

- The pot model (`tools/make_pot_model.py`) uses the user's sample (no bushing,
  16 mm shaft above the body) with a nominal 6.8 mm body. Measure shaft tip to
  PCB seat on a real pot before ordering panels.
- The jack STEP models are marked "Untested" upstream (as midi).
- The printed panel holes are nominal; drill or ream to Ø6.2 / Ø7.2 / Ø3.2.
