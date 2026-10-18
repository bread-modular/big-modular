# usb-power circuit and repository contract

Read root `AGENTS.md`, module `AGENTS.md` and `README.md` first.

Status: current native review clean (ERC/DRC/parity 0); manufacturing exports
regenerated; prototype bench performance is not claimed.

## Circuit

- 9 V PD via CH224A -> TPS26600 eFuse/protection (UV/OV, thermal latch, button
  retry) -> 9 V rail. ILIM 6.04k, UV 562k/100k, OV 806k/100k; no input-limit
  increase.
- TPS55340 positive boost -> PRAW; U3 TPS54302DDCR inverting buck-boost -> NRAW;
  U5 TPS54302 buck -> +5 V.
- TPS7A4700 -> +12 V (P12); TPS7A3301 -> -12 V (N12); precision N12 divider
  retained. U4/MID/TPS65131 and dormant-positive circuitry removed.
- SR2 inverter: L1 TMPC1205HP-220MG-D 22 uH (C357250); FB R9 100k + R15 120k +
  R84 6.2k over R10 10k; EN R91 100k with R92 20k + R93 2k; C89-C92 four
  C50254 2.2 uF/50 V plus C7 C14663 100 nF; local output 7 x C12891.
- L4/L5 SLO1040H6R8MTT 6.8 uH (C207852). D30 SS34 (C8678), anode NRAW, cathode
  system GND, startup mitigation only. D10, C62, C93 DNP; R32 fitted; no
  D11/D12.
- All parts front-side. No simultaneous ±800 mA or full-temperature 1 A
  guarantee; +400/-300 mA is a conditional target and 1.85 A an engineering
  allocation, not a rating.

## Sourcing

JLC-assembled R/C must be Basic and independently evidenced Economy eligible;
Preferred/Extended is not Basic. Keep native/BOM/PCB MPN, LCSC, package, ratings
and exclusion identity coherent. Precision R9/R10/R15/R72/R74/R86/R87 and
inherited R6, plus L1/L4/L5, are explicit Extended exceptions. Cached catalog
evidence is not live stock or order acceptance. No silent substitutions.

## Layout and tooling

- `hardware/`: project, schematic, PCB, panel and seven hierarchical sheets;
  local libraries, models and mechanical source.
- `docs/`, `tools/`, `BOM.csv`: module-local. No module test suite; verify with
  native ERC/DRC and export reports.
- `jlcpcb/`: complete regenerated canonical export (carrier/panel Gerbers,
  drills, both ZIPs, assembly BOM/CPL, `source-sha256.json`); regenerate only
  with `../../opt/kicad-tools/jlcpcb/export.py`. `production/` retired.
- `../../opt/`: shared tooling; never duplicate. `tools/kicad-project.json` is
  the carrier/hierarchical root. Raw candidates go in ignored `research/`.

Native schematic presentation owns placement/wires; accepted PCB owns routing.
Use `../../opt/kicad-tools/kicad_tools.py check`; no ignored rules, exclusions,
fake power flags or weakened assertions. Full ERC/DRC includes
warnings/exclusions/opens/parity.

Work only in the assigned isolated workspace. No advisor/delegation, commits,
merges, pushes, main writes, other-workspace access, GUI, orders or uploads.
Manufacturer data and prototype screening are not qualified performance.
