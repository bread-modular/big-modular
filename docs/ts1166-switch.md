# Requested 6×6 right-angle switch — footprint made, assembly fit BLOCKED

> **Retired alternative:** the user has chosen the earlier **TL3340AF160QG SMT**
> switch instead. A4.2 installs that part and retains 2HP / plain L brackets.
> The analysis, historical height preference and test results below describe the
> rejected THT proposal, not the current part selection or active SW1.


**Use the uploaded TS-1166VW-type drawing, not the old APEM land pattern.**
The custom library footprint is complete for its four solder holes. It is **not
installed on the active main PCB**, because the requested body does not fit the
current 2HP board position. No panel or bracket was silently widened/repositioned.

## Height to select

**Provisional choice: `6×6×4.3mm` / `4.3H`, the shortest option in the screenshot,**
for a recessed, tool-operated reset rather than a long exposed button. This is a
height *preference*, not a final fit/order release. Obtain a sample or seller
confirmation before buying a quantity.

Here **H runs along the button/push axis**, parallel to the main PCB and toward
the front panel. It is **not** the distance the mounted switch stands off the PCB.
The 7.1 mm seating-plane projection is a separate dimension. Choosing 4.3H instead
of 7H or 10H cannot make that lateral projection smaller.

The previous reset design intent is a tip at Z2.05, 0.45 behind the 1.6 mm panel
rear face. For H4.3, its H-reference plane would need to be at Z6.35 (`2.05+4.3`).
**That is a target, not a derived placement:** the supplied drawing does not
unambiguously dimension the H-reference plane and actuator axis relative to the
recommended PCB hole rows. We have NOT invented that datum from photograph pixels.
Final hole-to-panel position and recess/protrusion require the actual sample.
The seller's first photograph also has rough envelope labels, not a hole drawing.

## Custom KiCad footprint

Library identifier:

```text
BigModular:SW_TS1166VW_RightAngle_THT_P4.50_P7.00_Row2.50mm
```

[Download/open the footprint](../hardware/BigModular.pretty/SW_TS1166VW_RightAngle_THT_P4.50_P7.00_Row2.50mm.kicad_mod).
The existing `BigModular` footprint library already includes this directory.
[Native footprint plot](ts1166-footprint.svg) shows the holes and provisional
courtyard, **not** a fitted assembly or an accurate switch-body model.

Origin: centre of the two signal holes; viewed from the component side.
Local +Y is toward the actuator/front, not the direction of pressing force.

| Pad | Function | Local X | Local Y | Finished drill | Copper diameter |
|---|---|---:|---:|---:|---:|
| 1 | Normally-open contact A | −2.25 | 0 | 1.0 | 2.0 |
| 2 | Normally-open contact B | +2.25 | 0 | 1.0 | 2.0 |
| MP1 | Soldered metal support | −3.50 | −2.50 | 1.5 | 2.6 |
| MP2 | Soldered metal support | +3.50 | −2.50 | 1.5 | 2.6 |

- **Signal pitch 4.50; support pitch 7.00; row offset 2.50 mm.** All four are plated
  through-holes with copper/mask on both sides, no paste openings. Annular rings
  are 0.50/0.55 mm for manual soldering. Minimum nominal pad-to-pad gap is 0.495 mm.
- Circular signal pads retain clearance; silkscreen `1`/`2` identifies contacts.
  The seller schematic labels both endpoints identically, so `1` and `2` here are
  our numbering convention, not manufacturer-certified lead numbers.
- The support pads are **MP1 and MP2**, not two extra switch contacts. No ground
  or connection between them is imposed. Check case/tab continuity on the sample.
- Only the hole pattern is exact to the uploaded PCB layout. The courtyard is a
  provisional component/solder access reservation; body outline/H datum remain
  unqualified. There is no invented/borrowed 3D model and no panel cutout in this
  footprint. Do not use its courtyard as proof of physical fit.

## Two independent blockers

### 1. It is not a drop-in replacement in this 2HP assembly

Current geometry is front panel width9.8, main PCB B.Cu X3.1 / F.Cu X4.7. The
uploaded side view gives **7.1±0.1 mm from seating plane to housing extremity**.

```text
Available to the right of F.Cu: 9.8 - 4.7 = 5.1 mm
Requested switch extremity:   4.7 + 7.1 = 11.8 mm
Nominal panel-width overhang: 11.8 - 9.8 = 2.0 mm
```

The requested part therefore requires a **board/bracket arrangement change** or
more module width. A shorter actuator does not solve this. Shifting the PCB also
affects the existing 3 mm L brackets, solder-tail clearance and USB/LED/panel
alignment; it cannot honestly be presented as a footprint-only substitution.
The existing APEM SW1 is retained solely as an **old layout placeholder**, not as
an override of the user's new part choice or a current purchasing recommendation.

### 2. Same name, different pin rows

Your uploaded recommended PCB layout explicitly says **2.5 mm** between rows.
A public drawing with the same **TS-1166VW** name instead says **2.15 mm**.
It also dimensionally relates 3.65 and 1.5 (`3.65−1.5=2.15`). Consequently, the
model name alone cannot authenticate the seller's pin geometry. This custom
footprint deliberately follows **your 2.50 mm layout**, not the external variant.
The 0.35 mm row difference must not be dismissed or hidden by changing hole sizes.
[source](https://taoic.oss-cn-hangzhou.aliyuncs.com/7159/product/MXBESIJIA_1591957457000.pdf)

Ask the seller to confirm: **4.3H, 4.50/7.00 pitches, 2.50 row spacing,
Ø1.0/Ø1.5 recommended holes, 7.1 seating projection**. Obtain a sample and a
printed 1:1 hole test before PCB fabrication. Do not silently use a 2.15 mm part.

## Buying/document provenance

- Requested photo: [user image](/uploads/62a5d7e6-6f08-499a-bf5a-0d9c97bc710b.webp).
- Governing hole pattern: [user drawing](/uploads/a5154f41-b568-478f-afb8-d7f3d57e8687.webp).
- Height choices: [user listing screenshot](/uploads/fcec2814-e0ae-45fd-800a-3019a9f401a9.webp).
- The screenshot does not include a product URL; no exact AliExpress product link,
  seller authenticity, stock, price or DigiKey/LCSC substitute is claimed.
  Existing MJTP1117 links are **not** matching parts for this footprint.
- [Buying guide](parts-buying-guide.md) now distinguishes the requested candidate
  from the retained old PCB placeholder. Header/cable recommendations are unchanged.

## Verification and boundary

`/usr/bin/python3 -B tools/verify_ts1166.py` verifies actual native pads, drills,
plating/layers, numbering, annular rings and isolated support pads; reports the
2HP conflict instead of treating it as a pass. A standalone native KiCad coupon
has **0 DRC violations / 0 opens**, but that only tests the isolated pattern.
It is not the module, not 3D fit approval, and not a fabrication export.

Tests reject the 2.15 mm row variant, old APEM 5 mm signal pitch/1.3 mm support
drills, and accidental contact/support numbering merges. They also verify that
changing H never clears the lateral-body conflict. No routing, board/panel
replacement, schematic/BOM changes, purchase or commit was made for this request.

Current verification: **8 new switch tests pass; full suite36/38 pass**. Two
historical schematic-byte baseline checks fail after independently observed
schematic/project changes during this run. Those files were not reverted and
no baseline was relaxed. [Full validation report](../reports/ts1166-validation.md).
