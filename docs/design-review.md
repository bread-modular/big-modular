# Source / pin / analog review ledger

**Checked 2026-09-24.** These are concise extracted design facts, not redistributed datasheets. No stock quantities or prices are claimed. Product identifiers do not prove availability or pin-compatible substitution.

## Pin basis and settings

- **CH224K:** datasheet v1F figure 6.1: VDD1 via 1k and 1uF; CFG2=2, CFG3=3; DP4, DM5; CC2=6, CC1=7; VBUS sense8; CFG1=9; PG10; exposed ground is called 0 in WCH, mapped to 11 in the installed KiCad SSOP-10-EP footprint. CFG1=6.8k requests 9 V; CFG2/3 float. Section 5.5 permits VBUS sense NC and requires DP/DM shorted together on-chip side, disconnected from connector, for PD-only use. Figure 6.1 shows no added Rd on CH224K; do not copy the adjacent CH224D external-Rd circuit. PG behavior is not used to authorize load current. [source](https://components101.com/sites/default/files/component_datasheet/WCH_CH224K_ENG.pdf)
- **TPS26600:** IN1/2, UVLO3, NC4, OVP5, MODE6, SHDN7, RTN8, GND9, IMON10, ILIM11, dVdT12, NC13, FLT14, OUT15/16, EP=RTN. RTN must not be externally shorted to GND. 40.2k ILIM gives 0.2985 A nominal; UV ratio 249k/100k and OV 806k/100k use the 1.2 V thresholds (approximately 4.188/10.872 V). The internal operating floor also applies. RUN opens the UV divider feed, leaving UV low. SHDN is intentionally floating per internal pullup description. MODE tied RTN selects auto-retry current limiting; overload/thermal cycling is not a clean system shutdown. 100nF slew capacitor is a starting point; startup/inrush is unvalidated. A separate series diode supplies an unambiguous VBUS reverse-current barrier rather than depending on undocumented powered-output behavior. [source](https://www.ti.com/lit/ds/symlink/tps2660.pdf)
- **TPS62160:** pins 1 PGND, 2 VIN, 3 EN, 4 AGND, 5 FB, 6 VOS, 7 SW, 8 PG, EP9. 0.8 V reference and 40.2k/10k give 4.016 V. 2.2uH/22uF is the datasheet baseline; retain correct effective capacitance. Internal compensation; PG pulls down the TPS65131 enable net until the intermediate supply rises. [source](https://www.ti.com/lit/ds/symlink/tps62160.pdf)
- **TPS65131:** pins follow table 5-1; native library common pins remain connected. INP1/24 are boost switch nodes, INN5/6 connect input, OUTN13/14 drive the inverting inductor. **Negative diode cathode at INV_SW, anode at PRE_N**. VNEG15 senses negative output, FBN16 connects divider from PRE_N to VREF17. Positive feedback 1.05M/100k; negative 1.15M/100k; VREF=1.213 V gives ±13.9495 V nominal. PSP9/PSN11 ground disables power-save. CP21 10nF and CN18 4.7nF to ground follow compensation recommendations; VREF 220nF. 6.8pF feedforwards are rounded starting values from section 8.2.2.6 (6.8/R and 7.5/R). L2/L3 4.7uH, requested Isat≥3A; exact part/core loss/maximum switch-current margin pending. External diodes require 40 V rather than blindly copying the 20 V example at a different output. VIN4 uses 100Ω/100nF analog filtering. BSW7 unused is explicitly permitted but allows positive-output prebias. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf)
- **TPS62125:** pins 1 GND, 2 VIN, 3 EN, 4 EN_hys (intentionally NC), 5 FB, 6 VOS, 7 SW, 8 PG, EP ground. 0.8 V FB; 71.5k/10k sets 6.52 V. Table 2 permits 10uH/22uF for output 5..10 V. This topology is valid at 13.95 V input, but its up-to-1MHz/PFM behavior is a known limitation relative to the strict switching-frequency preference. [source](https://www.ti.com/lit/ds/symlink/tps62125.pdf)
- **TPS7A4901 / TPS7A3001:** both OUT1, FB2, NC3, GND4, EN5, NR/SS6, **DNC7**, IN8, exposed pad ground. DNC is never grounded. Minimum output effective capacitance 2.2uF, proposed nominal 10uF/25V. 10nF NR/SS and feedback feedforward require startup verification. Positive VFB=1.185 V, negative VFB=-1.176 V; each has 600mV maximum dropout in its specified maximum-load test. Positive EN tied positive IN; negative EN tied negative IN is explicitly permitted. Diodes are oriented to conduct from positive output back to input, and from negative input towards negative output, respectively, under reverse differential. They are NOT output isolation diodes or precise OVP. [source](https://www.ti.com/lit/ds/symlink/tps7a49.pdf) [source](https://www.ti.com/lit/ds/symlink/tps7a30.pdf)

## Output wiring / orientation

J2 is an **off-board standard 2×8, 2.54 mm cable interface**, not a selected footprint. Standard signal pairs are:

| Pins | Net |
|---|---|
| 1,2 | -12 V / red-stripe end |
| 3,4,5,6,7,8 | 0 V |
| 9,10 | +12 V |
| 11,12 | +5 V |
| 13,14 | CV — NC here |
| 15,16 | Gate — NC here |

The 10-pin interface ends at pins 9/10 and therefore **does not carry +5 V**. J2 is a 16-pin design because +5 V was explicitly requested. At final harness selection mark pin-1 triangle, red stripe and -12 V; verify electrical continuity at the actual mating face. Keying is not a substitute for polarity verification; historical keyed reversals exist. Physical key-to-pin-1 orientation is **not signed off until the exact connector is selected**. [source](https://doepfer.de/a100_man/a100t_e.htm) [source](https://division-6.com/learn/eurorack-power/) [source](https://northcoastsynthesis.com/news/ribbon-cable-experience/)

## Sourcing ledger

The following **MPN to LCSC identifier mappings only** were verified; no stock count, delivery time, price, JLC assembly eligibility or substitution is asserted:

- CH224K / C970725. Product introduction text mixes CH224A/Q information; rely on the CH224K-specific datasheet and do not assume pin-compatible substitution. [source](https://www.lcsc.com/product-detail/C970725.html)
- TPS26600PWPR / C544399. [source](https://www.lcsc.com/product-detail/Surge-Protection-Devices-SPDs_Texas-Instruments-TPS26600PWPR_C544399.html)
- TPS62160DSGR / C324077. [source](https://www.lcsc.com/product-detail/DC-DC-Converters_Texas-Instruments-TPS62160DSGR_C324077.html)
- TPS65131RGER / C87663. [source](https://www.lcsc.com/product-detail/C87663.html)
- TPS7A4901DGNR / C16430. [source](https://www.lcsc.com/product-detail/Linear-Voltage-Regulators-LDO_Texas-Instruments-TPS7A4901DGNR_C16430.html)

TPS62125DSGR, TPS7A3001DGNR, GCT USB4105-GF-A and all passive procurement are **candidates** with no verified LCSC number. Schottky diode entries are electrical requirements, not undocumented pin-compatible SS14 substitutions. F1 rating is provisional; exact fuse resistance, time-current characteristic and TVS energy coordination remain open. SMBJ12CA uses the bidirectional TVS symbol: standoff 12 V, breakdown 13.3..14.7 V, specified pulse clamp 19.9 V; system surge withstand is not established. [source](https://datasheet.octopart.com/SMBJ12A-Littelfuse-datasheet-9813940.pdf)

Rakit GO! is only a contextual example, not this design: its published 2HP/27mm and +12V 500mA / -12V 300mA require a dedicated 5V/2.4A source. Those loads/depth do not transfer to this prototype. [source](https://www.rakits.co.uk/product/go/)

## Review blockers not hidden by clean ERC

Analog loop stability with actual parts; all load combinations; ripple and LDO PSRR/headroom; start/stop/brownout rails; eFuse limit/inrush tolerance; host/source current authorization; TVS/fuse/cable fault coordination; independent output OVP and all-rail shutdown; resistor/capacitor derating; magnetic saturation; total thermal rise; exact J2 and strain relief; complete electrical PCB placement and routing. The current circuit is fully connected as a proposal but these engineering decisions remain incomplete.

## Library provenance

Project symbols include resolved copies of the installed KiCad standard library entries; custom TI symbols use the pin tables above. The GCT footprint is copied unmodified from the installed KiCad footprint library. Upstream KiCad library licensing applies to those library-derived assets; do not assume the repository's original LICENSE replaces upstream terms. [source](https://gitlab.com/kicad/libraries/kicad-symbols) [source](https://gitlab.com/kicad/libraries/kicad-footprints)
