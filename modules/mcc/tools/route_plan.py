#!/usr/bin/env python3
"""Emit the explicit routing plan (shared `pcb plan/apply` ops v1) for the 6HP MCC carrier.

Hand-routed: every track, via and pour is written out here in panel-frame millimetres
(KiCad = +100/+50); nothing is autorouted (TraceMaker failed fast at U1, docs/research.md).
Placement: docs/geometry.json (R3). Layer plan:
  U1    turned so each side faces its traffic: PB3/PB2/PB1/PB0 + PC0 up, PC1-PC3 + PA0
        right, PA2/PA3 + supply down, PA4-PA7 left. The bank/LED lines drop through the
        F.Cu shadow of the package (EP GND via between them); the rest escape on B.Cu.
  F.Cu  long vertical lanes: knobs (pot middles), MIDI RX/TX and PB0 up the middle strip,
        bank button/LEDs and PA3 down it, the MIDI-band +5V, the CV jack tips.
  B.Cu  the CV input clusters, op-amps, +5V east trunk (X28.4) and knob +5V column (X10.5),
        power entry, MIDI front ends.
Tracks 0.2 mm at the QFN, 0.25 mm signal, 0.3 mm +5V, 0.4 mm power; vias 0.6/0.3 mm.
GND pours on both layers with thermal reliefs.

  python3 -B tools/route_plan.py > research/route/plan.json   (then shared pcb plan/apply/promote)
"""
import json
import sys
import uuid

FAN, SIG, P5, PWR, VIA = 0.2, 0.25, 0.3, 0.4, (0.6, 0.3)
B, F = 'B.Cu', 'F.Cu'
OX, OY = 100.0, 50.0
YR = [37.0, 58.25, 79.5, 100.75]  # rows: knob shaft and CV jack (docs/geometry.json)
XT = 28.4                         # +5V east trunk (B.Cu)

ops = []


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/mcc/route/' + key))


def a(x, y):
    """Panel frame -> KiCad board coordinates."""
    return [round(OX + x, 4), round(OY + y, 4)]


RAILS = {'GND', '+5V', '+12V', '-12V', '+12V_F'}


def netname(net):
    return net if net in RAILS else '/' + net


def via(name, net, x, y):
    ops.append({'op': 'add_via', 'uuid': uid('via/' + name), 'net': netname(net), 'at': a(x, y),
                'diameter_mm': VIA[0], 'drill_mm': VIA[1]})
    return name


def pad(ref, number, index):
    """Pad by UUID (tools/build_layout.py pad_uuid) for duplicated pad numbers."""
    return {'uuid': str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/mcc/pcb/pad/{ref}/{number}/{index}'))}


def on(track_name, seg, x, y):
    """Branch endpoint on segment `seg` of a polyline (shared op UUID rule), on its centreline."""
    t = uid('trk/' + track_name)
    return {'track': t if seg == 0 else str(uuid.uuid5(uuid.UUID(t), str(seg))), 'at': a(x, y)}


def end(e):
    if isinstance(e, dict):
        return e
    if isinstance(e, tuple):
        return {'pad': {'ref': e[0], 'number': e[1]}}
    return {'uuid': uid('via/' + e)}


def track(name, net, layer, s, pts, e, w=SIG):
    ops.append({'op': 'add_polyline', 'uuid': uid('trk/' + name), 'net': netname(net), 'layer': layer,
                'start': end(s), 'waypoints': [a(x, y) for x, y in pts], 'end': end(e), 'width_mm': w})


# ---- U1 fan-out ----------------------------------------------------------------------------
# EP: GND pin 3 tied in, one via to the F.Cu pour between the A and B lanes.
via('u1/ep', 'GND', 17.0, 67.75)
track('u1/gnd', 'GND', B, ('U1', '3'), [], ('U1', '21'), FAN)

# Top side: PB3 RX, PB2 TX (vias, F.Cu up), PB1 CV2 (B.Cu up to U4 west), PB0 CV1 (via, F.Cu
# up to U4 east), PC0 bank button (via, F.Cu across the top of the package, then down).
via('rx/1', 'RX', 15.4, 63.9)
track('rx/s', 'RX', B, ('U1', '11'), [(16.2, 64.6)], 'rx/1', FAN)
via('tx/1', 'TX', 16.3, 62.9)
track('tx/s', 'TX', B, ('U1', '12'), [(16.6, 63.5)], 'tx/1', FAN)
track('cv2/adc', 'CV2_ADC', B, ('U1', '13'),
      [(17.0, 61.9), (14.7, 59.6), (14.7, 55.4), (12.8, 53.5), (12.8, 47.0), (13.4, 46.36)], ('U4', '7'), FAN)
via('cv1/1', 'CV1_ADC', 17.7, 63.2)
track('cv1/s', 'CV1_ADC', B, ('U1', '14'), [(17.4, 63.9)], 'cv1/1', FAN)
via('bank/1', 'BANK_SW', 18.2, 64.9)
track('bank/s', 'BANK_SW', B, ('U1', '15'), [(17.8, 65.6)], 'bank/1', FAN)

# Right side: PC1-PC3 bank LEDs (vias, F.Cu west into the package shadow, then down);
# PA0 to R5 and the UPDI header J4.
via('led_a/1', 'LED_A', 19.4, 65.6)
track('led_a/s', 'LED_A', B, ('U1', '16'), [(18.9, 66.95), (19.4, 66.45)], 'led_a/1', FAN)
via('led_b/1', 'LED_B', 20.3, 66.25)
track('led_b/s', 'LED_B', B, ('U1', '17'), [(19.3, 67.35)], 'led_b/1', FAN)
via('led_c/1', 'LED_C', 21.0, 66.95)
track('led_c/s', 'LED_C', B, ('U1', '18'), [(19.7, 67.75), (20.5, 66.95)], 'led_c/1', FAN)
track('updi/pa0', 'UPDI_PA0', B, ('U1', '19'), [(19.6, 68.15), (20.0, 68.55)], ('R5', '1'), FAN)
track('updi/j4', 'UPDI', B, ('R5', '2'), [(21.6, 71.83)], ('J4', '1'))

# Bottom side: PA2 CV3 (B.Cu down to U5 east), PA3 CV4 (via, F.Cu down west of the strip),
# VDD to C1, PA4 knob 1 (via, F.Cu up the strip).
track('cv3/adc', 'CV3_ADC', B, ('U1', '1'), [(17.8, 69.9), (18.4, 70.5), (18.4, 86.6)], ('U5', '1'), FAN)
via('cv4/1', 'CV4_ADC', 14.6, 72.9)
track('cv4/s', 'CV4_ADC', B, ('U1', '2'), [(17.4, 72.6), (14.9, 72.6)], 'cv4/1', FAN)
track('u1/vdd', '+5V', B, ('U1', '4'), [(16.6, 69.9), (15.6, 70.4), (14.72, 70.4)], ('C1', '1'), FAN)
track('c1/gnd', 'GND', B, ('C1', '2'), [(17.0, 70.5)], ('U1', '3'), FAN)
via('pot1/1', 'POT1', 14.95, 69.5)
track('pot1/s', 'POT1', B, ('U1', '5'), [(16.2, 69.5)], 'pot1/1', FAN)

# Left side: PA5 knob 2 (B.Cu west, F.Cu hop over the knob +5V column), PA6/PA7 knobs 3/4
# (vias, F.Cu west then down the pot middles).
via('pot2/1', 'POT2', 11.4, 68.9)
track('pot2/s', 'POT2', B, ('U1', '6'), [(11.7, 68.55)], 'pot2/1', FAN)
via('pot3/1', 'POT3', 13.0, 67.85)
track('pot3/s', 'POT3', B, ('U1', '7'), [(13.3, 68.15)], 'pot3/1', FAN)
via('pot4/1', 'POT4', 13.9, 67.2)
track('pot4/s', 'POT4', B, ('U1', '8'), [(14.4, 67.75)], 'pot4/1', FAN)

# ---- Knobs ---------------------------------------------------------------------------------
track('pot1/f', 'POT1', F, 'pot1/1', [(14.6, 69.15), (14.6, 48.5), (8.0, 48.5)], ('RV1', '2'))
track('pot1/c', 'POT1', B, ('RV1', '2'), [], ('C31', '1'))
via('pot2/2', 'POT2', 9.7, 69.2)
track('pot2/f', 'POT2', F, 'pot2/1', [], 'pot2/2')
track('pot2/c', 'POT2', B, 'pot2/2', [], ('C32', '1'))
track('pot2/rv', 'POT2', B, ('RV2', '2'), [], ('C32', '1'))
track('pot3/f', 'POT3', F, 'pot3/1', [(8.0, 67.85)], ('RV3', '2'))
track('pot3/c', 'POT3', B, ('RV3', '2'), [], ('C33', '1'))
track('pot4/f', 'POT4', F, 'pot4/1',
      [(5.5, 67.2), (5.5, 83.0), (2.6, 85.9), (2.6, 89.6), (5.5, 92.5), (5.5, 104.5), (8.0, 107.0)],
      ('RV4', '2'))
track('pot4/c', 'POT4', B, ('RV4', '2'), [], ('C34', '1'))

# ---- Bank button and LEDs (F.Cu lanes X15.75 / 16.3 / 17.7 / 18.25 down the middle; C out to the right edge) ---------
track('bank/f', 'BANK_SW', F, 'bank/1', [(15.75, 64.9), (15.75, 105.5), (13.4, 107.85), (13.4, 115.4)],
      pad('SW1', '2', 3))
track('bank/sw', 'BANK_SW', B, pad('SW1', '2', 2), [], pad('SW1', '2', 3))
via('led_a/2', 'LED_A', 16.3, 108.0)
track('led_a/f', 'LED_A', F, 'led_a/1', [(16.3, 65.6)], 'led_a/2')
track('led_a/r', 'LED_A', B, 'led_a/2', [], ('R6', '1'))
via('led_b/2', 'LED_B', 24.5, 109.1)
track('led_b/f', 'LED_B', F, 'led_b/1', [(17.7, 66.25), (17.7, 99.0), (24.5, 99.0)], 'led_b/2')
track('led_b/r', 'LED_B', B, 'led_b/2', [], ('R7', '1'))
via('led_c/2', 'LED_C', 28.5, 108.4)
track('led_c/f', 'LED_C', F, 'led_c/1', [(18.25, 66.95), (18.25, 98.4), (28.6, 98.4), (28.6, 108.0)], 'led_c/2')
track('led_c/r', 'LED_C', B, 'led_c/2', [], ('R8', '1'))
for i, (r, d, x) in enumerate((('R6', 'D4', 14.9), ('R7', 'D5', 19.9), ('R8', 'D6', 24.9))):
    track(f'led_{"abc"[i]}/an', f'LED_{"ABC"[i]}_AN', B, (r, '2'), [(x, 110.2), (x, 114.6)], (d, '2'))

# ---- CV1/CV2 ADC lines into U4, CV3/CV4 into U5 --------------------------------------------
via('cv1/2', 'CV1_ADC', 21.2, 46.36)
track('cv1/f', 'CV1_ADC', F, 'cv1/1', [(20.0, 60.9), (20.0, 47.3)], 'cv1/2')
track('cv1/u', 'CV1_ADC', B, 'cv1/2', [], ('U4', '2'))
track('cv1/t', 'CV1_ADC', B, ('U4', '1'), [], ('U4', '2'))
track('cv2/t', 'CV2_ADC', B, ('U4', '6'), [], ('U4', '7'))
track('cv3/t', 'CV3_ADC', B, ('U5', '1'), [], ('U5', '2'))
via('cv4/2', 'CV4_ADC', 12.9, 88.9)
track('cv4/f', 'CV4_ADC', F, 'cv4/1', [(14.6, 88.0)], 'cv4/2')
track('cv4/u', 'CV4_ADC', B, 'cv4/2', [], ('U5', '7'))
track('cv4/t', 'CV4_ADC', B, ('U5', '6'), [], ('U5', '7'))

# ---- CV input clusters (R1n/R2n/R3n/C1n/D1n beside each jack) -------------------------------
for n, y in enumerate(YR, 1):
    sh = f'CV{n}_SH'
    track(f'ch{n}/sh1', sh, B, (f'R1{n}', '2'), [], (f'R2{n}', '2'))
    track(f'ch{n}/sh2', sh, B, (f'R2{n}', '2'), [], (f'R3{n}', '1'))
    track(f'ch{n}/sh3', sh, B, (f'R3{n}', '1'), [], (f'C1{n}', '1'))
    track(f'ch{n}/sh4', sh, B, (f'C1{n}', '1'), [(25.9, y + 2.3)], (f'D1{n}', '3'))
    # jack tip -> R1n over the tip/sleeve pads on F.Cu
    via(f'ch{n}/in', f'CV{n}_IN', 26.83, y - 6.1)
    track(f'ch{n}/inf', f'CV{n}_IN', F, (f'J1{n}', 'T'), [(23.7, y - 6.1)], f'ch{n}/in')
    track(f'ch{n}/inb', f'CV{n}_IN', B, f'ch{n}/in', [], (f'R1{n}', '1'))
# GND stitching: the pour pockets between each cluster and the trunk (D1n GND pin), and U5's
# east side, tie to the F.Cu pour.
for n, y in enumerate(YR, 1):
    via(f'ch{n}/gnd', 'GND', 27.6, y + 2.15)
via('u5/gnd', 'GND', 20.5, 79.0)
via('u1/gnd', 'GND', 12.5, 75.0)
via('u5/gnd2', 'GND', 21.0, 93.5)
track('ch1/u', 'CV1_SH', B, ('U4', '3'), [(22.0, 47.64), (24.7, 44.94), (24.7, 41.4)], ('D11', '3'))
track('ch2/u', 'CV2_SH', B, ('U4', '5'),
      [(13.7, 49.7), (13.7, 51.9), (20.6, 51.9), (21.3, 51.2), (24.4, 51.2), (25.17, 52.0)], ('R12', '2'))
track('ch3/u', 'CV3_SH', B, ('U5', '3'), [(22.5, 90.13), (24.7, 87.93), (24.7, 84.1)], ('D13', '3'))
track('ch4/u', 'CV4_SH', B, ('U5', '5'), [(14.53, 92.5), (24.5, 92.5), (24.5, 95.2)], ('R14', '2'))

# ---- +5V -----------------------------------------------------------------------------------
# East trunk (B.Cu X28.4) from C3 to D14: CV offset resistors, clamps, U4 decoupling.
track('p5/reg', '+5V', B, ('U2', '3'), [(23.6, 29.8), (27.0, 29.8)], ('C3', '1'), PWR)
track('p5/trunk', '+5V', B, ('C3', '1'), [(XT, 29.35), (XT, 105.0)], ('D14', '2'), PWR)
for n, y in enumerate(YR, 1):
    track(f'p5/r2{n}', '+5V', B, (f'R2{n}', '1'), [], on('p5/trunk', 1, XT, y - 2.9), P5)
    if n < 4:
        track(f'p5/d1{n}', '+5V', B, (f'D1{n}', '2'), [], on('p5/trunk', 1, XT, y + 4.25), P5)
track('p5/c6', '+5V', B, ('C6', '1'), [(18.4, 50.2)], on('p5/trunk', 1, XT, 50.2), P5)
# Shunt: C2 bulk from the regulator; F.Cu hop to U3/R9 (the shunt reference wraps round U3).
track('p5/c2', '+5V', B, ('U2', '3'), [(21.4, 29.9), (20.0, 29.9), (20.0, 37.3), (18.6, 38.2)], ('C2', '1'), PWR)
via('p5/h1', '+5V', 18.7, 39.2)
via('p5/h2', '+5V', 19.1, 43.3)
track('p5/h1', '+5V', B, ('C2', '1'), [(18.2, 38.7)], 'p5/h1', P5)
track('p5/hf', '+5V', F, 'p5/h1', [], 'p5/h2', P5)
track('p5/u3', '+5V', B, 'p5/h2', [], ('U3', '2'), P5)
track('p5/r9', '+5V', B, 'p5/h2', [], ('R9', '1'), P5)
track('ref/r9', 'SHUNT_REF', B, ('U3', '1'), [], ('R9', '2'))
track('ref/r10', 'SHUNT_REF', B, ('U3', '1'), [(17.0, 39.5), (14.0, 39.5)], ('R10', '1'))
# Knob column (B.Cu X10.5 through the pot middles): U4, pots 1-4, U1 (C1), U5 (C7).
track('p5/u4', '+5V', B, ('U3', '2'), [(17.94, 43.6), (14.53, 43.6)], ('U4', '8'), P5)
track('p5/rv1', '+5V', B, ('U4', '8'), [(11.6, 45.09)], ('RV1', '3'), P5)
track('p5/w1', '+5V', B, ('RV1', '3'), [], ('RV2', '3'), P5)
track('p5/w2', '+5V', B, ('RV2', '3'), [], ('RV3', '3'), P5)
track('p5/c1', '+5V', B, ('C1', '1'), [], on('p5/w2', 0, 10.5, 71.2), P5)
track('p5/w3', '+5V', B, ('RV3', '3'), [], ('RV4', '3'), P5)
track('p5/u5', '+5V', B, ('RV3', '3'), [(11.6, 87.59)], ('U5', '8'), P5)
track('p5/c7', '+5V', B, ('C7', '1'), [(13.83, 86.9)], ('U5', '8'), P5)
# MIDI band (F.Cu from the trunk): D2 clamp, R2 RX pull-up, R3 input bias.
via('p5/t1', '+5V', XT, 31.5)
via('p5/d2', '+5V', 20.9, 14.6)
via('p5/r2', '+5V', 14.9, 10.9)
via('p5/r3', '+5V', 9.8, 15.2)
track('p5/tf1', '+5V', F, 'p5/t1', [(XT, 14.0), (21.5, 14.0)], 'p5/d2', P5)
track('p5/tf2', '+5V', F, 'p5/d2', [(20.3, 14.0), (15.4, 14.0), (15.4, 12.6), (14.9, 11.6)], 'p5/r2', P5)
track('p5/tf3', '+5V', F, 'p5/r2', [(10.4, 10.9), (9.8, 11.5)], 'p5/r3', P5)
track('p5/d2b', '+5V', B, 'p5/d2', [(20.9, 15.65)], ('D2', '2'), P5)
track('p5/r2b', '+5V', B, 'p5/r2', [], ('R2', '2'), P5)
track('p5/r3b', '+5V', B, 'p5/r3', [], ('R3', '2'), P5)

# ---- Power entry ---------------------------------------------------------------------------
track('p12/hdr', '+12V', B, ('J3', '9'), [], ('J3', '10'), PWR)
track('p12/d3', '+12V', B, ('J3', '10'), [], ('D3', '2'), PWR)
track('n12/hdr', '-12V', B, ('J3', '1'), [], ('J3', '2'), PWR)
track('p12f/u2', '+12V_F', B, ('D3', '1'), [(18.9, 32.25), (18.9, 28.3)], ('U2', '2'), PWR)
track('p12f/c5', '+12V_F', B, ('C5', '1'), [], ('D3', '1'), PWR)
track('p12f/c4', '+12V_F', B, ('U2', '2'), [(23.6, 27.6), (24.4, 28.3)], ('C4', '1'), PWR)

# ---- MIDI in (J1 -> R1/Q1 -> JP1) ----------------------------------------------------------
track('min/r1', 'MIDI_IN', B, ('J1', 'T'), [(9.0, 10.6), (12.33, 10.6)], ('R1', '1'))
track('min/r3', 'MIDI_IN', B, ('R1', '1'), [], ('R3', '1'))
track('min/jp', 'MIDI_IN', B, ('J1', 'T'), [(4.0, 12.08), (3.2, 12.9)], ('JP1', '3'))
track('qb/q1', 'Q1_B', B, ('R1', '2'), [(11.5, 12.9), (11.5, 15.2)], ('Q1', '1'))
track('qb/d1', 'Q1_B', B, ('Q1', '1'), [(14.1, 16.05), (14.1, 20.0)], ('D1', '1'))
via('rxq/1', 'RX_Q', 15.7, 14.9)
via('rxq/2', 'RX_Q', 9.7, 17.9)
track('rxq/r2', 'RX_Q', B, ('R2', '1'), [], 'rxq/1')
track('rxq/f', 'RX_Q', F, 'rxq/1', [(13.2, 17.4), (10.2, 17.4)], 'rxq/2')
track('rxq/q1', 'RX_Q', B, ('Q1', '3'), [], 'rxq/2')
track('rxq/jp', 'RX_Q', B, 'rxq/2', [(8.6, 18.3)], ('JP1', '1'))
via('rx/2', 'RX', 2.0, 32.5)
track('rx/f', 'RX', F, 'rx/1', [(15.3, 63.5), (15.3, 32.5)], 'rx/2')
track('rx/jp', 'RX', B, 'rx/2', [(2.0, 17.0)], ('JP1', '2'))

# ---- MIDI out (JP2 -> R4/D2 -> J2) ---------------------------------------------------------
track('txp/jp', 'TX_P', B, ('R4', '1'), [(19.21, 10.2), (28.6, 10.2), (28.6, 18.3)], ('JP2', '1'))
track('txp/d2', 'TX_P', B, ('R4', '1'), [(19.21, 13.2), (18.3, 13.2), (17.41, 14.1)], ('D2', '3'))
via('mout/1', 'MIDI_OUT', 16.2, 12.1)
track('mout/r4', 'MIDI_OUT', B, ('R4', '2'), [], 'mout/1')
track('mout/f', 'MIDI_OUT', F, 'mout/1', [], ('J2', 'T'))
track('mout/jp', 'MIDI_OUT', B, ('J2', 'T'), [(24.6, 13.4), (26.1, 14.9)], ('JP2', '3'))
via('tx/2', 'TX', 25.3, 17.0)
track('tx/f', 'TX', F, 'tx/1', [(16.0, 62.6), (16.0, 22.05), (25.3, 22.05)], 'tx/2')
track('tx/jp', 'TX', B, 'tx/2', [], ('JP2', '2'))


def zone(name, net, layer, poly):
    ops.append({'op': 'add_zone', 'uuid': uid('zone/' + name), 'net': netname(net), 'layer': layer,
                'polygon': [a(x, y) for x, y in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.2,
                'pad_connection': 'thermal'})


# ---- GND pours on both layers (whole board), thermal reliefs ---------------------------------
X0, X1, Y0, Y1 = 0.475, 29.525, 9.225, 119.275       # board outline
zone('gnd/' + B, 'GND', B, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])
zone('gnd/' + F, 'GND', F, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])

if __name__ == '__main__':
    json.dump({'schema_version': 1, 'operations': ops}, sys.stdout, indent=1)
    sys.stdout.write('\n')
