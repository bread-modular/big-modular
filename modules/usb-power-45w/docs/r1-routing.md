# usb-power-45w R1 placement/routing record

> **Status: steps 0-2 done; authorization gate cleared; placement/routing next.** No parts
> placed, no tracks/vias/zones yet. Not a release, not a performance or thermal qualification.

Board: `hardware/usb-power-45w.kicad_pcb` (worked on directly, `/tmp` backup per step).
Raw reports: ignored `research/r1/`.

## Step 0 (done)

| Change | Basis |
|---|---|
| J2/J3 -12 V marking as old J7: horizontal `1 / -12V / RED` outside the box (front side, visible with the plug mated) replaces the rotated `-12V` that sat under the box body; B silk `N12 GND GND GND P12 P5 NC NC` per pin | old `usb-power` J7 |
| U8 LM5067 VSSOP-10 land: 10 x 1.45 x 0.30, pitch 0.5, span 4.4, R0.05 (was 1.5 x 0.35, span 4.2, 0.15 gap) | TI DGS0010A land pattern example 4221984/A (LM5067 datasheet) |
| U4 PowerPAD thermal via pads: `pad_prop_heatsink`, like the U5-U7 HTSSOP footprints | footprint-type warning was the via pads |

`tools/r1_prep.py` records the edit; `tools/build_layout.py` makes the same marking.

**Header orientation was already the same as old J7** (checked on both native boards):
rotation 270, pin 1 (-12 V) at the native-X-high end = module bottom, odd row toward the
rear edge, key notch on the rear side. Pins 1/2 -12V, 3-8 GND, 9/10 +12V, 11/12 +5V, 13-16 NC.
J2 pin 1/2 at X111.75 Y68.275/70.815, pin 16 X93.97; J3 pin 1/2 X142.75, pin 16 X124.97.

### Step 0 validation (fresh, current board)

Shared `check` run `research/r1/check-step0/` on these input hashes (SHA-256, first 16):

| File | SHA-256 |
|---|---|
| `hardware/usb-power-45w.kicad_pcb` | `8d772aac8b8b843b` |
| `hardware/usb-power-45w.kicad_pro` (unchanged from M1) | `875416df0b051821` |
| `USBPOWER45.pretty/MSOP-10_3x3mm_P0.5mm.kicad_mod` (U8) | `025ef6f67f230ec3` |
| `USBPOWER45.pretty/TI_SO-PowerPAD-8_ThermalVias.kicad_mod` (U4) | `a028811923d20ff7` |

- Native ERC 0. Native DRC (KiCad 10.0.6, all severities, no exclusions): 4 errors, all
  the inherited J1/SW1 copper-edge items below; 0 warnings; 0 schematic parity; 493
  unconnected (nothing placed or routed). U8 clearance and U4 type warning are gone; no
  library-mismatch finding.
- Against M1 (`0ef47c5d`): same 217 refs and 150 nets; no pad net changes; only U8 pad
  size/position and U4 via-pad property changed; footprint positions/rotations unchanged;
  `.kicad_pro` rules, board `setup` and net classes unchanged; no `.kicad_dru`.
- Shared ref/pin/net parity still lists only the cosmetic `Net-(U4-RT/SYNC)` vs native
  `{slash}` escape (R13.2, U4.4); native DRC parity is 0.

## Single-sided placement: all components on F (user rule)

**User direction, 2026-10-31: every installed component stays on F, like the old usb-power
module.** B carries copper only (signal routing, thermal spreading). Back-side components are
not an option for this board.

Single-sided F placement is **dense and not yet proven either way**. An early raster area
proxy (now `research/r1/fit_study_proxy.py`, ignored) is **withdrawn as evidence**: it wraps at
boundaries, has no outside-board padding, uses a 1.75 mm pad dilation as a shape-dependent
proxy for the 2 mm SMD-copper rule, omits test pads and ignores that tracks may run inside
courtyards. Its numbers (approximate: about 2.6k mm2 free F area vs a similar summed
courtyard area) only say placement will be tight. A real answer needs a trial group placement.

## Step 1 (done): J1-only copper-edge allowance

User direction, 2026-10-31: "USB is fine. Make an exception for that." Only J1 is authorised;
not SW1, not the LEDs, not B parts.

`hardware/usb-power-45w.kicad_dru` holds the board's only custom rule,
`J1_front_shell_lugs_edge_0p55`: `edge_clearance` min 0.55 mm for pads where
`Parent == 'J1'`, `Pad_Number == 'S1'` and the position is within 0.13 mm of X64.93 or X73.57
and Y100.6-101.15 (the two forward shell lugs, measured 0.604 mm). The rear J1 S1 lugs, every
other pad and all other copper keep the 1.0 mm board setting; `.kicad_pro` and the board are
unchanged. Moving J1 drops the lugs out of the window, so 1.0 mm applies again. Negative
controls on a `/tmp` copy: a window matching no pad brings back both J1 errors; a window on
one lug clears only that lug.

**J1 courtyard allowance (documented, DRC does not check courtyards):** J1 courtyard extends
1.475 mm beyond the Y102.275 front edge (outer stroke edge) and sits 0.875 mm from the
X63.25 bracket cutback wall. Allowed for J1 only, at the current position and footprint.

### Step 1 validation (fresh)

Shared `check` run `research/r1/check-j1rule/`; native DRC `research/r1/drc-j1rule.json`.

| File | SHA-256 (first 16) |
|---|---|
| `hardware/usb-power-45w.kicad_pcb` (unchanged from step 0) | `8d772aac8b8b843b` |
| `hardware/usb-power-45w.kicad_pro` (unchanged) | `875416df0b051821` |
| `hardware/usb-power-45w.kicad_dru` (new) | `ee0ced558393066d` |

- ERC 0. DRC (KiCad 10.0.6, all severities): **2 errors** (SW1 MP copper edge, below),
  0 warnings, **0 exclusions**, parity 0, 493 unconnected (nothing placed). Step 0 had 4.
- Scope: 1 custom rule; no severity change; 219 footprints on F, 0 on B; no tracks, vias or
  zones; no net, position or footprint change; no files changed outside `modules/usb-power-45w/`.

## Step 2 (done): SW1 copper-edge allowance; SW1/LED courtyard approvals

User answer, 2026-10-31: "Yes. Allow it." to exactly option (A) of step 1: the SW1 (RESET) MP
pad copper allowance and the SW1/LED courtyard overhangs. Nothing else is authorised.

`hardware/usb-power-45w.kicad_dru` adds a second rule, `SW1_MP_case_pads_edge_0p55`:
`edge_clearance` min 0.55 mm for pads where `Parent == 'SW1'`, `Pad_Number == 'MP'` and the
position is within 0.13 mm of X102.60 or X106.90 and Y101.2-101.45 (the two TL3340 MP case pads,
1.9 x 0.7, measured 0.600 mm to the Y102.275 front edge). SW1 pads 1-3, the rear J1 lugs and all
other copper keep the 1.0 mm board setting. Moving SW1 takes the pads out of the window.

**Approved courtyard overhangs** (panel interfaces at current positions/footprints only; DRC
does not check courtyards; outer stroke edge beyond the Y102.275 front edge):

| Ref | Overhang | Note |
|---|---|---|
| J1 (step 1) | 1.475 mm | 0.875 mm to the X63.25 bracket cutback |
| SW1 | 0.325 mm | TL3340 actuator through the panel |
| D8, D16, D17, D18 | 2.535 mm each | bent-lead 3 mm LED bodies into the panel |

No other edge, 2 mm hand-solder or clearance exception exists. No DRC exclusions or severity
changes; no courtyard was shrunk.

### Step 2 validation (fresh)

Shared `check` run `research/r1/check-sw1rule/`; native DRC `research/r1/drc-sw1rule.json`;
negative controls `research/r1/neg-sw1rule/` (`/tmp` copies, board unchanged).

| File | SHA-256 (first 16) |
|---|---|
| `hardware/usb-power-45w.kicad_pcb` (unchanged from step 0) | `8d772aac8b8b843b` |
| `hardware/usb-power-45w.kicad_pro` (unchanged) | `875416df0b051821` |
| `hardware/usb-power-45w.kicad_dru` (J1 + SW1 rules) | `1f9ab0b4651170be` |

- ERC 0. DRC (KiCad 10.0.6, all severities): **0 violations**, 0 warnings, **0 exclusions**,
  native parity 0, 493 unconnected (nothing placed). Step 1 had 2 (SW1 MP).
- Negative controls: SW1 window moved off the pads -> 2 SW1 MP errors; window on X102.60 only
  -> 1 error (X106.90 pad); SW1 rule removed -> 2 errors. J1 controls as step 1.
- Shared ref/pin/net parity: only the cosmetic `{slash}` escape on R13.2/U4.4 (as step 0).
- Scope: 2 custom rules; 219 footprints on F, 0 on B; no tracks, vias or zones; no net,
  position, footprint, schematic or BOM change; nothing changed outside `modules/usb-power-45w/`.
  U8/U4 repairs and J2/J3 -12 V markings unchanged (hashes as step 0).

## Planned groups (next: placement/routing)

1. USB/PD input + main eFuse (F1, D1, D10 + thermal copper, U5) by J1, module top; CH224A
   branch and U9 always-on LDO next to it.
2. +12 V buck U2/L1/C34 + U6 eFuse; 3. +5 V buck U3/L2/C35 + U7 eFuse; centre, outputs to
   the J2/J3 power pins.
4. Inverting buck-boost U4/L3/C36 on its N12_RAW local reference island, then U8/Q4/R48-R49
   Kelvin sense to the -12 V header pins (module bottom).
5. Fault/reset logic and LED monitors behind the LEDs/SW1.

Stack: F signal/hot loops, In1 GND (N12_RAW local island under U4 only), In2 VIN 20 V,
B signal/thermal. Netclass patterns still hold copied stale names (+3V3_ESP32 ...); they
are replaced with this board's rails when routing starts.
