# Mechanical interface — unchanged PCB reservations

Existing 2HP panel: 9.8 x 128.5 mm; perpendicular carrier about100.5 x30 mm,
1.6 mm FR4, two plain 3 mm-wall M3 L brackets. No middle board/standoffs.
Current board geometry and TL3340 SMT hand-solder footprint remain unchanged.
Geometry JSON and small preservation contracts are regression inputs, not previews
or fabrication approval. `build_stack.py`/`build_mechanics.py` emit NEW candidates only.

**Next mechanical owner:** put USB at panel top, with SW1 retry button and single
red D10 close by; synchronize the simplified schematic and place all power parts.
Do not reuse current connector/LED/switch coordinates as final routing placement.
Existing board reset net placeholders and old USB net names intentionally remain;
no board sync, tracks, vias or zones were added here.

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
modeled as J2. Verify orientation/continuity and strain relief before use; never
parallel an active rack PSU. D10 cathode1=GND, anode2=R32 output; R32=1k from P5.
SW1 contacts1+3=EF_SHDN, contact2=RTN, MP case lands unconnected. Keep RTN separate
from system GND. Press disconnects input; stored output charge does not vanish instantly.
