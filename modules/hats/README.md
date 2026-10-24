# HATS

6HP Eurorack hi-hat: Bread Modular NOISE (blue noise, NOISE TONE / BLUE TONE) feeding the Bread
Modular HIHAT (bridged-T filter CUTOFF, vactrol VCA, envelope with DECAY for closed hats), MIDI
driven (notes <= 60 closed, > 60 open, velocity = accent). NOISE IN replaces the internal noise.
REC button (both MCUs) + REC LED. Outputs: AUDIO (~10 Vpp) and HAT CV (0..5 V, ENV LED). Status: S2
schematic + R1 routed 4-layer carrier; JLCPCB export in `jlcpcb/`, not supplier-accepted, not built. See `docs/research.md`.
