# LDO-R1 / basic-passive checkpoint — supervisor review

This workspace starts from base `b4d301d` plus the reviewed 040 basic-passive
native checkpoint (24 substitutions, R83/R84/R85, six 1206 capacitor lands, D10
DNP) plus the 043 capacitor closure. It is **not** a qualified manufacturing release.
The local-capacitance plan is implemented and independently rechecked; this is not
bench, thermal, startup or supplier-order qualification.

- 043 native: 107 electrical + 4 mechanical footprints, 585 tracks, 207 ordinary
  0.300 mm vias, 8 zones; native ERC/DRC/warnings/exclusions/opens/parity zero; all
  components front, zero B.Cu parts and zero B.Paste apertures.
- Setpoints: raw +13.537080/-13.928806 V; MID/P5 5.007547 V nominal,
  5.418152 V worst peak with the stated 0.1 V allocation; N12 -12.02025 V before
  IFB. Mixed R12/R14 0.1%/25 ppm/K with Basic 1%/100 ppm/K elsewhere.
- Implemented 043 local caps: C5/C18 -> 22 uF C12891; C68/C69 add 2x22 uF per VPROT
  buck (10.664 uF screen at 9.45 V); C70/C71 make 3x22 uF local MID with C6;
  C72 makes 3x22 uF local P5 with C19/C38 (27.631 uF; 39.164 kHz estimated
  crossover). C37 remains remote and is not counted local. C4/C16/C17 stay C13585;
  the 17 LDO-bank caps are unchanged.
- **Known limitation, not waived:** negative full-corner 1 A headroom is 0.178019 V;
  the 0.8 V dropout/accuracy condition FAILS. No full-temperature 1 A rail guarantee.
- The 10 uF input and <40 kHz crossover figures are application recommendations,
  not absolute IC guarantees. Typical screens and bench/loop evidence remain pending.
- The 043 source is exported to `jlcpcb/` as bare-PCB Gerbers plus assembly
  BOM/CPL; the old `production/` release archive was retired.
- Bench limits: capacitance lot/AC/bias/temp/aging, loop stability/input ringing,
  noise/PSRR, thermal/current, startup/reverse/shutdown, physical assembly/harness.
  No simultaneous 800 mA guarantee.

Supervisor inspects and merges; no assistant commit/merge/push/main writes.
No advisor, delegation, order or vendor upload.
