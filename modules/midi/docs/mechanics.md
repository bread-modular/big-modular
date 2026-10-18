# MIDI mechanics and 4HP fit (S2 placement)

**Verdict: the module fits 4HP**, so 6HP is not needed. The verdict is nominal,
from models: no physical jack, LED or printed-panel trial has been done.

Frame: panel origin at the upper-left corner seen from the front, X across, Y
down, mm. KiCad position = (100, 50) + panel XY on both boards. The carrier's F
side faces the panel, so the KiCad top view *is* the front view. All numbers come
from [`geometry.json`](geometry.json). The nominal 3D check is in
[`fit/fit-report.json`](fit/fit-report.json), produced by `tools/fit_assembly.sh`.

## Stack

| Item | Value |
|---|---|
| Panel | 4HP, 20.0 x 128.5 mm. FR4 1.6 mm (`panels/front-pcb`) or printed 2.0 mm (`panels/front-cad`) |
| Rail holes | Ø3.2 at (7.5, 3.0) and (7.5, 125.5): the Doepfer 4HP single pair (`HOLE_X0` in `case/tools/build_case.py`) |
| Carrier PCB | 19.0 x 110.0 x 1.6 mm, 2 layers, X 0.5..19.5, Y 9.25..119.25, parallel to the panel |
| Rail clearance | Skiff clear gap Y 8.0..120.5 (112.5 mm). The PCB keeps 1.25 mm per side (110 mm is the usual parallel-PCB maximum); the 16-pin IDC socket envelope also stays inside the gap |
| Fixing | The carrier hangs on the nine jack bushings and nuts. No brackets or standoffs |
| Panel rear seat | Z 10.0 above carrier F.Cu (top of the jack boss in both STEP models) |
| Jack thread past panel front | PJ301M-12: 2.90 mm (FR4) / 2.50 mm (print). PJ366ST: 4.36 / 3.96 mm. A 2.0 mm nut fits in every case |
| LED | 3 mm THT; body bottom Z 6.3, dome flush with the FR4 front (-0.005 mm) and 0.4 mm recessed in the print |
| Depth behind panel rear | 20.2 mm to the J10 header pin tips; add ~8 mm for the IDC plug and cable bend. JP1 (with shunt) and J11 are shorter than J10 |
| Interference | 0.0 mm³ for J1-J9 and D1-D8 against both panel variants (nominal models) |

## Front (F) layout: hand-soldered THT

| Column | X | Content |
|---|---|---|
| Jacks | 8.6 | J1 PJ366ST TRS at Y15.0. J2-J9 PJ301M-12 at Y26.5 + 10.5·k (J9 at Y100.0). Rotated 270° so T/TN/S run along X with S toward the left edge. Bodies are 9.0 mm along Y |
| LEDs | 17.2 | D1-D8 at the same Y as J2-J9, with pads vertical (K = pad 1, toward the bottom) |

- The jack envelope across X is 13.5 mm: the body runs X 4.1..14.6 and the S pad
  reaches X 1.07. The LED flange (Ø3.8) spans X 15.3..19.1, leaving 0.4 mm to
  the PCB edge at X 19.5.
- **Jack pitch is 10.5 mm**: 1.5 mm between jack bodies and nuts. This is dense
  but in the normal 4HP range; slim patch-cable plugs are recommended. The 11.5 mm
  IN→OUT1 gap separates the input visually. The pitch was tightened from 11.0 mm
  to free a jack-free zone at the bottom for a vertical power header that takes a
  16-pin IDC socket (below).
- Panel holes are jack Ø6.2 and LED Ø3.2. Labels: `MIDI`, `IN`, `1`..`8`,
  `BIG MODULAR`. The printed panel engraves them 0.4 mm deep.

## Back (B) layout: SMD for JLC assembly, plus headers

Each jack's three pads form a stripe ±1.3 mm around its Y. The SMD parts sit in
the bands between stripes; R20 uses the gap between J8's TN and T pads. The
through-hole headers on B need their F-side pads clear of jack bodies and LEDs, so
they go where F is free: beside J1 (no LED there) and below J9.

| Band | Parts |
|---|---|
| LED column beside J1 (X17.2, Y12.5..17.5) | **JP1** 1x3 2.54 mm TRS Type header (pin 1 Tip at the top, 2 DATA, 3 Ring), B silk `TRS`, `A` level with pin 1, `B` level with pin 3 (the shunt covers the lettered pin) |
| J1/J2 | R21 (4.7 k input series, X15.0), R2 (22 k RX pull-up, X5.8, beside the RX lane), R4 (ch1 LED) |
| Jn/Jn+1, every band | output n series resistor below jack n's tip (X13.52, jack + 3.6, rot 90) and LED n+1 resistor above its LED (X17.2, rot 270 so pad 2 faces the anode) |
| J4/J5 | ch3 pair, **R9** (ch4 output series) moved above J5 (Y54.1, rot 270), TX6-TX8 layer-change vias |
| J5/J6 (Y 64.25) | U1 ATtiny1616 (VQFN-20, 1 mm below the band centre for the fan-out), C1 100 n under U1, TX1-TX5 vias in the left zone, ch5 LED resistor R13 |
| J6/J7 | C3 10 u bulk in the left zone (X4.8), ch5/ch6 pairs |
| J7/J8, J8/J9 | ch6-ch8 pairs |
| J8 TN–T gap | R20 39 R 1206 LDO dropper |
| J8/J9 (Y 94.75) | U3 HT7550-1 SOT-89, C4, C5, D10 |
| Bottom zone, X8.6 (Y105.8..116.0) | **J10** 2x5 Eurorack power, vertical, pin 1 (-12 V) at the bottom, B silk `-12V` |
| Bottom zone, LED column (X17.2, Y107.7..110.3) | **J11** 1x2 2.54 mm UPDI header (pin 1 UPDI at the top, pin 2 GND), B silk `UPDI` |

### Power header and 16-pin IDC cables

- J10 pins: columns X7.33/X9.87, rows from Y105.84 (pins 9/10, +12 V) to Y116.0
  (pins 1/2, -12 V). A 10-pin cable fits as usual.
- A **16-pin IDC socket** goes on with its red stripe on pin 1 (bottom). Its
  positions 11-16 (+5 V, CV, Gate) overhang **upward** over the board, never past
  an edge. Envelope (a 2x8 socket that fits a box header: 25.4 x 6.4 mm body plus
  key bump): X4.8..12.4, Y94.4..119.8, underside 2.5 mm above B (it seats on the
  header's plastic spacer). The envelope stays inside the 20 mm slot and inside
  the rail gap (Y ≤ 120.5), so it doesn't depend on rail depth. The repo case rail
  is 12 mm deep and the socket starts about 14 mm behind the panel.
- Parts under the overhang: U3 SOT-89 (1.5 mm), C4 0805 (≤1.25 mm) and the
  clipped J9 jack leads, all below the 2.5 mm socket floor. Keep the J9 leads
  clipped to ≤1.5 mm. The envelope is drawn on `Dwgs.User` (`IDC16`) in the carrier.
- Unshrouded on purpose: a shrouded 10-pin box header would block the 16-pin
  socket, and it's wider than the board anyway. Key by the `-12V` silk.

### Jumpers

- JP1 (TRS Type) is a 1x3 header on B, next to J1, like the UPDI header. With a
  shunt it stands about 8.5 mm proud, less than J10, and it's reachable with the
  module out of the case. **Shunt on the `A` pair (1-2) = Type A; on the `B`
  pair (2-3) = Type B.** No shunt = no input (RX idles high). See
  [research.md §3.2](research.md).

## Assembly notes

1. JLC assembles the B-side SMD. Hand-solder J10, J11, JP1 and the jacks, then
   fit the JP1 shunt for the sender's TRS type (Type A on most gear).
2. Fit the LEDs **last, with the panel mounted**: push each LED into its hole
   (dome flush) and solder from the back. A 6 mm LED spacer gives about the same
   height if preferred.
3. Clip jack and LED leads on B to ≤1.5 mm. They share the back with SMD parts.

## Not yet verified

- The jack STEP models are marked "Untested" upstream. Measure the real body
  height, the boss and the bushing Ø before ordering panels; the 6.2 mm hole and
  the Z 10.0 seat follow from the models.
- The printed panel holes are nominal; drill or ream to Ø6.2 / Ø3.2.
- The U1 3D model is the shipped UQFN-20 3x3 P0.4 body, used as a visual proxy:
  KiCad doesn't ship the VQFN model its footprint references.
- Routing (R1) is complete on two layers with native DRC 0 (research.md §3.6); the
  3D fit was re-run after the routing placement changes and is unchanged.
