"""S9.0-only pinned TPS552892-Q1 symbol and TI RYQ0021B land pattern (+12V buck-boost, U2).

Source: https://www.ti.com/lit/ds/symlink/tps552892-q1.pdf, SLVSGT7 (April 2023), Table 5-1 (pin functions) and the
RYQ0021B package outline / example board layout / example stencil (TI drawing 4228792/A, 07/2022), inspected
2026-11-02. RYQ is a HotRod VQFN: no exposed pad; VIN (7), SW1 (8), PGND (9), SW2 (10) and VOUT (11) are 0.25 mm wide,
3.4 mm long lands across the package, PGND has a 0.33 mm wide centre section over 2.35 mm. Four side lands per short
edge (pins 1-4, 14-17, 0.6 x 0.25, 0.5 mm pitch, centres X -/+2.40), corner lands 5/13/18/21 (X -/+2.04) and the lands
6/12/19/20 (X -/+1.54, 0.25 x 0.60). KiCad frame: pin 1 top-left, pins 5-13 along the bottom edge (+Y), 18-21 along the
top edge (-Y).

One deliberate deviation from the TI example: the four corner lands are 0.625 mm long instead of 0.65 (inner end at
|Y| 1.075 instead of 1.05) so the copper gap to the adjacent side lands is 0.200 mm, the board's netclass clearance; the
TI example leaves 0.175 mm. The land still covers 0.425 mm of a maximum-length (0.55 mm) corner terminal. No clearance
rule is relaxed. Copper-pad solder-mask expansion 0.025 mm (TI NSMD: 0.07 max): every mask web >= 0.15 mm. Paste
follows the TI 0.125 mm stencil example: 1:1 on the small lands, each long land split into three 1.0 mm apertures
(Y -1.2 / 0 / +1.2), the PGND centre aperture 0.33 mm wide. No vias are added.
"""
from sexp import parse

FP_S90 = {'RYQ21': 'TI_RYQ0021B_VQFN-HR-21_3x5mm'}
MASK_MARGIN = 0.025      # mm per side on every copper pad
COPPER_GAP_MIN = 0.20    # mm, minimum copper gap between differently numbered lands (= board netclass clearance)
# Independent TI SLVSGT7 Table 5-1 pin table (number -> name), not derived from the symbol below.
TPS552892_TI = {'1': 'EN/UVLO', '2': 'MODE', '3': 'PG', '4': 'CC', '5': 'DITH/SYNC', '6': 'FSW', '7': 'VIN', '8': 'SW1',
                '9': 'PGND', '10': 'SW2', '11': 'VOUT', '12': 'ISP', '13': 'ISN', '14': 'FB', '15': 'COMP', '16': 'CDC',
                '17': 'AGND', '18': 'VCC', '19': 'BOOT2', '20': 'BOOT1', '21': 'EXTVCC'}
# Copper lands transcribed from the TI example board layout (centre X, centre Y, width, height), KiCad frame (Y down).
RYQ_LANDS = {
    **{str(n): (-2.40, y, 0.60, 0.25) for n, y in zip((1, 2, 3, 4), (-0.75, -0.25, 0.25, 0.75))},
    **{str(n): (2.40, y, 0.60, 0.25) for n, y in zip((17, 16, 15, 14), (-0.75, -0.25, 0.25, 0.75))},
    '21': (-2.04, -1.3875, 0.25, 0.625), '18': (2.04, -1.3875, 0.25, 0.625),        # corner lands (see deviation)
    '5': (-2.04, 1.3875, 0.25, 0.625), '13': (2.04, 1.3875, 0.25, 0.625),
    '20': (-1.54, -1.40, 0.25, 0.60), '19': (1.54, -1.40, 0.25, 0.60),
    '6': (-1.54, 1.40, 0.25, 0.60), '12': (1.54, 1.40, 0.25, 0.60),
    **{str(n): (x, 0.0, 0.25, 3.40) for n, x in zip((7, 8, 9, 10, 11), (-1.04, -0.54, 0.0, 0.54, 1.04))},
}
PGND_CENTRE = (0.0, 0.0, 0.33, 2.35)          # second, overlapping land of pin 9 (TI: 0.33 wide over 2.35 mm)
LONG_PINS = ('7', '8', '9', '10', '11')

# Symbol pins: (number, name, KiCad electrical type, x, y, angle). Left inputs, right outputs/feedback, switch nodes on
# top, grounds at the bottom; MODE / EXTVCC / VCC sit next to each other so they can be wired as one local node.
PINS = [('7', 'VIN', 'power_in', -15.24, 12.7, 0), ('1', 'EN/UVLO', 'input', -15.24, 7.62, 0),
        ('2', 'MODE', 'input', -15.24, 2.54, 0), ('21', 'EXTVCC', 'input', -15.24, 0, 0),
        ('18', 'VCC', 'power_out', -15.24, -2.54, 0), ('5', 'DITH/SYNC', 'input', -15.24, -7.62, 0),
        ('6', 'FSW', 'passive', -15.24, -10.16, 0),
        ('11', 'VOUT', 'power_out', 15.24, 12.7, 180), ('12', 'ISP', 'input', 15.24, 10.16, 180),
        ('13', 'ISN', 'input', 15.24, 7.62, 180), ('3', 'PG', 'open_collector', 15.24, 2.54, 180),
        ('4', 'CC', 'open_collector', 15.24, 0, 180), ('16', 'CDC', 'passive', 15.24, -2.54, 180),
        ('14', 'FB', 'input', 15.24, -7.62, 180), ('15', 'COMP', 'passive', 15.24, -10.16, 180),
        ('8', 'SW1', 'passive', -7.62, 17.78, 270), ('20', 'BOOT1', 'passive', -5.08, 17.78, 270),
        ('19', 'BOOT2', 'passive', 5.08, 17.78, 270), ('10', 'SW2', 'passive', 7.62, 17.78, 270),
        ('9', 'PGND', 'power_in', -2.54, -15.24, 90), ('17', 'AGND', 'power_in', 2.54, -15.24, 90)]


def symbol():
    pins = ''.join(f'(pin {typ} line (at {x} {y} {angle}) (length 2.54) '
                   f'(name "{name}" (effects (font (size 1.016 1.016)))) '
                   f'(number "{n}" (effects (font (size 1.016 1.016)))))'
                   for n, name, typ, x, y, angle in PINS)
    return parse(f'''(symbol "TPS552892_RYQ" (pin_names (offset 0.254)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 19.05 0) (effects (font (size 1.27 1.27))))
      (property "Value" "TPS552892_RYQ" (at 0 -19.05 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "USBPOWER45:{FP_S90['RYQ21']}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps552892-q1.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Description" "36 V 8 A four-switch buck-boost converter, external feedback, VQFN-HR-21 (RYQ)" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "TPS552892_RYQ_0_1" (rectangle (start -12.7 15.24) (end 12.7 -12.7)
        (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "TPS552892_RYQ_1_1" {pins}))''')


def footprint():
    text = f'''(footprint "{FP_S90['RYQ21']}" (version 20241229) (generator pcbnew) (layer "F.Cu")
      (descr "TI RYQ0021B VQFN-HR-21 3x5 mm, TPS552892-Q1, drawing 4228792/A; corner lands 0.625 mm (0.2 mm gap)")
      (tags "TPS552892 RYQ0021B HotRod") (attr smd)
      (property "Reference" "REF**" (at 0 -2.6) (layer "F.SilkS") (effects (font (size 0.7 0.7) (thickness 0.12))))
      (property "Value" "TPS552892-Q1" (at 0 2.6) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.1))))
      (fp_rect (start -2.5 -1.5) (end 2.5 1.5) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
      (fp_line (start -2.5 -1.0) (end -2.0 -1.5) (stroke (width 0.1) (type default)) (layer "F.Fab"))
      (fp_rect (start -2.95 -1.95) (end 2.95 1.95) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
      (fp_circle (center -3.15 -1.0) (end -3.05 -1.0) (stroke (width 0.12) (type default)) (fill solid) (layer "F.SilkS"))
    '''

    def pad(n, x, y, w, h, layers='"F.Cu" "F.Mask"'):
        margin = MASK_MARGIN if 'F.Cu' in layers else 0
        return (f'(pad "{n}" smd roundrect (at {x:g} {y:g}) (size {w:g} {h:g}) '
                f'(layers {layers}) (solder_mask_margin {margin}) (roundrect_rratio {min(.05 / w, .05 / h):.8f}))\n')
    for n, (x, y, w, h) in RYQ_LANDS.items():
        text += pad(n, x, y, w, h)
    text += pad('9', *PGND_CENTRE)
    # Paste-only apertures (no number): 1:1 on the small lands, three 1.0 mm segments on each long land.
    for n, (x, y, w, h) in RYQ_LANDS.items():
        if n in LONG_PINS:
            for yy in (-1.2, 0.0, 1.2):
                text += pad('', x, yy, 0.33 if (n == '9' and yy == 0.0) else w, 1.0, '"F.Paste"')
        else:
            text += pad('', x, y, w, h, '"F.Paste"')
    return text + ')\n'


# S9.1: Vishay WSLP1206, doc 30122, 0.006..0.050 ohm row.
# Pads a=1.65, b=1.93, inner gap l=1.80 mm; Kelvin routes must leave inner terminal edges.
FP_S90['WSLP1206'] = 'R_WSLP1206_18m_Kelvin'

def sense_footprint():
    return """(footprint "R_WSLP1206_18m_Kelvin" (version 20241229) (generator pcbnew) (layer "F.Cu")
      (descr "Vishay WSLP1206 doc 30122: pads 1.65x1.93 gap 1.80; Kelvin sense from terminal inner edges") (attr smd)
      (property "Reference" "REF**" (at 0 -1.65) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.1))))
      (property "Value" "0.018" (at 0 1.65) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.1))))
      (fp_rect (start -1.73 -0.93) (end 1.73 0.93) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
      (fp_rect (start -2.8 -1.22) (end 2.8 1.22) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
      (pad "1" smd roundrect (at -1.725 0) (size 1.65 1.93) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.1))
      (pad "2" smd roundrect (at 1.725 0) (size 1.65 1.93) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.1)))
"""
