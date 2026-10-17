# Thermal/process evidence — not qualification

Both TPS7A4700 and TPS7A3301 thermal pads are internally GND and require ground heat spreading. [source](https://www.ti.com/lit/ds/symlink/tps7a47.pdf) [source](https://www.ti.com/lit/ds/symlink/tps7a33.pdf)

The negative LDO EP is **not IN/NRAW**. U3 pin 1 remains NRAW; U2 EP17 remains RTN.
These islands and all component pin/net assignments are preserved. Both LDOs have
recommended maximum operating junction temperature 125 C; this PCB has no measured
junction temperature or qualified current rating. Use accepted SR2 load/ambient and
0.723/1.026 W U13 screens, then verify by bench testing.

New vias are ordinary plated through, 0.30/0.65 mm, unfilled/uncapped, tented both
sides, outside exposed/paste pads. Tenting does not guarantee via filling or flatness.
JLC recommends small holes for tenting; ordinary tenting is distinct from paid
filled/capped via-in-pad processing. [source](https://jlcpcb.com/help/article/pcb-via-covering)

JLC publishes +0.13/-0.08 mm through-hole tolerance and 18 um average hole plating;
these do not establish compliance with the frozen tighter drill/plating fabrication
contract. Explicit inner 1 oz is required instead of the default 0.5 oz. Keep these
as release-setting/vendor-review blockers, not silent rule changes. [source](https://jlcpcb.com/capabilities/pcb-capabilities)

`evidence/thermal-connectivity.json` records exact via UUID/coordinates, tenting,
EP spoke endpoints, filled subpolygons on F/In1/In2/B layers and no new hole/pad
intersections. Arrays share local In2 filled subpolygons with real EP-spoke corner
vias, rather than relying only on net-name labels. 41 older exposed-pad hole
intersections elsewhere remain separately listed and unqualified for ordinary PCBA.
