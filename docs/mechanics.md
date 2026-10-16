# Current single-LED electrical/mechanical revision

D10 ONLY is a hand-soldered red3mm +5V power indicator at existing X6.7/Y38 hole.
D11/D12 and Y46/Y54 holes are removed. No blink/controller. Remaining geometry
(USB, switch, outlines, M3 brackets and power landing) is preserved; no routing.
The following dimensions apply to this single-LED revision.

# A4.2 — two boards, plain M3 L brackets and restored SMT reset

**Placement/fit draft only. No routing, working LED/reset circuit, rated power output or fabrication approval.**

The supplied photo is used as an arrangement reference: a front panel and one
perpendicular main PCB. Its unseen construction and dimensions are not inferred.
The extra middle PCB, four 10 mm spacers and J3–J6 UI headers are removed.
Everything electronic that is placed (USB, one power LED and switch) is on the
main PCB. The existing off-board J2 power connector is retained as a flying-lead
connector, fed by new J7 solder lands: **no third PCB**.

- [Assembly drawing](assembly.pdf) / [SVG](assembly.svg)
- [Dimensioned M3 brackets](m3-brackets.pdf) / [SVG](m3-brackets.svg)
- [Printable bracket source](../hardware/mechanics/corner_braces.scad)
- [Switch and power buying guide](parts-buying-guide.md)
- [Native placement and fit checks](../reports/stack-validation.md)
- Previous A3 design: [superseded archive](archive/a3-stack-superseded.zip)

## Boards and coordinate system

All dimensions in mm. Panel front Z0, rear Z1.6; X right, Y down, Z into case.

| Feature | A4.2 dimensions / position |
|---|---|
| Front panel | 9.8 × 128.5 × 1.6 FR4, unchanged 2HP outline |
| Main PCB | 100.5 × 30 × 1.6 bounding envelope; Y14..114.5, Z2..32 |
| PCB plane | B.Cu X3.1; F.Cu X4.7; components on F.Cu |
| Rack holes | Ø3.2, X2.42, Y3 and Y125.5 — previous corner pattern retained |
| Panel bracket holes | Ø3.2, X6.4, Y22 and Y106.5 |
| Main PCB bracket holes | Ø3.2, same Y22 and Y106.5, Z15 |
| Main PCB front cutbacks | Z10 at Y16.5..27.5 and Y101..112, clearing bracket feet |
| USB mouth axis | X6.43, Y64.25, Z0.8 |
| USB panel aperture | X4.255..8.455, Y59.35..69.15, R0.6 corners |
| LED aperture | ONE Ø3.6, X6.7/Y38: D10 +5V POWER; former Y46/Y54 holes removed |
| Reset aperture | Ø3.2, X6.4, Y91 |
| Cable strain-relief holes | Ø2.5, main Y43.5 and Y70.5, Z27 |

The previous board plane, USB opening, D10 opening, plain L brackets and all mounting
holes are retained. Two additional LED openings are below D10. The selected
**TL3340AF160QG SMT** reset and its Ø3.2 access hole at **X6.4**, Y91 are unchanged. The panel remains
2HP and the main board remains 30 mm deep. The TS-1166VW candidate is retired,
not an unresolved request to widen this panel.

Panel KiCad coordinates map to `(X=x−50,Y=y−30)`. Main PCB KiCad coordinates map
to `(Y=x−35.75,Z=104.275−y)`. These transforms are used in independent native checks.

Rear PCB edge is still **30.4 behind the panel rear face**. This is NOT the full
module depth. Connector, flying cable and bend/strain-relief space depend on the
case. The earlier Z50 cable box was only a budget and is not a fit guarantee.

Rack grid phase remains X2.42 = 7.50−5.08. No sliding-nut-only requirement. The
Ø3.2 rack holes leave a nominal 0.82 edge web; a 6 mm head overhangs left by 0.58.
Check neighbouring panels, actual rail threads and FR4 bearing strength. Do not
countersink this 1.6 FR4 just to hide a large head.

## Two identical plain L brackets

Two rectangular legs joined at 90°, **3 mm thick**, two bores; no captive nut
pockets, channels, roofs, inserts or spacers. The upright now touches the main
PCB **back face**, not its component face. Ordinary nuts are outside the print.

Bracket-local origin is assembly `(X=0.1,Y=centre−5,Z=1.6)`.

| Dimension | Value (mm) |
|---|---:|
| Overall X × Y × Z | **9.2 × 10 × 18.4** |
| Both leg thicknesses | **3.0** |
| Panel bore axis, local X/Y | **(6.3,5.0)**, along Z |
| Main-PCB bore axis, local Y/Z | **(5.0,13.4)**, along X |
| Both clearance bores | **Ø3.2** |
| Side countersink | **Ø6.0 × 90°**, depth1.4; outside/left printed face |
| Remaining straight side bore | 1.6 |
| Installed bracket centres Y | **22 and106.5**; pitch84.5 |

The side countersink is the only feature beyond a plain L and two holes. It
keeps the screw head inside 2HP. **Countersink the printed plastic ONLY, never
the 1.6 mm PCB or front panel.** Main PCB holes remain ordinary Ø3.2 NPTHs.

Hardware for both brackets together:

- **2 × M3×8 pan/button screws** at the panel, head diameter≤6.
- **2 × M3×8, 90° flat countersunk screws** at the side. Length includes the
  head; DIN965 is a suitable style to trial, head diameter≤6. Do not substitute
  a raised countersunk or socket-cap head. Seat flush or up to0.3 below the face.
- **4 × plain M3 hex nuts**, across flats≤5.5, thickness≤2.4. No washers or nyloc
  nuts in these dimensioned stacks.

For the front screw: 1.6 panel +3 printed foot +2.4 nut =7, leaving1 nominal
thread projection. For the side: 3 printed leg +1.6 PCB +2.4 nut =7, leaving at
least1 when the countersunk screw seats flush. Side screw tip lies X8.1..8.4;
no side fastener needs to extend beyond X0..9.8. Actual seating must be checked.

**Post-solder access, out of rack:** slide loose nuts in from +X. Hold the front
nut with small needle-nose pliers gripping its near half from +X; a rear socket
driver is NOT promised. The clearance envelope is X6.4..30, Ycentre±5,
Z4.6..7.6. Hold the side nut using a5.5mm nut driver from +X (outside diameter≤8,
clear socket depth≥4); turn its screw from−X. Front screwdriver approaches−Z.
No unsoldering or main-PCB removal is required by the nominal tool model.

**Tight fit to trial:** the rotating front nut envelope clears the upright by
only **0.125 mm nominal**, and reaches X9.575 inside the9.8 panel. Print shrinkage,
actual nut size and tool shape can consume that margin. The checks are nominal,
not a tolerance analysis or proof that the user's specific pliers fit.

`corner_braces.scad` lays two L profiles flat for printing. **ABS is a reasonable
prototype material**, but measure shrinkage and use an enclosure with appropriate
ventilation; ABS warps and emits fumes. Use your filament's validated settings.
[source](https://help.prusa3d.com/article/abs_2058)

Trial one bracket first. Check bores, countersink seating, loose-nut access,
light tightening torque and USB/button/cable loads before printing/using both.
There is no structural, heat-creep or physical-fit qualification. OpenSCAD is
not installed here, so no rendered STL, slicer check or successful print is claimed.
The M3 countersunk style reference is dimensional guidance, not a purchased screw.
[source](https://fullerfasteners.com/tech/din-965-specifications-cross-recessed-countersunk-head-screws/)

## LED and reset: hand-solder access on main PCB

### D10 — one ordinary +5V power LED

D10 alone is a standard hand-soldered RED3mm through-hole lamp. Its original
2.54mm pitch, Ø0.9mm drills/1.8mm lands and square cathode pad1 remain unchanged.
Form leads90 degrees with a jig, not at the epoxy. Original optical axisX6.7/Y38,
Z nose-0.2mm and Ø3.6 panel hole are retained; no holder/light pipe/5mm substitute.
Select the exact lamp against the existing body/flange envelope and trial the fit.
D11/D12 and their two PCB footprints/Y46/Y54 panel holes are removed.

Final regulated P5 ->R32 1k ->D10 anode2 (LED_P_A), cathode1 ->GND.
Only these pad net labels change; no traces or resistor placement is added.
R32 is SMD0603 in the actual schematic/BOM, not the retired axial reservation.
There is no blink/controller requirement; D10 means+5V presence, not all-rail health.
D10 is manual populated (not DNP), excluded from JLC placement. Exact LED MPN,
brightness and formed-lead sample fit remain unqualified; circuit PCB is unrouted.

### SW1 — restored right-angle SMT tactile

**E-Switch TL3340AF160QG / LCSC C2886925** is the user's selected part. The exact
previous hand-solder library footprint is reused verbatim; no generic SMD clone
or through-hole alternative is substituted. The switch is on F.Cu; iron access
is from the component side, unlike the removed MJTP1117.
[source](https://www.e-switch.com/product/tl3340-series-subminiature-smt-right-angle-tactile-switch/)

| Feature | Nominal dimension / assembly position (mm) |
|---|---|
| Locator-row centre / footprint origin | Y91, Z4.1 |
| Three signal lands | Y89.775 /91 /92.225, Z5.75; widths 0.75 /0.60 /0.75, length2.30 |
| Two anchoring lands | Y88.85 /93.15, Z2.95; 1.90 ×0.70 |
| Two locating holes | Y88.875 /93.125, Z4.1; Ø0.90 **NPTH**, not solder holes |
| Housing height above PCB | 3.30; assembly upper X8.0, 1.8 inside panel width |
| Actuator axis | X6.4, Y91; 1.70 above F.Cu |
| Actuator diameter / tip | Ø2.0; Z2.05, 0.45 behind panel rear |
| Reset access hole | Ø3.2, X6.4 /Y91 |

The drawing's **3.40 dimension is along the push direction**, not above the PCB.
Order the exact suffix **AF160QG**; the retired seller's 4.3H stem choice does not
apply. The drawing shows pins1+3 common and pin2 as the other contact.
[source](https://configured-product-images.s3.amazonaws.com/2D/specs/TL3340AF160QG.pdf)

Custom toe extensions retain pad separation and clearance around the pegs. Fine
iron tip, flux and tweezers are required; this is not as easy as a large THT part.
Hand-solder and fit a sample before release. The five solder lands are exposed,
not hidden-pad/BGA connections. MP anchors have no assigned net pending an ESD
review; never assume they are signal contacts. The manufacturer's no-trace
reservation is shown on **Dwgs.User only**, not an enforced copper rule area;
it must be respected when routing is later authorized.

The button is recessed for tool access; no external plunger is selected. The
0.45 recess and 1.8 lateral margin are nominal, not a complete tolerance stack.
RESET_A_PENDING / RESET_B_PENDING remain isolated, with **no working reset circuit**.
The single D10 LED is THT; its schematic R32 SMD resistor is not placed yet. The TS-1166VW and MJTP1117 footprints remain as
retired alternatives, not active board parts. See the [buying guide](parts-buying-guide.md).

## Eurorack output socket and cable

The male-pins-inside-a-plastic-box part is a **shrouded/boxed male header**
(also sold as a keyed IDC box header). The cable end is the **female IDC socket**.
The interface here is **16-way / 2×8 / 2.54 mm keyed IDC**, carrying the design's
±12 V, GND and +5 V. A 10-wire module lead would omit the +5 V contacts. The mating
ribbon has **1.27 mm conductor pitch**, not 2.54; the contact grid and ribbon pitch
are different. Verify every pin end-to-end rather than trusting the red stripe.
[source](https://www.davidhaillant.com/eurorack-power-connectors-and-ribbon-cables/)
[source](https://www.digikey.com/en/articles/use-direct-plug-in-insulation-displacement-connectors)

**Physical implementation:** retain J2 on a short insulated, strain-relieved
flying lead. Candidate cable-mount male header is **Würth 61201625821**. It mates
to an ordinary female IDC cable end. This is not the same component as a PCB
box header with bare solder pins. A full shrouded header mounted normal to the
main PCB does not fit this 2HP stack; it is deliberately NOT falsely placed in
that space. J7 is a set of 16 numbered through-hole **wire solder lands**, not a
header to populate. The connector is outside the narrow board stack, wherever
case clearance allows. Its detailed housing/mate clearance is still unqualified.
[source](https://uk.rs-online.com/web/p/idc-connectors/8236645)

Use a trial 75–100 mm pigtail, 16-conductor, 28 AWG stranded copper ribbon, with
insulation and mechanical strain relief at the two Ø2.5 holes. Fan the stripped
ends to the 2×8 solder lands without exposed crossing conductors. Keep bare wire
ends and tie hardware away from all copper; confirm actual tie/clamp geometry.
The remaining power cable is **16-to-16, female-to-female, pin-for-pin**, typically
15–25 cm as a starting case-layout choice, not a certified length or current rating.

| Pin(s) | J7 → off-board J2 |
|---|---|
| 1,2 | −12 V / N12; red stripe at pin1 |
| 3–8 | GND |
| 9,10 | +12 V / P12 |
| 11,12 | +5 V / P5 |
| 13–16 | Not connected; no CV/Gate drive |

The actual sixteen J7 pad positions and nets are checked against the unchanged
J2 schematic pin audit. J7 itself is still a PCB-only reference needing deliberate
schematic integration. Pins13–16 have no PCB net and their wire ends must be
insulated. No routes or plane connections have been added.

**POWER OUTPUT ONLY. Connect only to an unpowered passive distribution board or
flying bus. Never connect to or parallel another live rack PSU.** No supported
load rating, working power build or safe-to-power claim follows from connector
selection. Pin1 marks, key orientation, each conductor, rail isolation, strain
relief, cable voltage drop and protection require independent checks first.
