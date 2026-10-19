# MIDI module research

There are two hardware versions, each a complete KiCad project:

- **V1** (`hardware/v1/`, sections 1-6): the Bread Modular V1 circuit, unchanged by
  this split. Fabrication export in [`../jlcpcb/v1/`](../jlcpcb/v1/README.md).
- **V2** (`hardware/v2/`, section 7): V1 plus mis-patch protection on the MIDI input
  and all eight outputs; MIDI IN takes 3.3 V and 5 V senders; still no optocoupler.
  Same panels, jacks, LEDs and stack. Fabrication export in
  [`../jlcpcb/v2/`](../jlcpcb/v2/README.md).

Sections 1-6 describe V1; paths there are relative to `hardware/v1/`, `tools/v1/`
and `jlcpcb/v1/`, and the shared mechanics (`geometry.json`, `mechanics.md`, panels)
apply to both versions.

Status (V1): **V1.0 fabrication export (S4/R5)** (rev. 2026-10-19): native schematic
(`hardware/v1/midi.kicad_sch`, ERC 0) at the **5 V** Bread Modular logic level, every
assembled part carrying JLCPCB fields (section 5), and the fully routed 2-layer
carrier with the regulator beside J10 on its heat sink (R3, section 3.6) and,
since S4/R4, the exact Bread Modular V1 input with no series resistor or pull-up
(section 3.2; shared check: no findings). The
JLCPCB files are in [`../jlcpcb/v1/`](../jlcpcb/v1/README.md). Opto removed and deferred
past V2 (section 3.5). This document records the Bread Modular baseline, the circuit as drawn, the
remaining open checks and dated sourcing observations. Nothing here is
bench-validated, and the export is not a supplier-accepted order.

## 1. Goal

- A 4HP Eurorack module that takes **TRS MIDI in** and fans it out to **8 TS
  "modular MIDI" outputs**. Each output carries one channel's MIDI stream as a
  logic-level UART signal (tip) plus ground (sleeve) over an ordinary patch cable.
- **ATtiny1616** firmware routes MIDI channel *n* to output *n*, as Bread Modular
  `midi` does.
- One LED per output, hand-soldered 3 mm THT.
- **Input = Bread Modular V1 direct input.** No optocoupler in this version (nor
  in V2); an isolated input with automatic voltage sensing is a later item (section 3.5).
- TRS Type A/B selected with a shunt on **JP1, a 1x3 2.54 mm header on the back**.
- Must accept **both 3.3 V and 5 V MIDI senders**.
- Outputs must drive 5 V Bread Modular receivers, so the logic rail is **5 V**
  (decision D1). Power comes from the Eurorack **+12 V** rail through a simple
  linear regulator (HT7550-1), as briefed; +5 V of a 16-pin cable is not used.
- Power header: 10-pin, but a **16-pin IDC cable must also fit** (section 3.1).
- UPDI programming on a **2-pin 2.54 mm THT header** (J11: UPDI, GND).
- Output protection stays as in Bread Modular: a 1 k series resistor and nothing else.

## 2. Bread Modular `midi` baseline (read-only source)

Source: `~/data/projects/bread-modular/modules/midi`. Netlists were exported with
`kicad-cli sch export netlist` from `git show` copies in `/tmp`; the BM checkout
was not modified.

### 2.1 V1 (1.0.3, commit `b069a1b`): the base for this module

| Block | BM 1.0.3 implementation |
|---|---|
| MCU | U1 ATtiny1616-M (VQFN-20 3x3 P0.4) at 5 V (`V_SUPPLY`) |
| MIDI in jack | J1 QingPu WQP-PJ366ST (TRS, vertical) |
| Input | **No opto.** `J1.T` -> CONFIG pin 3 (`MIDI_DATA_TYPE_A`), `J1.R` -> CONFIG pin 5 (`MIDI_DATA_TYPE_B`); a 2.54 mm shunt joins pin 4 (`MIDI_IN` = **PB3**, USART0 RX) to the chosen line. No series resistor, no pull-up. The unused line (pin 4 "source" of the sender) is left open, so no loop current flows and the sender's pin 5 swings rail to rail |
| Sleeve | `J1.S` tied straight to GND. CHANGELOG 0.5.0: a 10 k between MIDI ground and GND made some devices (Elektron) misbehave, so it was replaced by a direct connection |
| MIDI outs | 8 x 1 k series resistors. Ch1-7 `SoftwareSerial` TX on PA5, PA6, PA7, PB5, PB4, PB1, PB0; ch8 = USART0 TX on PB2 (1.0.3) |
| UPDI | PA0 through R1 4.7 k to CONFIG pin 1 |
| Firmware | Plain `Serial.begin` on PB3, no pin inversion, no pull-up |

In use this works with both 3.3 V and 5 V senders: 5 V is native to the 5 V
ATtiny1616, and 3.3 V highs read correctly in practice, although by datasheet a
3.3 V high is below the 0.7·VDD ≈ 3.5 V VIH at 5 V (it relies on typical
thresholds). This module keeps that input exactly (section 3.2).

### 2.2 V2 (2.0.x): the 6N137 version, which did not work

V2 replaced the direct input with a 6N137 (U2): data line -> R18 220 R -> LED
anode, LED cathode -> **sleeve** (`MIDI_GROUND`), D9 reverse across the LED, open-
collector output pulled up by R34 10 k to PB3, firmware inverts PB3 (`PORT_INVEN`).
U2 pin 7 (EN) is **unconnected**. BOM has no LCSC code (hand-fitted).

Root cause of the V2 failure is **not established** (no board measurement here).
Candidate causes to check on a V2 board, not conclusions:

- Non-standard loop: the LED is driven from the data line to the sleeve, so it
  depends on the sender driving pin 5 *high* against its own shield. Senders that
  only sink on pin 5, or adapters that don't carry the shield, give no current.
- 6N137 threshold: up to 5 mA IF (onsemi), 2-3x the H11L1 and close to the loop
  current of 3.3 V senders with 220 R outputs.
- EN floating and a 4.5-5.5 V supply (C15825 catalog). The supply would fit the
  5 V rail here, but the part is still not reused (section 3.5).

## 3. Circuit (as drawn in the S3 schematic, routed in R3)

### 3.1 Power and the power header

```
Eurorack J10 (2x5, 10- or 16-pin IDC cable): +12V -> D10 B5819W (series) -> VIN_D
                     -> R20 39R (1206) -> VIN_LDO (C5 1u) -> U3 HT7550-1 (SOT-89, 30 V max) -> +5V
                     GND pins -> GND;  -12V (pins 1-2) no-connect
```

- **J10 is an unshrouded vertical 2x5 header that also takes a 16-pin IDC socket.**
  Eurorack 16-pin cables plug onto a 10-pin header aligned at pin 1 (red stripe =
  -12 V); socket positions 11-16 (+5 V, CV, Gate) hang past the +12 V end. J10 is
  therefore vertical with **pin 1 at the bottom** (Y116.0) and the +12 V row on top,
  so the overhang runs up over the board instead of off its edge or into the next
  module. A shrouded box header (20.3 mm wide for 10-pin) would block the 16-pin
  socket and doesn't fit across 19 mm anyway. Geometry: `geometry.json`
  `power_header`, [mechanics.md](mechanics.md).
- D10 makes a reversed cable harmless: reversing swaps pins 1-2 with 9-10, so
  -12 V lands on the diode; GND stays on GND. B-side silk marks the -12 V end.
- The open contacts of positions 11-16 of a 16-pin socket sit 2.5 mm above the
  B side; nothing below them is taller than 1.5 mm, and clipped THT leads must stay
  ≤1.5 mm (they never touch the contacts, which are recessed in the socket).
- Bulk and decoupling: C5 1 uF / 25 V at the LDO input, C4 10 uF at the output,
  C3 10 uF bulk on the +5 V trunk, C1 100 nF under U1 (fed through the via under
  pin 4). Check that the HT7550-1 data sheet accepts a ceramic 10 uF output
  capacitor at the sourcing step.
- ERC power flags: `#FLG01` on GND at the Eurorack entry and `#FLG02` on VIN_LDO,
  which is fed from +12 V only through D10 and R20 (ERC can't see power through
  passive parts). These mark real supply entries and aren't there to silence anything else.

Screening power budget (estimates, not measurements):

| Load | Typical | Worst case |
|---|---:|---:|
| U1 ATtiny1616 at 20 MHz, 5 V | ~10 mA | 12 mA |
| 8 LEDs, (5 - ~1.9 V)/1 k each (~3.1 mA) | ~3-6 mA (activity flashes) | 25 mA (all lit) |
| 8 TS outputs into high-impedance inputs / into shorts (idle-high UART: 5 mA each) | ~0 | 40 mA |
| **Total from +12 V** | **~15 mA** | **~77 mA** |

Without a dropper the LDO would dissipate (12 - 0.45 - 5) V x I: about 0.10 W
typical and 0.50 W in the worst case, which is too hot for a bare SOT-89.
**R20 = 39 R, 1206** splits it: at 77 mA R20 drops 3.0 V (0.23 W) and the LDO keeps
about 0.27 W; at 15 mA they take 0.01 W / 0.09 W. The LDO input then sits at about
8.5 V (77 mA) to 11 V (15 mA), above the 5 V output plus dropout even on an
11.4 V rail (7.9 V at 77 mA). The worst case is a fault (every output shorted and
every LED lit at once). A standard 0.25 W 1206 would run at about 92 % there, so
R20 is a 0.5 W 1206 (UNI-ROYAL HP06W2F390JT5E, C414944, Extended), at about 46 %.
The HT75xx-1 SOT-89 tab is pin 2 (VIN), so U3's tab and R20's pad 2 sit on
dedicated **VIN_LDO heat-sink copper on both layers** (section 3.6). Since R3 the
regulator group (U3, R20, C4, C5, D10) sits right of the power header J10, and the
heat sink is the copper there: about 75 mm² on B.Cu around the tab and about
210 mm² on F.Cu across the whole board below the J9 pad row (around J10 and J11),
joined by nine vias. The total (~285 mm²) is about the same as R2's (~280 mm²), but
the B.Cu copper at the tab is doubled, there are nine vias instead of five, and the
heat now stays at the bottom edge, away from the J8/J9 jacks. Estimate only (no
thermal model or measurement): R20 pad 2 sits on the same VIN_LDO island as U3's
tab, so R20 does not move its 0.23 W anywhere else. The island takes the whole
dropper + LDO loss: about 0.10 W typical and about 0.50 W in the 77 mA fault case.
R20 only keeps its share off U3's die. With ~100-150 K/W for that copper the
island rises about 10-15 K typical and about 50-75 K in the fault case, and U3's
junction a little more. In a warm case (~40 °C) that puts U3 at roughly
100-120 °C in the fault case. The fault case needs every output shorted and every
LED lit at once, and the 1 k resistors cap it at ~77 mA. The layout is kept (R20
stays on the island); the bench fault test is the gate (README order gate 6):
12.6 V, all outputs shorted, all LEDs lit, 30 min, thermocouple on U3's tab, +5 V
must stay below 5.5 V. If the tab runs too hot, the fix is a later routing
revision that gives R20 pad 2 its own small pad off the island.
Eurorack draw is about 15 mA typical / 77 mA maximum on +12 V, and 0 mA on
-12 V and +5 V.

### 3.2 MIDI input: Bread Modular V1 direct, TRS Type A/B on JP1

```
J1 Tip  --> JP1.1 (A)
            JP1.2 --> RX (PB3, USART0 RX)   (direct: no series resistor, no pull-up)
J1 Ring --> JP1.3 (B)
J1 Sleeve --> GND (direct, as Bread Modular V1 / 0.5.0)
```

This is exactly the Bread Modular V1 input (1.0.0-1.0.3: TRS conductor chosen by
a header jumper, straight into PB3; checked against the BM `midi_1.0.1` and 1.0.3
netlists). S3 had added R21 4.7 k in series and R2 22 k to +5 V; S4 removed both
to match V1, which works in use with 5 V and 3.3 V senders. The input is for 5 V
and 3.3 V MIDI senders only; it is not protected against a mis-patched CV/gate
cable (decision D6).

**JP1 = TRS Type, 1x3 2.54 mm THT header on the back** (beside J1, in the LED
column, like the UPDI header J11). B silkscreen: `TRS` above the header, `A`
level with pin 1 and `B` level with pin 3: the shunt always covers the lettered
pin (1-2 = A, 2-3 = B); the shared middle pin 2 is unlabelled.

| JP1 shunt | TRS type | Data conductor | Gear |
|---|---|---|---|
| **1-2 (`A`)** | **Type A** (MMA/AMEI standard) | Tip (MIDI pin 5) | Korg, Make Noise, most current gear |
| **2-3 (`B`)** | Type B | Ring (MIDI pin 5) | Arturia, Novation (older), some others |
| none | - | - | No input; RX floats (see below) |

Only the data conductor (MIDI pin 5, the one the sender pulls low) is used. The
other conductor (pin 4, the sender's +V side) is left open, as in V1. With the
wrong shunt the data conductor sits at the sender's +V, so the input just stays
idle: harmless, move the shunt.

**3.3 V and 5 V senders.** U1 runs at 5 V: VIH ≥ 0.7·VDD = 3.5 V and
VIL ≤ 0.3·VDD = 1.5 V by datasheet. A 5 V sender is in spec directly. A 3.3 V
sender's high (3.3 V) is ~0.2 V below VIH by datasheet and relies on the typical
input threshold, as on Bread Modular V1, which works in use with both 3.3 V and
5 V senders. Accepted as is; not a bench item. With these senders PB3's clamp
diode carries almost nothing: a 5 V high is at most a few hundred mV above the
rail (limited by the sender's own output resistor), a 3.3 V high is below it,
and MIDI senders don't drive negative.

**Idle input floats.** With no cable (the PJ366ST has no switch) or no shunt, PB3
is not driven, as on Bread Modular V1. If that gives stray bytes, the firmware
fix is PB3's internal pull-up (`PORTB.PIN3CTRL |= PORT_PULLUPEN_bm` after
`Serial.begin`); no hardware change.

**Mis-patching is a known V1 risk (D6).** A ±12 V CV/gate cable patched into the
3.5 mm MIDI IN drives PB3's clamp diode directly, limited only by the source's
own output resistance, which is far above the ATtiny1616 injection-current
rating. That is accepted for V1 (Bread Modular V1 is the same); V2 adds input
and output protection (section 7).

**No galvanic isolation.** The sleeve is tied to GND, so the module shares ground
with the sender (V1 behaviour; it also suits senders that want the shield
grounded, per the Bread Modular changelog note on Elektron gear). Ground loops are
the job of the later opto input (section 3.5).

**Firmware:** no inversion (do **not** carry over Bread Modular V2's `PORT_INVEN`);
RX idles high. (This module's own V2 does need `PORT_INVEN`: section 7.2.)

### 3.3 MCU and pin map (kept identical to BM so the firmware ports)

| Function | Pin | BM role |
|---|---|---|
| MIDI in RX | PB3 (USART0 RX): direct from JP1 pin 2 | same pin, same circuit |
| OUT1-OUT7 | PA5, PA6, PA7, PB5, PB4, PB1, PB0 (`SoftwareSerial` TX) | same |
| OUT8 | PB2 (USART0 TX) | same (V1.0.3) |
| LED1-LED8 | PC0, PC1, PC2, PC3, PA1, PA2, PA3, PA4 | BM gate pins, now driving LEDs |
| UPDI | PA0 via R11 4.7 k to J11 | same |

- **UPDI header J11: 1x2 2.54 mm THT pin header on the B side** (left of the
  power header J10 since R3), pin 1 at the top: **1 UPDI, 2 GND**. Use a
  serialUPDI adapter or any UPDI programmer with 2.54 mm Dupont leads. There is no
  VCC pin: program with the module on Eurorack power. The rail is 5 V, so 5 V
  serialUPDI adapters match it, and UPDI goes through R11 4.7 k as in Bread
  Modular.
- **Clock:** at 5 V the ATtiny1616 runs at 20 MHz, as the BM firmware does
  (`board_build.f_cpu = 20000000L`). The firmware ports without clock changes; just
  don't carry over Bread Modular V2's `PORT_INVEN` (this module's V2 needs it, 7.2).
- All 18 I/O are used (17 GPIO + UPDI), as in BM. There is no spare pin for a
  MIDI-in activity LED.

### 3.4 Outputs and LEDs

- `GPIO -> 1 k -> TS tip`, sleeve = GND, exactly as in BM. There is no extra clamp
  or ESD part, per the brief.
- **Output mis-patching is a known V1 risk.** An idle-high output patched to
  +12 V pushes about (12 - 5.3) V / 1 k ≈ 6 mA through U1's clamp diode into
  +5 V. The HT7550-1 can't sink current, so with several outputs mis-patched
  +5 V can rise above U1's 5.5 V rating. Accepted for V1 (BM output stage, per the
  brief); V2 adds output clamps and the input protection (section 7).
- `GPIO -> 1 k -> LED -> GND`: about 3.1 mA per red LED at 5 V. Use
  high-efficiency 3 mm LEDs and raise the 1 k if they are too bright behind the
  panel (D5).

### 3.5 Later: opto-isolated input with voltage sensing (deferred past V2)

The reason for an optocoupler here is to **break ground loops**. The S1 attempt
(H11L1 enabled by a shunt, sharing RX with the always-connected direct path)
could not do that: the direct path and the sleeve-to-GND kept the sender's ground
tied to the module. So the opto is removed. It is not in V2 either (V2 adds
mis-patch protection, section 7); it comes back in a later version as a properly
isolated input:

- In opto mode, nothing but the opto LED loop may touch the jack: the direct
  path and the sleeve-to-GND link must both be disconnected.
- The mode is chosen **automatically by voltage sensing** instead of jumpers
  (e.g. sense whether the jack presents a current-loop source on pin 4, then
  switch the direct path/sleeve out). The sensing circuit is not designed yet.
- Opto part notes carried forward: **H11L1SM** (C899473, 3-16 V supply, threshold
  1.6 mA max @ 5 V, ~0.85x of that at 3.3 V by the typical curve, open collector)
  remains the lead candidate. TLP2361/ACPL-M61L (2.7-5.5 V, push-pull) become
  usable once the opto no longer shares RX with the direct path. The 6N137 is
  rejected: it needs 4.5-5.5 V and is the V2-Bread-Modular part that did not work.
  Loop-current estimates: 5 V MIDI 1.0 sender ≈ 5.5 mA, 3.3 V MMA sender ≈ 7.2 mA,
  3.3 V sender with 220 R/220 R ≈ 2.9 mA, against a worst-case threshold ≈ 1.9 mA.
- Space: on V1 the J1/J2 band on the back (where the S1 opto sat) carries only
  the RX and LED1 tracks. On V2 the input front end (Q1, R1, R2, R22, D9) and
  U2 use that area, so a later opto input needs its own layout pass.

### 3.6 Routing (R1; U3 heat sink R2; regulator moved beside J10 in R3; direct input R4; R5 silk only)

Two layers, every net routed with explicit geometry (no autorouter), written by
`tools/v1/route_plan.py` and applied with the shared `pcb plan/apply/promote`
transaction (README "Rebuild").

- **Widths:** 0.25 mm signals, 0.2 mm at the U1 fan-out (0.4 mm QFN pitch), 0.3 mm
  +5 V trunk, 0.4 mm VIN_D/VIN_LDO and regulator GND returns, 0.5 mm +12 V. Vias
  0.6/0.3 mm (48 in total).
- **GND:** F.Cu and B.Cu are both poured with GND, stitched by 14 edge vias
  between the jack rows, one via in U1's exposed pad (pin 3 tied to the pad) and
  two vias in the B.Cu strip between the CH8_LED/CH7_LED lanes (C1 pad 2). Before
  R2 that strip reached the rest of GND only through a ~0.2 mm neck between R17's
  pads. The shared zone op connects pads solidly (no thermal reliefs), so the THT
  jack sleeve and LED cathode pads need a hot iron when hand-soldering.
- **U3 heat sink (R3):** the regulator group moved from the J8/J9 band to the
  area right of J10 (board mm x 111.7-119, y 155-169), outside the 16-pin IDC
  overhang; the UPDI header J11 and R11 moved to the strip left of J10. GND is
  removed there and replaced by VIN_LDO copper (the tab's own net):
  - B.Cu: everything right of J10 below y 155 (U3's tab, R20 pad 2 and C5 pad 1
    sit on it; D10 and the GND/+5 V pads are cleared out of it).
  - F.Cu: the whole board width below y 153.9 (the J9 pad row), around J10 and
    J11. Their GND pins are cleared out of it on F.Cu and stay on the B.Cu GND pour;
    J10's +12 V pins are cleared too.
  - U3, C4 and C5 return to GND through 0.4 mm B.Cu tracks to J10 pin 4. Those
    tracks split the B.Cu heat sink into the tab piece (~50 mm²) and a piece under
    the caps (~25 mm²); both reach F.Cu through vias.
  - Nine VIN_LDO vias: five beside the tab (not in the pad, to avoid solder
    wicking) and four in the lower piece.
  - +5 V leaves U3 pin 3 through a via and runs up F.Cu through the J9 pad-row gap
    (x 111.55) to the trunk. UPDI comes down F.Cu to a via in the J8/J9 band and
    reaches R11 on B.Cu through the same gap (x 107.2). The rest of that gap is
    B.Cu GND, which joins the J10 GND pins to the main pour.
  - The shared `add_zone` has no zone priority and KiCad rejects intersecting
    zones, so each GND pour is the complement polygon kept 0.3 mm off its heat
    sink.
- **Layer plan.** The pin map is Bread Modular's, so on every side of U1 some
  nets go up and some go down. Each layer keeps a lane order that matches its turn
  order:
  - B.Cu up: RX (straight to JP1 pin 2), LED1-LED3 up the corridor, LED4 up the right
    channel (R9 sits in its crossing).
  - F.Cu up: TX1-TX4 from vias in the left zone. Each comes back to B through a
    via at x 112.3 beside its resistor.
  - TX6-TX8: up on B to vias in the J4/J5 gap, then down on F into the right
    channel, entering their resistors from the right.
  - TX5: across the F side of U1 and down the corridor.
  - UPDI: down the corridor on F, then on B to J11 left of J10.
  - LED5-LED8: down on B. LED8 crosses into the right channel above the power
    cluster.
  - +5 V: up the left channel on F (LDO -> C3 -> via under U1 pin 4 -> C1).
- **Placement changes made for routing** (all in `geometry.json`, generator
  rerun, fit re-checked):
  - The LED resistors are rotated 270 so pad 2 (LEDn_A) faces its LED.
  - R9 moved above J5.
  - U1 moved 1 mm lower.
  - C1 is under U1 and C3 is in the left zone.
  - These also cleared two pad shorts (C1/R9 and C3/R8) left by the S3 5 V
    regeneration.
- **Checks:**
  - Shared `check`: no findings. ERC 0, DRC 0 at all severities with zones
    refilled, 0 unconnected, schematic parity 0, ref/pin/net parity equal, and
    no exclusions.
  - The 3D fit is unchanged (`fit/fit-report.json`).
  - R2 re-ran the same checks after the heat sink, the part fields and the
    silkscreen release label: all still clean. R3 (regulator beside J10) re-ran
    them and the 3D fit again: all clean, fit report unchanged.
  - R4 (S4 schematic: R21 and R2 removed) rebuilt the board through the README
    sequence: RX runs on B.Cu from U1 pin 11 up x 107.8, across y 70.3 (where R21
    sat) and up x 115.6 to JP1 pin 2; the +5 V stub to R2 and its via are gone,
    so the F.Cu +5 V track runs straight from C3's via to U1's. `pcb apply`
    accepted it (ERC/DRC empty, parity equal), the shared `check` has no
    findings, and the 3D fit report is unchanged. Every other footprint position
    is unchanged (the CPL only lost the R2 and R21 rows).
  - R5 deleted the B silk `JLCJLCJLCJLC` order-number marker (one shared
    `delete_item` text op; `build_layout.py` no longer draws it). `pcb apply`
    accepted it (ERC/DRC empty, finding delta empty), the shared `check` has no
    findings, and the re-export differs from R4's only in B.Silkscreen. Copper,
    masks, paste, edge, drills, BOM and CPL are identical.

## 4. Decisions

| # | Decision | Recommendation |
|---|---|---|
| D1 | TS output logic level | **Decided (S3): 5 V.** U1 runs at 5 V from HT7550-1 on +12 V, so the outputs meet a 5 V BM receiver's VIH. A 16-pin cable's +5 V isn't used, which keeps 10-pin cables working. The input takes 3.3 V senders as Bread Modular V1 does (section 3.2) |
| D2 | LDO thermal margin vs fault cases | **Decided (R2/R3): R20 = 39 R 0.5 W 1206 (C414944) + VIN_LDO heat-sink copper on both layers, regulator group beside J10 (R3)** (sections 3.1, 3.6). R20 stays on the U3 island, so the island takes ~0.5 W in the fault case (estimate ~50-75 K rise); the bench fault test is the gate |
| D3 | Opto | **Decided: none in V1 or V2**; an isolated, voltage-sensed opto input is a later item (section 3.5) |
| D4 | TRS type selection | **Decided: JP1 1x3 2.54 mm header + shunt on the back**, `A` (1-2) / `B` (2-3) |
| D5 | LED colour/value | Drawn as high-efficiency red, 1 k (~3.1 mA at 5 V); confirm brightness behind the panel |
| D6 | Input resistors / protection | **Decided (S4): none, exactly Bread Modular V1.** R21 and R2 removed; JP1 drives PB3 directly. The input is for 5 V / 3.3 V MIDI senders (BM V1 works with both). A mis-patched ±12 V CV/gate cable exceeds the injection rating; accepted for V1, protection (input and outputs) is V2 (section 7) |
| D7 | V2 mis-patch protection | **Decided (V2 S3/R3):** NPN input front end (JP2 solder jumper can bypass it for debugging), BAT54SW clamp behind every 0805 1 k output resistor, CJ431 +5V shunt clamp (section 7) |

## 5. Sourcing (V1.0 release, dated, transient)

Observed 2026-10-18 ~18:40 UTC by the shared native audit
(`opt/kicad-tools/jlcpcb/assembly.py audit --strict-live`, 5 boards). Re-run at
~19:16 UTC on the R3 placement file (`research/hs3/audit/audit.json`): the same
result for every part (only six positions changed; the BOM is identical). Re-run
2026-10-19 ~02:22 UTC on the S4/R4 files (ignored `research/audit-r4.json`): 25
parts in 9 BOM rows (R2 and R21 gone, so the 22 k row is gone), and the same
result for every remaining part. Compact
record: `release_parts` in [`sourcing-candidates.json`](sourcing-candidates.json).
Raw report and snapshots: the ignored `research/audit-r2.json` and
`research/jlc-cache/`. Stock is a snapshot, not a reservation or order
acceptance. The audit checks the policy below against the catalog; the
requirements are in [`jlcpcb-audit-requirements.json`](jlcpcb-audit-requirements.json).

| Refs | Value | C-code | MPN | Package | Class | Stock observed |
|---|---|---|---|---|---|---:|
| R3-R10, R12-R19 (16) | 1 k 1 % 0.1 W | C21190 | UNI-ROYAL 0603WAF1001T5E | 0603 | **Basic** | 23.2 M |
| R11 | 4.7 k 1 % | C23162 | UNI-ROYAL 0603WAF4701T5E | 0603 | **Basic** | 18.6 M |
| R20 | 39 R 1 % **0.5 W** | C414944 | UNI-ROYAL HP06W2F390JT5E | 1206 | Extended (chosen) | 1,717 |
| C1 | 100 n 50 V X7R | C14663 | YAGEO CC0603KRX7R9BB104 | 0603 | **Basic** | 32.3 M |
| C3, C4 | 10 u 25 V X5R | C15850 | Samsung CL21A106KAYNNNE | 0805 | **Basic** | 6.5 M |
| C5 | 1 u 50 V X7R | C28323 | Samsung CL21B105KBFNNNE | 0805 | **Basic** | 2.3 M |
| D10 | B5819W 40 V 1 A | C8598 | CJ B5819W SL | SOD-123 | **Basic** | 602,705 |
| U1 | ATtiny1616 | C507118 | Microchip ATTINY1616-MNR | QFN-20 3x3 | Extended | 5,627 |
| U3 | HT7550-1 | C16106 | Holtek HT7550-1 | SOT-89-3 | Preferred Extended | 206,116 |

- **Every resistor and capacitor except R20 is Basic + Economy** with the existing
  land patterns, so no footprint changes or series/parallel networks were
  needed.
- **R20 is Extended by request** (a better part than a 0.25 W 1206). JLCPCB has no Basic
  39 R 1206 at all. The 0.5 W UNI-ROYAL HP06 has a full catalog record (200 V).
  Vishay RCS120639R0FKEA C4037776 (0.5 W anti-surge, 3,995 in stock) is the
  alternative; it wasn't chosen because the catalog omits its voltage rating.
- **Extended parts mean loading fees:** R20 and U1 are Extended and U3 is
  Preferred Extended, so expect JLCPCB's per-part Extended loading fee for each.
- **Audit result:**
  - Exact C-code, MPN, Economy and stock all pass, and R20 passes its stress
    check.
  - The only hard "fail" is the repo's Basic-only R/C policy flagging R20, which
    is intentional.
  - **Unknown:** the per-part human review attestations (land pattern, pin
    mapping, ratings, capacitor role); capacitor ESR and effective capacitance;
    and the D10/U1/U3 package-to-footprint matches.
  - These are left open on purpose (no boilerplate review notes).
- Earlier history: C14289 HT7533-1 (Basic) was superseded by the 5 V rail. The
  only Basic 5 V regulator found was AMS1117-5.0 C6187 (SOT-223, 15 V max), so
  HT7550-1 stays. Later opto candidates (not on either board): H11L1SM C899473,
  H11L1M DIP-6 C16587, 1N4148W C81598.

Hand-soldered, not JLC-assembled (no `LCSC` field, listed as manual in the
audit): J1 PJ366ST, J2-J9 PJ301M-12, D1-D8 3 mm LEDs, J10 2x5 header, J11 1x2
UPDI header, JP1 1x3 TRS header + 1 shunt.

## 6. References

- Bread Modular `modules/midi`: V1.0.3 (`b069a1b`) schematic and CHANGELOG (input baseline);
  2.0.1 schematic, `code/midi-2.0/platformio.ini` (6N137 version, pin map, clock).
- H11L1/H11L2 data sheet (Motorola Optoelectronics; same family as the onsemi
  H11L1M): electrical table and Figs. 3/4 (threshold vs VCC and temperature).
- Bread Modular `opt/AudioJacks` (MIT, Barwise): PJ301M-12/PJ366ST footprints and
  STEP models. Marked "Untested" upstream.
- Supplier attribute data: LCSC/JLCPCB catalog (URLs and hashes in
  `sourcing-candidates.json`); datasheet URLs are listed there per part.
- **Datasheets are not archived in the repo.** The HT7550-1 C16106 URL in
  `sourcing-candidates.json` no longer serves a PDF (it returns an HTML page,
  checked 2026-10-19), so "tab = pin 2 = VIN" (the heat-sink premise) and the
  ceramic output-capacitor question rest on the usual HT75xx-1 SOT-89 pinout, not
  on a document in the repo. Before the U1/U3/D10 review attestations are signed
  (§5, README order gate 4), archive their datasheet PDFs with SHA-256 and cite
  the pin-map, land-pattern and ratings pages.
- Mechanical fit: [mechanics.md](mechanics.md), [geometry.json](geometry.json),
  [fit/fit-report.json](fit/fit-report.json).

## 7. V2: mis-patch protection (S3 schematic, R3 routing)

V2 is V1 plus protection against a CV/gate cable (up to ±12 V, any source
impedance) patched into MIDI IN or any MIDI OUT, for as long as it stays in. The
outputs still drive another module's ATtiny1616 RX pin through 1 k at 5 V, MIDI IN
takes 3.3 V and 5 V senders, and there is still no optocoupler. The panels, jacks,
LEDs, stack and every V1 mechanical key in `geometry.json` are unchanged:
`tools/v2/build_layout.py` asserts that `docs/v2/geometry.json` differs from
`docs/geometry.json` only in `revision` and `back_side_parts`.

Sources: `hardware/v2/` (generators in `tools/v2/`, placement in
`docs/v2/geometry.json`, schematic PDF `docs/v2/midi-schematic.pdf`). Datasheets
read for this section (LCSC copies, SHA-256 of the PDFs in the ignored
`research/datasheets/`):

| Part | Document | SHA-256 | Used for |
|---|---|---|---|
| ATtiny1616 (C507118) | Microchip 40001997C, Table 37-1 (p. 552), 37.x I/O (VIH/VIL, Rp) | `97b2c869…` | Injection-current limit, VIH 0.7·VDD |
| BAT54SWT1G (C78260) | onsemi BAT54SWT1/D Rev. 11 | `800844c4…` | Pinout 1 A / 2 K / 3 common, VF, CT |
| MMBT3904 (C20526) | JSCJ MMBT3904 Rev. 2.1 | `6c2034cb…` | Pinout 1 B / 2 E / 3 C, VEBO 6 V, ts |
| CJ431 (C3113) | JCET CJ431/CD431 (Oct 2017) | `68a40507…` | SOT-23 pinout 1 REF / 2 K / 3 A, Vref, PD |
| 1N4148W (C81598) | Semtech 1N4148W | `54de8e40…` | SOD-123, pad 1 = cathode |

### 7.1 Why V1 is not protected

The ATtiny1616 absolute maximum ratings (Table 37-1) allow **±1 mA** of I/O pin
injection current at 4.9 V < VDD ≤ 5.5 V (the ±15 mA figure only applies at
VDD ≤ 4.9 V), 45 mA summed over all pins, and a pin voltage of −0.5 V to VDD + 0.5 V.
On V1:

- An output (GPIO → 1 k → tip) patched to +12 V pushes (12 − 5.3)/1 k ≈ 6.7 mA
  into the pin's clamp, and that current lands on +5V, which the HT7550-1 cannot
  sink. −12 V pulls about 11.4 mA out of the pin, and the 0603 1 k dissipates
  ~0.13 W against its 0.1 W rating.
- The input drives PB3 directly, limited only by the source's output resistance.

### 7.2 MIDI input: NPN front end

```
J1 T/R -> JP1 (TRS A/B) -> MIDI_IN --+-- R22 100k -- +5V      (idle pull-up)
                                     +-- R1 10k --+-- Q1 B    MMBT3904
                                     |            +-|<|- GND  D9 1N4148W (K at base)
                                     |   Q1 E -- GND
                                     |   Q1 C -- RX_Q --+-- R2 22k -- +5V
                                     |                  |
                                     |              JP2 1
                                     |              JP2 2 ------------ RX (U1 PB3)
                                     +------------- JP2 3
JP2: shipped open; solder 1-2 = protected, or 2-3 = direct (7.2.1)
```

- **3.3 V and 5 V senders.** Q1 switches at its VBE (~0.6 V), so a 3.3 V high gives
  (3.3 − 0.7)/10 k ≈ 0.26 mA of base current and a 5 V high 0.43 mA, against
  0.23 mA of collector current (R2). Q1 saturates with any hFE above ~1 (MMBT3904:
  100 minimum at 10 mA). A sender pulling its data line low through 220 R (or
  10-33 R) leaves MIDI_IN at a few millivolts (R22 sources 23 µA), far below 0.6 V.
  An open-collector sender works too: R22 is its pull-up.
- **±12 V.** +12 V drives (12 − 0.7)/10 k ≈ 1.1 mA into the base. −12 V is clamped
  by D9 at about −0.7 V at the base (Q1's VEBO is 6 V), again ~1.1 mA. R22 then
  sees 17 V (2.9 mW). PB3 only ever sees Q1's collector, 0 to 5 V.
- **Idle.** With no cable (the PJ366ST has no switch) or no shunt, R22 + R1 give
  Q1 about 39 µA of base current, enough to hold RX low = inverted idle. A shunt on
  the wrong conductor puts the sender's +V side on MIDI_IN: also idle.
- **Inverting.** RX is low for a MIDI high. **Firmware must set `PORT_INVEN` on
  PB3** (`PORTB.PIN3CTRL |= PORT_INVEN_bm`, with no pull-up), the opposite of V1
  (section 3.2) and the same pattern Bread Modular V2 used with its 6N137. The pin
  map is otherwise unchanged, so V1 and V2 firmware differ only in this one line.
- **Speed (simulated, 7.9).** Q1 is overdriven (forced gain ~1-2) and turned off
  only by R1 (~65 µA), so its storage time is longer than the datasheet's 200 ns
  (IB1 = IB2 = 1 mA). Simulated, a MIDI start edge reaches PB3 (RX past VIH) 0.9-2.3 µs
  late, and up to 4.4 µs at the stress corner. The opposite edge is 0.1-0.4 µs late.
  The worst skew is 12.5 % of the 32 µs bit. The ATtiny USART samples at mid-bit, so
  decoding is unaffected: the receiver clock-error window stays within 0.3 % of an
  ideal input's. The skew would have to pass ~4 µs before the window shrinks.
- No galvanic isolation (sleeve = GND, as V1).

#### 7.2.1 JP2: debug bypass of the input front end

JP2 is a 3-pad solder jumper (KiCad `SolderJumper-3_P1.3mm_Open`, copper only,
not in the BOM/CPL) on the back, left of R2 under the J1 sleeve pad. It selects
what drives PB3 (RX). **It ships open** (S3/R3): all three pads are separate, and
you solder one bridge by hand before first use. Switching is then desoldering one
bridge and soldering the other, with no copper to cut. (S2/R2 had pads 1-2 joined
by a copper strip.)

| JP2 | PB3 is driven by | Firmware | Mis-patch protection |
|---|---|---|---|
| **1-2** (solder bridge, silk `P`; the normal position) | Q1 collector (RX_Q), R2 pull-up | `PORT_INVEN` **on** | Yes (7.2) |
| **2-3** (solder bridge, silk `D`) | MIDI_IN directly, as V1 | `PORT_INVEN` **off** (V1 firmware) | **None**, as V1 |

- **Why a solder jumper, not a pin header:** a 2.54 mm 1x3 header needs ~8 mm of
  board length free on both sides (its THT pins come through the F side, where the
  jack bodies are). The only such spots are far from the input stage (the bottom
  zone, which is J10/J11 and the IDC socket envelope). The 1.3 mm-pitch pads fit
  between R2 and the left board edge with no other part moved.
- **Why R2 is on RX_Q, not RX:** in the direct position PB3 then sees only
  MIDI_IN, as in V1 (no 22 k on the pin). Q1 still switches from R1, but its
  collector is open and drives nothing.
- **Direct-mode levels:** MIDI_IN still carries R22 (100 k to +5V) and R1 + Q1's
  base (to ~0.7 V). A 5 V sender through 1 k (a V1/V2 output) gives a high of
  ~4.6 V (VIH 3.5 V) and a low of ~0.05 V. A 3.3 V sender through 33 Ω gives
  ~3.29 V: the same as V1, so below the datasheet VIH (0.7 VDD = 3.5 V) and only
  working on typical thresholds (section 3.2). Use the protected position for
  3.3 V senders.
- **No cable in direct mode:** R22 holds MIDI_IN, and so PB3, high = idle
  (non-inverted). V1 has no pull-up there at all.
- **As delivered, JP2 is open and PB3 floats:** MIDI IN does nothing until one
  bridge is soldered. The floating pin is harmless to the chip, but the received
  data is noise, so bridge 1-2 (or 2-3) before testing. **Never bridge all three
  pads:** that ties MIDI_IN to the Q1 collector, which pulls it
  down whenever the input is high, and nothing decodes.
- Switching: wick the solder off the present bridge, check with a meter that the
  pads are apart, then bridge the other pair.

### 7.3 Outputs: Schottky clamp behind the 1 k

```
GPIO (CHn_TX) --+-- Rn 1k 0805 -- OUTn tip      (Rn = R3, R5, R7, R9, R12, R14, R16, R18)
                +-- D(n+10) BAT54SW pin 3       pin 1 (anode) GND, pin 2 (cathode) +5V
```

- **Normal operation is unchanged:** the receiver still sees GPIO → 1 k → tip, a
  ~4.9 V high and ~0 V low. The clamps conduct only beyond about −0.3 V / +5.3 V.
  Their leakage is µA-level (2 µA max at 25 V). Their ≤ 10 pF sits on the GPIO
  side, driven by the pin (≤ 67 Ω), not behind the 1 k. Simulated (7.9), the
  receiver-side edges are identical to V1's to within 10 ns. The 1 k and cable
  capacitance set them, as in V1: 0.14 µs to VIL/VIH with 100 pF, 0.6 µs with
  450 pF, 1.3 µs with 1 nF.
- **Mis-patch:** the 1 k limits the current and the Schottky diverts it from the
  pin's internal diodes. −12 V on the tip draws 11.6 mA through the lower diode
  (VF ≤ 0.40 V at 10 mA, ≤ 0.50 V at 30 mA), so the pin stays above −0.5 V. +12 V
  pushes 6.7 mA through the upper diode (VF ≤ 0.40 V), so the pin stays below
  VDD + 0.5 V. The pin's own clamp current is then negligible, within the
  ±1 mA limit. Diode dissipation is ~5 mW.
- **Resistors:** 0805 (0.125 W, Basic C17513) instead of 0603. A hard −10.5 V
  op-amp output (the usual swing on ±12 V rails) puts 10.1 V / 0.102 W into the
  resistor, within its rating. A zero-impedance −12 V source would be 0.134 W, 7 %
  over the rating, and is not covered by the rating. Typical Eurorack outputs have
  ~1 k of output resistance, which halves the current (34 mW). A 1206 (0.25 W) did
  not fit: R7 and R9 share the J4/J5 band, and the via, the LED lanes and the tip
  pads leave no room for the longer pads.

### 7.4 +5V clamp: U2 CJ431 shunt

The upper clamps return the mis-patch current to +5V, and the HT7550-1 can only
source current. With several outputs on +12 V, the injected current (up to
8 × 6.2 mA ≈ 49 mA from hard sources) can exceed what U1 and the LEDs draw, and +5V
would rise toward U1's 6 V absolute maximum. U2 (CJ431, a TL431-type shunt
regulator) with R23 12 k / R24 10 k turns on at 2.495 V × (1 + 12/10) = **5.49 V**
nominal:

- Worst case (Vref 2.475-2.525 V, 1 % resistors, 4 µA REF current, 0.5 Ω dynamic
  impedance), it stays off below 5.39 V and clamps by 5.69 V. That is below the
  6 V absolute maximum and above the HT7550-1 output (5.0 V ± a few %), so U2 never
  fights the regulator. It is off in normal operation: ≤ 1 µA off-state current
  plus 0.23 mA in R23/R24.
- Worst-case dissipation: all eight outputs on a hard +12 V gives ~49 mA minus
  ~10 mA of MCU load, so ~39 mA × 5.5 V ≈ 0.21 W. That is 70 % of the 300 mW SOT-23
  rating (417 K/W), fault-only. One or two mis-patched outputs give ≤ 70 mW.
- The CJ431 SOT-23 pinout is **1 REF, 2 K, 3 A**. That is KiCad's `TL432DBZ`
  symbol, not `TL431DBZ` (TI's 1 K, 2 REF). The schematic uses `TL432DBZ` with
  value CJ431, and the netlist parity check confirms the pads.
- TL431-type parts can oscillate with some load capacitances. U2 sits on +5V with
  C3/C4 (10 µF each) and C1 (100 nF), and it is off unless there is a fault. Whether
  it is stable while clamping is a bench item (7.7).

### 7.5 Layout (R1, R2, R3)

V2 starts from the V1 R4/R5 copper (`tools/v2/route_plan.py`, shared
plan/apply/promote; nothing autorouted):

- **Clamps D11-D18** sit right of each output resistor, in the gap between the jack
  tip pad and the LED. Pin 3 goes to the resistor's GPIO-side pad (to the TX via for
  outputs 6-8), pin 1 to the LED's GND pad just above it, and pin 2 to a +5V via.
  D14 (output 4) has no LED GND pad above it and gets its own GND via.
- **R10** (LED 4) moved from the J4/J5 band to just below J5. LED4_A runs up
  between the J5 tip pad and D4 to the anode, which frees the J4/J5 band for D13 and
  D14. R7/R9 moved slightly apart and R18 0.15 mm up, for the longer 0805 courtyards.
- **+5V clamp rail:** F.Cu, 0.3 mm, along the right board edge (x 118.6), through
  the eight clamp vias. It is fed from the top: a new F.Cu spine branches off the
  V1 +5V trunk above J6 and runs straight up x 103.545 through the S/TN pad gaps of
  J5-J2 (the same gap the V1 trunk uses lower down) to U2. From there it continues
  to the J1/J2 band (R2, R22) and east to the top of the rail. The rail does not
  reach the LDO directly, so the F.Cu VIN_LDO heat sink stays one piece exactly as
  in V1.
- **Input stage:** Q1, R1, D9, R2 and R22 sit between the J1 ring and tip pads and
  below the tip pad. JP1 pin 2 is MIDI_IN.
- **JP2 (added in routing R2)** sits left of R2, under the J1 sleeve pad (pin 1 at the top). R2's
  top pad joins Q1's collector to JP2 pin 1 (RX_Q). RX comes up the V1 corridor
  lane, runs under the Q1 emitter GND via, up x 106.3 and between the R2 pads into
  pin 2. MIDI_IN leaves R1 through a via, crosses on F.Cu at y 69.35 (between the
  RING track and the +5V rail) and comes back to B.Cu through a via under pin 3.
  B silk `P` (pin 1) and `D` (pin 3) sit left of the jumper. Routing R2 changed
  nothing else: every other footprint, track, via and zone is as R1.
- **Routing R3** swaps JP2 to the stock `Open` footprint (same pads, no 1-2
  copper strip, no net tie). Nothing else on the board changed.
- **U2/R23/R24** sit in the J2/J3 band left of the corridor.
- **LED8's lane** stays in the corridor down to its resistor row. V1 crossed over at
  y 136.4, where D17 now sits.
- **GND stitching:** V1's right-edge stitching vias are gone (the rail runs there).
  The LED GND pads, the jack sleeve pads, the left-edge vias and four new GND vias
  join the pours.
- **Version marking:** B silk `MIDI V2.0` in the place of V1's `MIDI V1.0`.
  Both are visible on the assembled board's back.

### 7.6 Checks (V2)

- ERC 0 (`--severity-all`). The native netlist matches the generator's circuit
  table pin for pin (ignored `research/v2-src/check_netlist.py`): 62 components,
  46 nets, 10 no-connects (S2; S3 changes only JP2's symbol and footprint).
- Shared `pcb apply` accepted the routing candidate: ERC/DRC empty, 0 unconnected,
  parity 0. `pcb promote` re-bound every model by content (0 external). The
  routing-R2 candidate (ignored `research/v2-bypass/`) differs from R1 only in JP2, its three
  nets' tracks, two MIDI_IN vias and the `P`/`D` silk (checked by a board diff).
  The routing-R3 candidate (ignored `research/v2-jp2open/`) differs from R2 only in
  JP2's footprint (the 1-2 strip removed) and the title block: board diff, and
  per-layer plots pixel-identical except that strip on B.Cu.
- Shared `check` (`tools/v2/kicad-project.json`): `no_findings_in_requested_checks`
  (ERC 0, DRC 0 at all severities with zones refilled, 0 unconnected, schematic
  parity 0, ref/pin/net parity equal, `jlcpcb/v2/source-sha256.json` equal).
  Reports: `docs/v2/fit/schematic-erc.json`, `docs/v2/fit/carrier-drc.json`.
- 3D fit (`tools/fit_assembly.sh v2`): 0 mm³ interference against both panels. The
  report is identical to V1's (`docs/v2/fit/fit-report.json`), also after R2 and R3. No new
  part sits inside the 16-pin IDC socket envelope.
- Live assembly audit (2026-10-19 ~03:13 UTC, re-run for S2/R2 at 03:54 UTC and for S3/R3
  at 05:10 UTC, each with the same per-part result and JP2 reported as excluded
  from the BOM; `--strict-live`, 5 boards, bottom
  side): 41 parts in 18 BOM rows. Every C-code, MPN, Economy flag and stock level
  passes, and every resistor passes its stress check, including the 0805s against
  the 0.102 W fault requirement in `docs/v2/jlcpcb-audit-requirements.json`. The
  only hard fail is R20's intentional Extended class (as V1). Human review
  attestations remain open (section 5).

### 7.7 Open items (V2)

- **Bench:** patch +12 V and −12 V (bench supply, and a real CV output) into
  MIDI IN and each output for minutes, with the module running. Pass if U1 keeps
  routing and +5V stays below 5.7 V. Also check that U2 does not oscillate while
  clamping (scope on +5V with 2-8 outputs on +12 V).
- **Input:** receive from a 3.3 V sender and a 5 V sender, Type A and B, with V2
  firmware (`PORT_INVEN` on PB3) and JP2 1-2 soldered. Then, on one board, move
  the JP2 bridge to 2-3 and receive from a 5 V sender with V1 firmware (no
  `PORT_INVEN`) to confirm the direct path, and move it back.
- **Firmware:** V2 needs the one-line `PORT_INVEN` change (7.2). There is no
  firmware in this repository yet. For ATtiny-to-ATtiny links (V1 and V2 alike),
  correct the USART `BAUD` with the factory `SIGROW.OSC20ERR5V` value (7.9).
- The V1 items still apply to V2: U3 fault test and LED brightness (section 4),
  plus the order gates in `jlcpcb/v2/README.md`.

### 7.8 Sourcing (V2 additions, observed 2026-10-19)

| Refs | Part | C-code | Class | Stock observed |
|---|---|---|---|---:|
| D11-D18 (8) | onsemi BAT54SWT1G, SOT-323 | C78260 | Extended (no Basic dual Schottky found) | 62,593 |
| Q1 | CJ MMBT3904, SOT-23 | C20526 | **Basic** | 431,331 |
| U2 | CJ CJ431, SOT-23 | C3113 | **Basic** | 312,593 |
| D9 | Semtech 1N4148W, SOD-123 | C81598 | **Basic** | 4,453,208 |
| R3, R5, R7, R9, R12, R14, R16, R18 | 1 k 0805 0.125 W | C17513 | **Basic** | 44.2 M |
| R1, R24 | 10 k 0603 | C25804 | **Basic** | 39.6 M |
| R2 | 22 k 0603 | C31850 | **Basic** | 3.4 M |
| R22 | 100 k 0603 | C25803 | **Basic** | 19.3 M |
| R23 | 12 k 0603 | C22790 | **Basic** | 0.94 M |

Every V2 R/C is Basic except R20 (as V1). The clamps add one Extended part type
(one loading fee covers all eight). Stock is a snapshot, not a reservation.

### 7.9 Signal timing at 31.25 kbaud (simulated 2026-10-19)

ngspice transient (system libngspice, ignored `research/v2-sim/midi_timing.py`,
output `research/v2-sim/results.txt`). The bytes `90 3C 64 55 AA F8 FE 00 7F` are
sent back to back, and the receiver pin is read at the ATtiny datasheet limits
VIL 0.3 VDD / VIH 0.7 VDD. A model of the tinyAVR USART in normal-speed mode
(16 samples per bit, majority of 8/9/10, start validated, stop checked, 8 sample
phases) decodes the result. "Window" is the receiver clock error over which every
byte decodes. An ideal digital input gives −3.8/+5.5 % in this model. The
datasheet's Table 24-6 limit is about ±4.5 % for 8 data bits.

Models: Fairchild 2N3904 (MMBT3904 die), 1N4148, and a BAT54 fitted to the
BAT54SW typical VF with 10 pF CT. Q1 corners:

- **typ:** the model as published. Its storage time in the datasheet test circuit
  is 111 ns.
- **ds-max:** Tr ×1.82, so the datasheet test circuit gives the 200 ns maximum
  (`calibrate.py`).
- **stress:** 2 × ds-max, hFE 100, 85 °C.

| MIDI IN case (cable C, C on RX) | Start edge late | Other edge late | Window |
|---|---:|---:|---:|
| V2 OUT → 100 pF → V2 IN, 10 pF (typ / ds-max / stress) | 0.9 / 1.2 / 2.4 µs | 0.1 µs | −3.8 / −3.8 / −3.7 % |
| V2 OUT → 450 pF, 30 pF | 2.1 / 2.3 / 3.4 µs | 0.3 µs | −3.8 / −3.7 / −3.7 % |
| V2 OUT → 1 nF, 30 pF | 3.3 / 3.4 / 4.4 µs | 0.4 µs | −3.7 / −3.7 / −3.5 % |
| 3.3 V / 33 Ω → 450 pF, 30 pF | 1.2 / 1.4 / 2.4 µs | 0.1 µs | −3.8 / −3.8 / −3.7 % |
| 3.3 V / 1 k → 450 pF, 30 pF | 1.8 / 2.0 / 3.0 µs | 0.3 µs | −3.8 / −3.8 / −3.7 % |
| 5 V / 220 Ω → 450 pF, 30 pF | 1.4 / 1.6 / 2.8 µs | 0.1 µs | −3.8 / −3.8 / −3.7 % |

- RX is at 0.03 V and 5.00 V at mid-bit in every case, so 3.3 V and 5 V senders
  give full logic levels. The + side of the window is ≥ +5.5 % throughout.
- Skew budget: delaying the start-type edges of an ideal waveform by 4 µs gives
  −3.5 %. At 6 µs the window is −2.8 %, and at 10 µs −1.4 %. The worst simulated case
  (4.4 µs) is at the edge of where the window starts to shrink. A typical
  patch cable (≤ 450 pF) keeps it ≤ 3.4 µs.
- **Outputs:** V2 and V1 outputs give the same receiver-pin delays (to VIL/VIH),
  with GPIO drive 25 or 67 Ω (the VOH ≥ 4 V at 15 mA limit): 0.14 µs into
  100 pF, 0.6 µs into 450 pF, 1.3 µs into 1 nF. The window is the ideal one in every
  case. The CHn_TX node stays at 0.00-5.00 V, so the clamps never conduct.
  The mid-bit clamp current is 15 nA at 25 °C and 27 µA at 85 °C (model leakage),
  supplied by the GPIO.
- **Clock budget (V1 and V2 alike, not a front-end effect):** OSC20M is ±2 %
  only relative to its factory-stored error value (0-70 °C), but ±3 % at 25 °C and
  ±5 % over full operation without that correction. Two uncorrected ATtinys can
  exceed the ~4 % window. Firmware should therefore apply `SIGROW.OSC20ERR5V` to
  the `BAUD` value (or use a crystal-accurate sender).
- This is a simulation with generic models, not a measurement. The bench check in
  7.7 (3.3 V and 5 V senders) still applies.
