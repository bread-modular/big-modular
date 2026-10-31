# usb-power-45w — S6 schematic design

**Schematic only; no PCB or bench-qualified current/power rating.** S6 adds
per-rail protection, retained common fault shutdown/reset, three rail-status
panel LEDs and a revised MAIN LED. It preserves the three converter power stages.
See [S6 detailed design and qualification record](s6-rail-protection.md).

## Hierarchy and power flow

Open `hardware/usb-power-45w.kicad_pro` / `usb-power-45w.kicad_sch`, the hierarchy
root, not a child sheet as a standalone project. The root shows wired power flow,
following the existing `usb-power` module's presentation.

| Sheet | Contents |
|---|---|
| Root | Power flow, sheet interfaces and fault policy |
| 01_usb_input | USB-C/CH224A, TVS, backup fuse, reverse blocker, main TPS16630 |
| 02_positive_12v | +12 V buck, raw-side filtering, U6 output eFuse |
| 03_positive_5v | +5 V buck, raw-side filtering, U7 output eFuse |
| 04_negative_converter | LMR38020F inverting converter and raw-side filtering |
| 05_negative_protection | LM5067, external MOSFET/sense resistors, optical control/status |
| 06_fault_reset | Always-on 3.3 V supply, POR/manual RESET, startup timer and retained latches |
| 07_outputs_status | Parallel headers, delivered-voltage sensing and four panel LEDs |

```text
USB-C -> F1 -> VPD -> D10 -> EF_IN -> U5 TPS16630 -> VIN
              |                       RUN <- fault/reset control
              +-> D1 SMBJ22A
              +-> Q2/Q3 low-current limiter + D9 -> CH224A (requests 20 V)
              +-> U9 60 V LDO -> V3V3 always-on fault/status logic

VIN -> U2 TPS62933F -> P12_RAW -> U6 TPS16630 -> +12V headers
VIN -> U3 TPS62933F -> P5_RAW  -> U7 TPS16630 -> +5V headers
VIN -> U4 LMR38020F -> N12_RAW -> sense resistors/Q4 controlled by U8 -> -12V headers

Individual rail/eFuse/voltage status -> qualified retained FAULT -> all switches off
SW1 -> RESET supervisor -> clear FAULT and ARMED; common restart
```

**System ground is never switched.** Converter feedback and compensation remain
upstream of protection. C34/C35/C36 and original SMD LEDs D5/D6/D7 are also RAW-side.
Only delivered rails reach J2/J3. No independent output supplies may be paralleled.

## Source contract and input budget

The design requests 20 V without an MCU or PD NVM programming. For full-load
experiments, require a verified **20 V / 5 A contract and 5 A e-marked cable**,
typically from one dedicated 100 W-capable port. A multiport total-power label
is not enough. This design does not read available current and does not reduce
its demand to accommodate a weak charger. Such a source can droop, trip or cycle.

U5 remains **TPS16630PWPR / C1849461**, 60 V class. R5 3.3k + R29 1k set **4.186 A
nominal**; the conservative static screen is **3.693–4.698 A**. S6 allows **50 mA
normal auxiliary reserve** outside the main eFuse, giving about **4.748 A** at the
screened high corner, below the 5 A input-path class. This is not an instantaneous
short-circuit ceiling or a guarantee for faults in an auxiliary circuit.

The historical module name does not imply a 45 W output guarantee. Old individual
rail targets total 54.5 W; input-loss estimates around 66–67 W from S5 remain
planning estimates, now with additional protection/control losses. S6 rail
threshold tolerances can limit below those targets. A 100 W charger does not
make the module a 100 W-output supply.

## Retained input protection

- F1: S1206-SD-5.0A / C553937, 5 A / 63 V backup fuse. Not a PD current regulator.
- D1: SMBJ22A / C10214, 22 V stand-off and 35.5 V rated clamp at its specified
  surge current/waveform. U5's 60 V capability supplies margin; wiring inductance,
  pulse derating and actual surge behavior remain validation requirements.
- D10: ZHIDE SS1060 / C2917888, 60 V / 10 A SMC reverse-blocking diode. U5 does
  not supply reverse blocking. Screen up to 0.75 V drop and roughly 3.53 W at the
  high current limit; large thermal copper is required. This is not an ideal diode.
- UVLO: R2/R3 100k/7.5k, about 17.2 V rising and 16.08 V falling nominal.
- OVP: R28+R4 / R24 = 130k/6.8k, about 24.14 V rising nominal, with recovery
  above the highest normal 20 V PDO voltage. The original S4 corner calculations
  still apply; these values are unchanged in S6.
- C3 22n: about 9 ms ramp at 20 V. U5 PGOOD has its own deglitch delay.
- Main FLT and PGOOD now form **MAIN_OK at 3.3 V**, pulled up on the control page.
  U2/U3 enable from MAIN_OK. The old VIN divider and raw-voltage fault pullup
  R6/R7/R25 are removed. TP5 is MAIN_OK; TP6 is FAULT_LATCH.

The earlier TPS259470 replacement is not reintroduced: output eFuses do not fix
an input-clamp coordination problem. See the S4 record and feasibility research.

### Independent CH224A branch

Q2 BCX53-16,115 uses **Nexperia E1/C2-tab/B3**, unlike the original KiCad BCX53
manufacturer convention. Its pinned custom symbol preserves this mapping.
Q3 MMBT3906 senses R23 33 ohm and limits Q2 drive around 18 mA typical; this is
not a precision limit. D9 SMAZ24 shunts the low-current supply. R27 10k/250mW
provides base drive. D11 allows the 1u CH224A supply to discharge on input collapse
without reverse-biasing the PNP junctions. Do not remove these protections merely
because U5 is higher-voltage. Verify U1 supply stays below its limits during
surges, startup and shorts; the main TVS alone does not establish that.

## Converter stages and rail protection

| Rail | Converter, unchanged | Original load target | S6 nominal protection |
|---|---|---:|---:|
| +12 | TPS62933F; 1.2 MHz; 6.8uH | 2.5 A / 30 W | U6 2.647 A |
| +5 | TPS62933F; about 2 MHz; 3.3uH | 2.5 A / 12.5 W | U7 2.647 A |
| -12 | LMR38020F IBB; about 790 kHz; 15uH | 1 A / 12 W | LM5067/Q4 1.000 A |

These are **targets/settings, not bench-proven continuous ratings**. Positive
current-limit screening gives 2.335–2.971 A; negative gives 0.863–1.143 A plus
sense-bias considerations. Do not advertise a guaranteed 2.5/2.5/1 A minimum.
Prototype planning below the screened minimum, such as 2.2/2.2/0.8 A, is still
conditional on temperatures and total power. Short-circuit pulses can exceed
these static intervals.

U6/U7 MODE is open for local latch-off and they share RUN. Their UV/OV and ramp
networks are independent of load current. U7 is a 4.5 V minimum-input device;
validate its operation near the lowest +5 V converter output. The converter's
own current limiting/thermal protection remains a second layer, not a substitute
for output-protection testing.

U8 controls a real series switch in the negative conductor. R48/R49 form a Kelvin
50 mOhm shunt; R56 sets roughly 3.1 W MOSFET power limiting. Optical level shifting
separates UVLO/PGD from system-ground logic. See the S6 record for detailed VCC,
SOA, startup timing and reverse-collapse clamp qualifications.

### Retained converter details and open issues

- +12 V divider remains 47k/3.3k at 0.8 V reference: **12.194 V nominal**.
  The earlier upper-tolerance concern is not silently repaired in this task.
- +5 V divider remains 68k/13k: **4.985 V nominal**.
- -12 V divider remains 100k/9.1k at 1 V reference: about **-11.989 V**.
- U4's GND/exposed pad is N12_RAW. VIN-to-U4-ground capacitors see approximately
  VIN + 12 V. Its 2 A ordinary-buck IC rating is not 2 A negative output current.
- Q1 follows P12_RAW, not protected +12V. Common shutdown is supplied by the new
  output switches and input RUN; Q1 alone is not a precision rail supervisor.
- Fixed PWM avoids ordinary light-load burst behavior but does not guarantee
  quiet audio. Validate layout, switch-node coupling, beat frequencies and EMI.
- Validate effective MLCC capacitance, capacitor ripple/lifetime, loop stability
  (especially the inverting converter), load steps and thermal rise. Large nominal
  capacitance and a clean ERC are not stability proof.

## All-rail reset and panel indications

The always-on logic supply is upstream of U5 so a fault cannot clear its own
memory by turning off the main eFuse. After a typical 5.7 s startup qualification,
any persistent main/rail status failure sets FAULT and forces RUN low. ARMED
remains set through subsequent rail/input loss; the board does not automatically
retry after that common latch trips.

SW1 clears both latches through a POR/reset supervisor and disables all switches
while held, with about 20 ms release holdoff. Local protection remains active
while common startup qualification is pending. Normal positive and negative
ramps are not simultaneous; see the detailed record. External output capacitance
is not force-discharged and a brief RESET is not a guaranteed full module reboot.

Four hand-soldered 3 mm panel LEDs:

- **D8 MAIN:** valid input plus U5 FLT/PGOOD plus RUN; not simply +5 V presence.
- **D16 +12, D17 +5, D18 -12:** their own delivered voltage and rail protection
  status, plus RUN. The negative rail has its own monitor, not a borrowed +12 V lamp.
- A failed rail's lamp drops; when common shutdown latches, **all four go out**.
  They do not retain a fault-cause pattern. Individual status test pads are available.
- Typical voltage-presence thresholds are +9.98 V, +4.22 V, -10.05 V and 17.65 V
  input, not a precision regulation/PD-compliance certification.

## Sourcing, mechanics and release limits

See `s6-sourcing.json` for exact public JLC snapshots. New R/C are Basic and
Economic eligible; C5/C34/C35/C36 remain inherited Extended exceptions **without
approval**, so the Basic policy gate is still open. The selected negative
controller is approximately $3.08 at quantity 1 and only 33 units were observed;
it is not represented as meeting the main eFuse's sub-$3/high-stock target.

J2/J3 and the four panel LEDs are manual parts. TP1–TP16 are bare copper.
All new footprints are pinned locally; pad identities were checked. The LDO
uses TI DGN0008C land dimensions, and the optocoupler uses 2.54 mm lead pitch.
Final land-pattern/courtyard/paste/thermal-copper and supplier placement reviews
are required before layout/release. No PCB/panel is generated by this task.

The repository's shared inspect model-variable blocker remains distinct from
successful native root ERC and XML checks. No rules or exclusions were weakened.
Prototype and supplier validation, not this schematic, determine release readiness.
