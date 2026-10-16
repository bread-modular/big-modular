# Circuit / A4.2 mechanical acceptance matrix — NOT executed on hardware

Only the structural checks in `reports/` were executed. All tests below remain pending; use dummy loads only after fabrication blockers are resolved.

| Input / condition | Required outcome |
|---|---|
| Attach at 5 V, RUN open or closed, PG high or forced low | Negotiation housekeeping only; eFuse must not enable converters. Measure residual VPROT and all rails. |
| Non-PD / failed PD / missing 9 V fixed PDO | No useful rail output; remain off. No manual low-voltage override exists. |
| Valid fixed 9 V PD at >=0.5 A, PG high, RUN closed | Off. |
| Valid fixed 9 V PD at >=0.5 A, PG low, RUN open | Off. |
| Valid fixed 9 V PD at >=0.5 A, PG low, RUN closed | Controlled VPROT ramp, then 4V, then preregulators/LDOs; start with no load, ramp toward provisional ~40mA EACH simultaneous only after stability/thermal checks. Not a rating. |
| 9 V injected without a PD contract, or PG stuck low | The existing PG/window gate cannot distinguish this from compliant PD: FAILS strict contract-proof requirement; fabrication blocker. |
| Insufficient negotiated current or wrong PDO indication | Must remain off in the final design. Current CH224K PG cannot establish this: fabrication blocker. |
| Sustained 15/20/21 V with RUN closed and PG forced low | OVP holds eFuse off; upstream VBUS remains live. No TVS fitted; surge safety is unqualified. |
| Brownout, detach, reset, contract loss or renegotiation | PG/UV/OV shutdown response and residual stored energy measured; no uncontrolled restart or >5 V precontract converter output allowed. |
| Short/load step/all rail combinations | Check input authorization, eFuse current tolerance, thermal retry, rail asymmetry, overshoot and LDO dropout. |
| Reverse power at outputs | Check no USB backfeed, LDO stress and wrong-polarity clamps; not established by ERC. |
| Hot plug / CC ESD / VBUS surge | Define waveform/energy/source impedance first; select and coordinate protection before testing. Present design has no qualified solution. |
| Rail screws + adjacent 2HP panels | Round dia3.2 holes X2.42 = X7.50 minus one 5.08mm pitch. Test common fixed-strip phase, actual rail thread, neighbouring head clearance and the 0.82mm FR4 web. |
| Two plain M3 L brackets | 3mm legs, M3x8 front and countersunk M3x8 side, loose M3 nuts. Countersink PRINTED PLASTIC only. Trial ABS shrinkage, flush seating and 0.125mm nominal front-nut/upright clearance. |
| Post-solder M3 service | Main PCB remains soldered/fitted; front nut held with small pliers from +X, side nut driver from +X, screws driven from -Z/-X OUT OF RACK. Test actual tools. |
| USB aperture | Native J1 unchanged, but assembly X shifts to 6.43. Test cable shells/overmould, aperture and insertion/cable torque. |
| J7 landing / J2 keyed output / ribbon cable | Meter all 16 positions and polarity; pins13-16 NC. Verify 2.54 contact versus 1.27 ribbon pitch, copper wire, insulation, strain relief, mating key and case-dependent connector/bend clearance. Never parallel a live PSU. |
| LED | Fit actual 3mm THT lamp in dia3.6 opening, form leads with jig, inspect manual joints, select resistor and integrate circuit. Not an all-rail-health indicator. |
| Reset switch | TL3340AF160QG SMT. Trial fine-tip soldering of all five lands; verify pins1+3 common / pin2 opposite, isolated anchors and two Ø0.9 locator holes. Check body clearance, Ø3.2 opening X6.4 and recessed tip Z2.05. No reset circuit yet. |
| Reduced carrier power-layout fit | Complete deliberate placement and thermal/clearance review before routing; 30mm outline alone does not establish converter fit or safety. |

Bench instrumentation must independently verify PD PDO/current messages; measuring 9V alone does not pass. No cryptographic authentication or USB compliance certification is implemented.

## Retired TS-1166VW-type alternative (not selected / not installed)

Only if deliberately reconsidered in a future revision: the supplied row2.50/4.50-signal pattern must be sample-checked against the
conflicting row2.15 public drawing. Confirm H reference, all four solder holes and
case-tab continuity; resolve the 7.1-versus-5.1mm lateral fit before updating the
main PCB, panel opening or brackets. The isolated coupon DRC is not a module-fit
pass. See [switch analysis](ts1166-switch.md).
