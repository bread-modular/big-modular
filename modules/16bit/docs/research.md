# 16bit research and circuit intent (S3 schematic, S5 placement, R1 routed, rev1 review)

Bread Modular `16bit` (RP2350 + PT8211 I2S DAC) as a 6HP Eurorack module on a 4-layer
carrier. Brief (user, 2026-10-20):

- 6HP; use modules/8bit as the pattern; 4 layers allowed.
- Top: MIDI in (as 8bit) and two CV inputs. Bottom: two outputs.
- Four pots (Bread Modular has two).
- Mode button and an RGB LED with PWM brightness.
- S2 (user, 2026-10-20): use the 8bit DIP (THT 6 x 6 mm) switch for MODE and a red LED
  instead of the RGB one.
- S3 (user, 2026-10-20): no mux. P1/P2 attenuate CV1/CV2, jacks normalled to +5V so an
  unpatched input is a plain knob; P3/P4 are plain knobs. Move the CV jacks + P1/P2 down as a
  group, P3/P4 further down for separation; USB-C to the top edge (still on the back), plug from above.
- Schematic with nets connected for readability; component placement; **no routing yet**.

Nothing here is bench-tested. No sourcing lookups were made for this module yet.

## 1. Bread Modular 16bit baseline (read-only source)

Source: `~/data/projects/bread-modular/modules/16bit` (VERSION 1.6.0), netlist exported
natively from `16bit.kicad_sch`; firmware `code/16bit` (`includes/io.h`, `midi.h`, `boards`).

| Function | Bread Modular 16bit | Firmware |
|---|---|---|
| MCU | RP2350A QFN-60 on 3V3 (breadboard rail), 12 MHz ABM8 crystal + 1k/15p, internal core regulator (L1 3.3 uH, 4.7u), VREG_AVDD 33R/4.7u | pico-sdk |
| Memory | W25Q128JVS flash (QSPI), PSRAM on QSPI with CS on GPIO0 (10k pull-up) | |
| DAC | PT8211 on I2S GPIO1 BCK / GPIO2 WS / GPIO3 DIN; L/R through 1k + 10n | `BCK_PIN 1` |
| MIDI | GPIO5 RX / GPIO4 TX straight to headers (UART1) | `MIDI_RX_PIN 5` |
| Inputs | AIN_1/AIN_2 headers on GPIO26/27 (ADC0/1, 100k pull-downs); CV1/CV2 headers through MCP6002 + 1M pots (gain) on GPIO28/29 (ADC2/3) | `adc_gpio_init(26 + CV1_PIN)`, `CV1_PIN 2`, `CV2_PIN 3` |
| Mode | SW2 GPIO12 to GND, LED GPIO13 (1k) | `BUTTON_PIN 12`, `LED_PIN 13` |
| Gates | GPIO19/20 to headers | `GATE1_PIN 20`, `GATE2_PIN 19` |
| USB | USB-C data only (27R, 5.1k CC); VBUS not connected; BOOT (QSPI_SS) and RESET buttons | UF2 |

## 2. Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Keep the BM core circuit (RP2350A, crystal network, core regulator, decoupling, flash, PSRAM, PT8211 + 1k/10n, USB-C data-only, BOOT/RUN) and its GPIO map | BM firmware ports; user's builds prove the core |
| D2 | **CV1/CV2 jacks -> GPIO26/27 (ADC0/1)** = BM AIN_1/AIN_2 | ADC pins BM firmware already reads as raw inputs |
| D3 | **S3: RV1/RV2 = CV1/CV2 attenuators** (jack tip -> pot top, pot bottom GND, TN normal = +5V) -> U7 TL072 follower on ±12 V -> the D5 level shift; **RV3/RV4 = +3V3 dividers -> GPIO28/29 (ADC2/3)** with 10n wiper caps. S1/S2's 74HC4052 (U7), R19, C32 and the GPIO6 select are gone | User (S3). Four ADC pins = four readings, no switching. The follower keeps the 138k level shift from bending the 50k attenuator. Unpatched, P1/P2 give 0..+5 V = ADC 1.63..3.01 V (top ~42 % of the range, ~11 bits): firmware rescales. Patched, the knob scales the CV around 0 V; it cannot offset it. BM firmware needs its knob mapping changed (knobs now on ADC2/3 for P3/P4 only, P1/P2 arrive through ADC0/1) |
| D4 | Pots 50k linear (user stock RV09, no bushing/nut) as +3V3..GND dividers | Only 50k/1M exist; 50k is the better ADC source. BM's 1M CV-gain pots are replaced by separate jacks |
| D5 | CV input = 8bit S4 topology at 3.3 V: 100k in, 56k to +3V3, 120k to GND, BAT54SW clamp, 1n, MCP6002 follower on +3V3 | ±5 V bipolar CV with headroom (-5.9..+6.0 V -> 0..3.3 V, 0 V = 1.63 V mid-scale), Zin 138k, RP2350 ADC pins (not 5 V tolerant) only ever see 0..3.3 V |
| D6 | MIDI in = 8bit/MIDI V2 NPN front end with JP1 (shipped open), pull-ups to **+3V3** | Same as 8bit. 1-2 protected (firmware inverts GPIO5: `gpio_set_inover(5, GPIO_OVERRIDE_INVERT)`), 2-3 direct (stock BM firmware). GPIO5 is a 5 V-tolerant digital pin when powered |
| D7 | MODE = generic 6 x 6 x 7 mm THT tact switch (as modules/8bit SW1, stock `SW_PUSH_6mm_H7.3mm`) on GPIO12, pressed through the panel by the 8bit one-piece printed cap (same Z stack). Mode LED = 3 mm red THT (as 8bit D1) on GPIO13 through R20 1k to GND, as Bread Modular | User (S2): use the 8bit DIP switch and a red LED instead of the RGB one. GPIO13 is PWM6B, so the firmware sets the brightness by duty (~1.4 mA at 100 %). S1's 2N7002 drivers and GPIO14/15 are gone (pins open). The THT switch legs went through the B-side flash, so U2 moved to the right (above the legs) and U3 PSRAM into the band the LED drivers freed |
| D8 | Outputs: TL074 on ±12 V, non-inverting gain 6.1 (51k/10k) with -5.1 x VOFF (1.98 V from +3V3 via 10k/15k, buffered by U5C): PT8211 full scale 1.65 V ± 0.825 V -> 0 V ± 5.0 V, DC coupled, 1k 0.5 W 1206 series (as 8bit) | Eurorack level; the PT8211 mid-scale and VOFF both scale with +3V3. U5D is a grounded follower (spare) |
| D9 | Power: ±12 V through B5819W series Schottkys; +12V_F -> AMS1117-5.0 -> +5V -> AMS1117-3.3 -> +3V3 (MCU, memories, DAC, CV buffers) | ~65 mA on +5V: ~0.45 W in U8's SOT-223 (4-layer GND pour planned under the tab); U9 drops 1.7 V. VBUS stays unconnected as on BM: flash the module powered from the rack |
| D10 | Dropped: MIDI out (GPIO4), gate outs (GPIO19/20), BM breadboard headers | Not in the brief; 6HP space. Those pins are left open, so BM firmware that drives them is harmless |
| D11 | Footprints: BM RP2350 QFN-60 thermal-via, BM L_pol_2016, BM 0402 small-pad VREG caps, BM PSRAM "SOIC-8 Generic", BM RV09, BM K2 switch (RUN/BOOT); stock for the rest, including the 8bit MODE switch `SW_PUSH_6mm_H7.3mm` and `LED_D3.0mm`. USB-C = stock HRO TYPE-C-31-M-12 (the BM part) | User preference for BM footprints. BM's USB-C copy merges pads under A-numbers that the stock 14P symbol can't map. The RP2350 thermal-via pads carry the `heatsink` fabrication property (metadata only) so KiCad treats the part as SMD |
| D13 | S3 placement: J1 moved 0.4 mm left of the panel centre; J7 front 0.35 mm inside the top edge; MODE row 82.5 -> 84 | The right J7 SH pad must keep the native 0.5 mm copper-to-edge rule, which puts its left SH pad 0.14 mm inside J1's courtyard at X15 (DRC `pth_inside_courtyard`). The J7 front silk would cross Edge.Cuts if flush. U2 flash needs the 5.35 mm between the RV4 pins (now Y72.5) and the SW1 legs; at 84 it has 0.37/0.52 mm copper clearance and its silk clears both |
| D14 | S4 placement (user): LED and MODE swapped and moved beside the power header; CV jacks 34 -> 37, RV1/RV2 47.5 -> 53.5, RV3/RV4 65 -> 75.5, OUT 96 -> 92 | More finger room around the knobs and CV jacks. The freed MCU band let U1/U2/crystal move up between the pot rows (RV1/RV2 pins to RV3/RV4 tabs needs ~21.7 mm, hence the 22 mm pot-row pitch); U8 moved right of J6 under the LED; U7 joined U6 in the CV centre column and U3 moved under the RV2 body |
| D15 | S5 placement (user): MODE button + LED moved to the bottom corners near the panel edge (Y104.8 -> 113.5); OUT jacks 92 -> 99 | At Y92 the OUT row sat 16.5 mm under RV3/RV4, the same pitch as CV->RV1/RV2, so P3/P4 read as output controls; now 23.5 mm. SW1/D1 took the old regulator spots, so U8/U9 moved up into the band between the RV3/RV4 pins and the OUT jack T pads with U4 between them; output caps C3/C4 sit in the strips beside U5. Button cap (D7) spans Y110-117, inside the 120.5 rail gap |
| D12 | Board rule `min_through_hole_diameter` 0.2 mm (8bit: 0.3) | The BM RP2350 footprint's thermal vias are 0.25 mm drills; 4-layer boards at JLCPCB allow 0.15-0.2 mm vias. Recorded so it is a visible choice, not a silent relaxation |

## 3. Circuit (`hardware/16bit.kicad_sch`, ERC 0)

```
MIDI   J1 T -> R3 100k to +3V3; R1 10k -> Q1 MMBT3904 (D4 clamp) -> RX_Q (R2 22k to +3V3)
       JP1: 1 RX_Q / 2 MIDI_RX (GPIO5) / 3 MIDI_IN
CV1/2  Jx T (TN = +5V) -> RVx 50k top, wiper -> U7A/U7B TL072 follower -> 100k -> CVx_BUF (56k +3V3,
       120k GND, BAT54SW, 1n) -> U6 MCP6002 follower -> GPIO26/27 (ADC0/1)
KNOBS  RV3/RV4 +3V3 dividers, wiper 10n (C30/C31) -> GPIO28/29 (ADC2/3)
MODE   SW1 GPIO12 to GND (internal pull-up)
LED    GPIO13 -> R20 1k -> D1 3 mm red -> GND (as BM; ~1.4 mA, PWM6B duty = brightness)
DAC    U4 PT8211 (GPIO1-3) -> R26/R27 1k + C34/C35 10n -> U5A/U5B + inputs
OUT    U5A/B: Rf 51k, Rg 10k to VOFF (U5C follower of R34 10k / R35 15k + C36 10u) -> R30/R33 1k -> J4/J5
```

- **Output gain (S2).** PT8211 datasheet (BM `16bit-5v/verification/.../PT8211.txt`): maximum
  output level 2.2 / 2.5 / 2.7 Vpp min/typ/max at VDD = 5 V, i.e. ~0.5 x VDD. At 3.3 V (BM 16bit
  and here) full scale is ~1.65 Vpp (1.45..1.78 Vpp), centred on VDD/2. The S1 gain-3 stage
  therefore gave only ~5 Vpp. That matches the user's BM experience: 16bit output is low
  and needs BM `drive` at half pot (U1B gain 51k / (1k + 25k) ~ 2x) to sound right. S2 uses gain
  6.1 (Rf 51k / Rg 10k) with VOFF = 3.3 x 15/25 = 1.98 V, so full scale is 0 V ± 5.0 V typ
  (± 4.4..5.4 V across datasheet spread), and the offset error at mid-scale is -33 mV. TL074 on
  ±12 V has plenty of headroom. The DAC's own mid-scale error is amplified x6.1. Bench check:
  output swing and DC offset at digital zero.
- PWR_FLAGs: GND/+12V/-12V at the Eurorack entry, +12V_F/-12V_F behind D2/D3, +1V1
  (fed through L1) and VREG_AVDD (fed through R4). No others.

## 4. Placement (`docs/geometry.json`, render `docs/fit/placement-render.png`)

6HP panel 30.0 x 128.5 mm; carrier 29.0 x 110.0 mm, 4 layers, F side faces the panel.

| Panel row (Y) | Front (F) | Back (B) under it |
|---|---|---|
| 17.5 | J1 MIDI (X14.6, 0.4 mm left of centre) | MIDI front end + JP1 (left); USB-C J7 at the top-right edge, opening UP (front 0.35 mm inside the edge), R9-R12/C24 below it, BOOT SW2 / RUN SW3 below those |
| 37 | J2 CV1, J3 CV2 | CV1 parts (left edge), U6 MCP6002 + U7 TL072 (centre column), CV2 parts (right edge) |
| 53.5 | RV1 RV2 (CV attenuators, 16.5 mm under their jacks: one group) | C28/C29 between the inner tabs, U3 PSRAM (+C23/R8) under the RV2 body |
| 62-74 | (gap between the pot pairs) | MCU zone: U1 RP2350A between the RV1/RV2 pins and the RV3/RV4 tabs, decoupling ring, L1, Y1 crystal (left), U2 flash + C22 (right) |
| 75.5 | RV3 RV4 (22 mm lower: separate pair) | C30/C31 wiper caps |
| 84-92 | (gap: P3/P4 read apart from the outputs) | Regulator band: U9 AMS1117-3.3 (left), U4 PT8211 + C33 (centre), U8 AMS1117-5.0 (right) |
| 99 | J4 OUT L, J5 OUT R (23.5 mm under RV3/RV4) | U5 TL074 (centre) with C4/C37/R34 and C3/C38/R35 strips, C36 below it, L/R output passives at the edges |
| 105-117 | | J6 Eurorack power (centre, pin 1 bottom); D2/C21 left of it; D3/C2, R20, C1 right |
| 113.5 | SW1 MODE 6x6 THT (X5) and D1 red LED (X25) in the bottom corners, near the edge | C19 between the SW1 legs |

The MODE button reuses the modules/8bit two-part printed actuator (same switch and stack).

## 5. Open items

- Routing: done (R1, §6) and reviewed (rev1, §7). **Fabrication requires via-in-pad fill (resin
  plugged + copper capped, POFV)**: §7.2. Remaining router jogs are cosmetic; In2 carries 62.8 mm of signals.
- Sourcing: LCSC codes are filled only for parts already verified for modules/8bit; RP2350A, W25Q128JVS, APS6404L, PT8211, AMS1117s, TL074, TL072, MCP6002, crystal, inductor, 0402 passives, USB-C need dated live lookups before any export.
- Firmware: GPIO5 inversion when JP1 = protected; P1/P2 now arrive on ADC0/1 (rescale the unpatched 1.63..3.01 V knob range), P3/P4 on ADC2/3; LED PWM on GPIO13; CV scaling (0 V = mid-scale).
- Bench: PT8211 output swing / output level, LED brightness, AMS1117-5.0 temperature.
- Mechanics: 3D fit against the panel (LED height, switch cap with the 8bit print, USB-C plug from above: the board top edge is behind the rail, so the module comes out of the case to flash), printed panel.

## 6. Routing R1 (2026-10-20, `tools/route_r1.json` -> `tools/route_plan.py`)

Stack: F.Cu/B.Cu signals 0.2 mm; the +5V, ±12 V and ±12V_F rails 0.4 mm. **Correction (rev1 review):
+1V1 (68.7 mm), VREG_AVDD (19.0 mm), VREG_LX (6.8 mm) and the local +3V3 stubs (19.6 mm) are 0.2 mm,
not 0.4 mm** (the QFN pads are 0.2 mm wide; Bread Modular runs +1V1 at 0.15 mm, §7.3). In1.Cu
solid GND (no tracks); In2.Cu +3V3 plane, a few signal hops cost-weighted; vias 0.5/0.3 mm (board default). Router rules were never lower than
the native ones.

| Run (same frozen placement, rules, pours) | Unrouted | Vias | Notes |
| --- | --- | --- | --- |
| Freerouting (pinned, 40 passes) | 77 | - | swung 77..148 per pass, stalled |
| TraceMaker CPU r1 (no plane protection) | 8 (13 KiCad) | 190 | tracks on In1/In2, 20 thin power pieces, 2 off-centre vias |
| TraceMaker GPU r1 (CUDA build, sm_120) | 9 (17 KiCad) | 208 | same quality, no faster |
| TraceMaker r2a/b/c (`--no-tracks-on In1.Cu`, `--no-neck-nets`, In2 cost) | 9 / 5 / 10 | 237 / 231 / 216 | planes whole except a 2.3 mm² +3V3 island |
| **TraceMaker r3a** (r2b + `--first-nets`) | **4 (5 KiCad)** | 235 | **picked**; DRC 0, In1 1 piece |
| TraceMaker r4a/b/c (box rip-up round U1, re-route) | 11..13 | - | worse; dropped |

Finishing r3a (explicit, research/r2/s3..s35, every step checked with full native DRC):
- `tracemaker session` with hints `{version 1, no_tracks In1.Cu, In2 cost 4}`: QSPI_SCLK, I2S_WS (a
  session route without the hint put QSPI_SCLK on In1; discarded).
- TraceMaker cannot finish pins its escape analysis calls dead (U1 5, 8, 26, 41, 42, 56: "no
  channel at 0.2 mm"), so these were finished by hand: explicit escape stubs + vias, then a small
  0.05 mm grid A* (research/r2/scripts/gridroute.py, research only) from the via to the far pad:
  - MIDI_RX: B stubs U1.8 -> via 118.6/118.0 and JP1.2 -> via 102.0/63.5, 4-via path between them.
  - U1 bottom row: XIN inward to via 115.0/120.35; XOUT inward on a lane at Y120.65 to via
    112.6/120.45; +1V1 (pin 23) out to via 114.0/122.35, then C13.1 and U1.6; +3V3 pin 20 straight
    to C11.1's in-pad via (its old via removed).
  - POT3 inward to via 111.55/116.4 with a 3.4 mm In2 hop; I2S_WS inward to via 116.545/116.48.
  - I2S_WS moved off the In2 fence, which reconnected the +3V3 island (In2 now one piece).
- Cleanup: duplicate/zero-length/dangling segments dropped, near-via ends centred, tiny via stubs
  collapsed; the freezer drops in-pad stubs and trims 4 in-pad tails (pads are convex).

Result (`hardware/16bit.kicad_pcb`, promoted from the accepted stage-3 candidate of 3 shared
`pcb plan/apply` stages, 563 ops): 0 unconnected, DRC 0 at all severities (0 exclusions), parity 0,
ERC 0; 252 vias; copper F 871 mm, B 943 mm, In2 63 mm; widths 0.2 (966) / 0.4 (131), none below
rule; +3V3 In2 1 piece (78.5 %). **Correction (rev1 review):** GND on In1 is one main piece (83 %) **plus
two 2.6 mm² fill pieces** between the J6 GND pins (115.0/159.65 and 115.0/162.19), each tied to GND
only by its pad's thermal spokes; electrically GND, not an isolated island, but not "exactly 1 piece".
The rev1 review (§7) changed this copper; current numbers are in §7.5. Render `docs/fit/routed-render.png`.

## 7. Rev1 review of R1 (2026-10-20, independent review + finish pass)

Research notes and audit scripts: `research/rev1/` (ignored). Coordinates are KiCad board mm.

### 7.1 Claims re-verified from scratch

Shared `kicad_tools check` and native `kicad-cli pcb drc --severity-all --schematic-parity` on
the committed R1 board: ERC 0, DRC 0, unconnected 0, parity 0, 0 exclusions; panel DRC 0/0. 252 vias,
no tracks on In1, In2 signals 62.8 mm, widths 0.2/0.4 only. The two R1 doc claims that were wrong are
corrected in §6 (+1V1 is 0.2 mm, not 0.4 mm; In1 GND has two extra 2.6 mm² spoke-tied pieces at J6).

### 7.2 Fabrication requirement: via-in-pad fill (resin plugged + copper capped)

**This revision requires via-in-pad fill at the fab.** The router centred many vias in SMD pads.
Ordered as a plain 4-layer board (vias only tented), solder wicks down the open barrels during
reflow: starved joints and tombstoned 0402s are likely.

- Order wording: **"Via in pad: resin filled + copper capped (POFV, IPC-4761 type VII), plated over;
  all vias"** (at JLCPCB: "Via Covering: Epoxy Filled & Capped"). Confirm availability, price and
  the drill range for the 0.2/0.25/0.3 mm drills at order time; no live lookup was made.
- Board setup (`tools/build_layout.py` -> `hardware/16bit.kicad_pcb`): via tenting kept, **filling
  yes, capping yes**, so the requirement travels with the board file.
- Fallback if POFV is not available: hand-apply solder paste and reflow with the vias tented only;
  expect a higher reflow defect rate (inspect and touch up every in-pad joint, especially the 0402s).
- In-pad vias left after rev1 (counted by `research/rev1/scripts/vip.py`, a via whose copper overlaps
  an SMD pad of the same net):

| Category | Vias in SMD pads |
| --- | --- |
| GND plane stitch (to In1) | 53 (51 centred, 2 on the pad edge) |
| +3V3 plane stitch (to In2) | 27 (24 centred, 3 on the pad edge) |
| Signal or other rail | 43 (34 centred, 9 on the pad edge) |
| **Board vias in pads** | **123** |
| U1 exposed-pad thermal array (footprint vias, 0.25 mm drill, 0.6 mm pads) | 9 |

  U1's signal and power pads have **no** in-pad vias after rev1; the EP array is the only via copper
  inside U1's footprint pads.

### 7.3 Findings

| # | Sev | Finding | Location | Status |
| --- | --- | --- | --- | --- |
| F1 | Major (DFM) | Open vias inside SMD pads, board only tented (132 incl. U1 EP array) | §7.2 | 9 moved/removed (§7.4); rest = POFV fab requirement |
| F2 | Minor | U8 AMS1117-5.0 has no local input cap: nearest on +12V_F are C37 100n at 18.6 mm and C1 10u at 26.8 mm | U8.3 127.15/140.1 | Left: needs a schematic change (add ~10u at U8.3) |
| F3 | Minor | VREG_LX switch node goes through 2 vias and runs 4.3 mm on In2, the +3V3 plane layer | 111.54/115.57 -> 109.59/119.02 | Left: BM's LX is 10 mm at 0.15 mm on 2 layers; next rev route LX on B beside L1 |
| F4 | Minor | +1V1 is 68.7 mm of 0.2 mm track, 16 vias, one In2 hop (docs said 0.4 mm) | U1 / L1 / C13-C16 | Doc fixed; copper left (BM: 21.8 mm at 0.15 mm) |
| F5 | Minor | Four In2 hops (VREG_AVDD, +1V1, LX, POT3) cut slots into +3V3 left of U1 | x106-111.5, y114.7-119.3 | Left: slots run with the current flow; plane is one piece |
| F6 | Minor | XIN 17.0 mm, 2 vias, F.Cu among U1's thermal vias (XOUT 8.6 mm) | Y1 -> U1.21 | Left: placement-driven (BM 13.9 mm) |
| F7 | Minor | C17 (VREG_AVDD 4.7u) 8.2 mm from U1.46 through an In2 hop | C17 | Left: BM similar (5-7 mm) |
| F8 | Minor | QSPI: SCLK 54.2 mm / 7 vias, SS 53.5 mm (both branch to flash + PSRAM); SD0-SD3 31.6/36.6/42.1/42.6 mm (11 mm spread) | U1 -> U2, U3 | Accepted (§7.6) |
| F9 | Minor | AMS1117 tabs are VOUT (+5V/+3V3), so D9's "GND pour under the tab" doesn't heat-sink them; U8 (~0.45 W) cools through its pad and 0.4 mm tracks only | U8, U9 | Left: bench temperature check (§5) |
| F10 | Nit | U1.1's moved via clears the pad by only 0.03 mm (boxed in by an In2 QSPI_SD0 hop and B PSRAM_CS) | via 117.5/114.83 | Accepted: DRC clean; the edge sits outside the pad |
| F11 | Nit | Router jogs: duplicate QSPI_SS loop 0.065 mm beside its twin, QSPI_SD2 spur (11-15°), PSRAM_CS hairpin (12.5°), USB D- hairpin (5.4°), 5 tees running back along their parent, 0.05 mm zig-zags | U1.60, U1.58, R8, J7 | Fixed (§7.4) |
| F12 | Nit | USB D+/D- not pair-routed (about 2 mm mismatch, separate paths) | J7 -> U1 | Left: full-speed USB (12 Mbps) tolerates it |
| F13 | Nit | GND In1 has two extra 2.6 mm² pieces between the J6 GND pins | 115.0/159.65, 115.0/162.19 | Doc fixed (spoke-tied to GND) |

Checked and fine: decoupling C5-C12 1.7-2.8 mm, C13 4.0 mm (+1V1, U1.23), C14 2.0, C15 3.3,
C16 2.5 mm (straight line to the nearest U1 pin of the same net); no track under the U1 exposed pad;
annular rings 0.1 mm (0.5/0.3) and 0.15 mm (0.5/0.2); edge clearance, silk over pads and courtyards
pass native DRC at all severities; panel jacks align exactly, and the pot, switch and LED offsets match
`docs/geometry.json` and the footprint origins.

### 7.4 Rev1 copper edits (`tools/route_r1.json`, through the shared pipeline)

Edits are made by `research/rev1/scripts/edits.py`, prototyped with full native DRC, then rebuilt
end to end: `build_layout.py` (unrouted), `route_plan.py` (3 stages), shared `pcb plan/apply`
(intermediate stages with `--allow-draft-opens`, the last without), `pcb promote`. The promoted
copper equals the prototype (1311 items, 0 differences).

- U1.45 (+3V3, 0.2 mm pad): in-pad via 110.565/115.18 removed; pins 44/45 tie to the via at 110.11/114.79.
- U1.53/54 + C6.1 (+3V3): via 114.205/114.075 -> 114.205/113.7, 45° stub between the pad tips.
- U1.1 (+3V3): via 117.455/114.985 -> 117.5/114.83 + stub.
- U1.30 (+3V3): via 110.955/121.42 -> 110.65/121.75 + corner stub.
- U1.16 (/BUTTON): via 117.0/121.615 -> 117.35/121.615 on the same F.Cu lane.
- D5/D6 (BAT54SW SOT-323, 0.45 mm pads): GND/+3V3 vias 104.39/89.44, 104.39/90.74, 127.4/89.44,
  127.4/90.74 -> 0.75 mm right (105.15/128.15), 0.3 mm past the pad tip.
- Jog cleanup (F11): only loops and spurs that double back; same endpoints, nothing re-routed.
  Waypoints 788 -> 753.
- `tools/build_layout.py`: board setup filling + capping yes (§7.2).

### 7.5 Numbers after rev1

ERC 0; DRC 0 at all severities, 0 exclusions; unconnected 0; parity 0 (shared check and native,
`docs/fit/`); panel 0/0. 251 vias (246 at 0.5/0.3 mm, 5 at 0.5/0.2 mm); 1065 segments, widths 0.2 mm
(934) / 0.4 mm (131), none below rule; F 869.9 mm, B 933.5 mm, In2 62.8 mm (signals), In1 no tracks.
In2 +3V3 one piece; In1 GND one main piece + two 2.6 mm² spoke-tied pieces at J6.
Render (F | In2 | B): `docs/fit/routed-render.png`.

### 7.6 Pre-fabrication calls

1. **Via-in-pad**: order POFV (§7.2). Without it this revision is not fab-ready for reflow.
2. **QSPI 11 mm skew / 54 mm SCLK: acceptable, yes.** 11 mm on FR4 is about 70 ps, roughly 1 % of a
   75 MHz (clk_sys/2) SCLK period. The 54 mm branched SCLK is longer than a ~1 ns edge's critical
   length, so expect some ringing. The fix belongs in firmware, not copper: bring up at the
   default/conservative flash clock divider, run a PSRAM memory test, and raise the clock only if
   that passes.
3. Add a local input cap at U8 (F2) in the next schematic revision; until then, check U8's input
   on a scope at power-up and under load.
4. Bench: AMS1117-5.0 temperature (F9), VREG_LX ripple on +1V1 (F3), crystal start-up (F6).
