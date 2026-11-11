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
- Big VOL knobs: printable design in `mechanical/knobs/` (repo root) (2026-11-10): Ø16 base / Ø15 top x 13.5 mm, so
  4.32 mm between neighbours instead of the 2.3 mm a full Ø18 knob would leave; slit-sleeve grip (four
  fingers + ribs) on the 6 mm knurled shaft, closed pointer pocket 1.6 x 0.6 mm for a white paint pen.
  Slim option added the same day (user: Ø16 looks too wide): Ø13 base / Ø12.2 top x 13.5 mm, same grip,
  7.32 mm between neighbours; about the narrowest this grip allows (0.55 mm finger gap, 0.92 mm wall).
  Knob puller added the same day (user): spring tongs for both widths, 0.8 mm hooks under the knob
  base from above and below the knob (the only free direction: neighbours 4.32 mm apart sideways),
  straight pull. A fork or wedge from one side was rejected: 0.8 mm tines cannot lever, and a
  one-sided wedge lifts the knob off-axis and cocks it on the shaft.
  Shaft measured by the user the same day: 18 mm above the pot body top, about 13 mm above the panel
  front (the RV09 proxy has 16 mm, so 11.2 mm above the FR4 panel). Knobs went from 12 to 13.5 mm tall
  and the bore from 9.7 to 11.5 mm; grip, fit gauge and puller shape unchanged. With the nominal
  6.8 mm body the tip is 24.8 mm above the carrier: 13.2 mm over the FR4 panel, 12.8 mm over the
  2.0 mm printed one, both consistent with the measured 13.
  User test print, 2026-11-11: the slim width is the one to use, but even the tight fit was loose
  and wobbly. Cause, from a bending model of one finger (section from the CAD model): the ribs ran
  5.5 mm up from the mouth on 8.5 mm fingers, so the shaft bore on them 3.3 mm from the finger roots;
  the tight fit (crest Ø5.7) then needs 2.9 % / 4.4 % root strain on a Ø5.9 / Ø6.0 shaft and the
  nominal fit (Ø5.9) 0 / 1.6 %: a finger either did not touch or was bent past yield. Nothing held
  the shaft tip either (Ø6.3 bore), so the knob could rock around the ribs. A plain smaller bore was
  not used: a rigid press fit has a window of a few 0.01 mm, less than the printer's and the
  shaft's (Ø6.0 +0 / -0.1) tolerance, and the pot shaft is only rated for a 4 to 5 kgf push.
  Grip 2: fingers still 8.5 mm, rib only on their free end (shaft bears 6.4 mm from the root, on the
  plain shaft below the knurl), plus four small pilot ribs in the solid knob top that centre the
  shaft tip 8 mm above the finger ribs. Five fits instead of three, 0.12 mm apart on the diameter
  (finger crest Ø5.52 .. Ø6.00, pilot crest 0.3 mm larger); middle fit on a Ø6.0 shaft 0.9 % strain,
  5 N pull-off, 15 mN·m slip torque (PLA 2.5 GPa, friction 0.3; calculated, not measured). Fit gauge
  now five break-off tiles with the blind bore of the knob. Outside shape, height, bore depth and
  the puller are unchanged. An in-between version with 10.5 mm fingers hanging from the roof and no
  pilot was dropped: lower strain, but the shaft tip stays free in the Ø6.3 bore, so it can still rock.
  User test print of grip 2, 2026-11-11: even `fit1` does not hold. User direction: a different
  strategy, no slits ("broken spaces to move"), a tight fit as the knob is pushed on, like the Thonk
  Tall Trimmer Toppers that fit these pots (plain thin-walled push-on caps; the shop page gives no
  bore size, only "6 mm plastic shaft", at least 7 to 8 mm proud of the panel).
  Grip 3: solid knob, square blind bore tapered 0.3 mm across flats over the 11.5 mm depth (0.75 deg
  per wall), so the round shaft enters freely and wedges tighter as it goes in: the knob finds its
  own seat, which answers the "window of a few 0.01 mm" objection above. The shaft touches the middle
  of each flat only (four lines, no rocking). Each flat is a 0.9 mm two-perimeter wall joined to the
  solid corners at both ends with a closed relief pocket behind it (5.4 mm span, out to Ø10): stiff
  (185 N/mm per mm of length as a fixed-fixed beam) but not rigid, and it bends along the perimeters,
  not across the layers as the fingers did. Model (PLA 2.5 GPa, friction 0.3, perfect print): a 20 N
  push grips 3.7 mm of shaft, 20 N pull-off, about 60 mN·m slip torque, 1.8 % wall strain. Eight fits
  0.1 mm apart (roof 5.4 .. 6.1 across flats, mouth 0.3 larger); one step moves the seat 3.8 mm along
  the shaft, so between two fits the knob sits up to that much higher. The ladder is wide on purpose:
  both spring-finger grips were loose at crest sizes that should have held on paper, so the real shaft
  or the printed bore may be off the nominal; the shaft diameter has not been measured. Fit gauge:
  eight break-off tiles. Outside shape, height, bore depth and puller unchanged; puller re-checked on
  the new knob base (relief pockets open there): 13.9 mm² of base over the hooks on the slim knob at
  the worse rotation.
  User test print of grip 3, 2026-11-11: `fit1` (the tightest) fits and holds, but the knob moves on
  the shaft when the pot is turned hard against its end stop. Two readings: friction alone is not
  enough on this shaft, and the print is again looser than the model (the table wanted `fit4` /
  `fit5`, a bore 0.3 to 0.4 mm wider, part of it probably the thin walls bowing more than
  calculated). User direction: do it as the Thonk caps do, a round tapered hole with grooves in its
  top part that line up with the grooves at the top of the pot shaft.
  Shaft data: Song Huei R0904N, the tall trimmer Thonk sells as `R0904N-B50K, L-25 KQ`. Shaft type KQ
  on the Song Huei shaft-type sheet = Ø6 plastic shaft with a 40-tooth straight knurl on the top
  7 mm (KC is 18 teeth with a slot, KT 40 teeth, F a flat). Groove depth is not on the drawing.
  Torque 30 to 150 gf·cm, end stop 3 kgf·cm, push-pull 4 kgf (Thonk sheet) / 5 kgf.
  Grip 4: solid knob (no pockets or thin walls: 2.76 mm of wall on the slim knob), round blind bore,
  20 triangular teeth (90 deg, 0.6 mm base, 0.3 mm high at the roof) in the top 6.0 mm, one for
  every second knurl groove: 40 teeth at 0.47 mm pitch are below what a 0.4 mm nozzle prints, 20 at
  0.95 mm are not, and the knob still goes on in 9 deg steps. Tooth tips close in 0.3 mm on the
  diameter over the 6 mm (1.43 deg per side), so the teeth wedge into the grooves as the knob is
  pushed on (no play) and the knob finds its own seat; one 0.1 mm fit step moves the seat 2.0 mm.
  Seat model (geometry only: V grooves 0.2 mm deep assumed, tooth tips rounded to half a 0.45 mm
  line): tooth tip Ø5.5 at the roof seats a Ø6.0 shaft 1.1 mm short of the roof. Eight fits, tip
  Ø4.9 .. Ø5.6 (round bore 0.6 larger): the to-size fit is `fit7`, and the ladder runs 0.6 mm
  tighter from there because all three earlier grips came out loose; a repeat of the grip 3 offset
  lands around `fit3` to `fit5`. Outside shape, height, bore depth and puller unchanged; the puller
  was re-checked on the solid knob base (15.3 mm² over the hooks on the slim knob).
  Side effect: the knob no longer acts as a slip clutch, so a hard turn now loads the pot's end
  stop (3 kgf·cm).
  User test print of the grip 4 gauge, 2026-11-11: the 8-notch tile (`fit8`, the loosest: tooth
  tip Ø5.6, bore Ø6.2) goes into the grooves and locks; "workable". The tiles below it were not
  reported. Readings: the 40-tooth knurl is confirmed in practice (20 teeth drop in), and for the
  first time a print lands where the seat model puts a Ø6.0 shaft ("on the roof, light"), not
  0.3 to 0.4 mm tighter as with the thin-walled grips. User direction: more variants of the
  grooves in the top part of the hole, to pick the best fit.
  In that gauge bore and teeth shrank together, so the tooth depth was never tried on its own.
  Tooth ladder: round bore fixed at Ø6.2 (`BORE_D`), fit = tooth tip diameter at the roof,
  Ø5.45 .. Ø5.80 in 0.05 mm steps (`t1` .. `t8`; tooth height 0.375 .. 0.20 mm, base 0.75 ..
  0.40 mm, >= 0.22 mm of bore wall between two teeth at 0.97 mm pitch). `t4` is the old `fit8`
  (STEP difference 0.0 mm³ both ways); three steps deeper, four shallower. One step moves the seat
  1.0 mm along the shaft. Seat model on a Ø6.0 shaft: `t1` stops 2.1 mm short of the roof, `t2`
  seats 1.1 mm short, `t3` 0.1 mm short, `t4` / `t5` on the roof with 0.02 / 0.05 mm radial play,
  `t6` .. `t8` loose (0.07 .. 0.12 mm). Tooth angle and shape were left alone: a 0.4 mm nozzle
  rounds the tips to about 0.2 mm, so depth is the lever that prints. The new gauge tiles have one
  corner cut off, to tell them from the first gauge. Puller unchanged (STL byte-identical).
  User, 2026-11-11, after printing the tooth-ladder gauge and a slim `t4` knob: "the sizes on the
  fit gauge and the knobs are not correct", the slim `t4` knob "seems to be the previously
  `fit8`"; slim `t2` and `t3` knobs in print (result open). Read as: a tile and the knob of the
  same number did not fit alike. Checked on the exported STEP files: the bore sections of every
  tile and of the slim knob of that number agree at seven heights (tooth tip and bore diameter,
  0.001 mm), so the model was not the difference; the print was, cause not confirmed. A tile had
  the bore in a Ø12 boss on a plate with the bore roof (deepest teeth, where the grip is) 1.1 mm
  above the bed; a knob has it 2.0 mm up in its own shell.
  Gauge rebuilt the same day: one per width, = that width's eight knobs in one print (2 x 4, joined
  by break-off links on the bed), numbered by 1 .. 8 notches in the base rim, each in a ridge
  between two flutes. A gauge knob is the knob file apart from the notches (9 sections per knob,
  4 widths x 8 fits, no difference: `mechanical/knobs/research/check/gauge_vs_knob.py`). Left over: eight
  knobs printed together cool longer per layer than one or four.
  Same day, user: the variants in folders, and two slimmer widths. `mechanical/knobs/` (repo root) now has
  `wide/` (Ø16), `slim/` (Ø13), `slimmer/` (Ø11.5 base / Ø10.8 top, 14 flutes) and `slimmest/`
  (Ø10 / Ø9.4, 12 flutes), each with `t1` .. `t8` and its gauge, and `puller/`. Wide and slim
  knob STLs and the puller STL are byte-identical to the files before the move. Same bore, teeth
  and 13.5 mm height in every width; wall between bore and flute 4.07 / 2.76 / 2.10 / 1.44 mm
  (asserted >= 1.35 mm = three printed lines; was 2.0). Ø10 is where that wall and the base face
  (1.15 mm, what the puller hooks hold) end; Ø9.5 would leave a 1.2 mm wall. The thinner wall is
  the hoop that keeps the teeth in the grooves, so the fit picked on the slim knob need not carry
  over: each width has its own gauge. VOL knob to VOL knob 4.32 / 7.32 / 8.82 / 10.32 mm.
  Puller unchanged (STL byte-identical), re-checked on the new widths: hook tips close to 3.95 /
  3.5 mm off the axis (0.95 / 0.5 mm from the shaft), 14 / 9 mm² of knob base over the hooks,
  hook top 0.36 / 0.33 mm under the knob base on the printed panel.
  Still open: the user's slim `t2` / `t3` result; print the gauge of the chosen width and pick the
  fit (if the best fit still has a flaw:
  which one, twist play, hard push or sitting high; `TIP_TAPER` / `SPLINE_L` / `BORE_D` are the
  next levers); slimmer and slimmest are not printed (does the 1.4 mm wall hold the teeth, does
  the puller get under the slimmest); measure the shaft diameter over and below the knurl; check
  the gap under the first knob
  (1.7 mm FR4 / 1.3 mm printed; the puller hooks need >= 1.1 mm). `RV09_proxy.step` (copied from
  modules/32bit, same in the other modules) still has the 16 mm shaft.
  2026-11-12, user: knobs moved to the repo-root `mechanical/knobs/` (with the build
  script in its `tools/`, previews in `renders/`, scratch in `research/`), next to the case in
  `mechanical/case/`. Rebuilt from there: all 36 STLs byte-identical.
  Same day, user: folder renamed to `mechanical/knobs/` and every 4MIX reference inside removed:
  files `knob-<width>-tN`, `knob-<width>-fit-gauge`, `knob-puller`, script `tools/build_knobs.{sh,py}`,
  renders `knob-*.png`; the panel data the fit checks use is a snapshot of `docs/geometry.json` in
  `tools/reference/panel.json` and the RV09 model is copied to `tools/reference/RV09_proxy.step`.
  Rebuilt: all 37 STLs byte-identical to the old names, report unchanged apart from names.
- Check the standoffs' thread depth: M3x6 assumes >= 4.4 mm of thread at each end.
- Panel/3D fit check, FreeCAD printed panel, bench test (levels, crosstalk; BM 4mix needed
  routing fixes for send leakage: R1 keeps the SEND A/B buses apart on B along the channel rows,
  and the long SEND outs run on F over the solid In1 GND, but check send leakage on the bench).
- JLCPCB export done 2026-10-23 (`jlcpcb/`); order gates in `jlcpcb/README.md`.
