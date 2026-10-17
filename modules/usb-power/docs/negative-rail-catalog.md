# Negative-rail IC public JLC catalog evidence

**Research only. Catalog observation window: 2026-10-17T12:47:35Z–2026-10-17T12:49:22Z.**

Six exact stocked IC candidates plus the existing TPS65131 baseline were identified with **eight bounded live catalog requests**. An interim three-part shortlist was written to this file after R03, before the remaining requests. Machine-readable observations, exact requests and raw-response SHA-256 digests are in [negative-rail-catalog-evidence.json](negative-rail-catalog-evidence.json).

Astra independently owns datasheets and electrical feasibility. This report makes **no claim** that any candidate implements 9 V directly to approximately -14 V raw, works with the existing TPS7A3301 -12 V output, or supports 200–250 mA or possible 300–500 mA. Package labels below are catalog text, not footprint/pin compatibility approval. No circuit, native CAD, PCB, generator, BOM, test, shared-tool, export, routing, order or upload changes were made. Existing LDOs remain untouched. **Routing stays paused until user ACK.**

## Availability-only ranking

Ranking prefers actual Basic plus observed Economic eligibility, then public stock depth among the remaining eligible entries. It is **not an electrical, cost or design-selection ranking**. Manufacturers are catalog-reported identities, not independent physical authenticity certificates.

| Rank | Exact manufacturer MPN | C-code / normal public page | Catalog package (verbatim) | Basic / Extended | Economic PCBA eligibility, separately observed | Public stock | Evidence |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| 1 | Texas Instruments **TPS5430DDAR** | C9864. [source](https://jlcpcb.com/partdetail/TexasInstruments-TPS5430DDAR/C9864) | SOIC-8-EP | **Basic** | **Yes**, per-part type 0 | **204,384** | R04; discovery R02 |
| 2 | Texas Instruments **TPS54302DDCR** — existing exact identity | C311983. [source](https://jlcpcb.com/partdetail/TexasInstruments-TPS54302DDCR/C311983) | TSOT-23-6 | Extended | **Yes**, per-part type 0 | **21,907** | R01 |
| 3 | Texas Instruments **TPS54160DGQR** | C13530. [source](https://jlcpcb.com/partdetail/TexasInstruments-TPS54160DGQR/C13530) | MSOP-10-EP | Extended | **Yes**, per-part type 0 | **6,722** | R03 |
| 4 | Analog Devices **LT8330ES6#TRPBF** | C673741. [source](https://jlcpcb.com/partdetail/AnalogDevices-LT8330ES6TRPBF/C673741) | TSOT-23-6 | Extended | **Yes**, per-part type 0 | **779** | R05 |
| 5 | Analog Devices **LT3580EDD#TRPBF** | C462624. [source](https://jlcpcb.com/partdetail/AnalogDevices-LT3580EDDTRPBF/C462624) | DFN-8-EP(3x3) | Extended | **Yes**, per-part type 0 | **23** | R07 |
| 6 | Analog Devices **LT8362EDD#TRPBF** | C673762. [source](https://jlcpcb.com/partdetail/AnalogDevices-LT8362EDDTRPBF/C673762) | TDFN-10-EP(3x3) | Extended | **Yes**, per-part type 0 | **20** | R06 |
| Baseline only | Texas Instruments **TPS65131RGER** — existing exact identity | C87663. [source](https://jlcpcb.com/partdetail/TexasInstruments-TPS65131RGER/C87663) | QFN-24-EP(4x4) | Extended | **Yes**, per-part type 0 | **456** | R08 |

All shortlisted entries have `preferredComponentFlag=false`, no per-part missing-field issues, and live `stockCount>0`. The two low-stock ADI entries are much thinner catalog options than the others; no replenishment lead time was checked. Each selected row reports `componentSource="shop"`; **new-versus-used condition was not an explicit observed field** and must not be inferred from that value or stock quantity.

For the genuine new TI candidates, C9864 is actual Basic; C13530 is Extended, not Basic. Both independently show type 0. The existing C311983 is also Extended despite its reuse potential. No changes to native/BOM classifications or design identities are made by this research.

## Identity exclusions and honest failure handling

- R02 (`TPS5430DDAR`, limit 3) returned three rows with complete pagination, but the CLI **exited 1**: the separate **TPS5430DDAR-YJLTY / C9900001995** row reports manufacturer **JLCPCB Assembly**, stock **0**, and `missing:attributes`. It is **not accepted as the requested Texas Instruments identity**; a similar MPN is insufficient. No assertion is made about its underlying die.
- R04 was a deliberate exact-code lookup of discovered **C9864**, not an automatic replay or network-failure retry. It **passed** with no missing fields. The public code query also returned unrelated **GC9864N-3-200 / C3195204**; the unchanged adapter selected the unique exact C9864 from the untruncated response. The unrelated row is not a candidate.
- Genuine TI-labeled alternate suffixes **TPS5430DDARG4 / C3192324** (SO-8-PowerPad, R02) and **TPS54160DGQRG4 / C2071929** (MSOP-10-EP, R03) each showed **stock 0**. Their Extended/type-0 metadata does not make them stocked alternatives.
- **TPS54160DDAR was not verified and is not used**; the actual observed stocked identity is DGQR. No claim of DDAR existence/nonexistence is made.
- **LM2611 was not searched**: all six requested families yielded stocked exact entries. No new LDO, broad capacitor/passive, or clone-alternative research was performed.
- No HTTP/API/anti-bot blocker occurred. R02's missing-field failure is retained, not silently called a successful strict search. All six selected candidates and the baseline have independent passing per-part observations.

## Live request ledger

Public source URL for every request: <https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList>. These are read-only public catalog POSTs, **not** cart/order actions. Every body is `{"currentPage":1,"pageSize":N,"keyword":"…"}`. All responses were HTTP 200, API code 200, `mode=live`; all pages were untruncated.

| ID | Operation / keyword | Page size | Returned / total | UTC retrieval | CLI exit |
| --- | --- | ---: | --- | --- | ---: |
| R01 | lookup `C311983` | 20 | 1 / 1 | 2026-10-17T12:47:35Z | 0 |
| R02 | search `TPS5430DDAR` | 3 | 3 / 3 | 2026-10-17T12:48:02Z | **1**, excluded row missing attributes |
| R03 | search `TPS54160DGQR` | 3 | 2 / 2 | 2026-10-17T12:48:04Z | 0 |
| R04 | lookup `C9864` | 20 | 2 / 2, unique exact code selected | 2026-10-17T12:49:13Z | 0 |
| R05 | search `LT8330ES6#TRPBF` | 3 | 1 / 1 | 2026-10-17T12:49:15Z | 0 |
| R06 | lookup `C673762` | 20 | 1 / 1 | 2026-10-17T12:49:17Z | 0 |
| R07 | lookup `C462624` | 20 | 1 / 1 | 2026-10-17T12:49:19Z | 0 |
| R08 | lookup `C87663` | 20 | 1 / 1 | 2026-10-17T12:49:22Z | 0 |

### Raw-response SHA-256

These hashes cover the entire returned UTF-8 response, **not** selected fields or a reformatted JSON object. All eight were recomputed against the local raw snapshots. They are integrity aids, not supplier signatures.

| ID | SHA-256 |
| --- | --- |
| R01 | `7c5aa29f6b6036e4bc7b1bde5c81c541eb69195e463b5f248761eba96e08110e` |
| R02 | `7dcf7b3a18233a5914c50e348511c11b66f16173a0f360ebd00e4c515a7d9057` |
| R03 | `69bbfe9ce74b0304ba062b409acb54f17ff347ca86bf33bdb0ac654d847fe0cb` |
| R04 | `3954d27a7081c083cb664e6256557a9b0d2b7f63d6ce694afa020f56be706791` |
| R05 | `3aabc5e8e60c30ae936af9c285518dff3954de0330b4e6507385816328dbec60` |
| R06 | `757167b42d8937516daea36f2faa5e3bda31836c955b1d9722d5a08b007ee29b` |
| R07 | `b8b7f3221e7de0eaacb61b4f3a71af435638644e60e7f41dd51d0a2d76578a86` |
| R08 | `82aac4fad6dad6758904534dc90c960c5482135aefcbe6b5df2f56698356be6c` |

Raw snapshots total 55,553 bytes and remain **outside Git**, temporarily at `/tmp/negative-rail-catalog-3504c4bb-059/raw/`. They are not bulk tracked downloads and may not survive temporary-directory cleanup. The small JSON sidecar preserves selected observations, full-response digests and request provenance; it is not a complete raw replay fixture.

## Tooling and service evidence boundary

Read root `AGENTS.md`, canonical `opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`, shared JLCPCB assembly/export documentation, and actual CLI help before catalog use. Used the unmodified existing tool:

```sh
python3 -B opt/kicad-tools/jlcpcb/assembly.py lookup C9864 \
  --strict-live --max-requests 1 --timeout 15 \
  --cache-dir /tmp/negative-rail-catalog-3504c4bb-059/raw

python3 -B opt/kicad-tools/jlcpcb/assembly.py search 'LT8330ES6#TRPBF' \
  --limit 3 --strict-live --max-requests 1 --timeout 15 \
  --cache-dir /tmp/negative-rail-catalog-3504c4bb-059/raw
```

There were no retries, offline fallback, pagination sweeps, credentials, authenticated acceptance, anti-bot bypass, GUI or vendor uploads. Two narrow public-web discovery queries supplied the LT8362/LT3580 page identities before exact-code live lookup; they were **not used as inventory evidence**. One normal TPS65131 product-page read attempted to clarify cost. No premium search or supplier purchase was made. Actual assistant/search billing is not exposed, so a total research charge below $5 cannot be independently certified.

The existing adapter separately parses:

- `componentLibraryType="base"` → Basic; `"expand"` → Extended. Preferred status is an additional flag, never a promotion to Basic.
- Per-part `componentProductType=0` → Economic and Standard; 1 → Economic Only; 2 → Standard Only. Missing or unsupported values do not pass by assumption.

The **mapping itself is dated**, from JLC's frontend <https://jlcpcb.com/ssr/js/b1851ed7074a22a7e047.js>, observed **2026-10-05T04:51:32.467955Z**, as documented in the existing shared tool. It was not separately re-fetched in this bounded task. The **numeric per-part fields and stock were fetched live**. This is a public catalog service indication using that unchanged mapping, not an authenticated board/process/order guarantee.

## Price, quantity and release limitations

- **No currency-qualified price is reported.** The API supplies numeric quantity tiers but no explicit currency or purchase-MOQ field. The supplemental normal TPS65131 product-page extraction did not expose a usable price/currency/MOQ quote. The raw numbers are not relabeled as USD or used to claim savings. Thus TPS65131 **stock is confirmed above; comparable baseline cost remains unknown**.
- `leastPatchNumber` was **5** for C311983 and **0** for the other selected entries. `lossNumber` was **1** for C311983 and **0** for the others. These are verbatim public assembly metadata, **not** proven purchase MOQ, free attrition, waived minimums, or an accepted order quantity. Missing commercial conditions remain unknown.
- **Stock is not reservation/allocation.** Board quantity, aggregated usage, attrition, reel/minimum requirements, warehouse condition, replenishment, package/pin mapping, electrical feasibility, process compatibility and authenticated JLC acceptance all need separate review before ordering.
- No native KiCad/ERC/DRC/export or electrical verification was run: this task checks catalog evidence only. Final checks are JSON parsing, raw SHA-256/selected-field consistency, Markdown consistency, whitespace and an exact two-file Git change scope.

**Handoff:** prioritize catalog review of C9864, C311983 and C13530; retain C673741 as another stocked identity, and C462624/C673762 as explicitly low-stock entries. Astra must decide electrical suitability independently. No design selection or routing authorization is implied; user ACK is still required.
