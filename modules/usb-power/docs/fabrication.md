# Carrier and panel fabrication settings

Bare-PCB artwork only, built to standard JLCPCB settings. This is not an
assembled-product, supplier or purchasing approval. Canonical boards are
`hardware/usb-power.kicad_pcb` and `hardware/usb-power-panel.kicad_pcb`; the
complete regenerated carrier and panel export sets are in
[jlcpcb/README.md](../jlcpcb/README.md), with file identities in
`jlcpcb/source-sha256.json`. Native review: [REPORT.md](current-review/REPORT.md).

## Carrier — four-layer

- Outline **100.50 x 30.00 mm**, including the two front cutbacks. Machine to
  the Edge.Cuts **centreline** (not the outside of the 0.05 mm stroke), edge
  location ±0.10 mm. No V-score, castellation, edge plating or countersink.
- **JLC04161H-7628**, FR4 Tg155, **1.6 mm ±10%**, outer **1 oz** / inner
  **0.5 oz**; no paid stack, copper, impedance or material options.
- **HASL with lead (SnPb)**, green mask both sides, white legend. No ENIG or
  lead-free HASL unless separately authorized.
- **721 track segments, 251 through vias** (140 x 0.60 mm, 109 x 0.65 mm,
  2 x 0.50 mm in U2 pads 5/6; all 0.30 mm drill), **10 zones**, **120
  footprints** (116 electrical + 4 mechanical), none on the back.
- Vias are ordinary **tented, unfilled** 0.30 mm PTH; no plug, epoxy fill,
  copper cap or VIPPO. Tenting does not seal a barrel inside an exposed pad:
  via-in-pad wicking on prototype assemblies is an inspection point, not a
  fabrication reject or a supplier guarantee.
- Holes and slots stay native (component PTH 0.90/1.00 mm, USB shell slots
  0.60 mm wide); all drill/slot tolerances are JLC standard.
- **DNP:** D10, C62, C93. **J7** is a manual wire landing and is excluded from
  assembly. All fitted parts are front-side; B.Paste is intentionally empty.
  eFuse RTN must not join main GND.

## Panel — two-layer

- Outline **9.80 x 128.50 mm**, **2-layer FR4 Tg135, 1.6 mm ±10%**, black mask,
  white front legend, JLC default finish (no exposed copper). Copper is fully
  etched; no plated holes and no electrical assembly.
- Retained NPTH: five 3.2 mm mounting/switch holes and one 3.6 mm LED hole;
  location to profile ±0.10 mm per axis.
- USB aperture, **relative to the native panel datum (50.0, 30.0)**:
  **X 3.30, Y 28.10, W 5.00, H 10.80, R 0.60 mm**. Width/height ±0.20
  (each wall ±0.10), centre ±0.10 per axis, radius 0.50–0.70; the full
  through-thickness profile must meet these bounds.
- Bracket web **2.40 +0.0/−0.10 mm**. Worst-case available height at L1 is
  **5.44 mm** against **5.40 mm** needed (5.25 body/solder plus 0.15 residual);
  **measure the printed web**, not an older blocker. L1 max body 5.0 mm,
  L4/L5 max 4.0 mm.
- Do not enlarge holes, shift brackets or alter the outer rectangle. No
  countersinking, edge plating or scoring.
