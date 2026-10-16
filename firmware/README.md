# Big Modular ATtiny1616 diagnostics — unprogrammed prototype

**Main operation is disabled in checked-in firmware (`POWER_STAGE_QUALIFIED=0`).**
JP1 RUN stays open. Read `docs/electrical-prototype.md` power-up blockers first.
These sources are not evidence of an assembled, programmed or working controller.

## Build / tests

From the project root:

```sh
make -C firmware host-test
make -C firmware target
```

Outputs stay in `research/electrical-v1/firmware-build`. Host C tests compile with
warnings as errors. Target build requires an existing AVR toolchain supporting
`-mmcu=attiny1616` and matching device headers. It currently stops because avr-gcc
is unavailable. No global installation, target flashing or fuse writing was done.
`main.c` register names, timer accuracy and code size are not target-verified.

## Pin and programming contract

SOIC20 only (do not reuse this numbering for QFN):

| Physical pin | Function |
|---|---|
|1 /20|AUX3V3 /GND|
|2/4/5/6/7/10|ADC0 AIN4/6/7/8/9/10: +12/-12/+5/MID/VBUS/VPROT|
|3|PA5/VREFA unused; NC, not an external reference|
|8|PB3, bipolar enable, external100k pulldown|
|9|PB2, MCU permission: low enables PNP; Hi-Z denies|
|11|PB0 aggregate eFuse FLT_N|
|12/13/14|PC0/PC1/PC2 LED cathode sinks|
|15|PC3 reset/requalify button|
|16|PA0 UPDI|
|17/18|PA1/PA2 software open-drain I2C SDA/SCL|
|19|PA3 PD_PG_N|

J8:1 UPDI,2 AUX3V3,3 GND. Exact header/programming fixture remains a manual
provision, not placed on PCB. Use a 3.3V-compatible UPDI programmer and verify
its power behavior. Do not drive external AUX into an unpowered board until the
MCP1799 reverse/backfeed behavior and all sense paths are qualified. No flashing
command is prescribed until the actual programmer and safe power arrangement
are selected. Never change UPDI to reset/GPIO through unreviewed fuse settings.

Before flashing: real target compile; inspect fuse readback; verify 20MHz/6 clock
used by F_CPU; check runtime 2.6V BOD and watchdog settings against current device
headers/datasheet. Calibrate internal2.5V ADC reference and all divider/inverter
ratios. Prove safe GPIO states during reset, brownout, watchdog and programming.

Host logic tests cover independent rail faults, first-fault retention, missing9V
synchronous override, bad-I2C/current/RUN/FLT distinctions, startup sequencing,
hysteresis, reset, timestamp rollover and default deny. They do not test the
I2C/ADC HAL, silicon status freshness, fuse configuration, analog protection,
clock accuracy, target compiler/linker or actual LED brightness.

Healthy rails steady; overload-induced droop is a rail fault, not a measured
current-only overload. A latched affected rail flashes4Hz with the other outputs
OFF; actual missingPD9 overrides all at0.5Hz. General failure flashes all4Hz.
Reset is edge-triggered clear/requalification, not direct power authorization.
A host-passing logic state is not permission to set POWER_STAGE_QUALIFIED=1.
