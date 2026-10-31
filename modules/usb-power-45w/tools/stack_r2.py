"""R2 stacked two-board partition and interconnect manifest (user-approved single-IDC refit, 2026-10-31).

One source of truth for the board membership of every S7 schematic ref and for the soldered
2.54 mm board-to-board headers. Used by tools/board_schematics.py (native per-board schematics),
tools/build_stack.py (canonical boards) and tools/check_stack.py (independent checks).

BASE (hardware/base/): USB/CH224A, F1, D1, D10, U5 + local C2, always-on U9 latch/RESET, monitors,
panel LEDs, SW1, J1, the single output J2, and the whole negative-rail protection block
(U8/Q4/R48/R49 Kelvin, optos) that makes -12V from N12_RAW.
TOP (hardware/top/): all three converters (U2/U3/U4) with input caps, BOOT, L, FB, RT, the four
retained cans (C5 = converter-side VIN bulk, C34/C35/C36 raw-rail bulk), U6/U7 eFuses.
Partition rule: schematic pages 02/03/04 plus C5 are TOP, everything else BASE.
"""
from hierarchy6 import layout

TOP_PAGES = {2, 3, 4}
TOP_EXTRA = {'C5'}   # VIN bulk can at the converter-side VIN entry (8 mm: cannot sit under the top board)

# Power header XP (base XB1 / top XT1), 2x10 2.54 mm, pins n (odd) / n+1 (even) side by side.
XP_NETS = ['GND', 'GND', 'VIN', 'VIN', 'VIN', 'VIN', 'GND', 'GND',
           '+12V', '+12V', '+12V', '+12V', 'GND', 'GND', '+5V', '+5V', '+5V', '+5V',
           'N12_RAW', 'N12_RAW']
# Logic header XL (base XB2 / top XT2), 2x3.
XL_NETS = ['GND', 'MAIN_OK', 'RUN', 'P12_OK', 'P5_OK', 'V3V3']
HEADERS = {   # board -> [(ref, symbol, footprint key, nets)]
    'base': [('XB1', 'Conn_02x10_Odd_Even', 'HDR2x10', XP_NETS), ('XB2', 'Conn_02x03_Odd_Even', 'HDR2x03', XL_NETS)],
    'top': [('XT1', 'Conn_02x10_Odd_Even', 'HDR2x10', XP_NETS), ('XT2', 'Conn_02x03_Odd_Even', 'HDR2x03', XL_NETS)],
}
PAIRS = {'XB1': 'XT1', 'XB2': 'XT2'}   # same pin number = same soldered pin

# Screen currents (A) used for the per-pin budget table; from docs/s6-rail-protection.md screened
# maxima (main 4.698 incl. aux, rails 2.971, negative 1.143). Not a connector rating.
SCREEN_A = {'VIN': 4.748, '+12V': 2.971, '+5V': 2.971, 'N12_RAW': 1.143, 'GND': 6.0}
PIN_BUDGET_A = 1.5     # assumed design budget per 0.64 mm square soldered pin, not a vendor rating

HEADER_FIELDS = {
    'Conn_02x10_Odd_Even': dict(
        MPN='TSW-110-07-G-D', Manufacturer='Samtec',
        Note='Board-to-board power pins, 2x10 2.54 mm male header (style -07: tail 2.54 / plastic 2.54 / '
             'post 5.84), body on base F, post soldered through the top board (R2 stack). Per-pin current '
             'for soldered all-pins-loaded use is a prototype gate (docs/stack-r2.md); pins are not a '
             'mechanical support. Hand-soldered at stacking.'),
    'Conn_02x03_Odd_Even': dict(
        MPN='TSW-103-07-G-D', Manufacturer='Samtec',
        Note='Board-to-board logic pins (GND, MAIN_OK, RUN, P12_OK, P5_OK, V3V3), 2x3 2.54 mm male '
             'header, soldered on both boards (R2 stack). Hand-soldered at stacking.'),
}


def board_of(parts):
    """{ref: 'base' | 'top'} for every circuit-table ref (power flags included)."""
    by = {p['ref']: p for p in parts}
    plan = layout(by)
    return {r: ('top' if plan[r][0] in TOP_PAGES or r in TOP_EXTRA else 'base') for r in by}


def header_parts(board, part, fields_ok=True):
    """Circuit-table entries for the board's two headers (build_schematic part() style)."""
    out = []
    at = {'base': [(762.0, 60.96), (762.0, 152.4)], 'top': [(762.0, 60.96), (762.0, 152.4)]}[board]
    for (ref, sym, fp, nets), xy in zip(HEADERS[board], at):
        pins = {str(i + 1): n for i, n in enumerate(nets)}
        value = 'B2B 2x10 2.54mm' if sym.endswith('2x10_Odd_Even') else 'B2B 2x3 2.54mm'
        out.append(part(ref, sym, value, fp, xy, 0, pins, **HEADER_FIELDS[sym]))
    return out


# ---- geometry (study YZ frame: Y down the panel, Z depth from the panel front) -------------
# Native map for BOTH boards: native x = Y + 35.75, native y = 104.275 - Z; F faces point to +X.
STACK = {'panel_X': [0.0, 20.0], 'base_B': 2.5, 'base_F': 4.1, 'thickness': 1.6, 'gap': 5.0,
         'top_B': 9.1, 'top_F': 10.7}
J2_CLEAR = 1.5          # top outline to the J2 box (Wurth 61201621621 body max Y53.02..81.2, Z30.23..39.23)
TOP_REAR_Z = 28.7       # top board stops 1.53 mm in front of the J2 box (Z30.23) over Y51.5..82.7
                        # (study 28.0; +0.7 so the XT1 posts keep 2 mm from the SMD pads above them)
TOP_SPLIT_Y = 51.5
TOP_J3_Y = 82.7         # S7: J3 removed -> full depth again from Y82.7 (J2 box end 81.2 + 1.5)
NOTCH_Z = 20.5          # bracket foot, front nut/pliers and side-nut driver path (Z11..19)
TOP_OUTLINE = [(14.0, 2.0), (16.5, 2.0), (16.5, NOTCH_Z), (27.5, NOTCH_Z), (27.5, 2.0),
               (101.0, 2.0), (101.0, NOTCH_Z), (112.0, NOTCH_Z), (112.0, 2.0), (114.5, 2.0),
               (114.5, 42.0), (TOP_J3_Y, 42.0), (TOP_J3_Y, TOP_REAR_Z), (TOP_SPLIT_Y, TOP_REAR_Z),
               (TOP_SPLIT_Y, 42.0), (14.0, 42.0)]
# Supports: M3 through bolt, head under base B, plain 5.0 mm spacer, nut on top F (docs/stack-r2.md).
STANDOFFS = [(20.5, 36.7), (46.2, 36.7), (89.0, 36.7), (82.0, 7.3), (109.2, 36.7)]
# Study (20.5,37) (46.9,37) (96,23.3) (82,6.8) + one new: pulled inside the 1 mm edge rule for the top
# r4.25 tool courtyard; #3 left the middle of the U4 output caps for the freed J3 volume, #5 is new.
STANDOFF_CU_R = 3.6     # all-layer copper keep-out annulus r1.7..3.6 (spacer OD 6, washer/head 5.7)
STANDOFF_CY_R = {'base': 3.6, 'top': 4.25}   # top: nut + thin-wall 5.5 AF socket (OD <= 8.5) access
NUT_DRIVER = [(22.0, 15.0), (106.5, 15.0)]   # base F keep-out for the side nut + 8 mm driver
NUT_KEEP_R = 5.0

# Assumed max package envelopes above the own board face (mm), from package classes, NOT vendor
# maxima incl. solder (study HEIGHT table). Cans: SamYoung MVK 6.3x8 class, 8.0 assumed.
HEIGHT = {
    'CP_Elec_6.3x7.7': 8.0, 'L_SLO1040H6R8MTT': 4.2, 'TO-252-2': 2.4, 'D_SMC': 2.62,
    'D_SMB': 2.62, 'D_SMA': 2.62, 'SOIC-14_3.9x8.7mm_P1.27mm': 1.75,
    'SO-4_4.4x3.6mm_P2.54mm': 2.6, 'SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm': 1.75,
    'MSOP-10_3x3mm_P0.5mm': 1.1, 'TI_SO-PowerPAD-8_ThermalVias': 1.7, 'SOT-23': 1.45,
    'SOT-23-5': 1.45, 'SOT-23-6': 1.45, 'SOT-583-8': 0.6, 'SOT-89-3': 1.6,
    'TPS7A16_DGN0008C': 1.1, 'C_0603_1608Metric': 0.95, 'R_0603_1608Metric': 0.55,
    'LED_0603_1608Metric': 0.8, 'C_1206_3216Metric': 1.8, 'R_1206_3216Metric': 0.7,
    'Fuse_1206_3216Metric': 1.4, 'TestPoint_Pad_D1.0mm': 0.05,
    'HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3.4x6.5mm_Mask2.96x2.96mm_ThermalVias': 1.2,
    'HRO-TYPE-C-31-M-12': 3.36, 'SW_TL3340AF160QG_HandSolder': 3.3,
    'LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge': 3.9,
    'IDC-Header_2x08_P2.54mm_Vertical_Wurth_61201621621': 9.25,   # Wurth 8.85 +-0.15 -> 9.0 max, 9.25 kept
    'PinHeader_2x10_P2.54mm_Vertical': 2.5, 'PinHeader_2x03_P2.54mm_Vertical': 2.5,  # plastic on base F
    'Stack_M3_Spacer_Base': 0.0, 'Stack_M3_Spacer_Top': 0.0,
}
TOL = {'bracket_web_X': 0.2, 'base_thickness': 0.16, 'spacer_length': 0.1, 'top_thickness': 0.16,
       'solder_standoff': 0.1, 'top_board_bow': 0.3}     # assumed linear contributions, no vendor data
# Through bolt stack (assumed catalogue classes, not a selected MPN): ISO 7380 M3 button head under
# base B, plain 5.0 mm spacer (OD <= 6.0), DIN 934 M3 nut (m 2.4, AF 5.5) on top F.
BOLT = {'head_k': 1.65, 'head_d': 5.7, 'nut_m': 2.4, 'nut_AF': 5.5, 'nut_circ': 6.35,
        'length': 12.0, 'length_tol': 0.35, 'spacer_od': 6.0, 'min_exposure': 1.0}
# Stack pins: Samtec TSW-1xx-07-G-D (catalogue F-226 straight lead style -07: tail B 2.54, plastic 2.54,
# post C 5.84, overall A 10.92, .025" sq, recommended hole 1.02 +-0.03). Body on base F, tail through
# base (2.54 - 1.6 = 0.94 below base B), post through the top board: 4.1 + 2.54 + 5.84 = X12.48, i.e.
# 1.78 above top F (needs >= 0.5 for a fillet). Current: catalogue figures are mated, 2 positions
# powered; a soldered-both-ends, all-pins-loaded rating is not published -> prototype gate.
PIN = {'plastic': 2.54, 'tail': 2.54, 'post': 5.84, 'tail_below_base_B_max': 1.8, 'post_above_top_F_min': 0.5}
