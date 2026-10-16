# Onboard firmware retired

Current hardware has no MCU, UPDI, firmware build/flash dependency, blink logic,
or external LED controller. Old ATtiny sources/build tests were removed; Git history
is historical only. D10 is an ordinary final +5V ->1k ->red LED ->GND indicator.

Normal intended power operation is hardware-only: CH224A PG, TPS26600 UV/OV window
and RUN closed. JP1 stays OPEN in this unqualified prototype; this is a qualification
inhibit, not a requirement for a debugging MCU. J8 is an optional keyed20-pin debug
IDC exposing six conditioned senses/status/I2C/button, NOT Eurorack power.
