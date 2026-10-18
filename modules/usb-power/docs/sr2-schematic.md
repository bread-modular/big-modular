# SR2 implemented design and limits

SR2 replaces the U4 TPS65131/MID negative path with a direct TPS54302 inverting
buck-boost (U3) and removes the dormant-positive circuitry. The schematic and
canonical PCB are the current sources; routing derives from the 084 baseline,
the current review is clean (ERC/DRC/parity 0), manufacturing exports are
regenerated, and prototype bench performance is not claimed. Nothing here is
released.

## Implemented circuit

- U3 TPS54302DDCR/C311983: VIN3=VPROT, GND1=NRAW, SW2 -> L1 -> system GND,
  FB4 referenced to NRAW, BOOT6 -> C35 -> SW2. No PG pin invented.
- L1 TAI-TECH TMPC1205HP-220MG-D, 22 uH ±20%, C357250, 5.0 mm max body;
  Extended exception. Hot saturation, solder clearance and 3D fit remain
  unqualified.
- Upper FB R9 100k C122538 + R15 120k C705720 + R84 6.2k C4260; bottom R10 10k
  C95204, all 0603. Weighted initial tolerance 0.124668%, TCR 27.0557 ppm/K,
  not entirely 0.1%.
- EN upper R91 100k; lower R92 20k + R93 2k to NRAW (22k). C93 is DNP across
  the entire upper R9+R15+R84 divider. Never EF_SHDN, RTN or retired BI_EN.
- C89-C92 four C50254 2.2 uF/50 V VIN-to-NRAW plus C7 C14663 100 nF: 8.8 uF
  nominal, 3.96 uF bias/TC/tolerance screen; startup, current and ripple remain
  unqualified. C5/C68 stay the distinct VPROT-to-system-GND C12891 bank.
- Local output C6/C37/C70/C71/C9/C75/C76 reuse seven C12891: 18.0425 uF
  conservative DC+AC/temp/tolerance/aging screen at 15 V. Remote U13 five-cap
  bank is excluded from local ripple. Quiet-rail banks 4/6/5/4, same LDOs and
  precision N12 divider. C62/D10/C93 DNP.
- Added D30, same MDD SS34/C8678/SMA as D27-D29: anode 2 = NRAW, cathode 1 =
  system GND. Startup mitigation only, not a guaranteed clamp.
- Removed U4 and exclusive MID/dormant-positive/VREF/BI_EN/compensation
  circuitry; R15 is reused for the new FB. Current inventory: 116 components,
  344 real pins + 6 flags (350 total), 39 NC markers, 23 hierarchical ports.
- Preserved: input protection, eFuse/SW1, TPS55340 positive boost and
  output/harness sheets; U5 +5 V circuit and LDO pins/dividers. ILIM 6.04k,
  UV 562k/100k, OV 806k/100k remain.

## Numeric screens (not bench guarantees)

Machine-readable arithmetic: `sr2-schematic-budget.json`. TI SLVA933 section 5
supports the TPS54302 IBB topology; its application-board phase data are not
this board's data.

| Selected-network screen | Result / boundary |
|---|---|
| NRAW nominal / independent 1024 corners | -14.07752 V / magnitude 13.603127-14.557924 V |
| Reference / bias / resistor assumptions | 0.581-0.611 V table; ±100 nA FB sensitivity (not a max guarantee); independent tolerance/TCR signs |
| N12 nominal / high magnitude | -11.996750 V / 12.386251 V |
| LDO headroom after 0.1 V dip plus half screened ripple | 1.086775 V; accuracy screen, not an instant-load-step guarantee |
| Normal 9.45 V static span | 24.007924 V |
| eFuse OV upper incl. 100 nA leakage | 11.583679 V; threshold is not a clamp |
| OV + raw DC span | 26.141603 V |
| Extra raw excursion / input turnoff overshoot / SW ringing | 0.130101 V / 0.4 V / 1 V; allocated 27.671704 V, 0.328296 V to 28 V, unmeasured |
| EN startup / 28 V span + 5 uA sensitivity | 7.335634 V / 5.308159 V; 5 uA is not a guaranteed max |
| 22 uH at -20%, 272.6 kHz, 7.9375 V, 80% efficiency screen | ILavg 1.0273 A, peak 1.6033 A, valley 0.4513 A, RMS 1.0798 A |
| Local output ripple / capacitor RMS | 60.20 mVpp incl. 10 mOhm bank ESR allocation; 0.5067 A bank, sharing/heat unmeasured |
| +400/-300/+5 at 250 mA shared objective | 1.4694 A nominal / 1.7816 A adverse; below 1.85 A planning allocation, no supply rating |
| Negative LDO dissipation | 0.723 W nominal / 1.026 W adverse; PCB thermal qualification required |

TPS54302 is 28 V recommended / 30 V absolute on VIN/SW; EN and BOOT-SW are
5.5 V recommended / 7 V absolute. Negative SW undershoot and bootstrap
differential need separate scope checks. 108% FB OVP is not a guaranteed clamp
or open-feedback survival.

## Explicit unresolved gates

- Loop/phase does not pass: RHP/5 = NOT_QUALIFIED; modeled crossover
  1510-8126 Hz with 18.4-55.4 deg phase sensitivity. Measure actual loop,
  DCM/pulse-skip and load steps. No CFF is fitted or tuned.
- Zero-bias nominal-C/5 ms startup screen reaches 4.957 A, above the 4 A minimum
  current limit; pessimistic constant-C screen, not a loaded-start guarantee.
- Positive-NRAW excursion before switching: 0.545 V fast-step sensitivity,
  0.239 V nominal estimate at EN start. D30 mitigates but does not guarantee
  <=+0.3 V at arbitrary surge; establish actual IN/NR/FB/OUT excursion before
  energizing a production load.
- With VPROT=0 and negative energy remaining, EN sensitivity is 2.804 V. There
  is no output disconnect; test start/stop/unplug/short/retry. No external
  backdrive.
- Hot Isat/overshoot, X5R temperature, capacitor sharing/ESR, LDO thermal paths,
  stack/solder clearance and thin-magnetic availability remain bench gates.
- Allocations: 1.85 A is an engineering planning value, not an eFuse protection
  rating; 12000/6040 = 1.986755 A nominal is not a worst-case limit.
  +400/-400 mA exceeds both the 1.85 A planning allocation and the 1.986755 A
  nominal eFuse value; +600/-200 mA exceeds the 1.85 A planning allocation but
  remains below the 1.986755 A nominal eFuse value. No recalculation is implied.

## Verification

Native hierarchical ERC/DRC with all severities, opens and parity, plus exact
ref/pin/net/NC/field parity, is the verification gate; there is no module
unit-test suite. Current results are recorded in `docs/current-review/REPORT.md`.

Build/validation commands and the release boundary: [build.md](build.md).
