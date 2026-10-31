> **Superseded (2026-11-01):** BASE routing is finished (0 opens); see [final record](/modules/usb-power-45w/docs/r3-base/final/README.md). Kept as history.

# BASE R3 routing handoff - 25 opens (2026-10-31)

Internal transfer checkpoint for a focused completion pass. Mission remains: FINISH (0 opens).
Not a release, not a stop request.

## State

- Board: `hardware/base/usb-power-45w-base.kicad_pcb`
  sha256 `3058a7674e8cbc9be68ef285dd7c942790fde58a328e663c30252684a678d460`
- Native `kicad-cli pcb drc --schematic-parity --severity-all` (no refill): 0 violations, 0 parity,
  **25 unconnected**, 0 exclusions. Last full refilled check (checkpoint 4): same counts;
  `check_support_copper.py base --refill` 0 problems; 9 unit regressions pass; check_stack ERC 0 x3,
  aggregate netlist exact, problems []; via-in-SMD-pad/mask 0; In1 tracks 0; no zero/dup/dangling;
  all zones one piece.
- TOP: finished on main 4eb072f, untouched here.
- Manual batches: `tools/route_base_r3.py`, `route_base_r3_batches.py`, `route_base_r3_final.py`
  (shared plan/apply; do not replay batch IDs; add new unique IDs).

## 25 open connections (native DRC, net: count)

| Net | # | Endpoints still unjoined |
| --- | --- | --- |
| /LED_RETURN | 4 | Q10.3 (68.69,81.25), Q6.2 (76.53,92.38), Q7.2 (83.03,92.38), Q8.2 (84.64,88.55), Q9.2 (133.10,97.89) |
| /P12_OK | 3 | U14.2 (62.77,66.45), Q7.1 (84.93,92.38), TP12 (88.75,75.66), XB2-side track (134.75,71.08) |
| /P5_OK | 3 | U14.4 (62.77,69.00), Q8.1 (84.64,90.45), TP13 (90.95,75.66), XB2-side track (131.80,72.42) |
| /RUN | 2 | U14 track (67.72,70.27) - B (61.90,74.90); west RUN (76.19,67.90) - east RUN (118.25,71.28) |
| /N12_OK | 2 | U14.5 (62.77,70.27), TP14 (100.65,75.66), east track (131.20,97.89) |
| /V20_OK | 2 | west track (74.92,65.72), TP15 (98.45,75.66), east track (118.95,67.17) |
| /MAIN_OK | 1 | west track (84.47,73.00) - XB2.2 (133.54,67.33) |
| /MAIN_LED_OK | 1 | west track (73.65,65.72) - Q6.1 (78.43,92.38) |
| /BAD_FILTERED | 1 | U13.5 (74.92,70.67) - U15.4 (92.64,86.85) |
| /NOT_FAULT | 1 | U13.2 (71.11,70.67) - U12.8 (101.28,94.61) |
| /ANY_BAD | 1 | U14.6 (62.77,71.53) - R72.1 (91.90,93.22) |
| /NOT_RUN | 1 | U14.8 (67.72,72.81) - Q5.1 (124.91,98.15) |
| /VPD | 1 | R83.1 (87.05,67.17) - VPD track (81.50,81.10) |
| /MON_20 | 1 | R83.2 (87.05,65.53) - B track (133.40,92.88) |
| Net-(D18-K) | 1 | D18.1 THT (96.98,97.91) - Q9.3 (132.15,96.01) |

Full list: `open-final-ckpt4.txt` (identical set).

## Done and to preserve

- **U8 (LM5067) complete**: all pins routed. U8 (116.95,89.3). Gate pin 8 F straight to Q4 gate;
  N_SENSE_PIN under body to pin 7 (R89 filter and shunt Kelvin pickups unchanged); OUT pin 9 one
  0.5/0.3 via in U8-Q4 gap; PGD pin 10 to U17; N_UV, N_OV, N_VCC (incl. one short In2 V3V3-island
  power-only hop to R51, plane still one piece), N12_RAW quiet reference (C43/C44/R53/R55/D20/U16.3).
  Moved/rotated: C43 (115.3,91.95,180), R90 (118.4,91.95,180), R57 (118.6,80.25,180),
  C44 (120.95,91.5,-90), R55 (122.55,91.5,-90); D20 (111.95,89.5,90) unchanged.
- **Negative Kelvin/power**: Q4 (123.75,83.45,90) tab -12V, R48/R49 pickups at shunt pads, N12_RAW
  vs GND vs -12V distinct, U5 EP = GND, D10 VPD/EF_IN distinct. Keep broad pours/multi-vias.
- **LED drivers relocated near LEDs** (driver pads >= 2.0 mm from LED pads, 1 mm edge OK):
  Q6 (77.48,93.32,-90), R22 (80.02,93.4,-90), Q7 (83.98,93.32,-90), R86 (86.52,93.4,-90),
  Q8 (83.7,89.5,180), R87 (86.6,89.5,90). LED K/A links and V3V3 links routed.
- Fixed, never move: J1, SW1 (MP off-centre 1 mm track legal), LEDs, J2, XB1/XB2 positions/nets,
  outline, 5 supports + keepout sectors, brackets. No new B parts, no value/package/schematic change.

## MHB2 corridor (the remaining work)

West logic: U13 (73.65,68.195,90), U14 (65.25,68.995,0). ~13 nets above must leave eastward/southward.
MHB2 keep-out x78.35-85.55, y63.97-71.18. Fences: north edge (one free B lane ~y63.45-63.6),
MHB2 keep-out, In2-VIN/USB-PD power area + pours to the south, west edge.

Own copper in/near the band (all this mission, **may be ripped/re-laid**):
- TIMER_GO F north over MHB2 at y63.775 (W3-timer).
- FAULT_CLK B diagonal (78.4,73.075)-(83.2,77.875) then under U12 (W5-faultclk).
- MAIN_OK B diagonal (76.2,74.2)-(78.0,72.4) + B y72.4; ARMED B y71.875.
- RESET_N: under U13, short F hop (79.3-80.95, 70.9-72.0) south of MHB2, B diagonal past D9 to
  (84.7,75.6), via (89.3,80.2) west of XB1.
- VPD_U1 B x78.85 (y74.75-80.5); PD_BASE B x72.9.

Options (authorised, none tried to completion): rip FAULT_CLK/MAIN_OK diag and lay parallel B lanes
y71.45..74.25 at ~0.4 mm pitch south of MHB2 plus F lanes where only THT sits; take status nets
north between J2 pins or south past XB1; relocate the AI-placed U13/U14 + passives toward U12/U15
and re-route the block. The one-connection helper's NO_PATH results are local search results with
current copper, **not** proof of impossibility.

R83 (87.05,66.35,90): VPD feed and MON_20 east still open; D18-K THT (96.98,97.91) to Q9.3.

## Rules (unchanged)

Strict 1 mm edge except named pads; 2 mm SMD to front soldered connector pads; no vias in SMD
pad/mask (EP thermal only); no In1 tracks; In1 GND, In2 VIN left / V3V3 right one piece each;
no DRC/severity/exclusion relaxation; manual one-connection-at-a-time, DRC + parity + support
check after every batch; no autorouter. Final: 0 opens both boards, fresh check_stack, supports,
batch audit, images.
