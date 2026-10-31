# usb-power-45w R3: BASE board routing finished (prototype checkpoint, not a release)

> **Status (2026-11-01): BASE and TOP are both fully routed. 0 unconnected on both boards. Native DRC
> 0 violations / 0 warnings / 0 exclusions, schematic parity 0. ERC 0 on root, base and top. The
> aggregate base+top netlist equals the S7 root (216 refs, 145 nets).** This is a routed prototype
> checkpoint. It is not factory-ready: no fab export, no order, no 45 W / 54.5 W rating, no thermal
> or connector-current qualification.

This record supersedes the partial BASE reports: `../HANDOFF.md`, `../HANDOFF-25.md`,
`../checkpoint.md`, `../final-progress.md` and `../../r3-base-rescue/HANDOFF-LAST.md`, plus their
`open-*.txt` lists. Those files are kept as history; their open counts are no longer current.

## Boards (SHA-256)

| Board | SHA-256 |
| --- | --- |
| `hardware/base/usb-power-45w-base.kicad_pcb` | `b5f4e6b2bd6284f04f5ae32746b1a0550be3e449fd93dcb3f144de9ab3d82281` |
| `hardware/top/usb-power-45w-top.kicad_pcb` (byte-identical to `4eb072f`) | `922d34ab36596f123d9b7b7c67e7a22c116e14a0e083846d21c92b0f8b1a91eb` |

Starting point: the rescue checkpoint `affdc215` (BASE `bfdbf749...`, 2 opens: FAULT_CLK and NOT_RUN). No
TOP, schematic, rule, `.kicad_pro`/`.kicad_dru` or footprint-library edits. All batches went through the shared
`pcb plan`/`apply` gate with native refill. The writeback proof allows only the deletions and the one
move each batch names. The ops are in `reports/batches/`.

## Final batches

The routing was manual and done one connection at a time. A print-only raster helper only proposed
corridors. In that helper, refillable F/B pours were soft obstacles and pads, tracks, vias, the board
outline and the support keep-outs stayed hard. Every path was hand-tidied to a 0.05 mm grid and
45-degree geometry, then judged by native DRC and refill.

**FIN01, FAULT_CLK (U13.6 to U12.11).** U13.6 was boxed in by the parallel status bus on B.
- FAULT_CLK joins the bus as a new B lane at y 73.8, between P5_OK and P12_OK.
  - It enters through an F dogbone from U13.6 to a via at (69.3, 73.8).
- Bus re-lay, same nets:
  - **P12_OK** moved to y 74.4; its east via moved from (87.8, 73.8) to (87.8, 74.4).
  - **MAIN_LED_OK** moved to y 74.95.
  - **TP8** (GND test point) now ties to U14.7 GND on F instead of its own via at (68.2, 75.2), which blocked the new lane.
- FAULT_CLK leaves the bus at x 88.4. It hops V20_OK on F, passes between the XB1 pins at x 91.95 and runs
  down a B diagonal to an under-body dogbone via at (99.4, 90.8). That via sits between the U12 pin 10
  and pin 12 V3V3 dogbones; a 1.9 mm F stub goes from it to pin 11.
- **BAD_FILTERED:** its B diagonal near U15 was replaced by a 1.2 mm F hop across FAULT_CLK, with
  vias at (94.95, 83.6) and (94.1, 84.45).

**FIN02, NOT_RUN (U14.8 to Q5.1).** Q5 was **not** moved and NEG_OFF_K was not touched. No In2 hop was used.
- **Top corridor freed:** **RUN** now crosses the corridor between the board edge and the MHB2 support
  keep-out on B, at y 63.375 (below TIMER_GO). This removed RUN's F segment and its two corridor vias
  and freed the F lane for NOT_RUN at y 63.45.
- **C54** (U13 decoupler, AI-placed) moved 0.15 mm, from y 64.10 to 64.25, so the F lane clears its pads. Its
  GND/V3V3 stubs were re-laid to the same vias.
- **J2 north edge:** NOT_RUN runs F/B/F at y 66.95, hopping under the +5 V F bar. To make room for its via at
  (112.3, 66.95) above the square J2.1 pad, **MAIN_OK** (B) jogs to y 65.825 and **P5_OK** (B) to y 66.375
  over x 111-114. Both nets and their endpoints are unchanged.
- **South-east leg:** NOT_RUN continues on a B diagonal parallel to MAIN_OK and then a lane at y 74.8 under
  the MAIN_OK / V3V3 / GND via row. It goes down x 128.55, between the -12 V B pour edge and RUN (B, x 130),
  and ends at a dogbone via at (125.65, 97.25) next to Q5.1, clear of the pad and mask.
- Length is about 115 mm with 6 vias. NOT_RUN is a static HC20 enable into a 2N7002 gate, routed over the
  solid In1 GND plane.

**FIN03, refinements after 0 opens.**
- **VIN neck restored:** the first FAULT_CLK V20_OK hop put two vias in the In2 VIN band in front of XB1.
  That cut the narrowest VIN cross-section from 4.15 to 3.90 mm. The hop was moved to vias at
  (89.85, 74.9) and (89.3, 78.3), which sit in the existing via and XB1.2 antipad shadow. The minimum is
  back to 4.15 mm.
- **VBUS:** the safe thermal improvement from the core review is done. The F1 feed (66.8, 94.3) to F1.1 is
  now 1.0 mm wide instead of 0.55 mm.
- Not done:
  - **Extra U5 VIN vias:** the only room is about 0.05 mm from the pin-mask openings.
  - **U5 B GND patch:** not needed, because the footprint already carries a 5.8 x 3.2 mm B GND pad with 15 thermal vias.

## Final checks

| Gate | Result |
| --- | --- |
| Shared `kicad_tools.py check`, base and top (`reports/shared-check-*.json`) | `no_findings_in_requested_checks`: ERC 0, DRC 0, unconnected 0, parity 0, 0 incl. exclusions, source unchanged |
| Native DRC base, all severities + parity (`reports/drc-base.json`) | 0 / 0 / 0 / 0 |
| `check_stack.py` (`reports/check-stack.json`, `../../stack-r2/validation.json`) | `problems: []`. ERC root/base/top 0. DRC 0 opens both boards. Interconnect equivalence `equal: true`: root 216 refs / 145 nets = base 132 + top 88 minus stack-only headers. Stack mechanics unchanged (width 0.28 mm worst case, an assumed tolerance-screen result, not manufacturer-qualified, J2 1.50/2.93/5.19, 0 collisions) |
| Unit tests (`reports/unittest.txt`) | 9 run, OK |
| Support annulus r1.7..3.6, all Cu, stored and refilled, both boards (`reports/sup*.txt`) | 5/5 supports with 0 hits per board; problems 0; nearest 3.601 mm |
| Vias in SMD pad/mask; In1 tracks; zero-length / duplicate / dangling | 0; 0; 0 / 0 / 0 |
| In2 tracks | Unchanged from the accepted checkpoint: N_VCC hop, the RS48 LED_RETURN return hops and the VPD / VPD_U1 hops. No data on In2 |
| 1 mm edge | Copper rule 1.0 mm in DRC. Courtyards < 1 mm only for the fixed front parts D8, D16, D17, D18, SW1 and J1 (unchanged); C54 is at 1.175 mm. The only custom rules are the J1/SW1 pad-edge allowances |
| All parts on F | yes (0 B-side footprints). Fixed J1, J2, SW1, LEDs, XB1/XB2, mounts and outline unchanged. Only C54 moved |
| Protected copper (net diff against `bfdbf749`) | No changes on VPD, EF_IN, VIN, N_SENSE, N12_RAW, -12V, +12V, +5V, LED_RETURN or the U8/Kelvin nets. VBUS has one track widened. Zone outlines identical |

## Power paths re-checked on the refilled copper (nominal 35 / 15.2 / 15.2 / 35 um, screening only)

- **Filled areas unchanged** against the core review: VPD (F 51.58 / B 50.12 mm2), EF_IN (F 28.03 + 17.11 /
  B 87.46), VBUS B 12.52, +5V 24.3, N_SENSE, N12_RAW and the F -12V tab pour 56.33. D10, U5 EP GND (17 vias
  to In1), the U9 upstream tap and the U8 VEE/SENSE (R89) Kelvin copper are unchanged.
- **VIN In2:** minimum width 4.15 mm (unchanged), about 4.75 mOhm (was 4.73). One piece, 399.7 mm2.
- **GND In1:** one piece, 2922 mm2. The J1-XB1 neck is still 25.25 mm.
- **V3V3 In2:** one piece, 2374 mm2.
- **-12 V B pour:** one piece, 109.0 to 107.4 mm2. The NOT_RUN lane at y 74.8 trims about 0.15 mm off the pour's
  top edge. The strip from Q4 to the J2 column narrows from 1.55 to 1.45 mm at x 120 (about 2.3 mOhm at
  1 A, unchanged within rounding). The Q4 tab via column and its B area are not affected.
- **+12 V F pour:** 48.47 to 48.28 mm2, trimmed at the top end only. The 1.75 mm neck is unchanged.

## Residual gates (not routing defects; unchanged by this work)

- **Headers:** XB1 / J2 / TSW-110 / 103-07 height and current are provisional and not rated.
- **Fab:** no CAM / JLCPCB export, no supplier acceptance, no order.
- **Ratings:** no thermal bench data, no 45 W / 54.5 W rating, no feeder current guarantee. The 4.7 A figure is a screening value only.
- **2 mm rule:** the hand-solder gate covers J1, J2 and the TOP XT headers, which are soldered from the F side next to SMD parts. The BASE XB1/XB2 header tails are soldered on B, away from the F-side SMD pads, so the F-side SMD-to-XB pad distances are for information only. This is not a new exception.
- **Review:** this is a routing checkpoint subject to supervisor verification. Independent pre-fabrication/assembly sign-off and the hardware/bench gates remain.

## Images (`img/`)

- `base-final-FB.png`, `base-final-F.png`, `base-final-B.png`: whole BASE, native refill
- `zoom-fault-clk-u13-bus.png`, `zoom-not-run-top-j2-neg12.png`, `zoom-vin-in2-xb1.png`: new links and the VIN band
- `face-base.png`, `face-top.png`: stack face views from `tools/render_stack.py`
- `top-final-FB.png`: TOP, unchanged
