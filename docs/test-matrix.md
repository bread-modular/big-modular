# A1 acceptance matrix — NOT executed on hardware

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
| Rail screws + adjacent 2HP panels | Verify x=7.5 grid but reject ordinary-head overhang/thin FR4 web until mechanically resolved. |
| Brackets + USB cable + output harness | Check M2 screw availability/engagement, torque, insertion force, plug opening and cable bending. |

Bench instrumentation must independently verify PD PDO/current messages; measuring 9V alone does not pass. No cryptographic authentication or USB compliance certification is implemented.
