# J8 optional rail-sensing / debug IDC

**Review only, not power-up/fabrication qualified. JP1 stays OPEN for qualification.**
No MCU, firmware, blink or external power-enable/LED-control signals. Normal intended
operation and the single power LED do not depend on J8 or an external controller.

## Connector and fixed pin map

J8 is a keyed20-pin2x10 DEBUG IDC, not the16-pin J7/J2 Eurorack POWER OUTPUT.
Native footprint `BigModular:IDC-Header_2x10_P2.54mm_Vertical`; unplaced, exact keyed
MPN/cable/2HP fit unresolved. Component-side PCB view: pin1 rectangular marker(0,0),
pin2(2.54,0); odd pins down left/even right; pin19(0,22.86), pin20(2.54,22.86)mm.
Red stripe identifies pin1 row. Match shroud key/Fab marking to actual mating parts;
mating/socket view is mirrored. Mark cable DEBUG3V3 and continuity-test every pin.

| Pin | Net | Direction relative to Big Modular / conditioning |
|---|---|---|
| 1 | GND | Pin1/red-stripe return |
| 2 | DBG_AUX_MON | OUT: AUX3V3 via R61 10k, monitor ONLY, not a supply |
| 3 | ADC_P12 | OUT: P12 /6, R54/C42/D13/D14 |
| 4 | GND | Analog return |
| 5 | ADC_N12 | OUT: -N12 x0.165, R55/C43/D15/D16 |
| 6 | ADC_P5 | OUT: P5 /3, R56/C44/D17/D18 |
| 7 | ADC_MID | OUT: MID /3, R57/C45/D19/D20 |
| 8 | ADC_VBUS | OUT: fused VBUS /11, R58/C46/D21/D22 |
| 9 | ADC_VPROT | OUT: VPROT /11, R59/C47/D23/D24 |
| 10 | GND | Return |
| 11 | DBG_PG_N | OUT: active-low CH224A PG through R62 10k |
| 12 | DBG_FLT_N | OUT: aggregate eFuse fault through R63 10k |
| 13 | DBG_SDA | BIDIR: open-drain I2C through R64 1k, local R70 10k pullup |
| 14 | DBG_SCL | BIDIR: open-drain I2C through R65 1k, local R71 10k pullup |
| 15 | DBG_BUTTON_N | OUT: SW1/R41 10k/C40 100n through R66 10k |
| 16 | GND | Digital return |
| 17..20 | NC | Deliberately unwired; no enable or LED-control contacts |

## Safe optional debugger contract

Use separately powered3.3V instruments/controller, common ground, high-Z inputs;
I2C outputs open-drain only. Disable all external/internal debugger pullups and
push-pull high drive, including during boot/reset/off states. Never connect external
power to AUX_MON: it is an OUTPUT through10k, not an external supply input or a
controller supply. Its nominal ground-short current is0.33mA. No5V/USB tolerance.
This sink-only/Hi-Z contract supplies no positive voltage back into housekeeping;
series resistors/clamps are current limiting, NOT galvanic/powered-off isolation or
misuse protection. A debugger with unavoidable powered pullups is incompatible.

Inputs must tolerate board signals while debugger power is off without supply
injection, or unplug before either side is off. Sensor input target >=10Mohm and
<=100nA leakage;100nA alone gives up to2.67mV source error. Disable ADC pulls;
validate acquisition/reference/mux/cable loading. Use a short bench cable with returns.
I2C1k/10k gives about0.30V local low for a zero-volt external sink with only those
pullups; CH224A internal pulls/capacitance/thresholds need actual validation. Start
slow (<=10kHz suggested, not a qualified cable/bus rating). Never add powered pulls.
SW1 is optional debug user input, not an automatic reset or main-power bypass.

## Transfer functions / nominal ranges (not absolute-maximum ratings)

| Channel | Transfer | Nominal point | Example measurement interval | Nominal RC tau |
|---|---|---|---|---|
| P12 | V/6 | 12V ->2.000V | 0..15V ->0..2.500V | 2.67ms |
| N12 | -V x16.5k/100k | -12V ->1.980V | -15..0V ->2.475..0V | 1.00ms |
| P5 | V/3 | 5.011V ->1.670V | 0..5.5V ->0..1.833V | 1.67ms |
| MID | V/3 | 5.216V ->1.739V | 0..5.5V ->0..1.833V | 1.67ms |
| VBUS | V/11 | 9V ->0.818V | 0..32V ->0..2.909V | 1.91ms |
| VPROT | V/11 | 9V ->0.818V | 0..32V ->0..2.909V | 1.91ms |

Ranges above are arithmetic examples, NOT permission to apply15/32V or a guarantee
of ADC safety. The hardware gate rejects non-9V input. A2.5V external ADC reference
cannot measure the full32V example without overrange. Resistor tolerances, finite
op-amp swing, AUX tolerance and diode clamp Vf/leakage alter these values. Negative
sense is valid only with AUX alive; D25/D26 still protect NEG_SUM provisionally.
All six existing10k/100n filters and all14 BAT54WS clamps are retained.

## Hardware-only power and one ordinary LED

Normal intended operation: CH224A PG low -> Q1 -> JP1 -> EF_ENABLE, always subject
to independent TPS26600 UV/OV. Q2/external-permit circuitry is removed. JP1 stays
OPEN only as the prototype qualification inhibit; after qualification RUN closed
would allow hardware operation without any debugger/MCU attached.

Bipolar enable is local: MID -> R38 100k -> BI_EN -> original R40 100k ->GND.
Nominal BI_EN is MID/2 (2.608V at nominal MID); unlike an AUX-driven enable, it is
zero when MID is absent and does not source housekeeping power into U4's EN pins.
This simple bias is not an independent precision sequencer: EN leakage/thresholds,
startup/shutdown, MID overshoot and residual rails still require qualification.

Final regulated P5 -> R32 1k -> D10 anode2, cathode1 ->GND. D10 is one ordinary
hand-soldered red3mm power LED, retained at the original D10 panel position. No
blink or external LED control; dark with P5 absent. It shows **+5V presence only**,
not PD-contract validity or health of either12V rail. D11/D12/R33/R34 and their two
panel holes/PCB footprints are removed. Exact LED brightness/MPN/fit remain open.

## J7 and J2: one physical power harness, not redundant active outputs

J7 is carrier solder landing/copper, not an additional purchased box header. J2 is
the off-board keyed male16-pin endpoint on its flying lead, counted once in the
manual harness and not JLC placement. The schematic marks the cable boundary.
1/2=-12V,3..8=GND,9/10=+12V,11/12=+5V,13..16 NC. Never parallel another active PSU.
