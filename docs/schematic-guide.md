# Electrical hierarchy

Current 8-page native PDF: `schematic.pdf`; 127 components, 7 child sheets.
Read `electrical-prototype.md` and `../firmware/README.md` first.

- `big_modular.kicad_sch`
- `01_input_protection.kicad_sch`
- `02_hardgate.kicad_sch`
- `03_bucks.kicad_sch`
- `04_bipolar.kicad_sch`
- `05_diagnostics.kicad_sch`
- `06_sensing.kicad_sch`
- `07_output_rails.kicad_sch`

Local feedback/protection paths are actual wires. Hierarchical ports carry cross-sheet signals.
Boards remain mechanical reservations, not a synchronized power PCB.
