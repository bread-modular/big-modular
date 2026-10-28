# line-in research notes (S3/P3/R2)

## 1. Brief (user, 2026-10-28)

"We need a stereo line in module. Check the Bread Modular one for the idea. But
improve for Eurorack. Do the THT components and paneling for now. And schematics
with connected nets." Routing follows later.

## 2. Bread Modular baseline (`bread-modular/modules/line_in`, v1.0.1, native netlist)

Single 3.3 V supply, V_MID from a 1k/1k divider (R4/R5, C3-C5).
Per channel: TRS jack (PJ366ST) -> RV 50k (pin 3) -> wiper -> 100n -> 1M to V_MID
-> MCP6002 follower -> 22k -> inverting stage, 100k feedback (gain -4.55) -> 1k ->
OUT_L / OUT_R on a 5-pin header. Mono: OUT_L and OUT_R (after the 1k) -> 100k each
-> U3A inverting summer, 51k feedback -> 1k -> OUT_MONO. U3B unused, (+) floating.

## 3. Eurorack circuit (S2)

| Stage | BM | S2 | Why |
|---|---|---|---|
| Supply | 3.3 V + V_MID divider | ±12 V via B5819W per rail, 10u bulk, 100n per op-amp pin; divider removed | Eurorack bus, ground reference (modules/imix power block) |
| Op-amps | MCP6002 x3 | TL072CDT x3 (same unit use: U1 L, U2 R, U3 mono) | ±12 V rails, JLCPCB Basic |
| Coupling | 100n, 1M to V_MID | 1u (0805 X7R), 1M to GND | 0.16 Hz corner; ~10x less signal across the X7R at 20 Hz |
| Gain | 100k/22k = -4.55 | 100k/5.1k = -19.6, 20p across the feedback (~80 kHz) | S2 (user 2026-10-28): ~x20 as Doepfer A-119; -10 dBV (0.9 Vpp) reaches ~10 Vpp near half LEVEL, weak sources still get to Eurorack level; hotter sources clip near ±10 V, so turn LEVEL down |
| Outputs | 5-pin header, 1k 0402 | 3 x PJ301M-12 jacks, 1k 1206 0.5 W (ROHM ESR18, as acid) | Patchable; reused output part, continuous opposite-rail immunity not qualified (user accepts as-is) |
| Mono | sum after the 1k | sum from the gain-stage outputs (before the 1k), 100k/100k/51k, 20p | Loading OUT L/R no longer changes MONO |
| Spare U3B | (+) floating | grounded follower | No oscillating idle section |

Polarity: OUT L/R are inverted relative to the input (BM topology); MONO is in phase
(+10 x (L + R) at the follower outputs). A mono TS plug in IN grounds the ring, so
OUT R stays silent and MONO carries L only.

## 4. Mechanics (P3, user review 2026-10-28)

P2 (pots on top, all four jacks at the bottom) is superseded: the user moved IN back to
the top. P3: 4HP, one column at X10.0 (rail holes X12.58, board 19 x 110 mm, jacks at
rot 270). Top to bottom: IN Y19.0 (audio-out IN L Y19.5), LEVEL L Y36.5, LEVEL R Y58.0
(21.5 mm pitch), OUT L Y78.5, OUT R Y92.5, MONO Y106.5 (14 mm pitch). The height
between IN and OUT L is split evenly over the three gaps. J10 horizontal along the
bottom edge (rot 270 on B, as hats): pins X4.92..15.08, rows Y113.4 / Y115.94, pin 1
(-12 V) left; IDC10 envelope X1.11..18.89, Y110.27..119.07, on the board. 10-pin cable
only (a 16-pin socket would overhang the 4HP width).

Measured from the P3 board (panel frame):
- Courtyard to Edge.Cuts: J10 1.50 mm, jacks 1.67 mm, pots 3.06 mm.
- Courtyard gaps: IN-RV1 7.10 mm, RV1-RV2 7.71 mm, RV2-OUT L 7.05 mm, output jacks
  4.44 mm, MONO-J10 0.32 mm.
- B-side bands for SMD with the 2 mm hand-solder clearance: above IN ~5.2 mm, IN-RV1
  10.3 mm, RV1-RV2 7.5 mm, RV2-OUT L 6.55 mm, between output jacks 6.9 mm each;
  MONO-J10 none (plus the strips beside J10 and under the IDC10 socket for parts
  <= 2 mm tall).

## 5. Review answers (user, 2026-10-28)

- **Gain**: comparable modules: Intellijel Audio I/O, up to 20 dB (x10) of input gain
  with 0 dB = 10 Vpp; Doepfer A-119 unbalanced line input, gain 0..20. S2 follows the
  A-119 (user, 2026-10-28): LEVEL sets 0..x19.6.
- **Polarity**: no re-inversion stage; L in -> OUT L, R in -> OUT R (phase inverted,
  as BM).
- **Mono plugs**: a TS plug's sleeve covers the TRS ring contact, so R is grounded:
  OUT R silent, MONO = L only. Use a TRS cable or a mono-to-dual adapter.
- **Knobs**: repo practice is Thonk Tall Trimmer Toppers 7.8 mm (imix), audio-out
  19 mm pitch ~15 mm, 8bit 15 mm pitch ~11 mm, 4mix big knob 18 mm reserve (18HP).
  P3 labels sit 8.9 mm above the shafts, so knobs up to ~15 mm fit; 4HP width is the
  real limit.

## 6. R1 routing (2026-10-28)

Manual, group by group (root `AGENTS.md`): power entry, U3 sum, U2, U1, then the long F
links. Each batch was written to the board and checked (DRC/parity, vias in SMD pads,
2 mm hand-solder clearance, courtyard edge). Final: DRC 0 / unconnected 0 / parity 0.
Details in `Code.md` (R1).

## 7. Open points

- Live strict audit done at export (2026-10-28, `jlcpcb/README.md`): every code
  matches; R7/R8/R12 ESR18 0.5 W are Extended (subsequently accepted unchanged by the user).


## 8. S3/R2 input protection and review disposition

The user accepted the assembly/physical-fit concerns and asked to retain the
1k/0.5W output resistors if they match the other modules. ACID, HATS, 8bit and MCC
shipping BOMs use exactly ESR18EZPF1001/C2074262, so they are unchanged.

Added R13/R14 10k after C9/C10, and opposite BAV199 two-junction strings D3-D6 to
GND. The low-leakage audio clamp is deliberately not the MIDI module's digital
NPN input stage. Existing LEVEL/gain/MONO behavior, all prior placements and
panel hardware remain unchanged. Full native checks pass and the carrier export
is regenerated. New BAV199 diodes are Extended; the new resistors are Basic.

See `input-protection.md` for pin mapping, bounds, preserved geometry, evidence,
and the explicit powered-off limitation. This change is not a hardware/ESD or
supplier-acceptance certification.
