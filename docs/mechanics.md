# Mechanical definition — millimetres, nominal A0

## Assembly coordinate system

```
Front view (viewer at Z < 0)              Side cross-section
X = right, Y = down                       inward = +Z
      9.8 mm                              cable --> [front Z=0 | back Z=1.6]
   +----------+                                   mouth Z=+0.800
   |  M3 slot | Y=3.0                              =======> connector on carrier
   |          |                                     board front edge Z=2.000
   | M2 mount | Y=45.0                               board extends to Z=62.000
   |    ()    | USB long dimension is VERTICAL
   |    ()    | axis at X=4.900, Y=64.250
   | M2 mount | Y=83.5
   |          |
   |  M3 slot | Y=125.5
   +----------+ Y=128.5

Panel plane = XY. Carrier plane = YZ (PERPENDICULAR).
Carrier top/component face is at X=3.170; bottom at X=1.570.
USB insertion unit vector = (0,0,+1), dot panel normal = 1.
The 90-degree relation is between mating axis and PANEL PLANE,
not between mating axis and carrier PCB plane.
```

A standard right-angle receptacle on a panel-parallel board would point sideways. This carrier is deliberately perpendicular, rotating the receptacle's 8.94 mm shell width into panel Y. It does not rely on an unexplained footprint rotation to make a 3D assembly fit.

## Exact KiCad-to-assembly transform

- Panel KiCad origin `(50,30)` maps to assembly `(X,Y)=(0,0)`; front face is Z=0, material extends to Z=1.6.
- Carrier top view: `X=3.170`, `Y=x_KiCad-35.750`, `Z=104.275-y_KiCad`.
- J1 footprint origin is `(100.000,99.800)` at 0 degrees. Local mouth is **y=+3.675** from the footprint origin; front shell-stake center y=+1.075 plus datasheet 2.600 mm gives this same mouth coordinate.
- Therefore mouth depth is `104.275-(99.800+3.675)=+0.800 mm`.
- Manufacturer side view gives **1.730 mm** mating-axis height above PCB top: axis X = `3.170+1.730=4.900`.
- Axis Y = `100-35.750=64.250`; incoming cable travels from negative Z to positive Z. Footprint local mating direction is -y_KiCad, i.e. +Z assembly.
- This is a shallow **0.8 mm recessed mouth**, not a flush or rear-facing connector. Drawing mating view specifies ≥1.85 mm between receptacle mouth and plug-body front when mated; nominal plug-body front is ≤-1.05 mm, clear of the panel. The aperture leaves only 0.445 mm X and 0.430 mm Y nominal clearance per side around the 3.31 × 8.94 mm receptacle envelope; it must admit the *plug's metal mating shell* from the front without snagging the R0.6 corners. The plug overmould should remain ahead of the faceplate, but no ordinary plug-shell/overmould tolerance sample or insertion-force test is documented. **Front insertion of ordinary plugs remains an acceptance test**, not an inferred clearance certification; oversized/angled overmoulds are excluded.

## Dimensions and tolerance decisions

| Feature | Nominal geometry |
|---|---|
| Faceplate | 9.800 × 128.500 × 1.600 mm FR4 |
| 2HP nominal pitch | 10.160 mm; actual width leaves 0.360 mm clearance |
| Rail slots | 5.000 × 3.200 mm oblong NPTH, centers (4.900,3.000), (4.900,125.500) |
| Rail center spacing | 122.500 mm |
| USB aperture | X=2.725..6.925, Y=59.350..69.150; 4.200 × 9.800 mm, R0.600 corners |
| Shell front envelope | X=3.170..6.480, Y=59.780..68.720; 3.31 × 8.94 mm |
| Aperture web | Minimum side web 2.725 mm; not a fragile 0.3 mm strip |
| Panel bracket holes | Ø2.2 NPTH at (4.900,45.000), (4.900,83.500) |
| Carrier outline | Y=14.000..114.500, Z=2.000..62.000; 100.500 × 60.000 × 1.600 mm |
| Carrier bracket holes | Ø2.2 at (Y,Z)=(45,6),(83.5,6),(45,52),(83.5,52) |
| Front carrier edge | 0.400 mm behind panel rear; receptacle overhangs board by 1.200 mm |
| USB front stake copper to edge | 0.500 mm nominal; front slot and pad stay on board |
| Assembly depth | PCB 62 mm behind front; provisionally reserve to **Z=87 mm** for output harness/bend relief |

Outer board outlines are simple closed rectangles; USB cutout is a genuine closed rounded opening, not only silkscreen. Mounting pads are NPTH, no annular copper. Specify precision profile tolerance ±0.1 mm when seeking a quote; ordinary outline tolerance and board-thickness tolerance need a full stack-up review. The USB drawing has its own tolerances; the nominal clearances above are **not a completed worst-case stack**. No claim of 27 mm overall depth is made.

## Mechanical loads and hardware still to detail

Use four soldered through-hole USB **shell stakes**, not just signal pads, for connector attachment. Use two non-electrical insulating L-brackets at panel Y=45 and 83.5, bolted through the panel M2 holes and carrier Z=6 holes; retain the rear carrier at Z=52 or use those holes for harness strain relief. A suitable bracket must fit in X=0.4..9.4 mm and support the carrier top plane at X=3.170. Fastener heads, nuts, electrical clearances and assembly access require a sample fit.

Add an insulating cradle/shoulder support against the shell, above the rear signal contacts, transferring insertion force to the carrier brackets/panel. Do not press on USB contacts or rely on small SMT pads to react cable bending. **This cradle and brackets are dimensional requirements, not supplied production CAD or validated purchased parts.** Until fitted and tested, the connector load is still partly carried by soldered shell stakes. Mating force from the drawing is 5..20 N; qualify retention with that force and cable bending/torque.

J2 is a **floating, strain-relieved 16-pin cable connector**, not a tall vertical box header on the carrier that would exceed 2HP. Reserve a provisional harness envelope X=0.4..9.4, Y=40..75, Z=65..87. Exact keyed connector dimensions and cable-bend radius are unverified; do not buy or fabricate around that envelope without checking the selected connector drawing. A rear interposer, if needed later, requires a separate board and will not fit by implication.

The 2HP panel dimensions follow Doepfer's 3U/HP construction guidance. [source](https://doepfer.de/a100_man/a100m_e.htm)

USB pin/pad mapping and the 1.73/3.31/8.94/2.60/1.85 mm geometry come from GCT USB4105 drawing Rev B, including its recommended PCB layout. Manufacturer endpoint was unavailable during research; the public mirror was used (its certificate chain was invalid, so independently confirm the drawing before manufacture). [source](https://gct.co/files/drawings/usb4105.pdf) [source](https://ultran.ru/upload/iblock/398/USB4105.pdf)

An independent distributor drawing and the installed KiCad footprint agree on the connector family; revision-specific ratings must not be silently mixed. This design uses only 5/9 V, not the newer product page's higher voltage claim. [source](https://www.mouser.com/catalog/specsheets/Global_Connector_Technology_usb4105.pdf)
