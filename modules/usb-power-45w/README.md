> **Status: S3 schematic only (ERC 0, netlist = circuit table). No PCB, no panel,
> no JLCPCB export. Not built or bench-tested.**

# usb-power-45w

A USB-C PD Eurorack supply for 45 W and up. It asks the charger for **20 V**
(CH224A) and turns it straight into the rails with switchers. There are no LDOs
and no boost stage.

```
USB-C PD 20 V -> F1 5 A + SMBJ20A -> U5 TPS259470A eFuse -> VIN
VIN -> U2 TPS62933F buck, 1.2 MHz                -> +12V  (2.5 A)
VIN -> U3 TPS62933F buck, ~2.0 MHz               -> +5V   (2.5 A)
VIN -> U4 LMR38020F inverting buck-boost, ~790 kHz -> -12V (1.0 A), enabled from +12V
Out: J2 + J3 16-pin Eurorack box headers in parallel
Panel: SW1 RESET (U5 EN/UVLO) + D8 red 3 mm +5V power LED, as usb-power
```

- VBUS sees only about 2 uF when the cable goes in. The eFuse ramps the bulk
  capacitors at 2 V/ms (about 0.15 A), limits at 4.1 A and retries by itself.
- Everything stays off unless the charger gives 17.6-25.3 V, so a charger without
  20 V leaves the rails off.
- Front panel as in `modules/usb-power`: SW1 (TL3340AF160QG) is a RESET button.
  Pressing it pulls the eFuse EN/UVLO pin low, so all rails turn off; releasing it
  restarts them in order. D8 is a red 3 mm +5V power LED, hand-soldered.
- All three converters run in forced PWM (fixed frequency at every load, no
  light-load pulse skipping).
- A 45 W charger gives about 39 W across all rails together; a 60 W charger gives
  about 52 W.
- All parts come from the JLCPCB catalog (checked live on 2026-10-30/31). Every R/C
  is Basic; the active parts, magnetics and connectors are Extended.

Design maths, budget and open points: [docs/design.md](docs/design.md). The parts
list is in [docs/bom.csv](docs/bom.csv), and the schematic PDF in
[docs/usb-power-45w-schematic.pdf](docs/usb-power-45w-schematic.pdf).

| Path | Contents |
|---|---|
| `hardware/usb-power-45w.kicad_{pro,sch}` | Native project and flat S2 schematic (generated) |
| `hardware/USBPOWER45.{kicad_sym,pretty}` | Pinned symbols (KiCad 10 stock, CH224A / HRO USB-C from `modules/usb-power`, LMR38020F / TPS259470A from `tools/USBPOWER45-src.kicad_sym`) and footprints (RPW0010A hand-made from the TI land pattern) |
| `tools/circuit45.py` | Circuit table, drawing, values and JLCPCB fields |
| `tools/build_schematic.py` | Generator (modules/32bit engine): writes the schematic and checks the native netlist against the table |

## Regenerate and check

From `modules/usb-power-45w`:

```sh
python3 -B tools/build_schematic.py
kicad-cli sch erc --severity-all --exit-code-violations -o research/erc.rpt hardware/usb-power-45w.kicad_sch
kicad-cli sch export pdf -o docs/usb-power-45w-schematic.pdf hardware/usb-power-45w.kicad_sch
kicad-cli sch export bom --fields 'Reference,Value,Footprint,LCSC,MPN,Manufacturer,Voltage,QUANTITY' \
  --labels 'Refs,Value,Footprint,LCSC,MPN,Manufacturer,Voltage,Qty' --group-by 'Value,Footprint,LCSC' \
  --sort-field LCSC -o docs/bom.csv hardware/usb-power-45w.kicad_sch
```

`tools/kicad-project.json` is the shared-check profile. The shared `check` needs a
board, so it can only run once there is a PCB.
