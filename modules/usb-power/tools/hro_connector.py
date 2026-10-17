"""HRO TYPE-C-31-M-12 identity and deliberately reviewed Bread land mapping.

Body dimensions are from the exact HRO drawing, not the retired GCT model.
Land coordinates are the user-selected Bread local footprint, NOT a claim that
its 1.45 mm land length is dimensioned in the drawing. See docs/usb-hro-review.md.
"""
from copy import deepcopy
from sexp import nodes, one

MPN = 'TYPE-C-31-M-12'
FOOTPRINT = 'HRO-TYPE-C-31-M-12'
SYMBOL = 'HRO_TYPE_C_31_M_12'
LCSC = 'C165948'
DATASHEET = 'https://datasheet.lcsc.com/datasheet/pdf/9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948'
# Each wide land accepts two adjacent contacts. Do not create fictitious extra lands.
CONTACT_TO_LAND = {'B12':'A1', 'B9':'A4', 'B4':'A9', 'B1':'A12'}
PINS = {'A1':'GND', 'A4':'USB_VBUS', 'A5':'CC1', 'A6':None,
        'A7':None, 'A8':None, 'A9':'USB_VBUS', 'A12':'GND',
        'B5':'CC2', 'B6':None, 'B7':None, 'B8':None, 'S1':'GND'}
NOTE = ('HRO C165948; Bread local land. A1 includes B12; A4 includes B9; '
        'A9 includes B4; A12 includes B1; S1 shell=GND. USB data/SBU NC. '
        'No verified 3D model; see docs/usb-hro-review.md.')
# Local origin is the mating face projected onto the seating plane. Independent
# side-view anchors: front tab 2.60 mm and rear tab 6.77 mm from that face;
# local lands are 2.60 and 6.78, respectively (0.01 mm rounding difference).
BODY_WIDTH = 8.94
BODY_DEPTH = 7.35
BODY_HEIGHT = 3.26
MOUTH_YZ = (33.5, .8)
NATIVE_ORIGIN = (69.25, 103.475)  # carrier transform: Y+35.75, 104.275-Z


def symbol_from_usb(original, qualified=False):
    """Keep existing drawing/pin positions; collapse only hidden shared contacts."""
    result = deepcopy(original)
    old = result[1].split(':')[-1]
    result[1] = ('BigModular:' if qualified else '') + SYMBOL
    for unit in nodes(result, 'symbol'):
        unit[1] = unit[1].replace(old, SYMBOL)
        unit[:] = [v for v in unit if not (isinstance(v,list) and v[0]=='pin'
                    and one(v,'number')[1] in CONTACT_TO_LAND)]
        for pin in nodes(unit,'pin'):
            if one(pin,'number')[1]=='SH':one(pin,'number')[1]='S1'
    values={'Value':MPN, 'Footprint':'BigModular:'+FOOTPRINT,
            'Datasheet':DATASHEET,
            'ki_fp_filters':FOOTPRINT,
            'Description':'HRO 16-contact USB-C; 12 PCB lands plus shell; paired GND/VBUS contacts share lands'}
    for prop in nodes(result,'property'):
        if prop[1] in values:prop[2]=values[prop[1]]
    return result
