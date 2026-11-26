# Agent entry point

This repository is a monorepo of Eurorack modules built with shared KiCad
tooling.

## Layout

- `modules/<name>/` — one self-contained hardware project per module. It owns
  its KiCad sources (`hardware/`), `docs/`, module tooling (`tools/`) and
  upload-ready `jlcpcb/` outputs.
- `opt/` — shared, module-independent tooling (`opt/kicad-tools/` native KiCad
  checks, PCB/schematic edits, JLCPCB export/assembly; `opt/kicad-routing/`
  optional router facade). It stays at the repository root. Never move it into a
  module and never fork or duplicate it per module.
- `opt/updi-programmer/` — USB-C UPDI programmer (jtag2updi on ATtiny1616) for
  the modules' UPDI chips: generated KiCad project, firmware and README.
  `opt/attiny1616-tools/` holds the shared ATtiny1616 compile/flash scripts and
  shared sketch libraries in `lib/` (e.g. `lib/CvRecorder/`), symlinked into
  each sketch folder.
- `opt/esp32-tools/` — shared ESP32-S3 ESP-IDF setup/compile/flash scripts (reuse an
  installed `~/esp/esp-idf`), wrapped by `modules/32bit/firmware/`.
- `opt/stm32g0-tools/` — shared STM32G0 bare-metal (CMSIS) compile/flash scripts (reuse the
  `~/.breadmodular` ARM GCC; pinned CMSIS headers + xPack OpenOCD for ST-Link SWD), wrapped by
  `modules/hats/firmware/`.
- `opt/rp2350-tools/` — shared RP2350 Pico SDK setup/compile/flash scripts (reuse an
  installed `~/.breadmodular` Pico SDK 2.1.1 / ARM GCC 14.2 / picotool), wrapped by
  `modules/16bit/firmware/`.
- `mechanical/` — 3D-printed mechanics outside the KiCad modules, each folder with its
  own FreeCAD-headless `tools/`, ignored `research/` and print outputs: `mechanical/case/`
  (skiff case; `print/` is grouped as `side-panels/` (standard, four spacer sockets for bolt-on stand plates), `rails/`, `bottom-plate/`, `covers/`, `double-case/` (middle frame), `quad-case/` (flat 2 x 2 set with fused panels, also the angle joiner's upper element), `stands/angle-joiner/` + `stands/tiered-stand/`, and `accessories/top-brace/` + `accessories/cable-holder/` (clip-on patch cable comb) + `accessories/usb-riser/` (8HP collar that lifts modules/32bit 18 mm so its back USB-C plug passes over the back rail; CAD + slicer checked 2026-11-22, not printed); index in `print/README.md`, renders mirror it) and `mechanical/knobs/` (push-on
  knobs for the RV09 pots + puller; self-contained: a reference panel and the RV09 model in its `tools/reference/`) and `mechanical/solder-arm/`
  (desk-clamp soldering arm for the module PCBs, every part printed incl. threads: one 190 mm arm link, three toothed joints (yaw, raise,
  tilt / flip), two sliding jaws for 16 .. 157 mm boards; two-screw desk base only (the single-screw clamp was removed 2026-11-26): `print/two-screw-base/` wide 5–52 mm, `compact-28/` lighter 5–28 mm, `narrow-56/` half width (56 mm along the edge, screws 32 mm apart, 5–52 mm; 2026-11-26, CAD + slicer checked, not printed), same upper arm; the arm build checks every pose on the base; user: printed, "works really well" (2026-11-26), not load-tested) and `mechanical/button-cap/`
  (two-piece cap for the modules' tact-switch push buttons: modules/8bit plunger with a longer tip + press-on Ø8 / Ø6.5 head in front of
  the panel; first print 2026-11-18: head too loose, crush ribs tightened Ø3.5 -> Ø3.3, that fit not printed) and
  `mechanical/desk-cable-holder/` (under-desk patch cable comb, every part printed: 240 mm C-shaped hanger behind the desk edge,
  flange against the desk's underside, comb with 16 slots x 4 plug seats 64 mm below it, held by one C clamp with the solder arm's
  printed screw / nut / pad, the only part outside the desk; desks 8 .. 50 mm; second design, the first lay on the desk and stuck
  out; original centre clamp tilts even with the replacement shoe. Current simple retrofit: `print/end-clips/print-this.3mf` — two threaded end clips and two printed screws, one size for flat 8–50 mm desks. The existing hanger slides into the clips unchanged; the screws press on the desktop underside. CAD and PLA slicer checked, not physically load-tested).
- `modules/<name>/AGENTS.md` and `modules/<name>/Code.md` — module-specific
  circuit/release contract. Read them before touching that module.

| Module | Description | Release |
| --- | --- | --- |
| `modules/usb-power/` | USB-C PD 9 V input, TPS26600 protection, TPS55340 boost, TPS54302 inverting buck-boost, TPS7A4700/TPS7A3301 ±12 V, +5 V | SR2 schematic + 084 PCB source accepted; not released |
| `modules/usb-power-45w/` | USB-C PD 15 V / 3 A (CH224A, R1 56k, VHV/VBUS straight on VPD as in the WCH reference) -> TPS16630 main eFuse (precision UVLO, OVP coordinated with D24 SMBJ20A) -> TPS552892-Q1 +12 V buck-boost and LMR38020 -12 V inverting converter (own-input enable, sequenced after +12 V); ±12 V only, two 10-pin outputs J2/J3; always-on STARTED one-shot, fault latch and RESET; MAIN LED only; one 4-layer carrier, all parts on F, 4HP panel | **S9.4 / R2** schematic + **manually routed** board (`hardware/usb-power-45w.kicad_pro`; 2026-11-16: the first S9.3-10P / R1 board stayed at 5 V because Q2 BCX53 SOT-89 in the CH224A supply limiter had emitter and base swapped (Nexperia numbers the leads 3-2-1), so the limiter Q2/Q3/R23/R27/D9/D11 and TP2 are removed and U1/C1 re-routed onto VPD; a built R1 board works with a TP1-TP2 wire): two 10-pin IDC outputs J2/J3 (Wurth 61201021621); FB-injection soft starts on both converters start it from a strict 3.00 A source in one attempt (netlist plant peak 2.955 A, 0 U5 drop-outs); 178 refs / 81 nets, ERC 0, DRC 0 / 0 warnings / parity 0 / **0 unconnected**; In1 one-piece GND, two approved In2 hops, test points on B; routing contract in native DRC (8 net classes, 22 `S92_*` rules, 15 rule areas), no via-in-pad. Prototype targets +12 V 2.4 A / -12 V 0.8 A, <=33 W. Fab review 2026-11-06: SW1 case-pad link removed (the two DRC errors after a KiCad 10 Update PCB), third +12V output via at R109, third D1 TVS GND via (tvs.D1 PASS), U2 PGND via; J2/J3/D8 hand-fitted (`in_pos_files no`), J1 machine-placed; D1 SMBJ22A re-sourced to Littelfuse C224015 (stock; RUILON C10214 had 59). **S9.4 / R2 JLCPCB export in `modules/usb-power-45w/jlcpcb/` (2026-11-16, 149 top parts / 60 rows, shared `check` manifest equal; live stock not re-checked since 2026-11-06)**, J2/J3/D8 by hand; panel Gerbers; not supplier-accepted; one R1 board built and bench-started with the TP1-TP2 wire (15 V contract, ±12 V and LED seen unloaded; load / 3 A start / thermal tests open). `tools/check_s8_board.py` still lists contract items (min widths = taps/stubs, U2/R109/D10 thermal copper, U12.14-C52.1, D25-D24, TP22/TP23 pair, R116.1 in RA_AGND_ISLAND), reviewed and accepted for the first prototype, not waived (TH-1/TH-2 measure the thermal ones). Record `docs/routing/checkpoint.json` + `docs/routing/README.md`; review `docs/design.md`. |
| `modules/midi/` | 4HP TRS MIDI in (TRS A/B jumper header, no opto) -> ATtiny1616 -> 8 x TS modular MIDI outs + LEDs, +12 V -> 5 V LDO (Bread Modular `midi` based). Two versions: `hardware/v1/` (BM V1 direct input, unprotected) and `hardware/v2/` (±12 V mis-patch protected NPN input with a JP2 debug bypass, clamped outputs, +5V shunt) | V1.0 (S4/R5) and V2.0 (S3/R3) routed carriers + shared 4HP panels; JLCPCB exports in `modules/midi/jlcpcb/v1/` and `jlcpcb/v2/`, not supplier-accepted |
| `modules/audio-out/` | 4HP ±12 V pure-analog stereo out: 2 x TS in (IN R normalled to IN L; OPA1678 buffers) -> TRS consumer line out + TRS headphone out (MC33178, RV09 50k volume per ear) (Bread Modular `base` based) | S3 schematic (IN R normalled to IN L, no MONO jumper, unshrouded 10-pin power header, 10-pin cable) + R4 routed carrier (thermal-relief GND pours) (IN L, IN R, LINE, VOL L, VOL R, PHONES); 4HP panels; JLCPCB export in `modules/audio-out/jlcpcb/`, not supplier-accepted, not built |
| `modules/vca-mix/` | VCA-MIX, 6HP: 3 x vactrol VCA (Bread Modular V2CA, no CURVE; Bread Modular LOW/SVF vactrol driver; IN/CV/OUT per channel, CV unpatched = open) + per-channel volume after the VCA (OUT post-volume) + MIX out (Bread Modular imix style), buffered inputs/CV, 1 W output resistors, ±12 V, 10 x TL072 | S4 schematic + P4 placement + 6HP panels; R1 routed carrier, final (TraceMaker + cleanup, 0 unconnected; the 9 vactrol/pot stacking findings are user-approved DRC exclusions, D10; copied into `hardware/` past the shared gate, which still counts them, D14, user-verified manually; vactrol build notes on silk); JLCPCB export in `modules/vca-mix/jlcpcb/`, not supplier-accepted, not built |
| `modules/16bit/` | 16bit, 6HP: RP2350A + W25Q128 flash + APS6404L PSRAM, PT8211 I2S DAC -> TL074 ±5 V outs, MIDI in (NPN, JP1), 2 x CV in with attenuators, 2 knobs, MODE button + LED, USB-C data, 4-layer (Bread Modular `16bit` based) | S3 schematic; **P6 panel + R3 manual routing** (2026-11-15, user: OUT jacks at the very bottom Y110.4, MODE (record) button above OUT L at Y98 with the MODE LED 13.5 mm to its right (X21.0, user 2026-11-15: apart as in R2; the limit beside the J6 header pads), power header upright at the right board edge, MIDI jack 0.95 mm / CV jacks 1.3 mm up (the MIDI jack courtyard and the top edge are the limit), RV3/RV4 2.5 mm down so the pot rows are 31.5 mm apart; R2 copper kept above the output amp, the band below re-placed and re-routed by hand: DRC 0 / unconnected 0 / parity 0, no exclusions, 147 vias, none in SMD pads, plain tented, no POFV; re-placed SMD >= 2.03 mm from pot/jack pads, kept R2 parts as close as before (C31 0.225 mm); B silk BOOT/RESET/JP1 labels + `-12V` at J6); 6HP panel regenerated (DRC 0, holes checked against the carrier) + printed panel; **P6 / R3 JLCPCB export in `modules/16bit/jlcpcb/` (2026-11-15**, shared `check` manifest equal; bottom Economic, 86 parts / 43 rows, TM8211 for PT8211, cjiang L1 (live stock 53 on 2026-11-15), user-stocked Adafruit 4677 PSRAM), not supplier-accepted, not built; BM 16bit 1.6.0 firmware (six apps; polysynth + 16 wavetables (Kimura Taro CC0: classic synths, FM, complex) + Noise on P1 select / P2 position; sampler P1 kick drive / P2 DJ highpass resonance) in `modules/16bit/firmware/` (JP1 p/d builds, `opt/rp2350-tools`), compiled, not bench-tested; new `cpx4` app (Lyra-8-inspired 4-voice drone: TUNE on P1..P4, SHARP / MOD / DRIVE / FM routing on MCC-1, delay / feedback / mix / ladder cutoff + resonance on MCC-2; free-running MODE recorder, no MIDI clock: hold MODE + move a control records it on its own track (own length), release loops it with a glide from its last value back to its first, click removes every track; MODE debounced) with its two-unit MCC firmware in `modules/16bit/firmware/mcc/`, compiled + host-tested (`tools/sim_cpx4.cpp`, `tools/sim_free_motion_recorder.cpp`), not bench-tested |
| `modules/12bit/` | 12bit, 6HP: modules/8bit on an STM32G071C8T6 (ATtiny1616 low on stock): 8bit MIDI in (NPN, JP1) and bipolar CV in (MCP6001) at 3.3 V, three 50k knobs on the ADC (no low-pass), MODE button + LED, two DC-coupled ±5 V outs from the two 12-bit DAC channels (TL074 around VOFF), no gate out, SWD header, HT7533-1 +3V3, **2-layer**; S3: LM4040 3.0 V **+3V0 reference rail** (VREF+, knobs, VOFF, CV, MIDI pull-ups), +3V3 for the MCU only | **S3 schematic + R3 routing (2026-11-19, user: hardware fix for the output buzz of the first board)**: U5 LM4040B30FTA (C460604, Extended) + R18 2.2k from +12V_F make +3V0 for VREF+ (FB1), the knobs, VOFF, the CV shift + U2 and the MIDI pull-ups; U1 +3V3 moved beside the MCU and feeds only the MCU and J6.1 (own thin sense line); R5 51k / R6 100k / R10, R12 27k / R15 22k keep the S2 levels and ADC codes, so the firmware is the same; R3 = R2 + four hand batches (`research/route-s3/`; ERC 0 / DRC 0 / unconnected 0 / parity 0, no exclusions, 291 tracks / 65 vias, no vias in SMD pads, SMD >= 2.027 mm from pot/jack pads, courtyards >= 1.02 mm from the edge, B pour one piece, F one piece + the stitched strip); **S3 / R3 JLCPCB export in `modules/12bit/jlcpcb/` (2026-11-19**, shared `check` manifest equal; 2 layers, bottom Economic, 48 parts / 25 rows, 6 Extended part types incl. the LM4040; all codes live-checked, STM32G071C8T6 listed stock 965 on 2026-11-19, recheck), not supplier-accepted, **not built, not measured** (datasheet values; the DAC buffers still run on VDD/VDDA, but `humtest` step 7, buffers off, on the first board still hums, a bit duller (user 2026-11-19), so the reference is the path). Before that, the first board: S2 schematic (ERC 0, netlist asserted, LCSC codes live-checked 2026-11-06; MCU symbol = stock STM32G081CBTx renamed, pin table checked against DS12232, PB7 FT) + P3 placement (rows MIDI/CV, P1/P2, MODE + LED + P3, OUT 1/2 at the bottom; pot block centred between the jack rows; power header upright at the right edge) + **R2 2-layer routing** (user, 2026-11-07, to cut PCB cost: R1 4-layer F/B signal copper kept, In1 GND / In2 +3V3 planes removed, +3V3 re-routed as F/B tracks with 4 new vias, F and B GND pours), all SMD on B (DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, SMD >= 2 mm from pot/jack pads (closest 2.025 mm), courtyards >= 1.015 mm from the edge, B pour one piece, F pour one piece + one via-stitched 25 mm² strip); 6HP panel; its R2 JLCPCB export (2 layers, bottom Economic, 46 parts) is in git history, replaced by the S3 / R3 set; first board built (JP1 = P): firmware in `modules/12bit/firmware/` (`opt/stm32g0-tools`, CMSIS-DAP default): `clapsnare` synthesized clap + snare drum voice (MIDI note-on, P1 MORPH clap -> layered -> snare, P2 TONE with the CV in added to it (5 V = whole travel, bipolar), P3 DECAY, MODE = 4-bar three-knob recorder on MIDI clock; JP1 p/d builds; `p` flashed 2026-11-18, host-tested, hits checked over SWD, not heard / not tested with a MIDI source; knob ADC scan started by TIM6 once per sample after the 1 kHz software scan buzzed at the outputs, found with the `humtest` bench firmware (user: almost gone, a faint rest); since 2026-11-19 the scan only runs while the drum sounds or a take is recorded, flashed, user: "pretty good now"; the MODE LED no longer flashes on notes, recorder only, flashed), `crash` (2026-11-19, fourth version: crash cymbal + cowbell: P1 MORPH 808 / 909 style crash -> layered -> TR-808 cowbell, P2 TONE fully left = the classic sounds, up = tuned higher (crash a fifth, cowbell an octave), P3 FILTER resonant low-pass bypassed fully left, CV in on FILTER, clapsnare recorder; both sounds set against measurements of 808 / 909 recordings; every setting at the same level from measured tables (`crash/test.sh cal`), and that level driven into the soft clipper until the crash is as loud as the clapsnare clap by a loudness model (`crash/tools/loudness.h`; user: the third version sounded quieter than clap / snare; cowbell 1.5 dB above the crash on a meter, 2 phon under the clap), clapsnare velocity curve; compiled + host-tested, sample interrupt estimated by emulation; this version not flashed, not heard) and `osc3` three-oscillator mixer (user-confirmed working 2026-11-18) |
| `modules/low/` | LOW, 6HP: Bread Modular MCO (ATtiny1616 dual square, DETUNE/MIX) + LOW (two-vactrol LPG, CUTOFF) at 3.3 V; 8bit MIDI in; AUDIO and CV bypass inputs (10 Vpp / 0..5 V mapped to 0..3.3 V) normalled via a TS5A23157 to the MCO square mix and velocity DAC; TL072 ±12 V out | S3 schematic (ERC 0, signal nets wired, LCSC fields; R17/R18 47k/100k for Basic) + R3 manual divide-and-conquer routing, 2-layer, SMD >= 2 mm from pot/jack pads (closest U6 2.20 mm), 1 mm edge keep-out (copper-edge rule 1.0 mm; RV1/RV2 courtyards 0.82 mm, user-accepted) (KiCad DRC 0 / unconnected 0 / parity 0; the 3 U5-under-CUTOFF stacking items are user-approved DRC exclusions, still counted by the shared gate; no vias in SMD pads); JLCPCB export in `modules/low/jlcpcb/` (bottom Economic, all R/C Basic), not supplier-accepted, not built; BM MCO firmware in `modules/low/firmware/` (JP1 p/d builds), compiled, not bench-tested |
| `modules/acid/` | ACID, 8HP: Bread Modular MCO + ENV on one ATtiny1616 (3 envelope models + LEDs, REC button), BM SVF (two vactrols on B, RES 500k), all at 3.3 V; 8bit MIDI in; AUDIO and CV bypass inputs (10 Vpp / 0..5 V mapped to 0..3.3 V) normalled via a TS5A23157 to the MCO mix and the DAC envelope; no DRIVE: LP / HP / BP outs, each one TL072 stage with a 3-pad gain jumper (open x3.0 shipped, 2-3 x3.9, 1-2 x11.1; ~10 Vpp ceiling) + protected 0..5 V envelope CV out | S3 schematic (gain jumpers JP2-JP4, Rg 4.7k + 10k + 5.1k; ERC 0, every signal net wired; 0.5 W 1206 1k = ROHM ESR18) + R2 = R1 manual divide-and-conquer routing + gain-jumper clusters (LP/HP on the left edge strip, BP under RES/CURVE), 4-layer (vactrols under ATTACK/RELEASE, 22 stacking items user-approved DRC exclusions, still counted by the shared gate; KiCad DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, In1/In2 planes one piece; B silk UPDI + MIDI JP1 + gain-jumper labels); 8HP panel; JLCPCB export in `modules/acid/jlcpcb/` (S3/R2 carrier, bottom Economic, 98 parts), not supplier-accepted, not built; BM MCO + ENV merged firmware with the shared REC recorder in `modules/acid/firmware/` (JP1 p/d builds), compiled, not bench-tested |
| `modules/32bit/` | 32bit, 6HP. **S4 (2026-11-23): modules/usb-audio S5 carrier (CS4272, NE5532, AMS1117 +5VA, 2 in / 2 out, two firmware control pots + MODE, M3x10 standoffs) + a separate ESP32-S3 MCU board on J6/J7 with the panel USB-C**, for `master` in front of PA systems. S3 before it: **ESP32-S3R8 + W25Q128JVSIQ 16 MB flash + 40 MHz crystal** (S3, 2026-11-15: the contents of the ESP32-S3-WROOM-1U-N16R8 module, which is JLCPCB Standard PCBA only; same memory map, GPIOs and firmware; radio never used, LNA_IN open) + ES8388 codec, MIDI in (NPN, JP1), 2 x audio in (TL074, no normal), 2 x CV in with attenuators, TL072 ±5 V outs, MODE button + LED, USB-C data + BOOT/RESET, 4-layer (Bread Modular `32bit-5v` based) | **S4 carrier S4 / R2 + MCU board S1 / R2 schematics, both hand-routed (2026-11-23)**: ERC 0 / DRC 0 / unconnected 0 / parity 0, no exclusions, no vias in SMD pads (carrier 753 tracks / 124 vias, MCU board 239 / 41); **fab review 2026-11-23 (uncommitted)**: carrier R2 = seven +3V3 thermal vias + B / F +3V3 patches at U2 AMS1117-3.3 (0.71..0.79 W with the ESP32-S3 load, was on a bare tab pad), panel P2 = USB-C slot 9.5 -> 11.0 x 5.2 mm (the round slot ends cut 0.034 mm into the shell corners), MCU board R2 = the nine ESP32-S3 thermal vias drilled 0.3 mm instead of 0.2 mm (user: no extra PCB cost; no hole under 0.3 mm on either board), `main/` and `mcu/` re-exported with the same BOM / CPL, `docs/fit/` + `Code.md` + `README.md` brought to S4; S4 GPIO map in `docs/firmware-pins.md`; **S4 JLCPCB export in `modules/32bit/jlcpcb/` (2026-11-23**, two orders, no panel: `main/` carrier 88 parts / 33 rows bottom Economic + FR4 panel, `mcu/` 25 / 14 top Economic; shared `check` manifests equal; every code live-checked, no pre-order part, USB-C 414 / CS4272 1,147 free, recheck), not supplier-accepted; CS4272 driver and bench open (`docs/research.md` section 9). **ES1 variant (2026-11-23, uncommitted, `hardware/es/`, section 10; user: keep S4, add the ES8388 board with its own clock and supply, order both and compare)**: S3 / R3 + U10 LP5907MFX-3.3 codec supply from +5V (-> R5 10R -> +3V3_8388) + Y2 11.2896 MHz oscillator -> MCLK (ES8388 = I2S master, ESP32-S3 slave, GPIO21 open; firmware `BOARD=es1`, all three compile, not bench-tested); hand-routed in three batches, ERC 0 / DRC 0 / unconnected 0 / parity 0, no exclusions, 779 tracks / 136 vias, no hole under 0.3 mm (U1 / U4 thermal vias drilled 0.3); JLCPCB export `jlcpcb/es/` (108 parts / 45 rows bottom Economic + S3 panel as `panels/es/`, printed panel regenerated; every code live, no pre-order part; U10 C80670 / Y2 C2831381 Extended), not built. Below is S3, now history: **S3 schematic** (ERC 0, netlist asserted, 116 parts / 118 nets; R1 layout pin changes logged in `docs/firmware-pins.md`, none in S3) + **R3 manual divide-and-conquer routing** (2026-11-15: MCU area re-placed and re-routed around the QFN-56, the rest is R2 copper; flash above the chip, crystal and VDDA caps on its right, I2S / USB wrapped around the flash on F to via staircases at the left pin column; DRC 0 / unconnected 0 / parity 0, no exclusions, 760 tracks / 130 vias, none in SMD pads, In1/In2 planes one piece; 2 mm hand-solder clearance, closest new parts FB1 / C6 2.005 mm, the user-accepted R5/C27/R55/C46 at 1.33-1.75 mm unchanged; B silk MIDI JP1 labels); 6HP panel; **S3 / R3 JLCPCB export in `modules/32bit/jlcpcb/` (2026-11-15, carrier re-exported, bottom Economic, 103 parts / 43 rows, shared `check` manifest equal; ESP32-S3R8 C2913194 listed stock 21,376 on 2026-11-15, recheck)**, not supplier-accepted, not built; whole-BOM live audit and JLCPCB preview open; polysynth firmware in `modules/32bit/firmware/` (CV1 release, CV2 filter; JP1 p/d builds) + BM fxrack firmware (delay + new modulated-FDN hall reverb, PSRAM), compiled, not bench-tested; **`master` firmware (2026-11-22; 0.3.0 2026-11-23)**: end-of-chain processor instead of a DAW (IN L kick: filter + limiter; IN R mix: filter + 3-band dynamics keyed by the kick; parallel compressor; glue compressor (0.2.0: circuit model of the analog VCA bus compressor, feedback detector + RC timing), filter, look-ahead limiter; mono out; 0.3.0: one filter device per strip (low + high cut, resonance, 12 / 24 / 48 dB/oct), effect order per strip, limiter auto release), every setting from a web page over USB (Web Serial, `firmware/master/web/`: channel-strip mixer, the selected effect in a fixed-height panel below with graphs + knobs, side panel for connection / settings, slots dragged to reorder; `run.sh` serves it on port 3000) and saved in flash, about 4.8 ms in -> out as shipped (estimate), 240 MHz, compiled + host-tested, the chain run on the emulated ESP32-S3 (QEMU) equal to the host render; 0.2.0 heard on the built board, 0.3.0 not flashed, not heard; **0.4.0 (2026-11-24, uncommitted)**: the panel works the chain: CV1 / CV2 mapped to any settings with ranges, MODE switching on / off settings (0.4.1: one way picked on the page, click, hold or push), LED modes, channel off / solo, set up on the page's Panel tab (drag; touch: hold), settings only (QEMU +1 instruction per sample), host + page checks pass, not flashed |
| `modules/4mix/` | 4MIX, 18HP: Bread Modular 4mix (no overdrive) on ±12 V: audio only, every input AC-coupled; 4 channels (IN jack on top, SEND A, SEND B, VOL), 2 post-fader sends + 2 returns, top line SEND A, SEND B, RTN A, RTN B, MAIN, OUT (sends top left, return levels below their jacks); big-knob space on each channel VOL; 2x3 EXP IN (top left) / EXP OUT (top right) headers and power (bottom right) on the back; 2 x 10 mm M3 F-F hex standoffs MS1/MS2 hold the carrier bottom to the panel, 9 x TL072 | S2 hierarchical schematic (channel sheet x 4, ERC 0) + P6 placement (user hand placement, tidied; M3x10 standoffs MS1/MS2, mechanical footprints) + R1 manual divide-and-conquer routing, 4-layer (In1 GND, In2 +12V), all SMD on B (DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, SMD >= 2 mm from pot/jack pads, closest 2.27 mm); 18HP panel fit study; printable channel VOL knobs in `mechanical/knobs/` (repo root) (four widths in folders: `wide/` Ø16, `slim/` Ø13, `slimmer/` Ø11.5, `slimmest/` Ø10 mm, 13.5 mm tall for the measured shaft: 18 mm above the pot body, about 13 mm above the panel; paint-pen pointer pocket, eight fits each + a fit gauge per width (its eight knobs in one print, rim notches) + knob puller tongs in `puller/`; grip 4 = solid knob with 20 bore teeth keyed into the shaft's 40-tooth knurl, after the user's loose spring-finger prints and a friction-only press fit that slipped at the end stop; the first grip 4 gauge's `fit8` locked into the knurl, so the fits became tooth depths `t1`..`t8` on that tile's Ø6.2 bore, `t4` = old `fit8`, matched by the user's slim `t4` knob print; the tile gauge did not match the printed knobs; slimmer `t1` printed "not too tight", so the fits are now `h1`..`h8` with `h5` = old `t1`, the whole hole 0.05 mm smaller per step down to Ø6.0 at `h1`, `h6`..`h8` = old `t2`..`t4`; **`h4` (bore Ø6.15) is the user's pick on the P2S, 2026-11-12: print `h4` directly**; two-colour 3MF of every knob in `<width>/two-color/` (1.8 mm pointer inlay, five layers, 1.0 mm from the top-face edge); not every width and none of the new gauges test-printed); JLCPCB export in `modules/4mix/jlcpcb/` (bottom Economic, all R/C Basic except the 1 W 2512 output resistors), not supplier-accepted, not built |
| `modules/hats/` | HATS, 6HP: Bread Modular NOISE (blue noise, NOISE TONE / BLUE TONE) -> HIHAT (CUTOFF, DECAY, vactrol VCA), **S4: one STM32G071C8T6** (DAC1 noise, DAC2 velocity; CUTOFF knob on the ADC drives a second vactrol U11 by PWM, so CUTOFF and NOISE TONE are recordable; REC button + LED); **S5: LM4040 3.0 V +3V0 reference rail** for VREF+ and the two ADC knobs (the modules/12bit S3 fix), the rest on +3V3; NOISE IN normalled via a TS5A23157 to the internal blue noise; TL072 AUDIO out x3 + HAT CV out 0..5 V with ENV LED, ±12 V | **S5 schematic + R7 routing (2026-11-19, user: the modules/12bit reference fix on this board too)**: U12 LM4040B30FTA (C460604, Extended) + R52 2.2k from +12V_F make +3V0 for VREF+ (FB1) and RV1.3 / RV3.3; nothing else moved or changed value; DAC full scale 3.0 V (noise -0.8 dB, top velocity ~3 % lower, not compensated); R7 = R6 copper + six hand batches (`research/route-s5/`): U12 left of U4, R52 below RV3 / RV4, +3V0 on F / B with 4 vias, old FB1 via re-used, second under-chip +3V3 via for U2; ERC 0 / DRC 36 = 36 excluded, 0 active / unconnected 0 / parity 0, 672 tracks / 137 vias, no vias in SMD pads, In1 / In2 one piece, SMD >= 2 mm from pot/jack pads (closest 2.05 mm); **S5 / R7 JLCPCB export in `modules/hats/jlcpcb/` (2026-11-19**, shared `check` manifest equal; bottom Economic, 97 parts / 35 rows; panel unchanged; STM32G071C8T6 listed stock 965 on 2026-11-19, shared with modules/12bit, recheck), not supplier-accepted, **not built, not measured** (HATS is less exposed than 12bit: DAC behind the vactrol VCA, AC-coupled output); firmware: TIM6-triggered knob ADC scan with DMA (as 12bit), compiled + host-tested. Before that: **S4 schematic** (2026-11-08, user direction: one STM32 + PWM cutoff vactrol; ERC 0, netlist asserted) + **R4 manual divide-and-conquer routing** (2026-11-09; **R5** = same copper + fab-review B silk: J11 SWD pin legend, 1.0 mm vactrol notes, `-12V` at J10, stale U7 exclusion re-keyed; **R6** = fab fixes: C6/C25/C26 at their U2 pins by a local re-route, U1 tab +12V_F copper F/B + 8 vias, U11 stacking approved), 4-layer (In1 GND, In2 +3V3), all SMD on B, REC button SW1 + REC LED D6 on F at the bottom (as modules/16bit); U2 LQFP-48 between the pot rows, every pin dogboned to a via clear of the pads; vactrols U7 under CUTOFF and U11 under NOISE TONE / BLUE TONE on B (U7 and U11: 18 user-approved stacking exclusions each, all matched, 0 active DRC findings); R6: ERC 0 / unconnected 0 / parity 0, 639 tracks / 131 vias, RV1-RV4 courtyards 0.795 mm (user-accepted); P5 6HP panel (13 NPTH, REC hole + LED); the S4/R6 JLCPCB export (95 parts / 33 rows) is in git history, replaced by the S5 / R7 set (R43/R46 still Extended); STM32 firmware in `modules/hats/firmware/` (BM NOISE + HIHAT, PWM cutoff vactrol, shared REC recorder on CUTOFF + NOISE TONE; JP1 p/d builds, `opt/stm32g0-tools`), compiled + host-tested, not bench-tested |
| `modules/drive/` | DRIVE, 6HP: mono OTA overdrive + wavefolder on ±12 V: inverting input buffer -> linearized LM13700 VCA (DRIVE, exponential PNP converter, 6.5 dB / V) -> five LM13700 tanh cells summed as currents (soft clipper + two fold pairs at ±198 / ±405 mV, FOLD = their bias, level constant) -> TONE low-pass (wet only) -> dry / wet MIX (same polarity) -> 1k 2512; DRIVE CV and FOLD CV add to the knobs, no MIX CV; 4 x TL072, 3 x LM13700, 3 x SS8550 | **S1 schematic** (2026-11-15; ERC 0, netlist asserted, 92 parts / 50 nets; ngspice deck generated from the schematic, `tools/sim_drive.py`: wet gain -0.6 .. +31 dB, fold 0 .. 1.06, two folds per side, models not measurements) + **P2 placement** (user 2026-11-15: power header J10 upright at the right edge on B between the MIX pot and the OUT jack, the freed bottom strip used to move the controls down: CV jacks Y21, knob rows Y45 / Y80 (35 mm pitch), IN / OUT Y110.3; columns X8 / X22, pot courtyards 1.02 mm from the edge) + **R2 2-layer routing** (user, 2026-11-15: R1 manual divide-and-conquer 4-layer F/B signal copper kept, In1 GND / In2 +12V planes removed, +12V re-routed as a 0.4-0.5 mm F trunk with 7 new vias, F and B GND pours + 16 stitching vias; -12V as tracks), all SMD on B (ERC 0 / DRC 0, no exclusions / unconnected 0 / parity 0, 455 tracks / 102 vias, no vias in SMD pads, SMD >= 2 mm from pot/jack pads (closest 2.025 mm), copper >= 1.1 mm and courtyards >= 1.02 mm from the edge, B pour one piece + two pad/via-tied pieces, F pour one piece + 12 via-stitched pieces between the supply trunks); fab review 2026-11-15 (`-12V` silk at J10, B silk S1/R2; LM13700 100n caps 3.6-6.1 mm from their pins, judged fine for the first prototype; less quiet than 4 layers, bench item: hum / noise at high DRIVE); 6HP panel (DRC 0, 10 NPTH); R2 JLCPCB export in `modules/drive/jlcpcb/` (2 layers, bottom Economic, 83 parts / 29 rows; all Basic except LM13700MX/NOPB C174050 (Extended, 10,529 in stock) and the 2512 1k C54315 (Extended), 240k Preferred Extended), not supplier-accepted, not built |
| `modules/ladder/` | LADDER, 6HP: pure-analog Moog transistor ladder filter (DMMT3904W pairs, 47n NP0), no MIDI / MCU / VCA (S4, user 2026-11-15): expo cutoff (CUTOFF + CV x DEPTH, bipolar CV, 5 V = +8.3 octaves), **LM13700 OTA resonance** (S5, replaces the vactrol; RES + RES CV set the OTA bias current, self-oscillation at ~60 % of the knob) with the 16bit (1 + k) makeup; two dim CV LEDs after DEPTH, anti-parallel in the CV buffer loop (D11 positive, D12 negative; 21 uA / V = 0.06 mA at 5 V as shipped, three solder jumpers JP1..JP3 step it up to 0.53 mA); IN, CV, RES CV in, one OUT; 5 x TL072 + LM13700, ±12 V, HT7550 +5 V reference | **S5 schematic** (2026-11-15; ERC 0, netlist asserted, 108 parts / 62 nets; LM13700MX/NOPB C174050 Extended, MMBT5401 C8326, 22k C31850 live-checked 2026-11-15) + **P4 placement** (2026-11-15): 6HP, THT placed (IN + RES CV; CV + DEPTH with the two CV LEDs below, `-` / `+` on the panel; CUTOFF and RES alone on the centre line, 26 mm apart; OUT; J10 upright at the right edge; no vactrol) + **R1 manual divide-and-conquer routing** (2026-11-15), 4-layer (In1 GND, In2 +12V_F), all 95 SMD + 3 solder jumpers on B, F for the long north-south runs, three B bridges in the pot / jack zones (ERC 0 / DRC 0 / unconnected 0 / parity 0, no exclusions, 521 tracks / 81 vias, no vias in SMD pads, no tracks on In1 / In2, In2 one piece, In1 one piece + 7 spoke-tied fragments; SMD >= 2 mm from pot / jack pads (closest 2.015 mm), courtyards >= 1.0 mm from the edge (RV2 1.015 mm); B silk LED jumper legend); 6HP panel (11 NPTH) + printable panel; ngspice (models, not measured): passband within 2 % with resonance, self-oscillation 6..6.7 Vpp; **fab review 2026-11-15** (B silk texts 1.0 mm, JLC04161H-7628 stackup recorded, no copper change; DMMT3904W pin-out re-read from DS30311; live stock DMMT3904W C155305 684, 6 per board); **S5 / R1 JLCPCB export in `modules/ladder/jlcpcb/` (2026-11-15**, shared `check` manifest equal; bottom Economic, 95 parts / 30 rows; panel 11 NPTH), not supplier-accepted, not built; no firmware needed. The 10HP S3/R2 design (ATtiny1616 envelope, REC, vactrol VCA; routed, exported, never built) is in git history (`b32225b`) |
| `modules/usb-audio/` | USB-AUDIO, 6HP: 2 in / 2 out USB audio interface, CH32V307RCT6 (USB 2.0 HS, UAC2) on a separate MCU board soldered on 2.54 mm strips over the carrier F side (vertical HRO USB-C 1.3 mm proud of the panel), **S4: CS4272 codec** (CS4270 discontinued; I2S master, 24.576 MHz, 192 kHz, differential in / out, I2C 0x10), DC-coupled ±5 V in/out (CV too) with a 0..1 volume pot per jack (IN: jack, pot; OUT: pot, jack), **S5: 3 x NE5532** + OPA1679, resistor-divider ADC reference (no VCOM buffer), BOOT/RESET + SWD on the carrier back, **two M3x10 standoffs MS1/MS2 above the MCU board**, power header upright at the left edge, both boards 4-layer | **Panel P3 (2026-11-23, uncommitted): USB-C slot 9.5 -> 11.0 x 5.2 mm** (the 9.5 mm slot's round ends cut 0.034 mm into the shell's upper corners, found on modules/32bit), FR4 + printed panel + panel Gerbers regenerated, carrier / MCU sets untouched. **Carrier S5 / P2 / R5 (2026-11-22)**: S4 / R4 below with U4 / U5 / U7 = NE5532DR C7426 (Basic; user: cheaper than the OPA1656) and the VCOM buffer U8 + C33 replaced by R49 2.7k from +5VA over R40 / R41 (VCOM_BUF 2.41 V = 0.482 x VA, common mode only) + C38 10u / C39 100n, placed where U8 was on its vias (`research/route-s4/r16.py`): 101 refs / 65 nets, 818 tracks / 114 vias, ERC 0 / DRC 0 / unconnected 0 / parity 0; **`main/` JLCPCB set re-exported: 88 parts / 32 rows, 7 Extended types**, every code live-checked, none pre-order; NE5532 bias current gives 2.5 mV typical / 10 mV maximum of pot-dependent offset per follower (datasheet), not built. **S4 / P2 / R4 (2026-11-22, user: after two built S3 boards crackled, I2S locking at random bit offsets; root cause not scoped)**: CS4272 + U5 difference amplifiers + differential ADC drive, 10k pull-downs on I2S_SCLK / I2S_LRCK and 47k on I2S_DAC, MCLK scope pad; J1 at the left edge between IN 2 and the OUT 1 pot, rows 8 mm lower, MS1/MS2 at Y13.75 (the printed USB brace is retired, `panels/front-cad/r3-brace/`); hand-routed (`research/route-s4/`): SCLK / LRCK 2 mm on B from the codec pin into their series resistors without a via, four F trunks between J6 and the ADC bundle, 826 tracks / 116 vias; ERC 0 / DRC 0 (warnings included) / unconnected 0 / parity 0, no exclusions, no vias in SMD pads, no inner-layer tracks, planes one piece (In1 + two pad-tied 1 mm2 slivers), courtyards >= 1.01 mm from the edge, SMD >= 2.01 mm from pot/jack pads; B silk RESET / BOOT / SWD and J7 probe legends; 6HP panel with the two standoff holes and the longer USB slot (DRC 0) + printed panel regenerated; **`main/` JLCPCB set 2026-11-22** (bottom Economic, shared `check` manifests equal; the S4 set had 87 parts / 31 rows with four OPA1656IDR, replaced by the S5 set; CS4272-CZZR C2151111 free stock 1,156, recheck), `mcu/` re-exported from the unchanged MCU board S1/R2 (top Economic, 23 / 12); not supplier-accepted, **S5 not built**; **no CS4272 firmware yet**: UAC2 firmware 1.1.0 in `modules/usb-audio/firmware/` (48 / 96 / 192 kHz, DFU over the panel USB-C, loopback-tested on Linux on the first board) only runs on the CS4270 boards, an edge-synced I2S start test build for them is uncommitted |
| `modules/usb-audio-max/` | USB-AUDIO-MAX, **12HP** (10HP until S3): 6 in / 8 out USB audio interface, CH32V307RCT6 (USB 2.0 HS, UAC2) on a separate MCU board (modules/usb-audio MCU board + SPI1 for the second TDM line pair), TI PCM3168A codec (TDM clock master, SCKI 24.576 MHz, up to 96 kHz), DC-coupled +/-5.9 V in/out, no level controls; **S3: modules/multi-mix clock link** (CLK OUT J6 left / CLK IN J7 right, 2x5 headers on B, same circuit, pinout and ribbon; 48 kHz only; link detect by the codec I2C address: 0x47 master, 0x45 slave, 0x44 = S2 carrier); inputs 100k -> OPA1679 inverting driver on +5VA (single-ended ADC), outputs OPA1679 difference amplifiers on +/-12 V -> 1k; +5VA linear and precise (2 x 33R + discrete LM358/BCP56 regulator referenced to a REF5050, MMBT3904 current limit: +5VA is the DC reference of every channel), +3V3 from a TPS562208 FCCM buck (~580 kHz at every load, never in the audio band) behind a ferrite + 2.2R input filter, molded inductor; only the digital rail switches | **Carrier S3 / R2, 12HP, clock link (2026-11-20, user: clock from a Multi Mix or another unit, same ribbon / sockets, 12HP allowed, sockets centred)**: 5.05 mm added on each side (KiCad origin moved, jack grid / USB-C / MCU board centred), 21 link parts placed and hand-routed (`research/clk/`): four lines cross in the B band between the codec and the IN jack row, U4 group and two ADC bridges re-routed, U13 block east of the VCOM lines, In2 +3V3_C island grown to it; ERC 0 / DRC 0 (saved fills too) / unconnected 0 / parity 0, no exclusions, 253 vias, none in SMD pads, courtyards >= 1.0 mm from the edge, SMD >= 2.03 mm from jack pads; 12HP FR4 panel (DRC 0) + printed panel (**2026-11-23, uncommitted: USB-C slot 9.5 -> 11.0 x 5.2 mm**, panel Gerbers + printed panel regenerated); **`main/` JLCPCB set re-exported 2026-11-20** (200 parts / 42 rows, 16 Extended types, C211-C216 now C107043 as C33353 is pre-order only; shared `check` manifests equal), `mcu/` unchanged, not supplier-accepted, **S3 not built**; **firmware 1.1.0** probes the codec address and runs as the clock master, a linked (slave) unit is detected but not started yet (TDM start on a running clock open, also for modules/multi-mix), compiled, not flashed. Before that (S2 / R1, 10HP, first board built): **S2 schematics, final** (carrier + MCU board, ERC 0, netlists asserted, every LCSC code live-checked 2026-11-05: 49 codes, all Economic-eligible, PCM3168APAPR C529289 Extended, 1517) + footprint library; ngspice (models, not measured): +5VA loop PM >= 78 deg / GM >= 26 dB, buck ripple ~50 uV on +12V_F / 0.1 uV on +5VA, USB load bursts -142 dBFS at the jacks (as with the S1.2 LDO); **S1 placement, 10HP** (user: 10HP if 8HP is too tight; fit study 8HP 64 % vs 10HP 45 % SMD density, `docs/research.md` section 5): USB-C on top, IN 1-6 two rows of three, OUT 1-8 three rows (ninth spot empty, J1 power behind it), carrier 49.5 x 110 mm + modules/usb-audio-size MCU board centred, 10HP FR4 panel; **R1 manual divide-and-conquer routing, both boards** (2026-11-07): MCU board and carrier DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, no In1 tracks, courtyards >= 1 mm from the edge, SMD >= 2 mm from jack pads; carrier In2 = +12V_F plane + +5VA island (codec/inputs, finger to the regulator) + two +3V3_C islands; batches in `research/route/` (`build.sh`, `PLAN-codec.md`); 2 x M3x10 hex standoffs MS1/MS2 at the top corners beside the USB-C (2026-11-08, USB-C push support, coaxial panel holes; buck and SWD/oscillator corners re-placed around them); **fab-review fixes** (2026-11-08): MCU fills saved + JLC04161H-7628 stackup recorded, Q1 BCP56 `/V5_IN` heatsink pours F/B (165 mm2) + 8 thermal vias, U3 PCM3168A land (mask 7.4 x 7.4 over the 7.25 x 7.00 PowerPAD, 25 paste dots between the thermal holes, holes solid); ERC 0 / DRC 0 (saved fills too) / unconnected 0 / parity 0 both; JLCPCB export in `modules/usb-audio-max/jlcpcb/` (`main/` carrier bottom Economic + panel, `mcu/` top Economic; 10 Extended R/C placements, user decision open), not supplier-accepted, not built; 48 kHz all I2S, 96 kHz adds SPI1 (runtime switch); first board built: bring-up firmware in `modules/usb-audio-max/firmware/` (DFU flashing over the panel USB-C, no buttons; console; PCM3168A I2C + 48 kHz TDM link checked 2026-11-19; OUT 1-6 -> IN 1-6 and OUT 7/8 -> IN 1/2 loop tests 2026-11-19: mapping right, no crosstalk, loop gain 0.95-0.96 uncalibrated, linear to ±5.5 V); **firmware 1.0.1 "Bread Modular 6x8"** (UAC2 8 out / 6 in, 24-bit 48 kHz, per-channel `cal in` / `cal out` calibration, `looptest` PASS after `cal out`; 1.0.1 takes the iso OUT packets the controller flags NAK behind console output, which were the clicks of the 1.0.0 hour run, and debounces VBUS); host-side USB disconnects without an MCU reset seen, cause open; `cal in` / `cal ref`, macOS / Windows and the 96 kHz SPI1 path untested |
| `modules/multi-mix/` | MULTI-MIX, 20HP digital 4-channel mixer: PCM3168A codec (48 kHz) + CH32V307 MCU board (USB-C, UAC2 + USB-MIDI) soldered on two 1x12 strips; 4 IN + 2 RTN, SEND A/B, MAIN, USB 1/2 outs; TS MIDI IN jack (10k + BAT54S, not inverted -> PA10 USART1_RX -> USB-MIDI); 15 pots on a 74HC4067 as MIDI CCs; CLK OUT/IN 2x5 clock-only daisy chain (CLK IN an unshrouded header); modules/usb-audio-max power | Carrier S5 / MCU S4 schematics (ERC 0) + R3 manual routing, both 4-layer (DRC 0 / unconnected 0 / parity 0, shared `check` equal); fab review 2026-11-11 fixed (R2); **MIDI IN jack J11 above USB 1 added 2026-11-11** (S5/R3, panel P4 hole H35; CLK IN J7 moved up 4.42 mm as a plain 2x5 header; `docs/research.md` section 11); JLCPCB export in `modules/multi-mix/jlcpcb/` (`main/` carrier bottom Economic 203 parts / 46 rows + panel (**2026-11-23, uncommitted: USB-C slot 9.5 -> 11.0 x 5.2 mm**, panel Gerbers + printed panel regenerated), `mcu/` top Economic 25 / 13; 10 Extended R/C placements, user decision open), not supplier-accepted, not built; J101 courtyard 0.53 mm to the MS3 notch and MS3 courtyard 0.98 mm to the edge open (user decision); no firmware |
| `modules/motion/` | MOTION, 6HP: 4-knob motion recorder with 4 CV outs. ATtiny1616 reads four 50k knobs, records them straight into an MB85RC256V I2C FRAM (~81 s per knob, always saved) and plays them through an MCP4728 quad 12-bit I2C DAC -> TL074, -5..+5 V per output; REC button (hold + move a knob = record) and DEL button (SW2, RANGE in S1; hold + move a knob = delete that take, hold 5 s = erase all), four motion LEDs + REC + DEL LEDs on PWM pins; HT7550-1 +5V, +5VA (DAC reference) behind 10R | **S1 schematic** (2026-11-15, ERC 0, netlist asserted; MCP4728 pin 5 renamed `RDY_~{BSY}` for the shared parity) + **P1 placement** (knob zigzag with a motion LED beside each knob, buttons above the 2 x 2 jack block, power header on B between the lower jacks) + **R1 manual routing, 2-layer** (2026-11-15, user go-ahead; RANGE button confirmed): all 52 SMD on B, long runs on F, GND pours F / B in via-tied pieces (37 stitching vias, one GND net; solid on SMD pads, thermals on THT); shared `check` no findings (ERC 0 / DRC 0 / unconnected 0 / parity 0, no exclusions), 402 tracks / 89 vias, no vias in SMD pads except one ground via in the U2 exposed pad, SMD >= 2 mm from pot/jack pads (closest 2.025 mm), courtyards >= 1.015 mm from the edge; 6HP panel DRC 0; JLCPCB export in `modules/motion/jlcpcb/` (bottom Economic, 52 parts / 15 rows, 5 Extended types), not supplier-accepted, not built; requirements audit not written; firmware in `firmware/` (REC hold + move records into the FRAM, loops with a glide back, 5 s still hold erases; **2026-11-26, uncommitted**: range removed (always -5..+5 V, user: the RANGE click was confusing), the RANGE button is DEL (DEL + knob deletes that take, DEL held 5 s still erases all, DEL LED counts down), REC only records, re-record replaces the take (knob only, join fade not recorded), the knob attenuates its take 1 s after the take closes (relative from where it starts, no jump; gain saved at rest), motion LED blinks below 0 V; FRAM layout v2, old range byte ignored), compiled + host-tested (84 checks); earlier builds flashed and tried by the user, this one not flashed; **top clip C1 + panel P2 (2026-11-24, uncommitted)**: no jack holds the carrier top and the pots have no nut, so a printed C channel on the carrier top edge (inside the 1 mm keep-out strip, 0.2 mm off the rail) is screwed to the panel with one M3x6 / M3x8 through a new Ø3.2 hole at X25 / Y12 (`panels/top-clip/`); carrier unchanged, FR4 + printed panel and panel Gerbers regenerated, sliced, not printed |
| `modules/busboard/` | Busboard: passive 8 x 16-pin shrouded IDC Eurorack bus (Doepfer pinout, CV/GATE bussed only) for the case floor, 205 x 32 mm 2-layer, 4 x M3 holes beside the end headers (196 x 21 mm, bolted from under the bottom plate's solid frame; plate ribs under the board) | S1 schematic + R3 board (straight bus tracks, GND pours; ERC 0 / DRC 0 / unconnected 0 / parity 0); JLCPCB Gerbers in `modules/busboard/jlcpcb/` (no assembly), not supplier-accepted, not built |
| `modules/blank/` | Blank panels 2HP / 4HP / 6HP / 8HP: outline + Ø3.2 rail holes only (2HP X2.42, others X12.58, 8HP also X32.9), no labels | FR4 panels (native DRC 0) + FreeCAD 2.0 mm prints; JLCPCB exports in `modules/blank/jlcpcb/`, not supplier-accepted |

Canonical sources are `modules/usb-power/hardware/usb-power.kicad_{pro,sch,pcb}`
plus `modules/usb-power/panels/front-pcb/usb-power-panel.kicad_{pro,pcb}`. Read `modules/usb-power/Code.md` before
any hardware work. The MIDI module's sources are
`modules/midi/hardware/v1/midi.kicad_{pro,sch,pcb}` (V1) and
`modules/midi/hardware/v2/midi.kicad_{pro,sch,pcb}` (V2), plus the shared
`modules/midi/panels/front-pcb/midi-panel.kicad_{pro,pcb}`; their shared-tool
profiles are `modules/midi/tools/v1|v2/kicad-project.json`. Read
`modules/midi/Code.md` first. The VCA-MIX module's sources are
`modules/vca-mix/hardware/vca-mix.kicad_{pro,sch,pcb}` plus
`modules/vca-mix/panels/front-pcb/vca-mix-panel.kicad_{pro,pcb}`; read
`modules/vca-mix/Code.md` first.

## Tools

For KiCad read `opt/kicad-tools/skills/kicad-workflow/SKILL.md`; for
sourcing/assembly also read `opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`
and the jlcpcb docs. Common-tool-first; inspect actual CLI help. Do not strip
dependencies or weaken rules.

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config modules/usb-power/tools/kicad-project.json
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power/tools/kicad-project.json --reports <new-dir>
```

## Workspace rules

Work only in this isolated workspace. No advisor/delegation, commits, merges,
pushes, main writes, GUI interaction, orders or vendor uploads. Supervisor
reviews and merges verified work; the assistant does not merge. No access to
other workspaces for recovery; Bread Modular is read-only. No external project
changes. No arbitrary raw-rail/current guarantee changes.

## Required workflow

Read canonical `opt/kicad-tools` skills and relevant CLI help; common tools
first. Use `modules/usb-power/tools/kicad-project.json` for the carrier and
hierarchical root. New candidates and raw reports go in the module's ignored
`research/`; accepted fabrication outputs in the module's `jlcpcb/`. Reuse
shared native checks/export; do not add a new exporter or router.

Keep generators/BOM/native fields coherent; native schematic presentation owns
placement/wires and accepted native PCB owns routing. Explicit candidate edits
only.

Full native ERC/DRC includes warnings/exclusions/opens/parity; independent exact
ref/pin/net/NC/field parity and mechanics are required. No ignored rules,
exclusions, fake power flags or weakened assertions. Update accepted routing
baselines only for independently inspected intentional changes. Manufacturer
data plus prototype screening is not guaranteed performance. Source/sourcing
and Basic/Economy gates remain distinct; no stock claims without evidence.

## Routing: manual, divide and conquer (no autorouters)

User direction, 2026-10-21. It replaces the 2026-10-20 autorouter direction: the
16bit R1 TraceMaker copper needed 123 in-pad vias (POFV) and was stripped and
re-routed this way instead.

- **No autorouters.** Do not run Freerouting, TraceMaker (`route`, `tracemaker run`,
  `tracemaker session`) or any other full-board/bulk router, and do not hand them the
  board as a fallback. A small path-finding helper for **one connection at a time** is
  fine, as long as you check and accept each path yourself.
- **No vias in SMD pads.** Fan out with a short dogbone track to a via clear of the pad
  copper and its mask opening. The only exception is a footprint's own exposed-pad
  thermal vias (e.g. RP2350 EP). Check every via against every SMD pad after each batch;
  never propose POFV as the fix.
- **Work straight on the board** (`modules/<name>/hardware/*.kicad_pcb`), not on a
  research copy, and **update the board after every batch** so the user can reload it
  in KiCad and follow along. Back up the board to `/tmp/` before each round; DRC reports
  go in the module's ignored `research/`.

### Divide and conquer

1. **Clear the board first if asked:** strip tracks/vias, keep footprints and zone
   outlines, then park the SMD parts in a grid off the board edge so they can be
   placed group by group.
2. **Set up the layers before routing.** 4-layer: F.Cu signal / In1 solid GND /
   In2 main power plane (+3V3) / B.Cu signal, plus a Power net class. No tracks on In1.
   In2 only for short power hops when F/B are blocked, and check that the plane stays
   one piece afterwards.
3. **Place and route one functional group at a time**, near its connector: e.g. power
   entry + regulators by the power header, output amps between the output jacks, USB
   at its port, MIDI input at its jack, CV buffers by their pots, then the MCU with its
   memories, DAC and decoupling. Keep the space reserved for the MCU empty until it's
   that group's turn.
4. **Route a few traces per batch** (one net or a handful of local links), write them
   to the board, then run full native DRC + parity. Fix every new finding before the
   next batch. Report what the batch added and what is still open.
5. **Leave cross-board links until both ends are placed** (MCU pins, rails that cross
   the middle), and say so in the report instead of forcing a long detour.
6. **Stop and ask** when a choice needs the user: moving a fixed jack/pot or a part the
   user placed, ripping up earlier groups, or a schematic change such as a pin swap.
   Respect parts and copper the user routed by hand; only move them with a reason
   you report.
7. **Commit only when the user asks**, at the end of a group.

### 1 mm board-edge keep-out (must)

User direction, 2026-10-22. Applies to every carrier board, routed or not.

- **Nothing within 1 mm of the board edge**: no tracks, vias, pads, zone copper, and no
  component courtyards (SMD and THT) closer than 1.0 mm to `Edge.Cuts`.
- Set the board's **copper-to-edge clearance to 1.0 mm**
  (`min_copper_edge_clearance` in the `.kicad_pro`) so native DRC enforces it for copper
  and the pours pull back; refill zones and save after changing it.
- DRC does not check courtyards against the edge: measure them (courtyard bounding box
  incl. line width) after every placement batch and report any under 1 mm.
- If a fixed part (panel-located pot/jack) can't meet it, stop and ask; don't move it
  silently.

### 2 mm hand-solder clearance around pots and jacks

User direction, 2026-10-22 (was 3 mm on LOW R2, relaxed). Applies to every carrier board.

- **Every SMD pad >= 2.0 mm from every hand-soldered pot and jack pad**, mounting lugs
  included, measured copper edge to copper edge, so the iron has room.
- DRC does not check it: measure it after every placement batch and report the closest
  pads. The 1 mm edge keep-out wins where both can't hold; report the conflict.

### Power header upright at the side edge

User direction, 2026-11-15 (modules/drive P2: "move the power socket to the side and use that
space to move down the pots"). Applies to every new carrier layout; don't re-lay out a routed
module for it unless the user asks.

- **Put the 2x5 power header upright at a side edge on B** (the two pin columns vertical), in
  the gap between the lowest pot row and the bottom jack row, not lying along the bottom edge.
  Pins 1/2 (-12 V) at the bottom, silk `-12V` beside them.
- **Use the bottom strip this frees to move the pots and the bottom jacks down**, for roomier
  knob rows (modules/drive: knob rows Y45 / Y80 at 35 mm pitch, IN / OUT jacks at Y110.3 on a
  110 mm carrier; the modules/hats grid with the header along the bottom had Y41 / Y75 / Y102).
- Check the IDC socket envelope (10-pin and 16-pin cable, overhanging upward from pin 1)
  against the THT leads and B-side parts under it, and record it in `docs/geometry.json`.
  The 1 mm edge keep-out still holds for the header courtyard.
- References: modules/drive P2 (J10 at X23.8 / X26.34, Y91.2..101.36), modules/16bit P6,
  modules/8bit, modules/12bit.

### Routing rules learned on modules/16bit

- **Short critical paths first**: regulator input caps within 2-3 mm, decoupling cap
  at its pin with its own GND via, memories right beside the MCU so QSPI runs with no
  vias, USB D+/D- side by side on one layer with vias only at the port and the MCU.
- **Use F.Cu when only through-hole parts sit there**: it's the free layer for long
  runs and rail feeds. Hop with a via pair placed clear of the pads.
- **Heat**: a linear regulator dropping ~0.5 W gets a tab patch on F and B tied by
  thermal vias beside (not in) the tab.
- **Check after every edit, cleanup passes included**: native DRC + parity, vias in SMD
  pads, tracks on In1, plane pieces counted from the filled polygons (report small
  spoke-tied fragments separately), and inspect a render of the area.
- **Clean as you go**: no zero-length/duplicate/dangling segments, track ends centred
  on vias and pads, coordinates on a round 0.05/0.1 mm grid.
- **Shared `pcb plan` caps a plan at 256 ops** if you freeze copper as plan ops: split
  into stages of whole nets; intermediate stages need `--allow-draft-opens`.

## Parts: single-supply op-amp = MCP6002 (C7377)

User direction, 2026-11-14.

- For a single-supply (+3.3 V / +5 V) rail-to-rail op-amp use the dual **MCP6002T-I/SN
  (LCSC C7377, SOIC-8)**, even when only one channel is needed: it is a JLCPCB **Preferred
  Extended** part, so it carries no Extended feeder fee (~$3 per part type). Park the
  unused half as a grounded follower (+in to GND, -in to the output).
- Don't use the single MCP6001 (MCP6001T-E/OT, C29429, SOT-23-5): it is plain Extended.
  `modules/8bit` U4 was swapped on 2026-11-14; `modules/12bit` U2 still uses it (swap only
  when the user asks, it is a schematic + routing change).

## Parts: no JLCPCB pre-order parts

User direction, 2026-11-19 (modules/multi-mix C33353: listed stock 659, but pre-order only, ~$8 for six
2.2n caps).

- **Never put a pre-order part in a BOM.** JLCPCB's listed stock can include parts it has to buy in
  first; those come with a minimum purchase (C33353: 301 pieces) and a delay.
- The catalog endpoint `opt/kicad-tools/jlcpcb/catalog.py` uses shows it per part: **`canPresaleNumber`**
  (free stock) must be >= the quantity for the order (placements x boards + attrition) and
  **`minPurchaseNum`** must be 1. Listed `stockCount` alone is not enough (C33353: 659 listed,
  `canPresaleNumber` -1681, `minPurchaseNum` 301).
- Check every code this way at each JLCPCB export and again right before ordering, and record it. If a
  part is pre-order, swap it for an in-stock equivalent (same value, dielectric / rating, footprint),
  Basic first, then Preferred Extended, then Extended; don't put up with an Extended part whose minimum
  purchase makes it cost dollars.

## Holes: nothing under 0.3 mm

User direction, 2026-11-23 (modules/32bit MCU board: "update it to 0.3 or so, I don't want to cost extra").

- **No drilled hole under 0.3 mm on any board**: routed vias 0.3 / 0.6 mm (0.3 / 0.5 mm where it is tight), and
  the thermal vias of stock footprints too. KiCad's `..._ThermalVias` lands come with 0.2 mm holes: drill them
  0.3 mm in the module's `tools/import_footprints.py`, keep the pads and positions, and record the edit in
  `PROVENANCE.json` (modules/32bit `THERMAL_VIA_DRILL` is the example).
- **Set `min_through_hole_diameter` to 0.3 in the `.kicad_pro`** so native DRC enforces it. Don't lower it for a
  footprint.
- At every JLCPCB export read the smallest tool from the PTH drill file and state it in the upload map of the
  module's `jlcpcb/README.md`.
- Why 0.3: it is JLCPCB's standard hole at every layer count. Their capability page (read 2026-11-23) charges
  for 0.15 mm and smaller always, and for 0.2 / 0.25 mm holes when the via diameter is under 0.45 mm; a 0.3 mm
  hole needs no check against that table.
- Boards exported before this rule still have smaller holes, all on 4-layer boards with >= 0.5 mm pads (inside
  JLCPCB's free range by that page): modules/16bit (nine 0.25 / 0.6 mm RP2350 thermal vias), the
  modules/usb-audio-max and modules/multi-mix carriers (36 x 0.2 / 0.5 mm PCM3168A thermal holes each;
  multi-mix also ten 0.2 / 0.5 mm routed vias at the codec). Don't re-route them just for this; bring them to
  0.3 mm when that board is next changed.

## Fabrication outputs

`modules/usb-power/jlcpcb/` is the sole shipping-set location; `production/` is
retired, not an active archive. Read `modules/usb-power/jlcpcb/README.md`
(shared-tool export/CAM commands and promotion gates) before release work. Any
native electrical/PCB repair and new export belongs to a separate authorized
task; never hand-edit generated files.

### Printed front panel with every JLCPCB export (must)

User direction, 2026-11-16. Every module with a front panel ships a FreeCAD printable
panel next to the FR4 one.

- **When you do a module's JLCPCB export, also create or regenerate
  `modules/<name>/panels/front-cad/`** in the same task: `build_front_panel.py` plus its
  `.FCStd`, `.step` and `.stl` (plain, no labels, 2.0 mm unless the module's contract
  says otherwise, e.g. `modules/usb-power*` 1.6 mm for the brackets).
- The script reads the outline and NPTH holes (slots included) from
  `panels/front-pcb/<name>-panel.kicad_pcb` and asserts them against the module's
  `docs/geometry.json`; it checks one valid solid, the drilled-blank volume and a closed
  manifold STL. Copy the closest existing one (`modules/hats`, `modules/multi-mix` for a
  USB slot + standoffs) and run it headless:
  `~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py`.
- Regenerate it whenever the FR4 panel holes change, list it in `panels/README.md`, and
  never hand-edit its exports. Not test-printed unless the user says so.
