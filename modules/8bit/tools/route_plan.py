#!/usr/bin/env python3
"""Emit the explicit routing plan (shared `pcb plan/apply` ops v1) for the 8bit carrier.

All geometry is written out here in panel-frame millimetres (KiCad = +100/+50); nothing
is autorouted. Placement: docs/geometry.json (S4). Layer plan (docs/research.md section 3.7):
  F.Cu  long trunks: +5V (LDO -> left edge X1.4 -> top -> middle trunk X12.5 through the
        pot pin-3 pads, ending at RV2), UPDI (X1.95), POT1/POT2 to their
        wipers, MIDI_IN to JP1, -12V_F/+12V_F from the power entry to U3, FILT to U3,
        BUTTON and LED_A (the F-side SW1 pads and the LED); GND pour.
  B.Cu  SMD-local wiring, the U1 fan-out, RX (left edge), DAC / LED_DRV / BUTTON (right
        edge X16.75 / X17.3 / X17.9), the knob 3 filter under RV3; GND pour.
Vias 0.6/0.3 mm. Tracks 0.2 mm at the QFN, 0.25 mm signal, 0.3 mm +5V, 0.4-0.5 mm power.
GND pours on both layers with thermal-relief pad connections.

  python3 -B tools/route_plan.py > research/route/plan.json   (then shared pcb plan/apply/promote)
"""
import json
import sys
import uuid

FAN, SIG, P5, PWR, HDR, VIA = 0.2, 0.25, 0.3, 0.4, 0.5, (0.6, 0.3)
B, F = 'B.Cu', 'F.Cu'
OX, OY = 100.0, 50.0
XP5, XUPDI = 1.4, 1.95       # F.Cu left lanes (+5V, UPDI)
XRX = 1.5                    # B.Cu left lane (RX), also the VREF lane below RV3
XDAC, XLED, XBTN = 16.75, 17.3, 17.9   # B.Cu right lanes from the U1 fan-out
XMID = 11.25                 # pot pin gap between pins 2 and 3 (F: POT2 at RV1, +5V at RV3)

ops = []


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/8bit/route/' + key))


def a(x, y):
    """Panel frame -> KiCad board coordinates."""
    return [round(OX + x, 4), round(OY + y, 4)]


# Supply nets carry power symbols in the schematic (global names); the rest are local labels.
RAILS = {'GND', '+5V', '+12V', '-12V', '+12V_F', '-12V_F'}


def netname(net):
    return net if net in RAILS else '/' + net


def via(name, net, x, y):
    ops.append({'op': 'add_via', 'uuid': uid('via/' + name), 'net': netname(net), 'at': a(x, y),
                'diameter_mm': VIA[0], 'drill_mm': VIA[1]})
    return name


def pad(ref, number, index):
    """Pad by UUID (tools/build_layout.py pad_uuid) for duplicated pad numbers."""
    return {'uuid': str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/8bit/pcb/pad/{ref}/{number}/{index}'))}


def end(e):
    if isinstance(e, dict):
        return e
    if isinstance(e, tuple):
        return {'pad': {'ref': e[0], 'number': e[1]}}
    return {'uuid': uid('via/' + e)}


def track(name, net, layer, s, pts, e, w=SIG):
    ops.append({'op': 'add_polyline', 'uuid': uid('trk/' + name), 'net': netname(net), 'layer': layer,
                'start': end(s), 'waypoints': [a(x, y) for x, y in pts], 'end': end(e), 'width_mm': w})


# ---- power entry: J4 -> D4/D5 (series Schottky) -> bulk, LDO --------------------------------
track('p12tie', '+12V', B, ('J4', '9'), [], ('J4', '10'), HDR)
track('p12d', '+12V', B, ('J4', '10'), [], ('D4', '2'), HDR)
track('p12fc5', '+12V_F', B, ('D4', '1'), [], ('C5', '1'), PWR)
track('p12fu2', '+12V_F', B, ('D4', '1'), [(15.95, 107.8), (14.3, 109.3)], ('U2', '2'), PWR)
track('p12fc4', '+12V_F', B, ('U2', '2'), [(14.3, 110.2), (17.4, 110.2)], ('C4', '1'), PWR)
track('m12tie', '-12V', B, ('J4', '1'), [], ('J4', '2'), HDR)
track('m12d', '-12V', B, ('J4', '2'), [(11.4, 117.85)], ('D5', '1'), HDR)
track('m12fc6', '-12V_F', B, ('D5', '2'), [], ('C6', '2'), PWR)
via('p5ldo', '+5V', 11.4, 112.2)
track('p5u2', '+5V', B, 'p5ldo', [], ('U2', '3'), PWR)
track('p5c3', '+5V', B, ('U2', '3'), [], ('C3', '1'), PWR)

# ---- +12V_F to U3 pin 8 (B.Cu up to a via above J4, F.Cu past J3 TN to C7) -----------------
via('p12a', '+12V_F', 10.4, 102.7)
via('p12b', '+12V_F', 4.3, 92.4)
track('p12fup', '+12V_F', B, ('D4', '1'), [(15.95, 104.3), (10.4, 104.3)], 'p12a', PWR)
track('p12f', '+12V_F', F, 'p12a', [(10.4, 99.8), (6.0, 94.2)], 'p12b', PWR)
track('p12c7', '+12V_F', B, 'p12b', [], ('C7', '1'), PWR)
track('p12u3', '+12V_F', B, ('C7', '1'), [], ('U3', '8'), P5)

# ---- -12V_F to U3 pin 4 (F.Cu up the right side, under J3 T) ------------------------------
via('m12a', '-12V_F', 16.75, 116.0)
via('m12b', '-12V_F', 12.6, 98.6)
track('m12v', '-12V_F', B, ('C6', '2'), [], 'm12a', PWR)
track('m12f', '-12V_F', F, 'm12a', [(17.8, 115.0), (17.8, 102.4), (13.0, 102.4)], 'm12b', PWR)
track('m12u3', '-12V_F', B, 'm12b', [], ('U3', '4'), P5)
track('m12c8', '-12V_F', B, 'm12b', [], ('C8', '2'), P5)

# ---- output stage (U3 is mirrored on B: pins 1-4 on the right, 8-5 on the left) ------------
track('ao1', 'AMP_OUT', B, ('U3', '1'), [], ('R9', '2'), P5)
track('ao2', 'AMP_OUT', B, ('R9', '2'), [], ('R12', '1'), P5)
track('aud', 'AUDIO_OUT', B, ('R12', '2'), [(18.3, 97.6), (16.6, 99.3)], ('J3', 'T'), P5)
track('fb1', 'OUT_FB', B, ('U3', '2'), [], ('R9', '1'))
# OUT_FB under the U3 body and out between pins 8 and 7 to Rg (R8)
track('fb2', 'OUT_FB', B, ('U3', '2'), [(10.0, 93.865), (9.2, 93.23), (6.2, 93.23)], ('R8', '1'), FAN)
track('voff1', 'VOFF', B, ('U3', '7'), [], ('U3', '6'))
track('voff2', 'VOFF', B, ('R8', '2'), [], ('U3', '6'))
via('filtu3', 'FILT', 10.6, 95.6)
track('filt1', 'FILT', B, 'filtu3', [], ('U3', '3'))
track('filt2', 'FILT', B, ('U3', '3'), [(14.0, 95.135)], ('C13', '1'))

# ---- offset divider (R10/R11/C14, left of SW1) -> VREF lane -> U3 pin 5 --------------------
via('p5r10', '+5V', 1.45, 83.4)
track('p5r10', '+5V', B, 'p5r10', [], ('R10', '1'), P5)
track('vref1', 'VREF_DIV', B, ('R10', '2'), [], ('R11', '1'))
track('vref2', 'VREF_DIV', B, ('C14', '1'), [(2.5, 86.7)], ('R10', '2'))
track('vref3', 'VREF_DIV', B, ('R11', '1'), [(XRX, 87.9), (XRX, 96.405)], ('U3', '5'))

# ---- knob 3 passive low-pass under RV3: R7 -> RV3 pin 3, wiper -> FILT (pin 1 open) ---------
track('dacr', 'DAC_R', B, ('R7', '2'), [(13.8, 82.3)], ('RV3', '3'))
via('filtrv', 'FILT', 7.4, 90.0)      # between the SW1 pad row and the F BUTTON track
track('filtrv', 'FILT', B, ('RV3', '2'), [(10.0, 83.0), (7.4, 85.6)], 'filtrv')
track('filtf', 'FILT', F, 'filtrv', [(10.6, 93.2)], 'filtu3')

# ---- top: MIDI input, CV input ---------------------------------------------------------------
track('mi1', 'MIDI_IN', B, ('J1', 'T'), [], ('R3', '1'))
track('mi2', 'MIDI_IN', B, ('J1', 'T'), [], ('R1', '1'))
via('mia', 'MIDI_IN', 12.2, 23.6)
via('mib', 'MIDI_IN', 3.2, 26.5)
track('mi3', 'MIDI_IN', B, ('R1', '1'), [], 'mia')
track('mif', 'MIDI_IN', F, 'mia', [(12.2, 27.2), (3.2, 27.2)], 'mib')
track('mi4', 'MIDI_IN', B, 'mib', [], ('JP1', '3'))
track('qb1', 'Q1_B', B, ('R1', '2'), [], ('Q1', '1'))
track('qb2', 'Q1_B', B, ('Q1', '1'), [(9.35, 27.0), (14.45, 27.0)], ('D2', '1'))
track('rxq1', 'RX_Q', B, ('Q1', '3'), [], ('R2', '1'))
track('rxq2', 'RX_Q', B, ('R2', '1'), [], ('JP1', '1'))
track('rx', 'RX', B, ('JP1', '2'), [(XRX, 24.0), (XRX, 40.6), (7.6, 40.6), (7.8, 39.1)], ('U1', '11'), FAN)
track('cvin', 'CV_IN', B, ('J2', 'T'), [], ('R4', '1'))
track('cv1', 'CV_BUF', B, ('R4', '2'), [(9.0, 31.3)], ('D3', '3'))
track('cv2', 'CV_BUF', B, ('C9', '1'), [], ('D3', '3'))

# ---- CV buffer below the RV1 tabs: CV_BUF (F X6.95) down, CV_ADC (F X7.65) back up to U1 pin 14
via('cvbuft', 'CV_BUF', 6.3, 36.3)
via('cvbufb', 'CV_BUF', 6.95, 45.0)
track('cvb1', 'CV_BUF', B, ('C9', '1'), [], 'cvbuft')
track('cvbf', 'CV_BUF', F, 'cvbuft', [(6.95, 36.95)], 'cvbufb')
track('cvb2', 'CV_BUF', B, 'cvbufb', [(9.463, 45.0)], ('U4', '3'))
track('cvb3', 'CV_BUF', B, ('U4', '3'), [(9.463, 45.0), (13.4, 45.0)], ('R13', '2'))
track('cvb4', 'CV_BUF', B, 'cvbufb', [(6.2, 45.75), (5.6, 46.35)], ('R14', '1'))
via('cvadct', 'CV_ADC', 7.65, 37.9)
via('cvadcb', 'CV_ADC', 7.65, 46.3)
track('cva1', 'CV_ADC', B, ('U1', '14'), [], 'cvadct', FAN)
track('cvaf', 'CV_ADC', F, 'cvadct', [], 'cvadcb')
track('cva2', 'CV_ADC', B, 'cvadcb', [(7.3, 46.65), (7.3, 48.55)], ('U4', '1'))
# U4 is mirrored on B: follower feedback pin 1 (left) -> between the pad columns -> pin 4 (right)
track('cvfb', 'CV_ADC', B, ('U4', '1'), [(10.6, 48.55), (10.6, 46.65)], ('U4', '4'))
# +5V from the RV1 pin 3 pad to U4 pin 5, R13 and C15; U4 GND via left of the body
track('p5u4', '+5V', B, ('RV1', '3'), [(12.5, 49.3)], ('U4', '5'), P5)
track('p5r13', '+5V', B, ('RV1', '3'), [(12.5, 49.3), (13.4, 48.4)], ('R13', '1'), P5)
track('p5c15', '+5V', B, ('R13', '1'), [], ('C15', '1'), P5)
via('gndu4', 'GND', 8.2, 47.6)
track('gndu4', 'GND', B, ('U4', '2'), [], 'gndu4')

# ---- U1 fan-out ---------------------------------------------------------------------------------
via('gndep', 'GND', 10.0, 38.3)
track('gndu1', 'GND', B, ('U1', '3'), [], ('U1', '21'), FAN)
via('p5u1', '+5V', 12.7, 38.4)
track('p5u1', '+5V', B, ('U1', '4'), [(12.4, 38.7)], 'p5u1', FAN)
track('p5c1', '+5V', B, 'p5u1', [], ('C1', '1'), P5)
via('p5d3', '+5V', 11.4, 34.0)
track('p5d3', '+5V', B, ('D3', '2'), [], 'p5d3', SIG)
via('updi', 'UPDI_PA0', 10.0, 35.3)
track('updis', 'UPDI_PA0', B, ('U1', '19'), [(10.4, 36.0)], 'updi', FAN)
via('pot1', 'POT1', 11.2, 35.4)
track('pot1s', 'POT1', B, ('U1', '20'), [(10.8, 36.1)], 'pot1', FAN)
via('pot2', 'POT2', 12.4, 36.9)
via('btn', 'BUTTON', 18.4, 79.0)
track('pot2s', 'POT2', B, ('U1', '1'), [(12.0, 37.5)], 'pot2', FAN)
track('btn', 'BUTTON', B, ('U1', '5'), [(12.0, 39.1), (12.0, 40.2), (XBTN, 40.2), (XBTN, 78.4)], 'btn', FAN)
track('led', 'LED_DRV', B, ('U1', '6'), [(10.8, 40.8), (XLED, 40.8), (XLED, 81.4)], ('R6', '1'), FAN)
track('dac', 'DAC', B, ('U1', '7'), [(10.4, 41.4), (XDAC, 41.4), (XDAC, 90.7), (13.8, 90.7)], ('R7', '1'), FAN)

# ---- +5V network: LDO -> F left lane -> top -> D3/R2/R3 and the middle trunk ---------------
via('p5r2', '+5V', 5.6, 25.4)
via('p5r3', '+5V', 14.4, 20.6)
track('p5left', '+5V', F, 'p5ldo', [(11.4, 103.6), (XP5, 103.6), (XP5, 34.0)], 'p5d3', P5)
track('p5top', '+5V', F, 'p5d3', [(13.0, 33.0), (13.0, 27.5), (14.4, 24.0)], 'p5r3', P5)
track('p5r2f', '+5V', F, 'p5r3', [(5.6, 20.6)], 'p5r2', P5)
track('p5r2b', '+5V', B, 'p5r2', [], ('R2', '2'), P5)
track('p5r3b', '+5V', B, 'p5r3', [], ('R3', '2'), P5)
track('p5mid', '+5V', F, 'p5d3', [(13.0, 34.5), (13.3, 36.0), (13.3, 37.8)], 'p5u1', P5)
track('p5rv1', '+5V', F, 'p5u1', [(12.5, 39.5)], ('RV1', '3'), P5)
track('p5c2', '+5V', B, ('RV1', '3'), [], ('C2', '1'), P5)
track('p5rv2', '+5V', F, ('RV1', '3'), [], ('RV2', '3'), P5)

# ---- UPDI (F.Cu X1.95, around the R10 tap via) -> R5 -> J5 --------------------------------
via('updib', 'UPDI_PA0', 5.2, 97.6)
track('updif', 'UPDI_PA0', F, 'updi',
      [(XUPDI, 35.3), (XUPDI, 82.3), (2.6, 82.9), (2.6, 84.0), (XUPDI, 84.6), (XUPDI, 96.8)], 'updib')
track('updir5', 'UPDI_PA0', B, 'updib', [(4.95, 98.2), (4.95, 101.9)], ('R5', '1'))
track('updij5', 'UPDI', B, ('R5', '2'), [], ('J5', '1'))

# ---- pots: wipers (F.Cu from U1), ADC caps ---------------------------------------------------
track('pot1f', 'POT1', F, 'pot1', [(10.95, 36.4), (10.95, 40.0), (10.0, 41.0)], ('RV1', '2'))
track('pot2f', 'POT2', F, 'pot2', [(11.7, 37.6), (11.7, 40.5), (XMID, 41.5), (XMID, 63.5)], ('RV2', '2'))
track('pot1c', 'POT1', B, ('RV1', '2'), [], ('C10', '1'))
track('pot2c', 'POT2', B, ('RV2', '2'), [], ('C11', '1'))

# ---- mode LED and button --------------------------------------------------------------------
via('leda', 'LED_A', 17.6, 85.0)
via('gndled', 'GND', 15.5, 89.9)
track('gndled', 'GND', B, ('D1', '1'), [], 'gndled', P5)
track('leda1', 'LED_A', B, ('R6', '2'), [], 'leda')
track('leda2', 'LED_A', F, 'leda', [], ('D1', '2'))
SW1R, SW1L = pad('SW1', '1', 0), pad('SW1', '1', 1)      # pad 1 right (X9.105) / left (X4.905)
track('btnf', 'BUTTON', F, 'btn', [(18.4, 90.6), (9.1, 90.6)], SW1R)
track('btnsw', 'BUTTON', F, SW1R, [], SW1L)


def zone(name, net, layer, poly):
    ops.append({'op': 'add_zone', 'uuid': uid('zone/' + name), 'net': netname(net), 'layer': layer,
                'polygon': [a(x, y) for x, y in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.2,
                'pad_connection': 'thermal'})


# ---- GND stitching: ties the two pours across the islands the lanes cut on B.Cu -------------
for n, (x, y) in enumerate([(17.0, 34.0), (3.4, 36.6), (2.9, 50.2), (16.0, 49.6), (4.0, 63.0), (15.0, 62.5),
                            (4.0, 78.5), (15.0, 78.5), (5.0, 113.0), (17.5, 101.5), (12.6, 108.6), (16.6, 108.6)]):
    via(f'gnd{n}', 'GND', x, y)


# ---- GND pours on both layers (whole board), thermal reliefs ---------------------------------
X0, X1, Y0, Y1 = 0.475, 19.525, 9.225, 119.275       # board outline
zone('gnd/' + B, 'GND', B, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])
zone('gnd/' + F, 'GND', F, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])

if __name__ == '__main__':
    json.dump({'schema_version': 1, 'operations': ops}, sys.stdout, indent=1)
    sys.stdout.write('\n')
