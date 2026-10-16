# V1 mechanical routing preparation

Panel9.8 x128.5 x1.6mm; carrier100.5 x30 x1.6mm, perpendicular, B.Cu X3.1 /
F.Cu X4.7. Existing outline/reliefs, M3 brackets and J7 landing stay unchanged.
Panel origin is upper left, X across / Y down; Z into case. [Assembly PDF](assembly.pdf).

| Interface | Panel axis X,Y mm | Native carrier X,Y mm |
|---|---|---|
| J1 USB-C | 6.43,33.5 | 69.25,99.8 |
| D10 red3mm | 6.7,43 | pad1:77.48,97.905 |
| SW1 retry | 6.4,49.5 | 85.25,100.175 |

USB aperture X4.255,Y28.6,W4.2,H9.8,R0.6; SW1 hole3.2mm; LED hole3.6mm.
USB native pad numbering/mount pattern/model/orientation retained. Top bracket and
cutback end at Y27/Y27.5; the2.5mm carrier lip above them cannot support USB.
This is the highest practical cluster without changing the outline/brackets.
Clearances: USB pad-to-relief1.18mm; aperture-to-bracket1.6mm;
USB-to-LED solder envelopes2.51mm; LED-to-switch solder envelopes1.23mm;
switch body-to-LED flange2.35mm. LED flange max3.8mm leaves1.2mm lateral margin.
Order is USB -> D10 -> SW1; each keeps its own X, depth, orientation and land pattern.
LED pad1 remains1.27mm above its axis; SW1 peg row follows its own axis.
USB-to-switch solder envelopes8.08mm. All pairwise access gaps retain the0.8mm minimum.
Rail head ends at Y6; USB aperture begins28.6. Rail head still overhangs left0.58mm.
SW1 body3.3mm; button recessed0.45mm behind panel rear, no plunger. Solder from +X
with fine tip before fitting panel; all M3 nut/tool paths are checked out-of-rack.
Front nut/upright clearance is only0.125mm nominal: printed ABS/sample trial required.

L1/L4 now MDA1040-6R8M max4.0mm; L2/L3 CKCS6045 max4.7mm. The5.1mm normal
allowance reserves0.15mm solder +0.10mm assembly offset: margins0.85/0.15mm.
These are front-side envelope budgets, not fitted populated-board approval. Do not
flip inductors to the1.3mm backside allowance. Manufacturer height limits must hold.
64 active footprints, correct native fields/UUID paths/nets: J1/SW1/D10/J7 fixed;
60 power/passive parts unlocked in a labelled off-board grid, including0603 R32.
No missing footprints, no placement claim for staged parts; zero tracks/vias/zones.
Exact LED MPN, lead forming, USB cable overmould and finished cabled depth need trial.

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
parallel an active rack PSU. D10 cathode1=GND, anode2=R32 output; R32=1k from P5.
SW1 contacts1+3=EF_SHDN, contact2=RTN, MP case lands unconnected. Keep RTN separate
from system GND. Press disconnects input; stored output charge does not vanish instantly.
