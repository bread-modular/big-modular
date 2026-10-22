# 32bit firmware port: ESP32-S3 pin map vs Bread Modular 32bit-5v

Use this page when porting the Bread Modular `code/32bit` firmware. It lists every GPIO the BM
32bit-5v board uses, what the 32bit module does with it, and every hardware change that matters to
firmware. Source of truth for the nets: `tools/circuit32.py` (`MCU` table) and
`hardware/32bit.kicad_sch`.

## GPIO map (U1 ESP32-S3-WROOM-1U-N16R8)

| Function | BM 32bit-5v GPIO | 32bit GPIO (module pin) | Status |
|---|---|---|---|
| I2S MCLK | IO21 | IO21 (23) | same |
| I2S SCLK / BCLK | IO14 | IO14 (22) | same |
| I2S LRCK / WS | IO12 | IO12 (20) | same |
| I2S DSDIN (ESP32 -> codec DAC) | IO13 | IO13 (21) | same |
| I2S ASDOUT (codec ADC -> ESP32) | IO11 | IO11 (19) | same |
| I2C CCLK / SCL (ES8388, addr 0x10) | IO47 | **IO38 (31)** | **moved** (R1) |
| I2C CDATA / SDA | IO48 | **IO39 (32)** | **moved** (R1) |
| CV1 ADC | IO9 (ADC1 CH8) | **IO1 (39), ADC1 CH0** | **moved** (R1); different scaling (see below) |
| CV2 ADC | IO10 (ADC1 CH9) | **IO2 (38), ADC1 CH1** | **moved** (R1); different scaling (see below) |
| Mode button (to GND, internal pull-up) | IO8 | IO8 (12) | same |
| Mode LED (IO -> 1k -> LED -> GND) | IO18 | IO18 (11) | same |
| MIDI in | RXD0 / GPIO44 (UART0) | GPIO44 (36) | same pin; polarity depends on JP1 (see below) |
| MIDI out | TXD0 / GPIO43 | not connected | dropped (no MIDI out) |
| Gate outs | IO1, IO2 | IO1/IO2 now carry CV1/CV2 | dropped (no gate outs); IO9/IO10 are free |
| USB D- / D+ | IO19 / IO20 | IO19 / IO20 (13 / 14) | same (USB-Serial-JTAG / TinyUSB) |
| BOOT | IO0 | IO0 (27) | same |
| Reset | EN | EN (3) | same |
| PSRAM (octal, N16R8) | IO35-IO37 | not connected | must stay unused |

**Current state (R1 routing): CV1/CV2 and I2C moved** (bold rows), and the codec
audio inputs moved from LIN1/RIN1 to LIN2/RIN2 (see the change log). Every other BM pin number in the
firmware still works. If a later routing batch moves a pin, it gets a row in the change log below
and the table above is updated in the same change.

## Change log (hardware changes that touch firmware)

| Rev | Change | Firmware impact |
|---|---|---|
| R1 (2026-10-21) | CV op-amp halves swapped for layout: CV1 = U7B / U6B, CV2 = U7A / U6A (was A / B) | none: CV1 still reaches IO9, CV2 still reaches IO10 |
| R1 (2026-10-21) | ESP32 moved 4.4 mm left; U6 (MCP6002) moved into the strip beside the module's right pin row. CV1 ADC IO9 -> IO1 (pin 39), CV2 ADC IO10 -> IO2 (pin 38) | change the CV ADC pins: `ADC_CHANNEL_8` -> `ADC_CHANNEL_0` (CV1, GPIO1) and `ADC_CHANNEL_9` -> `ADC_CHANNEL_1` (CV2, GPIO2), both still ADC1 |
| R1 (2026-10-21) | ES8388 moved beside the module's right pin row. I2C SCL IO47 -> IO38 (pin 31), SDA IO48 -> IO39 (pin 32); the 4.7k pull-ups go to +3V3 (BM: +3V3_8388, same level through the 10R) | `Wire.begin(39, 38)` / `i2c_master` SDA = 39, SCL = 38 (BM: 48, 47) |
| R1 (2026-10-21) | Audio inputs wired to the ES8388 second input pair LIN2/RIN2 (pins 22/21; BM LIN1/RIN1) so they reach the VMID bias corner | select input 2 in the ADC input mux: ADCCONTROL2 (reg 0x0A) LINSEL/RINSEL = `01` (BM `00`); e.g. `0x50` instead of `0x00` |

## Behaviour differences vs BM (same pins, new code needed)

- **CV scaling.** BM feeds the ADC 0..3.3 V straight from the pot. Here each CV goes through a ±12 V
  follower and a level shift: `V_adc = 0.276 x V_cv + 1.628 V`. So 0 V CV reads ~1.63 V, +5 V
  reads ~3.01 V, and -5.9..+6.0 V spans 0..3.3 V. With nothing patched, the jack is normalled to
  +5 V, so the knob covers ~1.63..3.01 V, not 0..3.3 V. Rescale in firmware (subtract the
  offset for bipolar CV, or map 1.63..3.01 V to 0..1 for the knob).
- **MIDI polarity (JP1, shipped open, solder one side).** `1-2` (protected, recommended): the NPN
  front end inverts RX, so add
  `uart_set_line_inverse(UART_NUM_0, UART_SIGNAL_RXD_INV)`. `2-3` (direct): stock BM behaviour, no
  change, but the pin is unprotected.
- **Audio in.** ±5 V Eurorack audio is divided to ±0.9 V (x0.18) and AC coupled into LIN2/RIN2
  (BM: LIN1/RIN1, DC from a header). Use the PGA for gain and select input 2 (change log).
- **No normalling.** IN R is not normalled to IN L. Copy L to R in firmware if you want mono.
- **Audio out.** LOUT1/ROUT1 drive a non-inverting x3.55 stage (TL072, ±12 V) for about ±5 V at the
  jacks. Polarity is unchanged.
- **Radio.** Never used. Keep Wi-Fi/BT off: the 5 V linear regulator is sized for ~110 mA with no
  radio, and the U.FL connector stays empty.
