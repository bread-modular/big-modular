# usb-power electrical handoff — read-only research, not implementation

## Decision and boundaries

Keep TPS7A4700RGWR, TPS7A3301RGWR, TPS65131RGER, both TPS54302s and TPS26600. No source edits, fabrication, commit/merge/push, advisors/delegation, GUI or other workspace/external-project access was performed. Only this untracked research directory was written. Do not wait for migration; rebase the engineering context in a fresh chat **after migration is merged and a fresh implementation request is given**. This note is not approval to implement or order.

The reported negative fluctuation is NOT a bench observation by this review. The source reveals inadequate corner headroom, small bias-derated capacitor margins and unresolved shutdown behavior; it does not establish which causes the user's symptom. Raising negative raw voltage alone is rejected. There is no support for 800 mA, 1 A or symmetric ±350 mA supply claims.

## Authoritative source and stale evidence

Workspace HEAD at inspection: e452435 (main-based migration merge). Accepted capacitor-closure content is commit **352437640d67ba1c431b54533f22374c9796b300**, merged through 8f3c500. The Git branch named 043 points at older b4d301d; branch name alone is not the authority. Read accepted blobs, not another workspace. Root `hardware/`, `tools/`, `tests/` still match 3524376; canonical module hardware/tools/tests/jlcpcb and module AGENTS/Code are missing in this checkout. Some module docs/BOM exist, and other accepted docs remain at root. `source-provenance.json` records exact blob IDs and SHA256s.

Accepted native PCB contains the 043 C5/C18 + C68–C72 changes, 107 electrical + four mechanical footprints, 585 segments, 207 vias and eight zones. `accepted-native-pad-view.json` is a common-parser read-only pad/field view of the accepted Git blob (duplicate mechanical reference strings collapse in its ref-keyed map; do not use map length as footprint count). J7 pins 9/10 share **one P12 rail**, pins 1/2 share N12, 11/12 share P5. There are not two independently rated +12 V outputs. Other output connector branches were not found.

`modules/usb-power/docs/ldo-evidence/dc-budget.json` is stale: it assumes R75=23.2k, R76=2.49k and blanket precision factors, with -11.997925 V final nominal and 0.805588 V negative headroom. Accepted native values are R75=24k, R76=2.4k, R72/R83/R73=82k/9.1k/1.2k, R74=10k; substituted parts are 1%, 100 ppm/K. Old saved netlists/reports must not be treated as a fresh verification of this hardware.

Replayed **accepted `tools/ldo_budget.py` directly from Git**, overriding its data root only in process memory to read the moved module evidence; no tool edits. Its ordinary invocation currently fails because data paths were incompletely migrated. Reproduced results are in `accepted-budget-replay.json`:

| Magnitude, volts | Actual accepted 043 |
|---|---:|
| PRAW nominal / DC bounds | 13.537080 / 12.910821–14.184851 |
| NRAW nominal / DC bounds | 13.928806 / 13.061874–14.817399 |
| NRAW trough after allocated 0.100 V dip | 12.961874 |
| N12 nominal / modeled magnitude bounds | 12.020250 / 11.296067–12.783855 |
| Negative worst headroom | **0.178019** |
| Positive worst headroom | 0.510821 |
| MID/P5 nominal / DC bounds | 5.007547 / 4.712887–5.318152 |
| MID peak with 0.100 V allocation | **5.418152**; only 81.848 mV below 5.5 V |

These are corner **screens**, not guaranteed envelopes. Critical newly identified limitation: TPS65131 IFBP/IFBN=50 nA is in the **typical**, not maximum column (datasheet p5). The model's ±50 nA is an assumption. TPS7A33 ±2.5% overall accuracy requires 1 V input/output separation, not merely its 0.8 V maximum-dropout test condition. Applying that accuracy bound when headroom fails is a target-envelope/failure test, not proof actual outputs remain within the displayed bounds. No linear scaling of the 0.8 V/1 A bound to 150 mA is valid.

## Smallest fully specified candidate retained for the next review

Seven existing references, no added footprint, no active changes. These are a **conditional prototype candidate**, not an electrically qualified or Basic-compliant release. Exact replacements were verified against the public common catalog; three precision resistors and the 180k are NOT Basic. Explicit assembly-policy approval or a subsequently validated Basic alternative is required. Basic networks of 1% resistors do not become guaranteed 0.1% by averaging.

| Ref | Accepted value / MPN / C-code | Candidate value / MPN / C-code | Fresh classification |
|---|---|---|---|
| R15 | 150k 1%, 0603WAF1503T5E, C22807 | **150k 0.1%, 25ppm/K**, RT0603BRD07150KL, C326734 | Extended |
| R60 | 150k 1%, 0603WAF1503T5E, C22807 | **180k 1%, 100ppm/K**, 0603WAF1803T5E, C22827 | **Preferred Extended, NOT Basic** |
| R72 | 82k 1%, 0603WAF8202T5E, C23254 | **90.9k 0.1%, 25ppm/K**, RT0603BRD0790K9L, C728600 | Extended |
| R83 | 9.1k 1%, 0603WAF9101T5E, C23260 | **0 ohm**, 0603WAF0000T5E, C21189 | Basic |
| R74 | 10k 1%, 0603WAF1002T5E, C25804 | **10k 0.1%, 25ppm/K**, RT0603BRD0710KL, C95204 | Extended |
| R84, MID only | 510 ohm, 0603WAF5100T5E, C23193 | **820 ohm 1%**, 0603WAF8200T5E, C23253 | Basic |
| C62 | 10nF 50V, 0603B103K500NT, C57112 | **DNP for first diagnostic prototype**, retain pads | No purchased replacement |

Keep R73=1.2k Basic, R14=1.6M 0.1%, R76=2.4k Basic, R9=100k, R10=13k. Leave independent P5 R17/R18/R85 unchanged. Do not reuse retired D11/D12. No blanket passive substitution.

Why the extra divider work: tightening R15 and the final negative divider but retaining R60=150k gives only 0.790011 V screened headroom. Changing R60 alone to180k yields a 15.174829 V peak, beyond TPS65131's 15 V recommended output magnitude. The combined candidate gives:

- NRAW nominal -14.167585 V; magnitude DC 13.500831–14.832380 V.
- N12 nominal -11.996750 V; magnitude modeled 11.611808–12.386251 V (includes 0–0.1 ohm jumper allowance).
- Trough 13.400831 V minus worst target 12.386251 V = **1.014580 V headroom**; reserve over0.8 V is0.214580 V, but reserve over the1 V accuracy condition is only14.580 mV.
- Peak NRAW14.932380 V is only67.620 mV inside15 V. The0.1 V ripple/transient allocation must be measured; this candidate is deliberately bounded, NOT robust to arbitrary transients.
- A ±100nA raw-FB sensitivity instead of assumed ±50nA produces peak15.021841 V: **FAIL**. Thus R60's increase is not release-approved until FB uncertainty and real raw extrema are resolved. Safest first diagnostic fitting is the tightened dividers with R60 retained150k; only evaluate180k under controlled monitoring if needed. No new guaranteed current follows from either configuration.
- MID becomes4.908590 V nominal,4.620203–5.212565 V DC,5.312565 V allocated peak;187.435mV to5.5 V. Count4.520203 V after an allocated dip for current calculations. Reduced MID slightly worsens inverter current capability. At the old conservative27.631uF screen, TI crossover estimate is39.95kHz—barely below40kHz, not a loop proof. Do not lower MID further blindly.
- All capacitors retain25 V rating. Worst modeled inverting switch span MIDmax+|NRAW|max≈20.25 V, below24 V absolute differential; switching ringing still unmeasured. TPS65131 ±17 V absolute rail limits are NOT design targets.

All changed resistor dissipation is small: raw divider current under≈9uA gives R14<0.14mW and R60<0.016mW, R15<0.013mW. Final divider current≈120uA gives R72<1.4mW and R74<0.15mW; MID divider<55uA gives R9<0.31mW and R84<3uW. Individual voltages <15 V vs catalog75 V for0603 parts; precision manufacturer spec sheets confirm0.1%,25ppm/K,75 V. Values/rating/footprints still require native synchronization after authorization.

## Separate failure mechanisms and capacitor disposition

**Dropout/current starvation:** Monitor |NRAW|-|N12| and converter peak current together. Nominal headroom is already1.91 V in043, so low-current bench fluctuations cannot automatically be attributed to the0.178 V independent extreme. Converter overload, PD/eFuse retry, thermal behavior or layout/loop response may instead pull raw voltage down. An LDO cannot reject input variation when out of regulation.

**Capacitance and loop:** C54–56/C67 input and C57–59 output use exact Samsung CL31A226KAHNNNE/C12891 (22uF25V X5R1206). Fresh manufacturer DC curve matches the stored point set. Existing screen multiplies typical bias by0.90 tolerance×0.85 temperature×0.95 aging allowance: four input caps at15 V give12.359uF; three negative output caps at12.9 V give11.400uF. These only narrowly exceed TI's10uF minima; 47uF is recommended for AC performance. C9 local raw cap screens≈3.090uF at15 V; at150mA,≈30mVpp capacitive switching ripple before ESR/transients. Remote U13 input caps are not ideal local U4 AC capacitors.

The manufacturer also shows AC-level sensitivity: at0.01Vrms, zero-DC curve is-16.577%. Multiplying that as a **sensitivity only**, not a validated combined curve, lowers negative output screen to9.510uF. Thus the old cap screen is not assured under real low-ripple bias. If measured biased capacitance/AC tests fail, the smallest first capacitor contingency is one additional C12891 directly at U13 OUT/GND, raising3→4 caps (15.200uF original screen;12.680uF with this AC sensitivity). New ref/location must be allocated after migration. Do not add speculative compensation or wholesale capacitor banks now. Four input caps similarly screen≈10.31uF with the AC sensitivity, leaving little margin. C12891 was live-observed Basic+Economy eligible; no stock reservation or lifetime guarantee.

Keep U4 C10=4.5pF, C11=4.3pF, C12=220nF reference bypass, C13=10nF CP, C14=4.7nF CN; these follow TI §§8.2.2.6–8.2.3. Candidate C11 calculation7.5us/1.78Mohm=4.21pF is close to4.3pF. U4 PSN/PSP are grounded (power-save disabled), so do not diagnose its behavior as configured PFM. TPS54302 can pulse-skip at light load. No loop measurements exist.

**C62/start-stop:** TPS7A33 §8.1.4 expressly says CFF is not required for stability, making DNP a supported diagnostic option; removing it trades noise/PSRR/transient performance for removing this capacitive FB-kick path. It is not claimed to cure steady-state oscillation. A rapid N12 return toward0 can transfer up to120nC through10nF and push FB positive; divider Thevenin≈9.02k and RC≈90us do not bound instantaneous injection. FB-GND must stay-2..+0.3 V, and FB/OUT/NR relative IN must respect-0.3 V lower bounds. Do not copy TPS65131's10–100k feedforward series-resistor recommendation onto this different LDO. No unverified Schottky clamp VF/injection guarantee. C61 remains100nF (roughly120ms typical startup), C60 remains1uF. D27/D28 SS34 are external discharge paths, not reverse-current isolation or proof of0.3 V protection. Unplug/retry/raw collapse, external backdrive and output shorts remain validation gates.

## Current, power and thermal envelope — provisional only

Start no-load/25–50mA, then investigate at **+12 V200mA (2.4W), -12 V150mA (1.8W), simultaneously**, reserving independent +5 V250mA (1.25W). These are unmeasured targets at roughly25C ambient, not ratings. Beyond that, **+300/-200mA** (3.6W/2.4W) is a conditional characterization extension, not a release target. Approximate individual design ceilings under the pessimistic screen are **+350mA OR -250mA**, not both together with the +5 reservation and not ±350mA.

`candidate-arithmetic.json` holds separate-positive, separate-negative, simultaneous and extension calculations. Assumptions: minimum MID4.520203 V, raw magnitudes14.284851/14.932380 V; +2mA/-7mA raw-current overhead allowances;85% MID/P5 buck efficiency,75% boost and70% inverter efficiencies;0.15W auxiliary budget. These are explicit loss budgets, not guaranteed efficiencies. PD8.55 V is an assumed-5% supply corner; deduct0.15 V wiring and eFuse0.25ohm maximum modeled on-resistance. Requires a genuine9 V PD contract with sufficient current; CH224A requesting9 V does not prove the adapter's capacity.

| External rail loads | Output watts + / - | PD current screen incl +5 reserve | MID current | LDO corner watts + / - |
|---|---:|---:|---:|---:|
| +200mA only |2.4 /0|0.786A|0.884A|0.535 /0.079|
| -150mA only |0 /1.8|0.696A|0.749A|0.018 /0.577|
| +200/-150mA |2.4 /1.8|1.263A|1.592A|0.535 /0.577|
| +300/-200mA |3.6 /2.4|1.720A|2.249A|0.793 /0.743|
| +350/-250mA together |4.2 /3.0|**2.038A — reject**|2.696A|0.922 /0.909|

R8+R79+R80=6.04k => nominal eFuse12000/6040=1.986755A. Illustrative±5% IC scale plus full resistor factors gives1.850228–2.128449A (exact6.04k/9 V behavior still requires verification; table has other setpoints). Do not allocate17.88W as guaranteed usable outputs. At lower supply/high resistance the approximate protected-bus budget at1.85A is14.69W, shared by both bucks and all losses.

TPS65131 p5:1.95A is **typical switch peak**, not output current.1.8A minimum is specified atVIN3.6 V (boost alsoVPOS8 V), not a newly verified bound at our corners. p13 Eqs3/4 estimate peaks:

    ILpk+ ≈ VRAW+ * IRAW+ / (VMID * 0.64)
    ILpk- ≈ (VMID + |VRAW-|) * IRAW- / (VMID * 0.64)

At+200/-150 target these give0.997/1.056A. At+300/-200 give1.491/1.392A. At+350/-250 give1.738/1.728A, very close to the conditional1.8A screen before dynamic margins. At-350mA alone, the negative estimate is≈2.40A: reject. Inverting output-current arithmetic is not boost arithmetic.

Independent explicit CCM cross-check uses4.7uH-20%=3.76uH,1.25MHz minimum,0.5 V diode assumption, switch resistances0.30/0.62ohm and inductor DCR40.30mohm maximum×1.4 hot allowance. Solve volt-second balance including resistive losses, Iavg=Iout/(1-D); ripple=(Vin-Iavg*(Rswitch+RL))*D/(L*f); peak=Iavg+ripple/2. At initial target: duty0.707/0.794, ripple0.643/0.677App, peaks1.010/1.102A. Not close to87.5% typical duty cap, but waveform/operating bounds are not guaranteed. Light-load rows flagged DCM are not physical CCM predictions. CENKER's table lists4.97A Isat/3.30A Irms, but DC/temperature-dependent inductance and magnetic loss remain unqualified; its31mohm is **typical**,40.3mohm maximum.

MID buck L1/L4=6.8uH±20%; at290kHz minimum and9.45 V input, ripple can approach1.50App. Extension MID load2.25A implies≈3.0A peak (below the4A high-side minimum table condition), but regulator/inductor thermal dissipation can bind first. No unrestricted3A rail promise.

Thermal: use Tj=Ta+P*theta_eff only as sensitivity, with40–80C/W for each LDO, not JEDEC32.5/33.7C/W as board measurements. Four copper layers/thermal pads do not establish theta_eff. At initial target with80C/W: Tj≈68/71C at25C ambient,93/96C at50C. At extension:≈88/84C at25C,113/109C at50C. Nearby X5R body must stay<=85C independently. Ground-current allowance5mA negative is not a full-temperature maximum. MID buck budget dissipates1.27W initially/1.79W at extension with85% efficiency; this is a serious thermal gate. TPS65131 die conduction plus unmeasured0.25W switching allowance screens≈0.66W initially; diode/inductor/converter total losses are not all dissipated inside U4. Verify copper/airflow/case coupling before any sustained rating.

### Startup/inrush screen (not a timing guarantee)

C3 remains100nF. TPS2660 p7 gives4.7uA typical dVdT current and24.6 gain: nominal VPROT slope≈1156 V/s, roughly7.8ms to9 V. Nominal local VPROT bulk C4+C5+C18+C68+C69=98uF draws≈0.113A while ramping, before running converters. A screen using5.5uA×25.5 gain, C3×0.9 tolerance×0.85 temperature, and bulk×1.1 gives≈0.198A; combined effects/AC bias still unmeasured. Startup input load and retry timing need checking, not just steady-state power.

Each raw rail has110uF nominal (C8/C9 plus its four LDO-input parts), whose low-voltage capacitance is much larger than its15 V effective value. Forcing110uF to14.17 V in1ms would require1.56A **rail** charging current, already beyond the inverter; TPS65131's≈1ms soft-start current-limit ramp is NOT a1ms output-rise guarantee. At120ms LDO startup, nominal66uF N12 charging averages≈6.6mA, in addition to external load. Keep initial downstream load low during startup; test full-load/retry explicitly. Raising NRAW modestly adds startup energy and inverter duty, not capacity.

## Reproducible corner equations

All resistor extremes independently enumerated, no RSS or assumed matching:

    Basic factors B = [0.99*(1-100ppm*100K), 1.01*(1+100ppm*100K)]
                    = [0.9801, 1.0201]
    Precision P = [0.999*(1-25ppm*100K), 1.001*(1+25ppm*100K)]
                = [0.9965025, 1.0035025]
    NRAW magnitude = VREF*(RT/RB) - VFBN*(1+RT/RB) + IFBN*RT
    VREF=[1.200,1.225], VFBN=[-0.024,+0.024], IFBN=±50nA ASSUMED
    candidate RT=1.6M*P +180k*B; RB=150k*P+2.4k*B
    N12 magnitude = 1.175*[0.975,1.025]*(1+RT/RB) + IFB*RT
    RT=90.9k*P+1.2k*B+[0,0.1ohm], RB=10k*P; IFB=±100nA
    MID=[0.581,0.611]*(1+100k*B/(13k*B+820*B))
    Headroom = min(raw DC)-0.100-max(final target)
    Peak raw = max(raw DC)+0.100
    Pbus = (VRAW+*(I++0.002)/.75 + |VRAW-|*(I-+0.007)/.70)/.85
           + 5.418152*.25/.85 +.15
    Pbus = I_PD*(8.55-.15-.25*I_PD)

The100K resistor envelope is conservative; X5R is only-55..85C and does not inherit125C capability. Do not multiply0.8 V by current ratio. No full-temperature raw-FB bias bound or measured loss/thermal/loop result was obtained.

## Focused next validation and implementation gate

Fresh chat must first verify migration completeness and exact accepted/native parity, then obtain authorization and sourcing-policy decision. Synchronize native schematic/PCB fields, generator constants, BOM, tests, budgets and descriptive evidence together; no CSV-only swaps. Do not weaken tests, strip3D dependencies, or overwrite historical release evidence. Use common private check/native ERC/DRC and exact pin/net/NC/field parity; no production export until separately authorized.

For bench: current-limited known9 V PD source, no external backdrive. Measure VIN9/VPROT/MID/PRAW/NRAW/P12/N12 simultaneously enough to distinguish regulator dropout from eFuse retry/PD droop. Start unloaded then25–50mA; test each rail separately, then+200/-150 with+5 loaded250mA. Check fast0↔target steps, low/high input, warm board, startup/unplug/retry. Capture U13 FB/NR/IN/OUT with appropriate probes for absolute/differential limits. Characterize C62 fitted vs DNP without claiming either is proven quiet. Measure biased effectiveC, ringing/noise/PSRR, raw peak/trough and U3/U4/U12/U13/capacitor temperatures. Increase only after this passes; abort for raw magnitude approaching15 V, MID approaching5.5 V, repetitive limiting, rail tracking, sustained ringing, or thermal/capacitor limits. Current/load reduction is the first fallback, not more raw voltage.

No fresh native ERC/DRC or bench proof was claimed. Common `pcb inspect --config tools/kicad-project.json` failed closed on unsupported3D/embedded/image dependency handling (`pcb-inspect.json`); dependencies were not removed. Narrow Git-native text/pad inspection used the existing common exporter parser, not a new exporter. Relevant workflow/assembly skills, README/API docs and actual CLI help were read.

## Manufacturer and catalog provenance

Downloaded documents, text extracts and exact URL/retrieval-UTC/SHA256 are retained in `download-provenance.json`. Key sections:

- TPS65131 SLVS493E pp4–6 (operating/absolute/table limits), pp13–16 §§8.2.2.2–8.2.3 (peak estimates, inductors, capacitors, feedforward), p27 thermal: https://www.ti.com/lit/ds/symlink/tps65131.pdf
- TPS7A33 SBVS169D pp5–6 (absolute,10uF,dropout,accuracy conditions), p14 dropout, pp15–16 §§8.1.1–8.1.4: https://www.ti.com/lit/ds/symlink/tps7a33.pdf
- TPS7A47 electrical/thermal tables pp5–6 and §7.2.2: https://www.ti.com/lit/ds/symlink/tps7a47.pdf
- TPS54302 electrical table p5, pp17–18 Eq14/crossover and compensation: https://www.ti.com/lit/ds/symlink/tps54302.pdf
- TPS2660 pp7–8 ILIM/RON, slew/startup sections: https://www.ti.com/lit/ds/symlink/tps2660.pdf
- SBVA042 §2.3 p8, positive-LDO shutdown analogue, NOT a TPS7A33 clamp guarantee: https://www.ti.com/lit/an/sbva042/sbva042.pdf
- Samsung exact family characteristic data (25C,120Hz,0.5Vrms DC curve): https://product.samsungsem.com/mlcc/CL31A226KAHNNN.do
- Yageo exact one-page spec sheets: https://yageogroup.com/component-documentation/download/specsheet/RT0603BRD07150KL ; https://yageogroup.com/component-documentation/download/specsheet/RT0603BRD0790K9L ; https://yageogroup.com/component-documentation/download/specsheet/RT0603BRD0710KL
- CENKER CKCS6045 manufacturer table p2: https://www.cenkersz.com/file/upload/product_series/SMD_Power_Inductor_CKCS6045_Series.pdf

Seven bounded live common-tool lookups are in `catalog-C*.json` and `catalog-raw/`. Each includes observed per-part Economy eligibility, exact MPN, source URL, request, timestamp and raw hash; all seven were Economy-eligible observations, not authenticated order acceptance. C12891/C21189/C23253 were Basic; C22827 was Preferred Extended; precision codes were Extended. No broad stock scan or stock guarantee. Fresh eligibility/quantity/attrition/manual preview remain release gates.
