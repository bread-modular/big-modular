# MOTION research and circuit intent (S1 schematic, P1 placement)

A 6HP motion recorder: four knobs, four CV outputs. Hold REC and move a knob to record
that knob's motion; release and it loops. The brief (user, 2026-11-15):

- 6HP, **four knobs and four CV outs**. Each output is recorded by holding the one REC
  button and moving its knob by hand. An LED shows the motion.
- A **range selector**, one for the whole module: off = 0..+5 V, on = -5..+5 V.
- Once recorded, a take can be **moved up and down with its knob**.
- ATtiny1616 if it is good enough; extra memory and DACs as needed.
- Second message: the FRAM version, **recorded straight into the FRAM** (always saved,
  no save step); **hold REC for 5 s without moving a knob = erase every take**.
- Third message: schematic, THT placement and a 3D view with the panel. No routing yet.

Nothing here is built or bench-tested. The firmware (2026-11-24, `firmware/`) is compiled and
host-tested only. Sourcing is a dated
catalog observation, not an order.

## 1. Why these chips

| Need | ATtiny1616 alone | Decision |
|---|---|---|
| Take memory | 2 KB RAM: ~8 s per knob at 8 bit / 50 frames per second | **MB85RC256V** 32 KB I2C FRAM: no write delay, 10^12 cycles, so the takes are recorded and played straight from it |
| Four outputs | One 8-bit DAC | **MCP4728** quad 12-bit I2C DAC: four equal outputs, cheaper than the 8-bit quads in stock |
| Save | 256-byte EEPROM | Not needed: the FRAM is the working memory, every take survives power-off |
| Pins | 17 I/O | 14 used, 3 spare |

Take length: 32,768 bytes / 4 knobs / 2 bytes per frame / 50 frames per second =
**~81 s per knob** (a shared pool, split freely, is a firmware option). 2 bytes hold the
10-bit knob reading; 50 frames per second with interpolation between frames is enough
for a hand-moved knob.

I2C load at 400 kHz (estimate): playing and recording four tracks is ~3.5 % of the bus;
a 1 kHz update of all four DAC channels is 20-30 %.

## 2. Decisions made here (not in the brief)

| # | Decision | Why |
|---|---|---|
| D1 | **RANGE is a second tact button with its own LED** (LED on = -5..+5 V), state kept in the FRAM | The same 6 x 6 mm switch and printed cap the user already uses; "off / on" maps onto the LED. A toggle switch would be a new, unmeasured panel part. Not confirmed by the user |
| D2 | **RANGE is firmware only**: the output stage is always -5..+5 V; 0..+5 V uses DAC codes 2048..4095 | No analog switches; 12 bits leave 2.4 mV steps in the 0..+5 V range |
| D3 | **The four motion LEDs are driven by the MCU (hardware PWM)**, not by the output op-amps | Brightness can show the position in the selected range in both ranges, and the firmware can dim and blink them. The pins are spare |
| D4 | **All six LEDs through 10k** (0.33 mA at full duty) | `modules/mcc`: red LEDs at 3 mA had to be dimmed to 1 % in firmware. Dim by the circuit, fine-tune by PWM |
| D5 | **DAC reference = its supply (+5VA)**, and the output offset comes from the same +5VA | Everything is ratiometric: 0 V sits at DAC mid-scale whatever the regulator does. The MCP4728's own 2.048 V reference has no pin to derive the offset from |
| D6 | **10k / 100n low-pass (160 Hz, 1 ms) before each output amplifier** | Removes the 1 kHz update steps; far above any hand motion |
| D7 | **Knob zigzag, motion LED beside each knob** in the opposite column | Roomy knobs on 6HP: neighbouring knobs are 21.7 mm apart, same-column knobs 33 mm |
| D8 | **Power header on B between the lower jacks** (as `modules/16bit` R2), jack columns 1.45 mm outside the knob columns | The zigzag leaves no edge window long enough for a 16-pin socket without THT leads under it; the centre strip between the jack columns is free |

## 3. Circuit

### Power

Eurorack 2x5 header J5 -> series B5819W on each rail (D7, D8) -> +12V_F / -12V_F
(10u each) -> TL074. HT7550-1 (U1, 1u in, 10u out) -> +5V for the MCU, FRAM, pots and
LEDs; ~17 mA, ~0.11 W in the SOT-89.

**+5VA** = +5V through R1 10R with C6 10u + C7 100n (1.6 kHz): the MCP4728 supply, which
is also its reference, and the offset of the four output stages. Load <= 3 mA (DAC ~1 mA,
up to 0.5 mA per output stage), so <= 30 mV drop; one channel swinging full scale moves
+5VA by ~5 mV (0.1 % of span on the others).

### MCU: ATtiny1616 at 5 V, 20 MHz

| Pin | Net | Function |
|---|---|---|
| PA1 / PA2 / PA6 / PA7 | POT1..POT4 | Knobs, ADC0 AIN1 / 2 / 6 / 7, 10n at each pin |
| PB0 / PB1 | SCL / SDA | TWI0 default pins, 400 kHz, 2.2k pull-ups |
| PB2 / PA3 / PA4 / PA5 | LED1..LED4 | Motion LEDs, TCA0 split-mode WO2 / WO3 / WO4 / WO5 (default pins) |
| PB3 / PB4 | LED_REC / LED_RANGE | TCA0 WO0 / WO1 on their alternate pins (`PORTMUX.CTRLC`), because the default pins PB0 / PB1 are the I2C bus |
| PC0 / PC1 | REC_BTN / RANGE_BTN | Buttons to GND, internal pull-ups |
| PA0 | UPDI | 4.7k to J6 pin 1 |
| PB5, PC2, PC3 | - | Spare, unconnected |

No Bread Modular firmware exists for this module, so the pin map follows the hardware
and can still change during routing (ask first: it is a schematic change).

### I2C devices

- **U4 MB85RC256V** (SOP-8 150 mil, address 0x50, A0-A2 and WP tied low), 100n.
- **U3 MCP4728** (MSOP-10, address 0x60), VDD = +5VA, LDAC tied low (an output updates
  when its write is acknowledged), RDY/BSY unused. The firmware selects VREF = VDD.
  Its outputs start from its own EEPROM at power-on, before the MCU writes them: write
  mid-scale (0 V out) to that EEPROM once at bring-up.

### Outputs (x4)

`DAC -> 10k / 100n -> TL074 (+) ; (-) = 10k to +5VA and 10k to the output -> 1k -> jack`

- Gain 2 around +5VA: **Vout = 2 x Vdac - (+5VA)**. Code 0 = -5 V, 2048 = 0 V,
  4095 = +5 V. The DAC output stops ~10 mV short of GND and ~40 mV short of its supply, so the
  ends are ~-4.98 V / ~+4.92 V.
- Zero error: Rf / Rg are 1 % parts, so 0 V can sit up to +/-50 mV off; the span follows
  +5VA (HT7550-1, +/-3 %). Fine for modulation; a per-channel trim in firmware is possible.
- 1k series resistor (0.5 W 1206): a permanent +/-12 V mis-patch dissipates 0.29 W.
  Output impedance 1k, as the other modules.

### Buttons and LEDs

- SW1 REC, SW2 RANGE: 6 x 6 x 7 mm THT tact switches (the `modules/8bit` part and printed cap).
- D1-D4 motion, D5 REC, D6 RANGE: 3 mm THT, 10k each from the MCU pin.

## 4. Firmware intent (written 2026-11-24: `firmware/README.md`)

- Idle: each output plays its take in a loop; the knob shifts the take up or down.
  No take: the output follows the knob.
- REC held + a knob moved: that knob is recorded (frames written straight to the FRAM);
  REC released: the take loops. The `modules/16bit` CPX4 recorder has this behaviour
  (one track per control, own length, glide from the last value back to the first).
- REC held 5 s with no knob moved: every take is erased (REC LED counts down).
- RANGE click: toggles 0..+5 V / -5..+5 V for all four outputs, stored in the FRAM.
- Motion LED brightness = output position within the selected range.

## 5. Sourcing (live lookups 2026-11-15, `docs/sourcing-candidates.json`)

| Part | LCSC | Class | Stock | Price (1+) |
|---|---|---|---|---|
| ATtiny1616-MNR (U2) | C507118 | Extended | 10,100 | $1.25 |
| MCP4728T-E/UN (U3) | C478093 | Extended | 15,946 | $2.63 |
| MB85RC256VPNF-G-AMERE2 (U4) | C45273903 | Extended | 16,911 | $2.16 |
| TL074CDR (U5) | C12594 | Extended | 177,450 | $0.24 |
| ESR18EZPF1001 1k 0.5 W 1206 (x4) | C2074262 | Extended | 99,501 | $0.02 |
| 10R 0603 (R1), 2.2k 0603 (R3, R4) | C22859, C4190 | Basic | millions | - |

All are Economic-assembly eligible. The other R/C, the B5819W and the HT7550-1
(Preferred Extended) are the `modules/8bit` parts. 52 assembled SMD parts, 18
hand-soldered THT parts. Stock is a snapshot, not a reservation. A full assembly audit
has not been run (there is no board export yet).

U3 land pattern: the stock KiCad `TSSOP-10_3x3mm_P0.5mm` (pads 1.45 x 0.30 mm, as
`modules/hats` uses for its 10-lead VSSOP), not the stock `MSOP-10` whose 0.35 mm pads
leave 0.15 mm gaps, under the 0.2 mm clearance. Compare it with the Microchip MSOP-10
(UN) drawing at the fab review.

## 6. Open

- User confirmation of D1 (RANGE as a button + LED) and of the panel layout.
- Routing (manual, divide and conquer), then fab review and JLCPCB export.
- Firmware bench test (written: `firmware/`; it sets the MCP4728 EEPROM default itself).
- The printed panel is in `panels/front-cad/` (not test-printed); no own button caps (the
  `modules/8bit` cap fits the same switch and stack).
- 3D interference check; measured jack / LED / switch heights (the stack is the nominal
  `modules/8bit` one).

## 7. Routing and export (R1, 2026-11-15)

User, 2026-11-15: the tact RANGE button is fine (D1 confirmed), the layout is good, route
and export. The carrier is hand-routed on 2 layers (`Code.md` routing contract) and
exported to `jlcpcb/`. MCP4728 pin 5 was renamed `RDY_~{BSY}` (shared parity, see
`AGENTS.md`). Still open: JLCPCB preview, the requirements audit file, firmware, caps,
bench. Things to look at on the first board: DAC / TL074 ground noise (the ground pours
are in via-tied pieces, not one plane) and the 0 V offset (section 3).

## 8. Top clip (C1, panel P2, 2026-11-24)

User: the carrier top is not held to the panel. All four jacks sit in the bottom 25 mm and
the user-stock RV09 pots have no bushing or nut, so the upper 85 mm of the carrier hung
free. Options weighed: M3 standoffs on the carrier (needs holes in a routed, exported
carrier: rejected), a hook fused onto the printed panel (snap arm only 0.9 mm thick between
the rail and the board edge, and no help for the FR4 panel: rejected), a separate printed
clip screwed to the panel (chosen: carrier unchanged, works with both panels).

The clip grips only the 1 mm edge keep-out strip, which by the routing rules carries no
copper and no courtyard, and the rail gap leaves 1.25 mm above the board edge for the
0.9 mm spine. The jacks still set the carrier height; the clip stops the top edge moving
toward or away from the panel. The screw sits right of `MOTION`, 2.2 mm from the D1 LED
hole and 7.2 mm outside the widest (Ø16) knob skirt. Contract in `geometry.json`
`top_clip`; checks in `panels/top-clip/`.

