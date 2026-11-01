"""S8.3-only pinned TPS259470 symbol and TI RPW0010A land pattern.

Source: https://www.ti.com/lit/ds/symlink/tps25947.pdf, SLVSFC9C,
Table 5-1 and TI drawing 4225183/A (2019), inspected 2026-11-01.
RPW is NOT a generic 10-pad DFN: 5/6 are long internal IN/OUT strips;
1/4/7/10 have L-shaped pads. There is no separate grounded exposed pad.
The corner land is represented by two overlapping, identically numbered SMD
pads, matching the manufacturer's L shape. Separate paste apertures follow the
0.100 mm stencil example (93% corners / 82% power strips). No vias are added.

S8.4 (review M7): copper-pad solder-mask expansion 0.025 mm, inside TI's NSMD "0.05 MAX ALL AROUND".
Every copper gap of this land pattern is 0.20 mm, so every mask web, including the IN(5)/OUT(6) web whose
bridge would bypass the eFuse, is 0.20 - 2 x 0.025 = 0.15 mm (was 0.10 mm). MASK_WEB_MIN is the contract.
"""
from sexp import parse

FP_S83 = {'RPW10': 'TI_RPW0010A_VQFN-HR-10_2x2mm'}
MASK_MARGIN = 0.025      # mm per side on every copper pad (S8.4)
MASK_WEB_MIN = 0.15      # mm, minimum solder-mask web between differently numbered copper pads


def symbol():
    rows = [('1', 'EN/UVLO', 'input', -12.7, 2.54, 0),
            ('2', 'OVLO', 'input', -12.7, -2.54, 0),
            ('3', 'AUXOFF', 'open_collector', 12.7, 2.54, 180),
            ('4', '~{FLT}', 'open_collector', 12.7, -2.54, 180),
            ('5', 'IN', 'power_in', -12.7, 7.62, 0),
            ('6', 'OUT', 'power_out', 12.7, 7.62, 180),
            ('7', 'DVDT', 'passive', 2.54, -12.7, 90),
            ('8', 'GND', 'power_in', 0, -12.7, 90),
            ('9', 'ILM', 'passive', 12.7, -7.62, 180),
            ('10', 'ITIMER', 'passive', -12.7, -7.62, 0)]
    pins = ''.join(f'(pin {typ} line (at {x} {y} {angle}) (length 2.54) '
                   f'(name "{name}" (effects (font (size 1.016 1.016)))) '
                   f'(number "{n}" (effects (font (size 1.016 1.016)))))'
                   for n, name, typ, x, y, angle in rows)
    return parse(f'''(symbol "TPS259470_RPW" (pin_names (offset 0.254)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 13.97 0) (effects (font (size 1.27 1.27))))
      (property "Value" "TPS259470_RPW" (at 0 11.43 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "USBPOWER45:{FP_S83['RPW10']}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps25947.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "TPS259470_RPW_0_1" (rectangle (start -10.16 10.16) (end 10.16 -10.16)
        (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "TPS259470_RPW_1_1" {pins}))''')


def footprint():
    text = f'''(footprint "{FP_S83['RPW10']}" (version 20241229) (generator pcbnew) (layer "F.Cu")
      (descr "TI RPW0010A, TPS259470, drawing 4225183/A; IN=5 OUT=6, no GND exposed pad")
      (tags "TPS25947 RPW0010A") (attr smd)
      (property "Reference" "REF**" (at 0 -2.0) (layer "F.SilkS") (effects (font (size 0.7 0.7) (thickness 0.12))))
      (property "Value" "TPS259470ARPWR" (at 0 2.0) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.1))))
      (fp_rect (start -1 -1) (end 1 1) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
      (fp_line (start -1 -0.5) (end -0.5 -1) (stroke (width 0.1) (type default)) (layer "F.Fab"))
      (fp_rect (start -1.5 -1.5) (end 1.5 1.5) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
      (fp_circle (center -1.4 -1.4) (end -1.3 -1.4) (stroke (width 0.12) (type default)) (fill solid) (layer "F.SilkS"))
    '''
    def pad(n, x, y, w, h, layers='"F.Cu" "F.Mask"'):
        margin = MASK_MARGIN if 'F.Cu' in layers else 0.05      # paste-only apertures unchanged from S8.3
        return (f'(pad "{n}" smd roundrect (at {x} {y}) (size {w} {h}) '
                f'(layers {layers}) (solder_mask_margin {margin}) (roundrect_rratio {min(.05/w, .05/h):.8f}))\n')
    for n, x, y in [(1, -.9, -.7), (4, -.9, .7), (7, .9, .7), (10, .9, -.7)]:
        text += pad(n, x, y, .6, .3)
        text += pad(n, -.725 if x < 0 else .725, -.875 if y < 0 else .875, .25, .65)
    for n, x, y in [(2, -.9, -.225), (3, -.9, .225), (8, .9, .225), (9, .9, -.225)]:
        text += pad(n, x, y, .6, .25)
    for n, x in [(5, -.25), (6, .25)]:
        text += pad(n, x, 0, .3, 2.4)
    # Paste-only pads have no number/net. The 5/6 apertures are split with a 0.2mm web.
    for x, y in [(-.9,-.6875),(-.9,.6875),(.9,.6875),(.9,-.6875)]:
        text += pad('',x,y,.6,.28,'"F.Paste"')
        text += pad('',-.7125 if x<0 else .7125,-.875 if y<0 else .875,.225,.65,'"F.Paste"')
    for x in (-.9,.9):
        for y in (-.225,.225): text += pad('',x,y,.6,.25,'"F.Paste"')
    for x in (-.25,.25):
        for y in (-.63,.63): text += pad('',x,y,.275,1.06,'"F.Paste"')
    return text + ')\n'
