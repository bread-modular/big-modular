# Basic substitutions — native checkpoint040, not a manufacturing release

> Migration recovery: source/electrical content below is retained checkpoint evidence.
> `jlcpcb/` is a STALE recovered Git export snapshot, not a fresh migrated export.
> Run commands from `modules/usb-power`; shared `opt/` stays at repo root. See
> [migration-recovery.md](migration-recovery.md) for current checks and Astra handoff.

Base `b4d301d075f7556b6c06758ccbffcc1a2b1694fa`; base PCB SHA256
`7d709a4fc313b13bddc7f1664f199313f482dd9ed0a82d3592a452cf92d35af3`.
24 existing parts substituted; R83=9.1k joins R72=82k and R73=1.2k;
R84/R85=510R complete R10/R18=13k bottom legs. Six1210 capacitors now have
actual1206 land patterns. All17 LDO-bank parts and fixed interfaces preserved.

Native ERC/DRC/errors/warnings/exclusions/opens/parity all0. Independent324pins
including43 NCs; full ref/pin/net and field parity agree. 107 electrical+4 mechanical
footprints;585 tracks,207 ordinary0.300mm through vias,8 zones;107F/0B and0B.Paste.
Generator exactly reproduces native schematics/BOM/pin audit. D10 stays DNP.
Fitted purchasing:100 instances,42 unique codes;26Basic/16Extended unique,
81Basic/19Extended instances. No sourcing allocation or Economy approval claimed.

Nominal MID/P5=5.007547V; raw+13.537080/-13.928806V; N12=-12.020250V before IFB.
Independent1%/100ppm/K/100K plus actual TPS54302 reference bounds give
4.712887..5.318152V; +0.100V allocation=5.418152V, not a5% accuracy guarantee.
N12 magnitude11.296067..12.783855V; negative minimum headroom0.178019V:
full-temperature1A dropout/accuracy NOT assured. No rail/current guarantee raised.

**043 capacitor closure (implemented and independently checked):** C13585 input bias screen gave 3.095uF each
at9.45V. The accepted plan changes C5/C18 to22u C12891 and adds C68/C69, giving
2x22u local VPROT screens of10.664uF at9.45V per buck. New C70/C71 make three local
22u at MID/L1 with C6; new C72 makes three local22u at P5/L4 with C19/C38, screening
27.631uF at5.5V. Lowest Vout4.712887V gives TI Eq14 fo=39.164kHz, below the<40kHz
no-feedforward guideline. C37 remains remote and is not counted local. C4/C16/C17
stay C13585 and the17 LDO caps are unchanged. The10uF input and40kHz crossover
figures are application recommendations, not absolute IC guarantees; typical
screens, bench/loop, inrush and lot evidence remain pending. The caps exist in the
043 native source and are independently ref/net/field checked; physics is not qualified.

`research/basic-swaps/` contains full native reports, independent checks,
engineering numbers, two views and all-files patch/hash handoff. Phase A in the
release workspace reconciles checkers/budget/current docs to this 040 source, but
production/assembly/CAM are regenerated from the 043 source. Do not treat this as
bench or order qualification. C22765/C23260/C23193 now have
dated strict-live public identity/Economy observations in the release research
folder; that is not stock or order approval. No commits/main writes, orders/vendor
uploads or fabrication/assembly exports performed.
