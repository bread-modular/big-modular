# Big Modular — A0 USB-C PD Eurorack supply prototype

**ENGINEERING PROTOTYPE — NOT FOR FABRICATION OR CONNECTION TO VALUABLE MODULES.**

Created using the installed **KiCad 10.0.6** command-line engine and PCB API. This is a pin-connected, seven-sheet circuit proposal with real reference designators, not only a block diagram. It is **not an electrically or thermally validated design**. Exact passive procurement, protection coordination, startup, EMI and mechanical hardware remain incomplete. No prior MOTU M6 architecture was available or presumed. No sibling repository was accessed.

## Open these files

- `hardware/big_modular.kicad_pro`: main project.
- `hardware/big_modular.kicad_sch`: root schematic; six circuit sheets alongside it.
- `docs/schematic.pdf`: exported readable schematic.
- `hardware/big_modular.kicad_pcb`: perpendicular carrier / future power board. **J1 USB-C is the only electrical footprint placed.**
- `hardware/front_panel.kicad_pcb`: separate 2HP FR4 mechanical faceplate; only non-electrical holes.
- `BOM.csv`: prototype components; candidate versus verified LCSC identifiers explicitly distinguished.
- `docs/pin-net-audit.json`: intended connections, including intentional NCs.
- `reports/`: actual KiCad ERC, netlist, DRC and programmatic geometry checks.
- `docs/mechanics.md`: assembly coordinates, depth, tolerances and load path.

**Both boards have zero tracks, zero vias and zero zones.** Pads inherent to the USB footprint are present. There are no fabrication Gerbers or placement files. Do not auto-update either board from the schematic: that would violate the connector-only placement boundary. Full schematic parity is intentionally absent.

## Electrical architecture

```
USB-C VBUS -> F1 -> input TVS + CH224K sink (requests 9 V)
                 -> series reverse-blocking diode -> TPS26600 eFuse
                    [JP1 RUN permission; UV/OV, current limit, controlled slew]
                 -> TPS62160 -> 4.016 V intermediate
                 -> TPS65131 -> +13.9495 V and -13.9495 V preregulators
                    +13.95 -> TPS7A4901 -> nominal +11.9922 V
                    -13.95 -> TPS7A3001 -> nominal -11.9952 V
                    +13.95 -> TPS62125 -> +6.52 V
                                          -> TPS7A4901 -> nominal +5.0007 V
                 -> OFF-BOARD standard 16-pin Eurorack power-out harness
```

The approximately ±13.5 V proposal was raised to **approximately ±13.95 V** to reserve more dropout/ripple/transient margin. +6.52 V implements the requested +6.5 V preregulation. Using a buck from the positive preregulator for +5 V costs another conversion stage, but avoids a 14-to-5 V linear heat load. The +5 V branch **shares the positive boost stage's power budget**; the outputs are not independently rated.

The TPS62125 custom symbol names pin 4 **EN_hys**, left unconnected as its datasheet permits; do not assume it is the same function as TPS62160 AGND. The negative LDO is a real negative regulator: IN/EN at negative preregulator, ground/EP at 0 V, OUT negative. Feedback uses its **-1.176 V FB voltage**, not a positive-LDO formula applied blindly. TPS65131 negative feedback goes to VREF through the lower divider, not ground. Sources and relevant sections are in `docs/design-review.md`.

## Input-source truth table and permission

| Input state | RUN jumper | Result / permitted use |
|---|---|---|
| Generic computer / legacy USB, no enumeration | **OPEN** | Converters OFF; only sink/protection housekeeping. No useful-output or USB compliance claim. Do not close RUN on an unauthenticated host. |
| Dedicated non-PD 5 V source, explicitly approved ≥500 mA and adequate voltage at the port | Closed by operator | Lower-power three-rail bench fallback; tentative simultaneous **20 mA per rail**. Not an established rating. |
| USB-C non-PD with advertised 1.5 A or 3 A | Closed only on approved source | Same conservative fallback; this design does **not decode or exploit** the advertisement. |
| Approved PD charger with a 9 V fixed profile and ≥500 mA available | Closed by operator | CH224K requests 9 V; tentative simultaneous **40 mA per rail** after measured 9 V/valid contract. Current authorization is not inferred from PG. |
| PD unsupported, negotiation failed, charger remains at 5 V | As above | Only fallback budget. PG never raises the hardware limit. |
| Unexpected 12/15/20 V or excessive input | Either | eFuse OV cutoff is intended near 10.9 V; fault coordination must be tested. No higher-power mode is authorized. |
| Brownout / overload / startup failure | Closed | UV/current limit/thermal behavior can interrupt or retry. Outputs may collapse asymmetrically; never assume glitch-free rails. |

The nominal eFuse limit is `12 / 40.2 = 0.2985 A`, **fixed in every mode**, not an advertised rail rating. A provisional +20% error allowance gives 0.362 A with a -1% resistor, plus sink/controller current; this is a screening calculation, **not a guaranteed bound at this uncharacterized operating point**. It is intentionally below the user's 500 mA conservative host ceiling, but **500 mA is not universal pre-enumeration permission**. Default RUN is OPEN. This is **not an automatic safe-host-power product**. A final host-compatible implementation needs actual source-current detection/enumeration and validated total/inrush limits.

No external CC Rd resistors duplicate CH224K's reference circuit. DP/DM on the chip are shorted together and disconnected from receptacle data pins (PD-only mode); there is no BC1.2 or data enumeration. No E-mark simulation circuit is used. CH224K PG is diagnostic only and is not claimed to prove a current contract or safe fallback. Never inject a negotiated voltage into another USB port; this design has one sink receptacle and a series reverse-blocking barrier, not a USB passthrough or MOTU power mux.

## Headroom and power envelope — estimates, not test results

- The 4.016 V intermediate stage accepts both 5 V fallback and 9 V PD after protection, keeping TPS65131 below its 5.5 V input ceiling. If diode/fuse/cable drop puts the eFuse input below approximately 4.2 V, fallback shuts down; specify a good dedicated source, provisionally **≥4.9 V at J1** under load. No guarantee is made at the extreme of USB cable drop.
- Screening ±12 V headroom: take preregulator magnitude -5%, reserve 0.25 V downward ripple/transient, and allow the LDO output +2.5%. `13.9495*0.95 - 0.25 - 12*1.025 = 0.702 V`, versus datasheet **0.600 V maximum dropout**. Only about 0.10 V screening margin remains; resistor/bias tolerances and simultaneous transients need a proper worst-case analysis. This does **not** establish best PSRR or a guaranteed clean output.
- +5 V screening: `6.52*0.97 - 0.20 - 5*1.025 = 0.999 V` versus 0.600 V maximum dropout. Again verify actual ripple/step response and tolerance. During startup or current limiting these headroom assumptions are false.
- At 20 mA on every rail: output power is **0.58 W**; at 40 mA each, **1.16 W**. Assuming 75% bipolar, 85% intermediate and 80% +6.52 V buck efficiency gives about **1.13 W / 2.26 W** converter-chain input before diode and housekeeping losses. Actual low-load efficiency is unmeasured.
- LDO heat at 40 mA each is approximately 0.078 W on each ±12 V LDO and 0.061 W on +5 V, total **0.217 W**. Estimated total loss can approach **1.2 W or more** in PD mode. No thermal layout, copper area, enclosure-temperature or junction-temperature qualification exists. Derate or turn off if bench tests disagree.

These are **provisional simultaneous test-load ceilings**, not independent maximums, and not a promise that a generic 5 V USB host can power Eurorack modules. Please specify required **continuous and peak current on +12 V, −12 V and +5 V**, available source profiles, case depth and acceptable ripple/noise before the real design is finalized.

## MHz switching is not proof of audio cleanliness

TPS62160 is nominally 2.25 MHz and TPS65131 nominally 1.25 MHz. TPS65131 PSP/PSN are grounded to disable power-save mode. **TPS62125 operates up to 1 MHz and uses light-load PFM; the strict always-MHz request is not met.** TPS62160 also changes operating behavior at light load. Unsynchronized converters can create beat tones, low-frequency burst envelopes and demodulated interference. LDO PSRR at MHz is finite; quoted integrated noise is not a system guarantee.

Future routing must minimize hot-loop area, use shielded inductors and physically separated feedback/switch nodes, keep low-noise returns out of switching currents, and use Kelvin sensing. Validate converter LC/compensation with actual MLCC DC-bias derating, inductor saturation and DCR. Test startup, all load combinations, conducted/radiated EMI, cable noise, audio-band spectra and transient headroom. Do not add undamped LC filters without loop-stability analysis. No such routing or measurements were performed here.

## Important incomplete engineering items

- Passive values and required ratings are specified, but many exact MPNs, packages, DC-bias curves, stock and assembly sourcing are **not selected or validated**. BOM is not a purchase-ready JLC order.
- eFuse and LDO current/thermal protection, a series diode, input TVS, and output reverse-differential / wrong-polarity clamps are present. **Independent precision output overvoltage shutdown/crowbar, fault latching of all three rails, TVS/fuse energy coordination and reverse-powered output tolerance are not complete.** A failed LDO can expose preregulator voltage to a module. Do not connect valuable loads.
- BSW is intentionally unused; the positive boost path can prebias before enable. No guaranteed three-rail tracking, sequencing, startup into capacitive loads, or rapid discharge is implemented.
- Case hardware, USB shell capture, cable selection and keyed IDC assembly need physical fit/load tests. Mechanical coordinates are nominal, not a tolerance-qualified assembly.
- The PCB is **not electrically buildable**: only the USB footprint and mounting holes exist. No placement feasibility, loop area, thermals or completed power-board layout is claimed.

## Checks and regeneration

See `reports/validation-summary.md` for final counts and the honest interpretation of warnings. ERC detects connectivity/type issues; it does not prove analog correctness. Board DRC is run without schematic parity and **without zone refill**; missing/unconnected copper is intentional.

```
/usr/bin/python3 tools/build_project.py
kicad-cli sch erc hardware/big_modular.kicad_sch --severity-all -o reports/erc.rpt
kicad-cli sch export netlist hardware/big_modular.kicad_sch -o reports/big_modular.net
kicad-cli pcb drc hardware/big_modular.kicad_pcb --severity-all --format json -o reports/carrier-drc.json
kicad-cli pcb drc hardware/front_panel.kicad_pcb --severity-all --format json -o reports/panel-drc.json
/usr/bin/python3 tools/verify_project.py
```

The generated files themselves are the deliverables and do not require research downloads to open. Local copyrighted PDFs/text/images are excluded by `.gitignore`, never staged, and must not be merged. No commit or merge was performed.
