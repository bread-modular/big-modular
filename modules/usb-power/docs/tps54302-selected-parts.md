# TPS54302 IBB — selected passive handoff

**Parts only; no CAD/PCB approval.** U3 TPS54302 -> about -14 V raw -> retained TPS7A3301 / -12 V / 300 mA objective. Evidence: [small JSON](tps54302-selected-parts.json). The hard component-normal allowance is **5.1 mm**, not 6.5 mm: [engineering.md, lines 58–65](engineering.md#footprints-and-bounded-sourcing). No mechanical relaxation is authorized.

## Exact shortlist

All selected rows independently show **Economic PCBA product type 0**, using the unchanged shared tool's dated mapping. Basic/Extended is separate. Stock is a UTC snapshot, not allocation/order acceptance. `SR1` rows reuse this repo's Git object `0f5b49d` evidence, **not a new live fetch**.

| Role | Exact manufacturer MPN / JLC code | Package | Library | Stock | UTC snapshot, 2026-10-17 |
|---|---|---|---|---:|---|
| **Selected L, 22 uH fallback** | Bourns **SRP1245A-220M / [C1848803](https://jlcpcb.com/partdetail/C1848803)** | SMD,13.5x12.5mm | Extended | **16 — thin** | **13:56:22Z**, live |
| **IC-local bypass** | Samsung **CL31B225KBHNNNE / [C50254](https://jlcpcb.com/partdetail/C50254)** | 1206 | **Basic** | **338,484** | 13:53:07Z, live |
| Reuse 100 nF type | Yageo **CC0603KRX7R9BB104 / [C14663](https://jlcpcb.com/partdetail/C14663)** | 0603 | **Basic** | 31,932,563 | 13:53:14Z, live |
| Optional upper FB | Yageo **RT0603BRD07100KL / [C122538](https://jlcpcb.com/partdetail/C122538)** | 0603 | Extended, existing SR1 | 1,358,377 | 11:17:30Z, SR1 |
| Optional upper FB | Yageo **RT0603BRD07120KL / [C705720](https://jlcpcb.com/partdetail/C705720)** | 0603 | Extended, existing SR1 | 93,064 | 11:17:07Z, SR1 |
| Optional lower FB | Yageo **RT0603BRD0710KL / [C95204](https://jlcpcb.com/partdetail/C95204)** | 0603 | Extended, existing SR1 | 2,058,191 | 11:17:30Z, SR1 |
| Optional upper trim | Uniroyal **0603WAF6201T5E / [C4260](https://jlcpcb.com/partdetail/C4260)** | 0603 | **Basic** | 814,513 | 13:53:53Z, live |

## L — C1848803 replaces the rejected taller candidate

- **22 uH ±20%, shielded carbonyl-powder**. Manufacturer table at **25°C**: **Isat 10 A at 20% L drop**, **Irms 6.5 A at 40°C rise**, **DCR 50 mΩ typical / 58 mΩ maximum**. Adequate published normal-current class for the supplied ~1 A RMS / ~1.4 A peak envelope, with credible room above the supplied **6 A fault limit plus small overshoot**. **10 A is not represented as a guaranteed minimum, especially hot.** The sheet has L-vs-I / temperature-rise plots, not separately temperature-indexed hot saturation curves or a guaranteed hot minimum. Actual fault overshoot, hot L retention and temperature still require qualification. [source](https://www.bourns.com/docs/Product-Datasheets/SRP1245A.pdf)
- Body **13.5±0.5 by 12.5±0.3 mm**, height **4.8±0.2 = 5.0 mm maximum**: **within the 5.1 mm component-height limit**, but only 0.1 mm arithmetic clearance. Not the ideal ≤4 mm. No board-fit/assembly-stack approval: Astra must check solder stand-off, courtyard, placement and real clearance. Manufacturer land-pattern drawing specifies **14.2 / 8.0 / 5.0 mm** dimensions; use the actual drawing, not a guessed generic footprint. [source](https://www.bourns.com/docs/Product-Datasheets/SRP1245A.pdf)
- Exactly **one bounded low-height check**, following the user's correction: manufacturer SRP1245A sheet plus one 3-row live MPN query. Genuine Bourns identity **C1848803** is present in the complete two-row response. **Stock 16 is a real sourcing risk**; requested board quantity/attrition and replenishment were not established. No more stock searches were made.
- **REJECTED mechanically:** earlier Bourns **SRP1265A-220M / C2041465**, 22 uH, listed Isat 12 A / Irms 9 A, DCR 32.5 typ / 37 max mΩ, stock 8,243 at 13:52:07Z, Extended/type 0. Its **6.2±0.3 = 6.5 mm maximum height violates 5.1 mm**. It is **not** an implementation fallback or an authorized height relaxation. [source](https://www.bourns.com/docs/Product-Datasheets/SRP1265A.pdf)
- **27 uH not verified.** Suggested `SRP1265A-270M` is absent from the inspected family table; its one live query failed schema validation, not a proven zero-stock result. The other returned low-height-query row, **FAUL1350-220MT / C5298325**, is a **different cjiang identity**, not Bourns: catalog Isat 6.5 A / Irms 4.5 A, DCR 58 mΩ, stock 293. Height and manufacturer fault/hot data were **not verified**; do not silently substitute it.

## C — Basic C50254, bias loss explicitly included

- Exact Samsung **2.2 uF ±10%, 50 V, X7R (-55 to +125°C), 1206**; dimensions **3.20±0.20 × 1.60±0.20 × 1.60±0.20 mm**. E-suffix identity is manufacturer-listed. **No 25 V part across VIN-to-NRAW.** [source](https://product.samsungsem.com/mlcc/CL31B225KBHNNN.do)
- Exact-MPN Samsung characteristic sheet, hosted by DigiKey: standalone DC-bias graph at **24–27 V ≈ -36% to -42%, or 1.3–1.4 uF per part**, measured at **1 kHz / 1 Vrms**. These are approximate visual readings of **typical**, not guaranteed, data. [source](https://media.digikey.com/pdf/Data%20Sheets/Samsung%20PDFs/CL31B225KBHNNNE_Character.pdf)
- Its **25 V bias-TCC graph is lower**: roughly -45% near 25°C (~1.2 uF), approaching -50% at endpoints (~1.1 uF). Preserve this discrepancy; do not choose only the favorable standalone curve. Initial -10% tolerance applied to the latter gives **~0.99 uF as a screening estimate**, not a proven minimum across voltage/temperature/aging. [source](https://media.digikey.com/pdf/Data%20Sheets/Samsung%20PDFs/CL31B225KBHNNNE_Character.pdf)
- ESR graph: **approximately 6–10 mΩ near 400 kHz**, E4294A / **0.5 Vrms**, with no DC-bias condition stated. **Biased ESR and real small-signal effective C at 24–27 V remain unverified.** [source](https://media.digikey.com/pdf/Data%20Sheets/Samsung%20PDFs/CL31B225KBHNNNE_Character.pdf)
- Select the **part type**, leaving bank count/startup/placement to Astra. One part is not 2.2 uF effective; **parallel Basic copies** avoid another Extended type. Two are 4.4 uF nominal, approximately **2.2–2.8 uF typical**, and **1.98 uF in the illustrative tolerance/temperature screen**, not a guaranteed 2.2 uF minimum.
- Reuse **C14663: 100 nF ±10%, 50 V X7R, 0603**, live Basic/type-0 confirmed, for the existing small-bypass role subject to Astra's confirmation. Exact supplier-linked manufacturer sheet is in JSON; its bias/ESR were not requalified. No output-capacitor resweep.

## Optional FB — reuse actual SR1 Extended codes

**Preferred four-resistor recipe:** upper **100 kΩ C122538 + 120 kΩ C705720 + Basic 6.2 kΩ C4260 = 226.2 kΩ**; lower **10 kΩ C95204**. All are **0603**. This reuses three actual SR1 precision types, including its existing 120 kΩ, with **no new Extended 220/226 kΩ type**. Type reuse does not authorize removing required positive-converter/LDO resistors.

- Three Yageo RT types: **±0.1%, ±25 ppm/°C, 0.1 W at 70°C, 75 V maximum working voltage**, also limited by `sqrt(P*R)` and temperature derating. Manufacturer B/D suffix meanings and 0603 ratings verified. **Extended, not Basic.** [source](https://yageogroup.com/content/datasheet/asset/file/PYU-RT_1-TO-0-01_ROHS_L)
- C4260 supplier attributes: **6.2 kΩ ±1%, ±100 ppm/°C, 0.1 W, 75 V**, independently Basic/type 0. Exact manufacturer-sheet URL retained; PDF text extraction unavailable.
- Narrow arithmetic: Basic trim is **2.741%** of upper R; upper initial worst-case tolerance **±0.1247%**, weighted TCR bound **±27.06 ppm/°C**. Not a complete 0.1% divider or statistical error cancellation. Astra owns full reference/FB-current/tolerance/TCR/headroom closure; no all-Basic margin claim.
- If restricting precision reuse to only 100 kΩ and 10 kΩ types: upper **2×C122538 + 2×C95204 + C4260**, lower **C95204** gives the same values/bounds but **six physical resistors**. Prefer four if existing C705720 reuse is accepted. No large network/dynamics study.

## Evidence and authorization boundary

**Eight bounded live JLC requests:** one failed 270M query, three one-page searches (two truncated discovery pages and the complete low-height check), four exact-code lookups. Seven successful raw-response SHA-256 digests and selected fields verified; no retry/pagination sweep, converter-IC rescan, offline fallback, orders/reservations or vendor uploads. SR1 observations retain original UTC/hash provenance from Git; their original raw bodies were not independently rehashed here. Scratch evidence stays ignored under `modules/usb-power/research/tps54302-parts/`.

Shared CLI/skill/docs read once. Type-0 service mapping remains the shared tool's dated 2026-10-05 observation; `assemblyComponentFlag` is retained separately in JSON without inventing its undocumented meaning. **Authenticated process/quote acceptance remains unknown.** Stock/quantities/attrition and exact footprints need later recheck. Billing is not exposed, so the $3–4 target cannot be certified.

Only this new Markdown and its small JSON are deliverables, made diff-visible by **`git add -N`**. No existing files, CAD, code, PCB or main writes. JSON/hash/field consistency and diff/whitespace verified; no CAD/ERC/DRC/bench qualification claimed. Supervisor's **Opus + DeepSeek V4 Flash reviews precede final schematic presentation and any PCB work**; no review/delegation is performed here. User must see the final reviewed schematic before routing ACK. **No PCB work is authorized.**
