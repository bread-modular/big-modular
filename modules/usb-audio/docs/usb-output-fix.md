# USB routing / output-resistor repair — carrier S3/R3, MCU S1/R2

Scope approved by the user on 2026-10-24: fix USB and R36/R37 only; leave the other
review findings unchanged for now. No commits, orders, uploads or supplier acceptance.
Panel, mechanical placements, MCU pins, codec, regulators and mute arrangement are unchanged.

## USB

The old connector-side D+ net contained three vias in a branched network, but **each
active orientation used two**. D- used zero. Comparing the two nets' *total copper*
was not a valid path-skew measurement. The corrected layout adds two transitions
on D-, retains the connector geometry, and checks the actual A6/A7 and B6/B7 paths
separately. There is no pin swap or component move.

- Both polarities now have **two through-vias per active connector-to-ESD path**;
  U102-to-U101 remains on F.Cu with zero vias.
- F.Cu references In1 GND. All B.Cu USB segments reference a new, stitched
  **In2 GND island**, not +3V3. In1 GND, In2 +3V3 and the new island each remain one
  filled polygon. No signal traces were added to an inner plane.
- The VBUS cross-strap was moved above the connector, and U102's VBUS via was moved
  into the clear space between its two pad rows (0.50/0.30 mm via, **not in a pad**).
  This removes the VBUS antipad from underneath the converging USB pair.
- `USB_HS` now covers all four USB nets on both sides of U102. Single-ended
  connector/package fanouts use 0.40 mm tracks; coupled MCU-side routing uses
  0.30 mm tracks / 0.20 mm gap. Ordinary 0.20 mm clearance is preserved.
- The MCU PCB now explicitly records **JLC04161H-7628**, nominal 1.6 mm, 0.035 mm
  outer copper, 0.0152 mm inner copper, 0.2104 mm outer prepregs (Er 4.4),
  1.065 mm core (Er 4.6). Solder mask is recorded as 0.01524 mm / Er 3.8.

| Orientation | D+ planar length, connector + MCU sides | D- planar length | Mismatch |
|---|---:|---:|---:|
| A6/A7 | 8.91135 mm | 9.32556 mm | 0.41421 mm |
| B6/B7 | 12.72556 mm | 12.50092 mm | 0.22464 mm |

The two vias add the same nominal 3.2 mm vertical length to every active path.
U102 package-internal delay is not included. Its two paths use the same package.
The MCU-side planar paths are 3.02745 mm each.

`tools/check_usb.py` independently checks these four paths, a 0.5 mm mismatch bound,
transition counts, USB class assignments/widths and the physical stackup. It samples
all USB trace centerlines and edges against the filled ground-reference polygons
at 0.05 mm intervals, except a bounded 0.7 mm neighborhood around the signal vias'
necessary antipads. The original board is a failing negative control. This check
is additional to, not a replacement for, full native ERC/DRC/parity.

### Impedance target and limits

Nominal IPC-2141-style estimates, dimensions in mm:

```text
Z0 = 87 / sqrt(Er + 1.41) * ln(5.98*h / (0.8*w + t))
Zdiff = 2*Z0 * (1 - 0.48*exp(-0.96*s/h))
h = 0.2104; t = 0.035; Er = 4.4
0.40 mm uncoupled fanout: Z0 = 45.67 ohm
0.30 mm coupled traces, 0.20 mm gap: Zdiff = 88.62 ohm
```

These are **nominal uncoated estimates**, not a 2-D/3-D field solution or measured
impedance. Connector branches, pad escapes, the short converging sections, vias,
solder mask and package internals are discontinuities. Specify the named stackup
and a **90 ohm differential / 45 ohm single-ended USB target** to the fabricator;
obtain their impedance/process confirmation before claiming controlled-impedance
production. Do not substitute an arbitrary four-layer stack. USB HS eye/functional
testing in **both plug orientations** remains a prototype test, not an automated pass.

References checked for this change:
- [JLC stackup and material parameters](https://jlcpcb.com/impedance)
- [TI USB layout guidance, section 5.3](https://www.ti.com/lit/ug/sllu149e/sllu149e.pdf)
- [ST USBLC6-2 pinout and flow-through layout](https://www.st.com/resource/en/datasheet/usblc6-2.pdf)
- [Nominal impedance equations](https://prototypeguru.com/microstrip-impedance-calculator-ipc-2141/)

## R36/R37 output fault-power sizing

Keep the existing **1k output resistance** without adding an Extended R/C part:

| Output | Parallel network | Each physical resistor |
|---|---|---|
| OUT1 | R36 || R38 | 2k, 1%, 0.25 W, 1206 |
| OUT2 | R37 || R39 | 2k, 1%, 0.25 W, 1206 |

All four are **UNI-ROYAL 1206W4F2001T5E / C17944**. The shared exact-code live lookup
confirmed Basic and Economic eligible. The native circuit table, schematic,
footprint fields, BOM and CPL use this exact part. New R38/R39 sit on B beside their
partners; no existing component moved. Two F-side jumper tracks with dogbone vias
complete the parallel connections; all SMD assembly remains on B.

- Effective rating: **1k / 0.5 W** per output at ambient <=70 C; not 0.5 W per part.
- Original observed fault (+5.2 V output, -12 V patch): 17.2 V across each network,
  **0.14792 W nominal per resistor**, rather than 0.29584 W in one 0.25 W part.
- Sizing margin (not a new rail guarantee): output magnitude <=5.5 V, external
  patch magnitude <=12.6 V. Each resistor sees the **full 18.1 V**, not half.
- At 1% low resistance: 18.1^2 / 1980 = **0.16546 W per part**. Including the
  catalog's 100 ppm/C TCR over -40..85 C gives <=**0.16655 W** per part.
- Uni-Royal's normal chip-series derating is 100% through 70 C, then linear to zero
  at 155 C: a 0.25 W part allows **0.20588 W at 85 C**. The resistor-only calculation
  therefore has margin. Nominal 25 C parallel tolerance corners are 990 / 999.9 /
  999.9 / 1010 ohm; current sharing is checked per member, not assumed exact.
- Unlimited rail-to-rail faults, unpowered back-drive and arbitrary sustained
  saturation are **not** guaranteed. This is a resistor-sizing repair, not system
  fault certification. The previously deferred startup/mute behavior is unchanged.

### U7 heat is still a bench qualification

The unchanged 1k effective resistance does not reduce the op-amp's fault current.
For nominal +/-12 V supplies and a +/-12 V external patch, worst output-stage
DC dissipation is about 12^2/990 = 0.1455 W/channel near zero output. At a conservative
+/-12.6 V margin, this is 0.1604 W/channel. With both channels faulted, maximum
quiescent current and the datasheet's 144 C/W SOIC thermal metric, the illustrative
rise is about 66.5 C; **simultaneous faults at 85 C are not qualified**. Actual PCB
thermal resistance differs from the datasheet test board. Screen one- and two-channel
faults, U7 temperature and resistor temperatures on the prototype. No changed
resistor rating is presented as proof of whole-module thermal safety.

References:
- [Exact supplier part](https://jlcpcb.com/partdetail/18632-1206W4F2001T5E/C17944)
- [Uni-Royal normal chip-series datasheet: 1206W4 rating, dimensions, derating](https://datasheet.octopart.com/0603WAF4702T5E-Uniroyal-datasheet-182172491.pdf)
- [TI OPA1678: current/thermal information](https://www.ti.com/lit/ds/symlink/opa1678.pdf)

## Verification and export handoff

Persistent compact results and exact source hashes: `usb-output-fix-verification.json`.
Both final shared checks report ERC 0 / DRC 0 / unconnected 0 / parity 0 / exclusions 0,
and current manifests/mirrors match. All original carrier tracks remain unchanged;
MCU copper edits are confined to USB/VBUS plus one ground stitch/island. Native save
only normalized the hidden Note font thickness of J102/J103; their geometry is unchanged.

Raw native checks, live catalog evidence, before/after comparisons and renders are
in ignored `research/usb-fix/`. Re-run from the repository root:

```sh
python3 -B modules/usb-audio/tools/check_usb.py
python3 -B modules/usb-audio/tools/check_edges.py
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-audio/tools/kicad-project.json --reports <new-carrier-report-dir>
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-audio/tools/kicad-project-mcu.json --reports <new-mcu-report-dir>
```

The matched fabrication sets are `jlcpcb/main/` and `jlcpcb/mcu/`; see their parent
README for upload files, current source hashes and the unchanged deferred gates.
The panel fabrication files are unchanged. This scoped repair is not an assertion
that the previously deferred regulator/mute/firmware/assembly/bench work passed.
