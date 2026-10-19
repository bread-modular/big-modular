# 8bit solder jumper (back of the carrier)

One solder jumper, **JP1**, **shipped open**: bridge one side with a blob of solder
before first use. No copper needs cutting, and a bridge can be removed with solder wick.
It sits top-left on the back, beside the MIDI parts, labelled `P` / `D`, with the legend
`JP1 MIDI IN: P=PROTECTED D=DIRECT` at the top edge.

Knob P3 has no jumpers: it is always the passive low-pass, as on Bread Modular.

## JP1: MIDI input (pick one)

| Bridge | Mode | Use |
|---|---|---|
| **P** (pad 1 to the middle) | Protected | The MIDI V2 transistor front end. Survives ±12 V patched into the MIDI jack, accepts 3.3 V and 5 V MIDI. It inverts the signal, so the firmware needs `PORTB.PIN3CTRL \|= PORT_INVEN_bm;` after `Serial.begin`. |
| **D** (pad 3 to the middle) | Direct | MIDI jack tip straight to PB3, no protection. Stock Bread Modular 8bit firmware works unchanged. |

Bridge exactly one side. With JP1 open the MCU's MIDI input floats.

## Firmware pins at a glance

| Input | Pin | Note |
|---|---|---|
| Knob P1 / P2 | PA1 / PA2 | As Bread Modular (`PIN_CV1` / `PIN_CV2`) |
| Knob P3 | - | Passive low-pass on the DAC output, no MCU pin (as Bread Modular) |
| CV in | PB0 | New (`analogRead(PIN_PB0)`), 0-5 V, clamped |
| MIDI in | PB3 | Invert in firmware when JP1 = P |
| Mode button / LED | PA4 / PA5 | As Bread Modular |
