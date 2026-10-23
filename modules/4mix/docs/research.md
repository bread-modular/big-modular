# 4mix research notes (S2/P6)

## 1. Brief (user, 2026-10-22)

Redesign Bread Modular `4mix` for Eurorack in 18HP; all controls rotary; space for a big
MAIN knob (same pot); no overdrive; MAIN, RETURN and SEND in the top area; each channel's
input jack on top of its strip; schematics adapted to Eurorack levels/impedance with wired
nets and a single-channel sub-sheet; channel expansion via MAIN/SEND inputs on internal
headers, no jacks. This step: THT placement only, no routing.

Revision (user, 2026-10-22, S2/P2): pure audio mixer, AC-couple every input; top area as one
line in the order SEND A, RETURN A, RETURN A level, (gap), SEND B, RETURN B, RETURN B level,
MAIN, OUT, for more channel height; power at the bottom and the expansion headers at the top,
moved to the sides, EXP IN and EXP OUT on opposite sides.

## 2. Bread Modular baseline (`modules/4mix` 1.0.2, read-only)

Single 3.3 V supply, MCP6002, V_MID bias. Channel: 56k inverting buffer (56k || 47p) ->
100R -> VOL pot; wiper -> 56k -> MAIN_MIX; wiper follower -> 100R -> SEND A/B pots ->
56k -> send buses (post-fader). Main: summer U1B -> 100R -> MAIN pot -> U3A summer with
the RETURN A/B levels (returns: 10k + 1M + 100p -> follower -> 100R -> pot) -> U3B
inverter -> overdrive -> 1k MIXOUT. Sends: U5A/B summers -> 330R. Cascade: IN_MIXOUT and
IN_SEND_A/B -> 1M pull-down -> 56k inverters -> buses.

## 3. Circuit (S2)

Same topology on ±12 V (TL072 everywhere, ground-referenced, V_MID/U6 removed):

- Channel (sheet x 4): PJ301M-12 (TN -> GND) -> 10u (C n04) -> 100k -> inverting buffer 100k || 20p
  (100k input impedance) -> 100R -> VOL; wiper -> 100k -> MAIN_SUM; follower -> 100R ->
  SEND A / SEND B pots -> 100k -> SENDA_SUM / SENDB_SUM. 100n per supply pin.
- Summers U1B / U5A / U5B (100k || 20p). MAIN_MIX -> 100R -> RV1 MAIN -> 100k -> OUT_SUM.
- Returns J3/J4 (TN -> GND) -> 1u (C23/C24) -> 10k -> follower (1M || 100p to GND) -> 100R -> RV2/RV3 ->
  100k -> OUT_SUM. U3A sums, U3B inverts -> 1k 2512 -> J5 MAIN OUT.
- SEND A/B outs: 1k 2512 (mis-patch survivable, as modules/imix).
- Expansion: J7 EXP OUT = MAIN_MIX (pre-master), SENDA_MIX, SENDB_MIX via 1k; J6 EXP IN ->
  1M pull-down -> 10u (C25-C27) -> 100k inverter -> 100k into the bus (BM cascade path). Chain an
  expander's J7 to the master's J6 with a 6-way ribbon; polarity is kept end to end.
- Power: 2x5 header, B5819W per rail, 10u bulk. 9 x TL072 (~25 mA per rail).

## 4. Decisions

- D1: resistor scale 56k -> 100k (Eurorack 100k inputs); feedback caps 20p (imix values).
- D2: the BM 100R in series with each 56k summing resistor is dropped (meaningless next
  to 100k; modules/imix does the same). The 100R pot-drive resistors stay.
- D3 (S2, user): audio only, every input AC-coupled. Channels and EXP IN: 10u (BM channel
  value) into 100k; returns: 1u into the 1M bias; all -3 dB at 0.16 Hz. TN still grounds
  unpatched jacks (no BM 1M bias needed: the 100k / 1M already set the DC). Outputs stay
  DC from the op-amps (TL072 offset only).
- D4: EXP OUT is pre-master (BM chained the final MIXOUT); the master's MAIN knob then
  sets the whole chain, and returns belong to the master.
- D5: EXP headers 2x3 (not 2x5) so a Eurorack power cable can't be mistaken for one.
- D7 (P2): the top line does not fit side by side (8 parts need ~78 mm at minimum pitch of
  88 mm usable, leaving no gap and no big-knob room), so jacks take an upper row (Y16.6) and
  pots a lower row (Y31), keeping the user's left-to-right order. Big-knob reserve 28 mm
  (was 30 mm). Channel rows IN 52 / A 70.5 / B 89 / VOL 107.5 (18.5 mm pitch, was 14.5).
- D8 (P2): J6 EXP IN top left, J7 EXP OUT top right, J8 power bottom left, all in the side
  margins on B. Chain: expander LEFT of the master (its J7 at the right edge meets the
  master's J6 at the left edge); the master is rightmost.
- D9 (P3, user hand placement, 2026-10-22): sends together top left (SEND A X6.6, SEND B
  X20), RTN A X35 / RTN B X52 at Y16.6 with LVL A / LVL B right below (Y30), MAIN X69 on
  the jack row (Y16.6; the hand position Y15.1 put its courtyard 0.65 mm from the top edge),
  OUT X84.5. Channel rows IN 47 / A 65.5 / B 84 / VOL 106. The big knob is for the channel
  VOL knobs, not MAIN: Ø18 mm reserve each (2.3 mm between neighbours). Tidy: 0.1 mm grid,
  columns back on the panel-centred 4HP pitch (hand move was 0.46 mm left, VOL 0.5 mm off its
  column), J3/J4 swapped so RETURN A sits over LVL A and RETURN B over LVL B.
- D10 (P4, user 2026-10-22): J8 power moved to the bottom-right margin (pads centre X86.3,
  pin 1 at the bottom); the IDC16 socket envelope X82.5..90.1 stays inside the panel width.
- D11 (P5, user 2026-10-22): the carrier bottom has no jacks to hold it to the panel, so two
  printed L brackets (user's idea; M3 bolt + nut each end) do. BRK1 X25.33 / BRK2 X65.97 (midway
  between the VOL columns), carrier bolt Y102, panel bolt Y114. The foot lies on the carrier F
  side between the VOL pot bodies (7.2 mm wide, ~0.8 mm from each RV09 body); the upright fills
  the 10 mm stack below the pot bodies, where only the pot pins are. Nuts are captive (foot-top
  hex pocket; upright side slot open toward the board bottom edge), so both bolts go in from
  outside: carrier bolt from B, panel bolt from the front. Panel bolt heads (pan, D5.5) are 1.2 mm
  clear of the 18 mm big-knob circles. Width is set by the pot gap, so the nut pocket side walls
  are 0.75 mm (only locate the nut; the clamping load bears on full-width faces).
- D12 (P6, user 2026-10-22): the L brackets are replaced by the user's 10 mm M3 female-female hex
  standoffs (5.5 AF). The carrier F to panel rear stack is exactly 10 mm, so each standoff is
  coaxial: one M3x6 from the carrier B side, one M3x6 from the panel front (M3x8 x 2 = 12.8 mm of
  thread in 10 mm would meet). MS1 X25.33 / MS2 X65.97, Y114: lowest spot where the hex clears the
  1 mm edge keep-out (courtyard R3.3 -> 1.93 mm) and highest where the panel screw head (R2.75)
  clears the 18 mm big-knob circles (1.18 mm); hex 0.57 mm from the VOL pot courtyards. Mechanical
  footprints with empty Reference + MechanicalID (shared parity convention).
- D6: wipers see 100k to a virtual ground (BM style): ~44 % at mid rotation on 50k B.

## 5. Open items

- Sourcing: live-audited 2026-10-23 (`jlcpcb/README.md`): all Basic except the 1 W 2512 1k (Extended).
- RV1 Note field still says "big-knob position" (stale since P6: the big knobs are the channel VOLs).
- Big VOL knobs: confirm the actual knob diameter (reserve 18 mm) and shaft fit on RV09.
- Check the standoffs' thread depth: M3x6 assumes >= 4.4 mm of thread at each end.
- Panel/3D fit check, FreeCAD printed panel, bench test (levels, crosstalk; BM 4mix needed
  routing fixes for send leakage: R1 keeps the SEND A/B buses apart on B along the channel rows,
  and the long SEND outs run on F over the solid In1 GND, but check send leakage on the bench).
- JLCPCB export done 2026-10-23 (`jlcpcb/`); order gates in `jlcpcb/README.md`.
