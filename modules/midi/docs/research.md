# MIDI module research

Status: **S3 schematic + R1 routed carrier** (rev. 2026-10-18): native schematic
(`hardware/midi.kicad_sch`, ERC 0) at the **5 V** Bread Modular logic level (S3), and
the fully routed 2-layer carrier (R1, section 3.6; shared check: no findings). Opto
removed, deferred to V2. This document records the Bread Modular baseline, the
circuit as drawn, the remaining open checks and dated sourcing observations.
Nothing here is bench-validated and nothing is released.

## 1. Goal

- A 4HP Eurorack module that takes **TRS MIDI in** and fans it out to **8 TS
  "modular MIDI" outputs**. Each output carries one channel's MIDI stream as a
  logic-level UART signal (tip) plus ground (sleeve) over an ordinary patch cable.
- **ATtiny1616** firmware routes MIDI channel *n* to output *n*, as Bread Modular
  `midi` does.
- One LED per output, hand-soldered 3 mm THT.
- **Input = Bread Modular V1 direct input.** No optocoupler in this version; an
  isolated input with automatic voltage sensing is planned for **V2** (section 3.5).
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
thresholds). This module also runs U1 at 5 V and adds R2 22 k to +5 V so that a
3.3 V high lands just above VIH (section 3.2).

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

## 3. Circuit (as drawn in the S3 schematic, routed in R1)

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
| R2 22 k RX pull-up | 0 (RX idle high) | 0.23 mA |
| 8 LEDs, (5 - ~1.9 V)/1 k each (~3.1 mA) | ~3-6 mA (activity flashes) | 25 mA (all lit) |
| 8 TS outputs into high-impedance inputs / into shorts (idle-high UART: 5 mA each) | ~0 | 40 mA |
| **Total from +12 V** | **~15 mA** | **~77 mA** |

Without a dropper the LDO would dissipate (12 - 0.45 - 5) V x I: about 0.10 W
typical and 0.50 W in the worst case, which is too hot for a bare SOT-89.
**R20 = 39 R, 1206** splits it: at 77 mA R20 drops 3.0 V (0.23 W) and the LDO keeps
about 0.27 W; at 15 mA they take 0.01 W / 0.09 W. The LDO input then sits at about
8.5 V (77 mA) to 11 V (15 mA), above the 5 V output plus dropout even on an
11.4 V rail (7.9 V at 77 mA). The worst case is a fault (every output shorted and
every LED lit at once). R20 then runs at about 92 % of a standard 0.25 W 1206
rating. Prefer a 0.5 W 1206 part at the sourcing step (same footprint).
The R1 routing adds no extra copper to the U3 tab (VIN_LDO) beyond its own pad and
0.4 mm tracks, so check U3's temperature on the bench in that fault case.
Eurorack draw is about 15 mA typical / 77 mA maximum on +12 V, and 0 mA on
-12 V and +5 V.

### 3.2 MIDI input: Bread Modular V1 direct, TRS Type A/B on JP1

```
J1 Tip  --> JP1.1 (A)
            JP1.2 (DATA) --R21 4.7k--> RX (PB3, USART0 RX)
J1 Ring --> JP1.3 (B)
J1 Sleeve --> GND (direct, as Bread Modular V1 / 0.5.0)
RX pull-up: R2 22k to +5V
```

This is the Bread Modular V1 input (TRS conductor chosen by a header jumper,
straight into PB3) plus two resistors: R21 limits the clamp current if a wrong
(CV/gate) cable is plugged in, and R2 holds RX idle-high when there is no cable
or no shunt, and lifts 3.3 V highs.

**JP1 = TRS Type, 1x3 2.54 mm THT header on the back** (beside J1, in the LED
column, like the UPDI header J11). B silkscreen: `TRS` above the header, `A`
level with pin 1 and `B` level with pin 3: the shunt always covers the lettered
pin (1-2 = A, 2-3 = B); the shared middle pin 2 is unlabelled.

| JP1 shunt | TRS type | Data conductor | Gear |
|---|---|---|---|
| **1-2 (`A`)** | **Type A** (MMA/AMEI standard) | Tip (MIDI pin 5) | Korg, Make Noise, most current gear |
| **2-3 (`B`)** | Type B | Ring (MIDI pin 5) | Arturia, Novation (older), some others |
| none | - | - | No input; RX idles high, no garbage bytes |

Only the data conductor (MIDI pin 5, the one the sender pulls low) is used. The
other conductor (pin 4, the sender's +V side) is left open, as in V1. With the
wrong shunt the data conductor sits at the sender's +V, so the input just stays
idle: harmless, move the shunt.

**3.3 V and 5 V senders.** U1 runs at 5 V: VIH ≥ 0.7·VDD = 3.5 V and
VIL ≤ 0.3·VDD = 1.5 V by datasheet. A 5 V sender is in spec directly. A 3.3 V
sender's high alone is below VIH, so R2 (22 k to +5 V) lifts it. With R21 4.7 k
plus a 33-220 R sender output, RX sits at about 3.3 + 1.7 x 4.9/26.9 ≈ 3.6 V
for a 1 bit (just above 3.5 V) and 5 x 4.9/26.9 ≈ 0.9 V for a 0 bit (below
1.5 V). The 3.3 V high margin is only ~0.1 V by datasheet, so bench-check with a
real 3.3 V sender. A wrong cable carrying +12 V into the jack is clamped at PB3
through R21: (12 - 5.3 V) / 4.7 k ≈ 1.4 mA. Check that against the ATtiny1616
injection-current limit at the sourcing step (decision D6). R21 with ~10 pF of
pin capacitance is ~50 ns, negligible at 31.25 kbaud.

**No galvanic isolation.** The sleeve is tied to GND, so the module shares ground
with the sender (V1 behaviour; it also suits senders that want the shield
grounded, per the Bread Modular changelog note on Elektron gear). Ground loops are
the V2 opto input's job (section 3.5).

**Firmware:** no inversion (do **not** carry over V2's `PORT_INVEN`); RX idles high.

### 3.3 MCU and pin map (kept identical to BM so the firmware ports)

| Function | Pin | BM role |
|---|---|---|
| MIDI in RX | PB3 (USART0 RX): R21 4.7 k from JP1 + R2 22 k pull-up to +5 V | same pin |
| OUT1-OUT7 | PA5, PA6, PA7, PB5, PB4, PB1, PB0 (`SoftwareSerial` TX) | same |
| OUT8 | PB2 (USART0 TX) | same (V1.0.3) |
| LED1-LED8 | PC0, PC1, PC2, PC3, PA1, PA2, PA3, PA4 | BM gate pins, now driving LEDs |
| UPDI | PA0 via R11 4.7 k to J11 | same |

- **UPDI header J11: 1x2 2.54 mm THT pin header on the B side** (bottom of the LED
  column, beside the power header), pin 1 at the top: **1 UPDI, 2 GND**. Use a
  serialUPDI adapter or any UPDI programmer with 2.54 mm Dupont leads. There is no
  VCC pin: program with the module on Eurorack power. The rail is 5 V, so 5 V
  serialUPDI adapters match it, and UPDI goes through R11 4.7 k as in Bread
  Modular.
- **Clock:** at 5 V the ATtiny1616 runs at 20 MHz, as the BM firmware does
  (`board_build.f_cpu = 20000000L`). The firmware ports without clock changes; just
  don't carry over V2's `PORT_INVEN`.
- All 18 I/O are used (17 GPIO + UPDI), as in BM. There is no spare pin for a
  MIDI-in activity LED.

### 3.4 Outputs and LEDs

- `GPIO -> 1 k -> TS tip`, sleeve = GND, exactly as in BM. There is no extra clamp
  or ESD part, per the brief.
- `GPIO -> 1 k -> LED -> GND`: about 3.1 mA per red LED at 5 V. Use
  high-efficiency 3 mm LEDs and raise the 1 k if they are too bright behind the
  panel (D5).

### 3.5 V2: opto-isolated input with voltage sensing (deferred)

The reason for an optocoupler here is to **break ground loops**. The S1 attempt
(H11L1 enabled by a shunt, sharing RX with the always-connected direct path)
could not do that: the direct path and the sleeve-to-GND kept the sender's ground
tied to the module. So the opto is removed from this version and comes back in V2
as a properly isolated input:

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
- Space: the J1/J2 band on the back (where the S1 opto sat) now carries R2 and the
  RX/+5 V/LED1 tracks of R1, so V2 will need that band re-laid out.

### 3.6 Routing (R1)

Two layers, every net routed with explicit geometry (no autorouter), written by
`tools/route_plan.py` and applied with the shared `pcb plan/apply/promote`
transaction (README "Rebuild").

- **Widths:** 0.25 mm signals, 0.2 mm at the U1 fan-out (0.4 mm QFN pitch), 0.3 mm
  +5 V trunk, 0.4 mm VIN_D/VIN_LDO, 0.5 mm +12 V. Vias 0.6/0.3 mm (37 in total).
- **GND:** F.Cu and B.Cu are both poured with GND, stitched by 14 edge vias
  between the jack rows plus one via in U1's exposed pad (pin 3 tied to the pad).
  The shared zone op connects pads solidly (no thermal reliefs), so the THT jack
  sleeve and LED cathode pads need a hot iron when hand-soldering.
- **Layer plan.** The pin map is Bread Modular's, so on every side of U1 some
  nets go up and some go down. Each layer keeps a lane order that matches its turn
  order:
  - B.Cu up: RX (to R21/R2), LED1-LED3 up the corridor, LED4 up the right
    channel (R9 sits in its crossing).
  - F.Cu up: TX1-TX4 from vias in the left zone. Each comes back to B through a
    via at x 112.3 beside its resistor.
  - TX6-TX8: up on B to vias in the J4/J5 gap, then down on F into the right
    channel, entering their resistors from the right.
  - TX5: across the F side of U1 and down the corridor.
  - UPDI: down the corridor on F to the J11 corner.
  - LED5-LED8: down on B. LED8 crosses into the right channel above the power
    cluster.
  - +5 V: up the left channel on F (LDO -> C3 -> via under U1 pin 4 -> C1), then
    on B to R2 at the top.
- **Placement changes made for routing** (all in `geometry.json`, generator
  rerun, fit re-checked):
  - The LED resistors are rotated 270 so pad 2 (LEDn_A) faces its LED.
  - R9 moved above J5.
  - U1 moved 1 mm lower.
  - C1 is under U1, C3 is in the left zone, and R2 is beside the RX lane.
  - These also cleared two pad shorts (C1/R9 and C3/R8) left by the S3 5 V
    regeneration.
- **Checks:**
  - Shared `check`: no findings. ERC 0, DRC 0 at all severities with zones
    refilled, 0 unconnected, schematic parity 0, ref/pin/net parity equal, and
    no exclusions.
  - The 3D fit is unchanged (`fit/fit-report.json`).

## 4. Decisions

| # | Decision | Recommendation |
|---|---|---|
| D1 | TS output logic level | **Decided (S3): 5 V.** U1 runs at 5 V from HT7550-1 on +12 V, so the outputs meet a 5 V BM receiver's VIH. A 16-pin cable's +5 V isn't used, which keeps 10-pin cables working. The input handles 3.3 V senders through R2 (section 3.2) |
| D2 | LDO thermal margin vs fault cases | **Decided: R20 = 39 R 1206** (section 3.1); prefer a 0.5 W part, and bench-check U3 in the fault case |
| D3 | Opto | **Decided: none in this version**; isolated, voltage-sensed opto input in V2 (section 3.5) |
| D4 | TRS type selection | **Decided: JP1 1x3 2.54 mm header + shunt on the back**, `A` (1-2) / `B` (2-3) |
| D5 | LED colour/value | Drawn as high-efficiency red, 1 k (~3.1 mA at 5 V); confirm brightness behind the panel |
| D6 | R21 value | 4.7 k unless the ATtiny1616 injection-current limit (~1.4 mA from a +12 V wrong cable) asks for more; raising it lowers the 3.3 V-sender high margin |

## 5. Sourcing observations (dated, transient)

Retrieved 2026-10-18 ~14:10 UTC with `opt/kicad-tools/jlcpcb/assembly.py lookup
--strict-live`. Compact record: [`sourcing-candidates.json`](sourcing-candidates.json).
Raw snapshots are in the ignored `research/jlc-cache/`. Stock is a snapshot, not a
reservation or order acceptance. Passives are not sourced yet.

| Ref | C-code | MPN | Package | Class | Economy | Stock observed |
|---|---|---|---|---|---|---:|
| U3 | C16106 | HT7550-1 (Holtek, 30 V) | SOT-89-3 | Preferred Extended | yes | 206,116 |
| U1 | C507118 | ATTINY1616-MNR | QFN-20-EP 3x3 | Extended | yes | 5,626 |
| D10 | C8598 | B5819W SL | SOD-123 | **Basic** | yes | 354,667 |

U3 was looked up again at S3 (same day). C14289 HT7533-1 (Basic, 118,291) is
superseded by the 5 V rail; the only Basic 5 V regulator found was AMS1117-5.0
C6187 (SOT-223, 15 V max input), so HT7550-1 stays.

V2 opto candidates from the same pass (not on this board): H11L1SM C899473
(Extended, 2,692), H11L1M DIP-6 C16587 (Extended, 11,180), 1N4148W C81598 (Basic).

Hand-fitted, not JLC-assembled: J1 PJ366ST, J2-J9 PJ301M-12, D1-D8 3 mm LEDs,
J10 2x5 header, J11 1x2 UPDI header, JP1 1x3 TRS header + 1 shunt. The schematic
carries `LCSC` fields for the three parts above only. Passives are unsourced, no
export has been made, and the ATtiny1616 and land patterns still need the
per-part audit in `opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`.

## 6. References

- Bread Modular `modules/midi`: V1.0.3 (`b069a1b`) schematic and CHANGELOG (input baseline);
  2.0.1 schematic, `code/midi-2.0/platformio.ini` (6N137 version, pin map, clock).
- H11L1/H11L2 data sheet (Motorola Optoelectronics; same family as the onsemi
  H11L1M): electrical table and Figs. 3/4 (threshold vs VCC and temperature).
- Bread Modular `opt/AudioJacks` (MIT, Barwise): PJ301M-12/PJ366ST footprints and
  STEP models. Marked "Untested" upstream.
- Supplier attribute data: LCSC/JLCPCB catalog (URLs and hashes in
  `sourcing-candidates.json`); datasheet URLs are listed there per part.
- Mechanical fit: [mechanics.md](mechanics.md), [geometry.json](geometry.json),
  [fit/fit-report.json](fit/fit-report.json).
