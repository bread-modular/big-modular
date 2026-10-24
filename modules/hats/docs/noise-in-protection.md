# NOISE IN sense protection (S3)

The signal-conditioning branch (R11 = 100k, C10/R12/R13/U9B) and the switch truth table are unchanged. This change protects the separate **jack-normal contact detection** branch; R12 was never in series with that branch.

## Circuit

- J2 TN -> `NIN_SENSE_RAW` -> **R49, 22k** -> `NIN_SENSE` -> U5 IN1.
- **R14 changes from 1M to 470k**, from +3V3 to `NIN_SENSE`.
- **D7, Nexperia BAV199,215 (C40919)**, is a low-leakage dual series diode in the existing HATS SOT-23 footprint: pad 1 = lower diode anode / GND; pad 2 = upper diode cathode / +3V3; pad 3 = common junction / `NIN_SENSE`.
- Empty jack: TN is connected to T, so R49 + R11 pull IN1 low and U5 selects internal BLUE_NOISE. Patched jack: TN opens, R14 pulls IN1 high and U5 selects NIN_BUF. No firmware participation.
- R49 is UNI-ROYAL 0603WAF2202T5E, C31850. R14 is 0603WAF4703T5E, C23178. Both were observed Basic and Economy eligible; D7 was observed Extended and Economy eligible. Public catalog evidence is in `research/s3-r2/` and must be refreshed before ordering.

## Logic-margin calculation

Nominal empty-jack voltage: `3.3 * (100k + 22k) / (470k + 100k + 22k) = 0.680 V`.

All resistor tolerance corners were enumerated with:

- VDD = 3.0..3.6 V; resistors +/-1%.
- Signed leakage budget: 1 uA U5 input leakage plus 80 nA for each D7 diode = 1.16 uA. The 80 nA diode budget uses the published hot-junction maximum, not a typical room-temperature leakage value.
- TI limits VIH >= 0.7*VDD and VIL <= 0.3*VDD, in the 3.3 V electrical-characteristics table (default -40..85 C conditions).

Minimum calculated margins: **158.9 mV low**, **349.3 mV high**. These are component-budget calculations, not measured temperature qualification. Raw corners: `research/s3-r2/protection-corners.json`.

U5 electrical characteristics and input limits. [source](https://www.ti.com/lit/ds/symlink/ts5a23157.pdf)

D7 pinout, leakage (5 nA at 25 C / 80 nA at 150 C, VR=75 V), and forward-voltage characteristics. [source](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf)

## Contact-transient protection and limits

R49 limits the separate sense-path current when the normal contact briefly sees a patched bipolar signal. For a +/-12 V contact event, a conservative negative-clamp-current bound including R14 current is **0.561 mA**, versus U5's published 50 mA negative input-clamp-current limit. The conservative instantaneous R49 dissipation bound using 15.6 V across its minimum resistance is **11.2 mW**, below its 0.1 W nominal rating.

**BAV199 is a silicon diode, not a -0.3 V Schottky clamp.** Do not claim the control input is always held above -0.5 V. Negative events can share current with U5's internal input clamp; TI's absolute-maximum note explicitly permits the input-voltage limit to be exceeded when the clamp-current limit is observed. The external upper diode limits positive excursions to the 3.3 V rail plus a diode drop. At 25 C its specified maximum VF at 1 mA is 0.9 V; cold/hot and contact-transient behavior still require prototype testing.

The two existing 1k/1k midpoint dividers draw at least about 2.97 mA over the stated supply/tolerance range, exceeding the limited positive injected sense current while powered. This avoids relying on the LDO sinking current during that event. When unpowered, rail injection/back-powering is still a consideration; do not treat this circuit as a hot-swap isolator.

This is **not** an IEC ESD qualification, unlimited mis-patch guarantee, or protection redesign of the analog/audio branch. Bench checks remain: empty/inserted selection, slow insertion/contact bounce with positive and negative signals, power-off patching, rail excursion, and temperature margin.
