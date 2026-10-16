# Validation matrix — MCU-free electrical prototype

| Gate | Scope / required evidence |
|---|---|
| Source and native ERC | Current hierarchy/local libraries; no exclusions added |
| Electrical connectivity | Independent pin roles, six complete sense paths, protection/feedback wires, exact intended native delta |
| Pin/pad mapping | Every assigned footprint, actual numeric pin IDs/coordinates; J8 pin1/key/20-pin cable continuity |
| No controller / reset / disconnect | No-debug operation; PG+UV/OV hardware gate, MID-derived BI enable; dynamic leakage/discharge unqualified |
| Optional debugger | 3.3V Hi-Z/sink-only, no external pullups/AUX drive in ANY powered/off/boot state |
| PD/window | Fixed9V/current/status freshness and real-source fault injection; hardware rejects fallback/overvoltage |
| Sequence / fault | MID/2 EN thresholds, startup/shutdown and residual rails; no precision sequencing/all-rail supervision |
| Sensing | Actual ADC load/acquisition/reference, offset/leakage/Vf/temp, wrong polarity/residual rails/off-state injection |
| Power stage | Fuse/I2t, inductors/caps, MID overshoot, compensation, noise, load/thermal and continuous-current limits |
| PCB / mechanics | Only D11/D12 and two holes removed; D10 geometry/other mechanics preserved; later placement/sync/routing/fit needed |
| Manufacturing | Blocked; no Gerbers/CPL/orders/uploads authorized |

[Verification checkpoint](electrical-validation.md) lists checks actually run;
other rows are requirements, not claimed test passes. JP1 remains OPEN.
