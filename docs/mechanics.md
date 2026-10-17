# V1 HRO toleranced bare-PCB mechanics

Panel9.8 x128.5 x1.6mm; carrier100.5 x30 x1.6mm, perpendicular, B.Cu X3.1 /
F.Cu X4.7. Existing outline/reliefs, M3 brackets and J7 landing stay unchanged.
Panel origin is upper left, X across / Y down; Z into case. [Assembly PDF](assembly.pdf).

| Interface | Panel axis X,Y mm | Native carrier X,Y mm |
|---|---|---|
| J1 HRO USB-C | 6.33,33.5 | 69.25,103.475 |
| D10 red3mm | 6.7,43 | pad1:77.48,97.905 |
| SW1 retry | 6.4,49.5 | 85.25,100.175 |

USB aperture X3.90,Y28.10,W5.00,H10.80,R0.60; SW1 hole3.2mm; LED hole3.6mm.
HRO local land imported with honest paired-contact symbol mapping; no verified3D model.
See [HRO review](usb-hro-review.md) for exact drawing/local deviations and datum derivation. Top bracket and
cutback end at Y27/Y27.5; the2.5mm carrier lip above them cannot support USB.
This is the highest practical cluster without changing the outline/brackets.
Clearances: USB pad-to-relief1.18mm; aperture-to-bracket1.1mm;
USB-to-LED solder envelopes2.51mm; LED-to-switch solder envelopes1.23mm;
switch body-to-LED flange2.35mm. LED flange max3.8mm leaves1.2mm lateral margin.
Order is USB -> D10 -> SW1; each keeps its own X, depth, orientation and land pattern.
LED pad1 remains1.27mm above its axis; SW1 peg row follows its own axis.
USB-to-switch solder envelopes8.08mm. All pairwise access gaps retain the0.8mm minimum.
Rail head ends at Y6; USB aperture begins28.1. Rail head still overhangs left0.58mm.
SW1 body3.3mm; button recessed0.45mm behind panel rear, no plunger. Solder from +X
with fine tip before fitting panel; all M3 nut/tool paths are checked out-of-rack.
Front nut/upright clearance is only0.125mm nominal: printed ABS/sample trial required.

## M3 bracket face mounting and current cutbacks

The upright seats on the carrier **BACK face** (B.Cu at X3.1); the foot seats on
the front panel **REAR face** (Z1.6). Each leg is fastened normal to its mating
face: the side screw runs along +X through the web and PCB, with its nut on F.Cu;
the panel screw runs along +Z through the panel and foot. The PCB is **not threaded
through the bracket**. Ordinary 90-degree face mounting is valid and does not
inherently require PCB notches.

The retained custom L has a web at X0.1..3.1, Z4.6..20 and a foot at
X0.1..9.3, Z1.6..4.6, each 10mm wide in Y about Y22 / Y106.5. Filling the current
notches back to the carrier's Z2 front edge would overlap that foot and FR4 at
X3.1..4.7, Z2..4.6, Y17..27 / Y101.5..111.5. The existing carrier cutbacks at
Y16.5..27.5 / Y101..112 to Z10 clear **this L plus its loose M3 nuts/tool paths**.
Z10 is the retained dimension, **not a proven minimum** or a universal L-bracket rule.

Simply reversing this same 3mm web onto X4.7..7.7 puts its outward foot beyond the
9.8mm panel. The available 5.1mm right-side strip cannot contain the current 5.5mm
AF loose M3 nut. This is a conflict in the current configuration, not a claim that
M3 brackets or notch-free 90-degree mounting are impossible. A notch-free 2HP
alternative at these board/panel positions needs changed hardware: smaller
fasteners, a threaded leg or slimmer hardware are possibilities only, not yet
dimensioned, selected or approved. Current outlines, holes, part positions and
M3 fasteners remain unchanged; no alternative manufacturing proposal is implied.

The [geometry contract](../tools/stack_geometry.py),
[bracket source](../hardware/mechanics/corner_braces.scad) and
[existing nominal M3 access check](../tools/m3_fit.py) describe the retained
cutout configuration. Its nominal check remains valid, not a physical-fit or strength approval.

L1/L4 now MDA1040-6R8M max4.0mm; L2/L3 CKCS6045 max4.7mm. The5.1mm normal
allowance reserves0.15mm solder +0.10mm assembly offset: margins0.85/0.15mm.
These are front-side envelope budgets, not fitted populated-board approval. Keep all
components on the front; the back carries no parts. Manufacturer height limits must hold.
99 active footprints and native fields/UUID paths/nets; J1 HRO placement rederived,
SW1/D10/J7 fixed. All97 purchased fitted parts placed; D10 is DNP (footprint/pads
retained); carrier552 tracks/201 vias/8 zones.
Front panel remains passive. Only the USB aperture size/position changed; all other physical interfaces retained.
D10 remains DNP: no LED MPN/procurement, lead forming or fitted-LED check is claimed;
USB cable overmould and finished cabled depth still need trial.

## J7 physical board output landing

| Contacts | Net / purpose |
|---|---|
| 1,2 | N12 / -12 V / red-stripe end |
| 3..8 | GND |
| 9,10 | P12 / +12 V |
| 11,12 | P5 / +5 V |
| 13..16 | NC; no CV/gate/bus drive |

J7 is numbered solder lands, not a second purchased box header. One manual flying
lead terminates in the keyed16-pin output harness; that off-board connector is not
modeled as a second schematic connector. Verify orientation/continuity and strain relief before use; never
parallel an active rack PSU. D10 is DNP: cathode1=GND pad, anode2=R32 output pad, and
the physical footprint/indicator circuit remain; R32=1k from P5 stays fitted.
SW1 contacts1+3=EF_SHDN, contact2=RTN, MP case lands unconnected. Keep RTN separate
from system GND. Press disconnects input; stored output charge does not vanish instantly.

## Fabrication tolerance acceptance

Both finished boards1.60 +/-0.16mm; each aperture wall +/-0.10mm, centre
registration +/-0.10 X/Y and R0.50..0.70 through thickness. Measured assembly
registration +/-0.10 X/Y, seating+.05 X, squareness<=.5deg, shell width+.15 / height+.10; in-plane angular registration<=.5deg with
additional .040mm X / .016mm Y corner sweep.
Independent complete worst-case corner margin0.233458mm; previous aperture would
interfere by0.428610mm under this same budget. Minimum outer-edge ligament0.60mm.
See [full acceptance budget](fabrication.md) and [generated fit report](usb-fit.json).
Loose M3 hole clearance does not guarantee registration; physical assembled/cable/ABS
trial is pending, while the declared bare-board artwork is ready for the required process.
