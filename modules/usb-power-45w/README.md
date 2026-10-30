> **S5 schematic only: native ERC 0, XML/table and pad-number parity checked.**
> No PCB, panel, manufacturing release or bench qualification. Full-load rail targets are not bench-qualified.

# usb-power-45w

USB-C PD Eurorack power with direct forced-PWM switchers, no LDOs. S5 sizes the
eFuse for **board-side protection**, not a 45 W adapter budget. The three
converter stages are unchanged; the historical module/directory name is retained.

- **eFuse:** TPS16630PWPR, C1849461, 60 V input. **4.186 A nominal** main-path
  threshold using R5 3.3k + R29 1k; conservative static input screen **<=4.724 A**,
  including normal auxiliary current, with margin below the 5 A connector class.
- **Source:** for full load, verify a **20 V / 5 A PD contract and 5 A e-marked
  cable**, typically a dedicated 100 W-capable port. No MCU/NVM/current-contract
  tracking. Smaller supplies can trip or cycle; they are not automatically budgeted.
- **Input path:** D10 upgraded from SMA SS56 to **60 V / 10 A SMC SS1060**.
  D1 TVS, U1's separate supply protection, UVLO/OVP, PGOOD, inrush ramp and
  auto-retry remain. The larger diode still requires substantial thermal copper.
- **Outputs:** +12 V / 2.5 A, +5 V / 2.5 A, -12 V / 1 A remain the design targets,
  **54.5 W combined**, not proven simultaneous ratings. Estimated full-load input
  is about 66–67 W with the documented assumptions. No 100 W output claim.
- **Panel:** SW1 disables/restarts U5 through SHDN; it does not guarantee discharge
  of module capacitors. D8 indicates +5 V presence.
- **Sourcing:** R5/R29 Basic + Economic. Four inherited electrolytics remain
  Extended and an unresolved Basic-policy gate. U5 remains below $3 at the checked
  quantity-1 tier; stock/prices in the sourcing record are observations, not reservations.

Read [design and budget](docs/design.md), [S5 changes and qualification](docs/s5-current.md),
[BOM](docs/bom.csv), and the [schematic PDF](docs/usb-power-45w-schematic.pdf).

## Files

| Path | Purpose |
| --- | --- |
| `hardware/usb-power-45w.kicad_{pro,sch}` | Native S5 project and schematic |
| `hardware/USBPOWER45.{kicad_sym,pretty}` | Pinned symbols and footprints |
| `tools/circuit45.py` | Circuit table, drawing, parts and native fields |
| `tools/build_schematic.py` | Existing generator, now supports `--output-root` for review candidates |
| `tools/verify_design.py` | Circuit-specific native XML/field/pad checks and tolerance calculations |
| `docs/s5-sourcing.json` | Dated catalog evidence, source hashes and explicit policy blockers |

## Rebuild and check (from repository root)

Generate into an explicit candidate first; copy required local hardware libraries
and project settings there before running this command. Without `--output-root`,
the generator writes the module's canonical sources, so only do that for an
authorized circuit change.

```sh
python3 -B modules/usb-power-45w/tools/build_schematic.py --output-root <candidate-module-root>
kicad-cli sch erc --severity-all --exit-code-violations -o <reports>/erc.rpt <candidate-module-root>/hardware/usb-power-45w.kicad_sch
kicad-cli sch export netlist --format kicadxml -o <reports>/netlist.xml <candidate-module-root>/hardware/usb-power-45w.kicad_sch
python3 -B modules/usb-power-45w/tools/verify_design.py --netlist <reports>/netlist.xml --hardware <candidate-module-root>/hardware
```

Native PDF/BOM exports use `kicad-cli sch export pdf` / `sch export bom`.
No new exporter is provided. `tools/kicad-project.json` is the shared-tool profile;
full shared `check` needs a PCB, which does not exist yet. Shared schematic inspect
also reports an unresolved 3D-model variable; dependencies/rules were not stripped
to bypass it. Native CLI schematic checks are independent of those blocked gates.
