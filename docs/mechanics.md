# A1 mechanical proposal — dimensioned, NOT qualified

Open [assembly.svg](assembly.svg) or [assembly.pdf](assembly.pdf): original FRONT, SIDE and TOP views plus enlarged right-angle block/screw section. [assembly-geometry.json](assembly-geometry.json) gives machine-readable nominal coordinates; `tools/build_mechanics.py` regenerates both drawings without external artwork.

## Rail correction — primary drawing, not an inferred standard

Doepfer specifies 128.5mm panel height and **9.80mm actual width for 2HP**. Its embedded **A100FP.gif** explicitly shows **x=7.5mm, Ø3.2mm, y=3mm from each end** and horizontal spacing N×5.08mm. Hence vertical pitch is 128.5−6=122.5mm. The raster drawing, not just extracted page text, was inspected. [source](https://doepfer.de/a100_man/a100m_e.htm) [source](https://doepfer.de/a100_man/A100FP.gif)

The previous centres x=4.9 were **2.6mm off that grid**. A1 corrects the actual panel PCB to **(7.5,3), (7.5,125.5), Ø3.2 NPTH**. A 5.0×3.2 slot centred at x=7.5 extends to x=10.0, outside the 9.8mm panel, so it has been replaced with the primary drawing's circular hole, not falsely represented as a compliant slot.

**Mechanical blocker:** this leaves only 0.7mm FR4 web. A 6mm M3 head centred at 7.5 extends to x=10.5: **0.7mm into the adjacent module's width**. The drawing shows that head envelope dashed. A centred head would have to be **<4.6mm diameter for any lateral clearance** (4.6mm gives zero margin), yet the hole is Ø3.2 and its FR4 web remains just 0.7mm; no manufacturer-evidenced reduced-head M3 screw/washer with qualified bearing area and no tested FR4 strength has been identified. Standard M3x6 hardware cannot be promised to fit between adjacent panels. The rail positions are now correct, but head clearance and edge strength are NOT solved. A possible alternative is centred slots with sliding M3 nuts, but that would be a deliberately non-fixed-grid panel revision requiring user acceptance; it is not the present PCB. Do not fabricate this thin-web panel or claim universal 2HP rack compatibility.

The Doepfer panel is 2mm aluminium; this project's 1.6mm FR4 is not mechanically equivalent. The secondary SDIY description is useful context, not a substitute for the primary x=7.5 drawing. [source](https://sdiy.info/wiki/Eurorack_panel_components)

## Coordinate system and unchanged J1

X right, Y down in front view; Z inward. Panel front Z=0, rear Z=1.6. Panel KiCad origin (50,30) maps to assembly (0,0). Carrier is perpendicular, in the YZ plane:

```
X component face = 3.170; PCB bottom = 1.570
Y = x_KiCad - 35.750
Z = 104.275 - y_KiCad
J1 origin = (100.000, 99.800), rotation 0 degrees (unchanged)
J1 local mouth = y_KiCad + 3.675 -> assembly Z=0.800
Mating axis height above PCB = 1.730 -> X=4.900
Mating centre Y=64.250; insertion vector (0,0,+1)
```

Axis is normal to the faceplate, not sideways. The prior GCT USB4105 drawing basis (1.73 axis height, 3.31 shell height, 8.94 width, mouth datum) is retained; no new connector shift or footprint modification was made. Live manufacturer drawing access failed during this pass, so revision-specific fit remains to re-confirm before procurement. [source](https://gct.co/files/drawings/usb4105.pdf)

| Feature | Nominal mm |
|---|---|
| Panel | 9.8 × 128.5 × 1.6 FR4 |
| Aperture | X=2.725..6.925, Y=59.35..69.15; 4.2×9.8, R0.6 |
| Receptacle shell front envelope | X=3.17..6.48, Y=59.78..68.72 |
| Shell clearance per side | 0.445 X, 0.430 Y nominal |
| Panel interposer holes | Ø2.2 at X=4.9, Y=45 and 83.5 (unchanged) |
| Carrier | Y=14..114.5, Z=2..62; 100.5×60×1.6 |
| Carrier support holes | Ø2.2 at (Y,Z)=(45,6),(83.5,6) |
| Rear tie holes | Ø2.2 at (45,52),(83.5,52), not case mounting points |
| Front board/panel rear gap | 0.4 |
| Front shell copper/board edge clearance | 0.5 |

Top/bottom rail holes are distant from the USB aperture in Y, so changing their X does not intersect the opening. Carrier starts at Y=14 and ends 114.5; keep the rail access regions Y<10 and Y>118.5 clear. This is an access envelope, not qualification against every rail profile.

## Two actual right-angle interposers

Rather than undefined L-brackets or bent FR4, specify **two solid machined aluminium corner blocks**, mutually perpendicular tapped mounting faces. They are custom parts, not claimed stocked parts. Each is X=5.80, Y=8.00, Z=8.40, occupying X=3.17..8.97 and Z=1.60..10.00; centred at Y=45 or 83.5. Flat-bottom blind tapping is necessary to keep the two perpendicular bores separate.

| Datum relative to each block's (Xmin,Ymin,Zmin) | Position / thread |
|---|---|
| Panel-facing bore, axis +Z | X=1.73, Y=4.00; M2×0.4 |
| Carrier-facing bore, axis +X | Y=4.00, Z=4.40; M2×0.4 |
| Both blind bores | Full thread >=2.6, total depth including tip <=2.8 |
| Four fastening screws | M2×4, low head height <=1.2 and diameter <=3.8; exact screw unselected |
| Nominal thread engagement | 4.0−1.6=2.4; no washer in this stack |
| Minimum nominal bore separation | Panel bore ends Z=4.4; side M2 envelope begins Z=5.0: 0.6 web |

Carrier screw heads are on PCB bottom, X=0.37..1.57; blocks finish X=8.97, inside the 9.8 width. Heads/blocks clear the connector because their Y centres differ by 19.25mm from the USB axis. Side screws must be fitted before installing adjacent modules. PCB thickness, screw-length tolerance, bottoming, thread strength, torque and availability of the required low heads are **open qualification items**, not an approved fastener BOM. Tapped holes target ±0.05 position, block outline ±0.10; these are requested tolerances, not achieved measurements.

Block contact regions must remain bare FR4 with copper/component keepouts on a future layout. No claim that anodization alone insulates copper. FR4 edge-tapped, bent or soldered-on brackets are **not** selected: their thread retention/bending strength has not been established. The four soldered USB shell stakes transfer plug forces into the carrier and these blocks. No independent shell cradle is supplied, and PCB flex/USB stake loading require force and torque tests.

## Assembly / cable and plug acceptance

1. Machine/deburr/tap the two blocks; inspect blind-bore separation and selected screw lengths.
2. Bolt blocks to the bare carrier's Z=6 holes from its bottom face, then solder J1 including all shell stakes. These are mechanical mock-up steps only; the board has no electrical power circuit.
3. Loosely fasten panel M2 screws into block front faces; align the aperture with the mouth before tightening. Check screw bottoming and the 0.4mm board-front gap.
4. Reserve rear holes at Z=52 for an insulated tie/strain-relief. A floating 16-pin harness exits behind Z=62; provisionally reserve X=0.4..9.4, Y=40..75, Z=65..87. Exact IDC dimensions/bend radius remain unselected. Do not assume a wide/tall header fits 2HP.
5. Trial rail screws before installing between neighbours. M3×6 through panel1.6 plus washer0.5 gives 3.9mm nominal reach into the rail; actual nut depth and head interference remain blockers.

Aperture/profile target ±0.10 and hole float consume the modest nominal USB clearances. Mouth is recessed 0.8mm. Earlier mating geometry suggests the overmould can remain ahead of the panel, but **no standard-plug fit promise** is made: metal-shell corner radii, plug body, angular insertion and cable torque need samples and worst-case stack-up. No strength, insertion-force or enclosure fit test was performed.
