# Current lamp correction

Buy ONE ordinary hand-soldered red3mm formed-lead LED for D10, not three lamps.
Final P5 ->R32 1k ->anode2, cathode1 GND; exact MPN/brightness/fit still unqualified.
D11/D12 are retired. Other mechanical buying notes below remain provisional.

# A4.2 switch, Eurorack output connector and cable buying guide

These are **procurement candidates**, not an order, reservation or release BOM.
No shipping-to-Sri-Lanka, delivered price, seller authenticity or current checkout
availability is guaranteed. Public listings and manufacturer drawings were checked;
JLC/LCSC catalogue snapshots are retained separately and are NOT cable stock proof.
The current127-part electrical design/BOM supersedes the old circuit. See [mechanics](mechanics.md).

## Single manual power LED

D10 alone is an ordinary RED3mm THT lamp, leads formed90 degrees, no proprietary
holder/5mm substitution. One retained Ø3.6 hole atX6.7/Y38 and two2.54-pitch/Ø0.9
solder-through pads are provided. Trial the actual lamp against the envelope in
[mechanics](mechanics.md). D11/D12 are removed; do not purchase three lamps.
D10 is manual/excluded from JLC placement. Final regulated P5 feeds its anode
through R32 1k SMD0603; cathode GND. No blink/controller. Exact LED MPN, stock,
price, brightness or physical fit is not guaranteed; sourcing remains provisional.

## Selected reset switch — E-Switch TL3340AF160QG (SMT)

The user chose to return to this earlier **90° side-actuated surface-mount,
normally-open momentary tactile switch**. The exact MPN is **TL3340AF160QG**,
LCSC **C2886925**. Do not order the pictured TS-1166VW or MJTP1117 for the active
A4.2 board. The restored footprint is `BigModular:SW_TL3340AF160QG_HandSolder`.
[source](https://www.e-switch.com/product/tl3340-series-subminiature-smt-right-angle-tactile-switch/)

| Supplier | Where to buy / verification |
|---|---|
| DigiKey | **TL3340AF160QG**, exact-MPN listing. The product page could not be fully extracted this pass; no stock/checkout guarantee. [source](https://www.digikey.com/product-detail/en/e-switch/TL3340AF160QG/EG4627CT-ND/1885974) |
| LCSC | **C2886925 — E-Switch TL3340AF160QG**. Product identity checked on the public page and with one bounded live catalogue lookup. [source](https://www.lcsc.com/product-detail/C2886925.html) |
| AliExpress | No exact, authenticated TL3340AF160QG listing verified. Use a search for the exact MPN only as a lead, not as permission to buy a visually similar clone. [source](https://www.aliexpress.com/w/wholesale-TL3340AF160QG.html) |

**No separate 4.3H/7H/10H choice applies:** order the exact part number above.
The drawing specifies **3.30 mm above-PCB body height**, **1.70 mm actuator-axis
height**, and **3.40 mm overall dimension along the actuation direction**. Avoid
confusing a distributor's generic “height” field with these different axes.
[source](https://configured-product-images.s3.amazonaws.com/2D/specs/TL3340AF160QG.pdf)

It is **SMT, not through-hole**. The custom pads provide exposed iron-access
areas: three signal lands and two anchoring lands, plus two unsoldered locating
holes. Use a fine tip, flux and tweezers; trial solder a sample before release.
No hand-solder temperature/time process has been qualified. Pins1+3 are the same
contact; pin2 is the other contact. Anchors are left without a circuit net.
The reset opening is now X6.4 /Y91, Ø3.2; no wider panel or printed plunger is used.

### Retired alternatives (do not populate on A4.2)

- **TS-1166VW-type:** custom uploaded-drawing footprint retained for reference,
  not selected. Its 7.1 mm projection does not fit the current 5.1 mm allowance;
  the 2.50-versus-2.15 mm row-pattern conflict is still documented, not resolved.
  [Historical analysis](ts1166-switch.md).
- **APEM MJTP1117:** the preceding THT switch has been removed from the active
  board. Its library footprint is retained, but is not pin-compatible with SW1.

## What the male pins inside the plastic box are called

**Shrouded male header**, **box header**, or **keyed IDC box header** is the PCB
part name. The plastic surrounding the pins is the shroud; gender is determined
by the metal contacts, not by the surrounding box. Its mate on the ribbon cable
is a **female IDC socket**. This is a standard connector family, not a special
Eurorack-only part. [source](https://www.digikey.com/en/products/detail/on-shore-technology-inc/302-S161/2794234)

Use **2×8 contacts on a 2.54 mm grid**, male pins on the supply/output connector
and female IDC sockets on the detachable cable. The ribbon conductor spacing is
**1.27 mm**. The existing design supplies +5 V as well as ±12 V, so use a full
16-to-16 cable for the bus feed, not a 10-to-16 module lead.
[source](https://www.davidhaillant.com/eurorack-power-connectors-and-ribbon-cables/)
[source](https://www.digikey.com/en/articles/use-direct-plug-in-insulation-displacement-connectors)

### Selected form: cable-mount male IDC on the output pigtail

The two-board draft uses **Würth 61201625821** as the cable-mount connector
candidate. J7 on the main PCB is solder-through wire landing pads, not the
footprint for this connector. This avoids placing a bulky box header sideways
outside the 2HP board envelope. Cable housing position is case-dependent.
[source](https://uk.rs-online.com/web/p/idc-connectors/8236645)

- **DigiKey:** Würth **61201625821**, 16-position male IDC cable header.
  [source](https://digikey.se/product-detail/en/wurth-electronics-inc/61201625821/732-5454-ND/4846927)
- **LCSC:** no equivalent **cable-mount male** SKU was confidently verified.
  Use their custom-cable enquiry and specify the exact male IDC form, pinout and
  free solder ends. **No quote or drawing upload has been submitted.**
  [source](https://lcsccable.com/customize)
- **AliExpress:** 2.54 mm IDC female-to-male ribbon assembly with a **16-pin**
  variant. Candidate donor for a pigtail, not a verified Eurorack-wired assembly;
  confirm the selectable variant and meter every conductor. Listing indexed,
  not a completed seller/stock/mating audit.
  [source](https://www.aliexpress.com/item/32950903082.html)

### Buy the PCB-mount shrouded header

These are the **male-pins-inside-a-box** parts described. Select16-pin/2×8,
2.54mm mating pitch, and check notch/pin1 orientation. They are not interchangeable
with the cable-mount pigtail part above. **J7 is still wire lands, not a qualified
box-header placement**; identifying these parts does not silently change that.

| Supplier | PCB header |
|---|---|
| DigiKey | **On Shore302-S161**, straight/vertical, shrouded16-pin2.54mm THT. [source](https://www.digikey.com/en/products/detail/on-shore-technology-inc/302-S161/2794234) |
| LCSC | **BOOMELE C9038**, 2×8, 2.54mm through-hole **ejector-header variant** (larger housing/latches). Product page/catalogue checked; its “Free Hanging” category is misleading. Check drawing before laying out. [source](https://www.lcsc.com/product-detail/C9038.html) |
| AliExpress | **16-pin2×8, 2.54mm right-angle box header** listing. Indexed identity only; full page/stock not verified. Not a drop-in footprint approval. [source](https://www.aliexpress.com/item/32606233643.html) |

Straight and right-angle versions have different PCB footprints. Ejector/latch
versions are bulkier than basic box headers. These links identify buyable part
families, not approval to solder an arbitrary one onto the current wire lands.

## Detachable cable

Specification: **16-pin female IDC to 16-pin female IDC, straight-through 1→1
through 16→16**, keyed, 2.54 mm mating pitch, 1.27 mm ribbon conductor pitch,
stranded copper. Start with 15–25 cm only if the actual case layout suits it.
A factory ribbon assembly is not automatically Eurorack polarity-qualified.

- **DigiKey:** Assmann **H3CCH-1606G**, 16-position socket-to-socket assembly,
  152.4 mm length. Candidate: review drawing/key orientation and verify continuity
  before using for Eurorack; no connector/cable combination was physically tested.
  [source](https://www.digikey.com/en/products/detail/assmann-wsw-components/H3CCH-1606G/1218559)
- **LCSC:** custom cable service. No specific ready-made 16-to-16 Eurorack cable
  SKU was verified, so this is an **enquiry link**, not an in-stock product.
  Specify 16 conductors, full pin-for-pin wiring and the two female keyed ends.
  [source](https://lcsccable.com/customize)
- **AliExpress:** Eurorack ribbon-power-cable listing. Choose **16-to-16**, not
  10-to-16, and check the seller's current available variant and length.
  [source](https://www.aliexpress.com/item/32993706140.html)
- Eurorack-specific alternative: Synth Cable Supply Co 16-to-16 cable.
  [source](https://synthcablesupplyco.com/products/eurorack-ribbon-power-cable-16pin)

## Mandatory power precautions

This module is a **PSU output**, not a normal Eurorack module power input. Feed
only passive, unpowered distribution. **Never parallel it with an existing
active rack supply.** The project is still incomplete and has no qualified load
rating; sourcing connectors does not approve powering the circuit.

Pin pairs: **1–2 −12 V; 3–8 GND; 9–10 +12 V; 11–12 +5 V; 13–16 NC**. Red stripe
belongs to pin1/−12 V, but inspect key/triangle orientation and meter all wires.
A reversed crimp or wrong key defeats the apparent protection of a shroud.
[source](https://www.davidhaillant.com/eurorack-power-connectors-and-ribbon-cables/)

The Würth drawing download was blocked (HTTP403); this pass verifies its catalogued
cable-mount form, not all housing tolerances. DigiKey/selected AliExpress pages
could not be fully extracted; product identity is supported by indexed listings.
Do not treat those limitations as verified availability or a completed fit audit.
