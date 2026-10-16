# Current electrical review

See [electrical-prototype.md](electrical-prototype.md) for actual circuitry and
persistent blockers. MCU/UPDI/firmware/blink/external-enable logic is removed.
Normal intended power is hardware PG + UV/OV with RUN closed; JP1 is currently
OPEN only for qualification. MID/2 provides local bipolar enable. Optional20-pin
J8 exposes all six conditioned senses/status/I2C/button; no external LED control.

D10 alone is final P5 ->R32 1k ->red LED ->GND (+5V presence, not all-rail health).
D11/D12 and two panel holes/PCB lamps are removed; other geometry is preserved.
PD/current proof, off-state injection, analog accuracy, fuse/magnetics/MID overshoot,
noise/thermal/loop behavior and physical fit remain unqualified. No routing or
manufacturing export/approval. Bounded Basic candidates were not qualified swaps.
