#!/usr/bin/env python3
"""Emit the explicit routing plan (shared `pcb plan/apply` ops v1) for the midi carrier.

All geometry is written out here in board millimetres; nothing is autorouted.
Layer plan (docs/research.md section 3.6; S5 LED drivers section 3.4). The Bread Modular pin map sends nets up and
down from every side of U1, so each layer keeps a lane order that matches its turn order:
  B.Cu  RX + LED1-LED4 up, LED5-LED8 down, TX6-TX8 up to their layer-change vias,
        resistor stubs, power chain, U3 heat sink, GND pour.
  F.Cu  TX1-TX4 up, TX5-TX8 + UPDI down, +5V trunk and LED anode rail, TIP/RING, U3 heat
        sink, GND pour.
  LED drivers: B.Cu clusters (Qn, RLEDn, RBn) above each LED; the LED lanes end at RBn.
Vias 0.6/0.3 mm. Tracks 0.25 mm signal, 0.2 mm U1 fan-out, 0.3 mm +5V, 0.4-0.5 mm power.

  python3 -B tools/v1/route_plan.py > research/v1/route/plan.json   (then shared pcb plan/apply/promote)
"""
import json
import sys
import uuid

SIG, PWR, VIA = 0.25, 0.4, (0.6, 0.3)
B, F = 'B.Cu', 'F.Cu'
JACK = {n: 76.5 + 10.5 * (n - 1) for n in range(1, 9)}           # OUTn jack centre Y
JREF = {n: f'J{n + 1}' for n in range(1, 9)}
RTX = {1: 'R3', 2: 'R5', 3: 'R7', 4: 'R9', 5: 'R12', 6: 'R14', 7: 'R16', 8: 'R18'}
RLED = {1: 'R4', 2: 'R6', 3: 'R8', 4: 'R10', 5: 'R13', 6: 'R15', 7: 'R17', 8: 'R19'}
RB = {n: f'R{n + 30}' for n in range(1, 9)}                     # LED n base resistor (10k)
Q = {n: f'Q{n + 10}' for n in range(1, 9)}                      # LED n switch (MMBT3904)

ops = []


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/midi/route/' + key))


def r(v):
    return round(v, 4)


def via(name, net, x, y):
    ops.append({'op': 'add_via', 'uuid': uid('via/' + name), 'net': net, 'at': [r(x), r(y)],
                'diameter_mm': VIA[0], 'drill_mm': VIA[1]})
    return name


def end(e):
    if isinstance(e, tuple):
        return {'pad': {'ref': e[0], 'number': e[1]}}
    if isinstance(e, dict):
        return e
    return {'uuid': uid('via/' + e)}


def on(name, x, y):
    """Branch endpoint on the first (straight) segment of an earlier polyline."""
    return {'track': uid('trk/' + name), 'at': [r(x), r(y)]}


def track(name, net, layer, a, pts, b, w=SIG):
    ops.append({'op': 'add_polyline', 'uuid': uid('trk/' + name), 'net': net, 'layer': layer,
                'start': end(a), 'waypoints': [[r(x), r(y)] for x, y in pts], 'end': end(b), 'width_mm': w})


# ---- per-channel stubs at the jacks (B.Cu, straight) ------------------------------------
for n in range(1, 9):
    track(f'out{n}', f'/CH{n}/OUT', B, (RTX[n], '2'), [], (JREF[n], 'T'))

# ---- LED drivers (Bread Modular gate_out), one cluster in the band above each LED --------
# LEDs are rotated 270: cathode (pad 1) up toward the cluster, anode (pad 2, +5V) down.
# Right column: Qn (rot 180: B lower left, E upper left, C right) above RLEDn (pad 1 LED_K
# left, pad 2 Q_C right). Tip column below the previous series resistor: RBn (pad 1 CHn_LED
# left toward the lane, pad 2 Q_B right). E goes to a GND via left of Q, clear of the F.Cu
# TX6-TX8 channel. Exceptions: Q11 sits below JP1 (E via right of it, above the rail start),
# R34 stands beside the J5 tip pad (R9 fills the J4/J5 tip column), R35 sits low in the U1 band.
QY = {n: JACK[n] - 6.05 for n in range(1, 9)}
QY[1] = 71.05
EVIA = {n: (114.55, JACK[n] - 7.6) for n in range(1, 9)}
EVIA[1] = (118.6, 69.1)
EVIA[5] = (114.4, 111.4)
for n in range(1, 9):
    qy, ch = QY[n], f'/CH{n}'
    via(f'e{n}', '/GND', *EVIA[n])
    track(f'qe{n}', '/GND', B, (Q[n], '2'), [(116.95, 69.1)] if n == 1 else [], f'e{n}')
    track(f'qc{n}', f'{ch}/Q_C', B, (Q[n], '3'), [], (RLED[n], '2'))
    track(f'ledk{n}', f'{ch}/LED_K', B, (RLED[n], '1'), [], (f'D{n}', '1'))
    if n == 1:
        qb = []                                   # R31 pad 2 is level with the Q11 base
    elif n == 4:
        qb = [(115.6, qy + 0.95)]                 # up the J5 tip / D4 gap from R34
    elif n == 5:
        qb = [(115.2, 116.0), (115.2, qy + 0.95)]  # up beside R13 from R35
    else:
        qb = [(114.925, qy + 0.95)]
    track(f'qb{n}', f'{ch}/Q_B', B, (RB[n], '2'), qb, (Q[n], '1'))

# ---- MIDI input: J1 -> JP1 (TRS A/B) -> RX (U1 PB3), Bread Modular V1 direct -------------
track('tip', '/TIP', F, ('J1', 'T'), [], ('JP1', '1'))
track('ring', '/RING', F, ('J1', 'R'), [(107.6, 67.9), (116.0, 67.9)], ('JP1', '3'))

# ---- power chain: J10 +12V -> D10 -> R20 -> U3 (HT7550) -> +5V --------------------------
track('p12a', '/+12V', B, ('J10', '10'), [], ('J10', '9'), 0.5)
# The regulator group sits right of J10 (outside the 16-pin IDC overhang) on its heat sink.
track('p12b', '/+12V', B, ('J10', '10'), [], ('D10', '2'), 0.5)
track('vind', '/VIN_D', B, ('D10', '1'), [], ('R20', '1'), PWR)
track('vinldo', '/VIN_LDO', B, ('R20', '2'), [(114.3, 159.06)], ('U3', '2'), PWR)
track('vinc5', '/VIN_LDO', B, ('C5', '1'), [], ('R20', '2'), PWR)
track('p5c4', '/+5V', B, ('U3', '3'), [], ('C4', '1'), PWR)
# GND returns of U3/C4/C5 run on B.Cu through the heat sink to J10 pin 4.
track('gu3', '/GND', B, ('U3', '1'), [(115.8, 165.65)], ('C4', '2'), PWR)
track('gc5', '/GND', B, ('C5', '2'), [(118.1, 164.2), (115.8, 164.2)], ('U3', '1'), PWR)
track('gc4', '/GND', B, ('C4', '2'), [(111.5, 165.65), (111.5, 164.3)], ('J10', '4'), PWR)

# ---- U1 fan-out, up side ------------------------------------------------------------------
FAN = 0.2                       # 0.4 mm QFN pitch: 0.2 mm stubs keep 0.2 mm to the next pad
TXV = lambda n: JACK[n] + 4.425  # TXn series resistor pad 1 Y (R_odd at jack + 3.6, rot 90)

# TX1-TX4: left pins -> vias on a diagonal in the left zone -> F.Cu up the corridor ->
# via at x 112.3 -> B.Cu stub into the series resistor pad 1.
TXV = {n: JACK[n] + 4.425 for n in range(1, 9)}
TXV[4] = 103.275                                              # R9 sits above J5 (rot 270)
TXL = {1: 106.85, 2: 107.25, 3: 107.65, 4: 108.05}            # corridor lanes (F)
TXZ = {1: (104.35, 115.45), 2: (104.95, 114.7), 3: (105.55, 113.95), 4: (106.15, 113.2)}
TXJ = {1: 109.75, 2: 110.15, 3: 110.55, 4: 110.95}            # jog Y above U1 (F)
TXS = {1: [(106.75, 115.45)], 2: [(105.6, 114.65)], 3: [(106.2, 114.25)], 4: [(106.6, 113.85)]}
for n in range(1, 5):
    vx, vy = TXZ[n]
    net = f'/CH{n}_TX'
    via(f'tx{n}a', net, vx, vy)
    via(f'tx{n}b', net, 112.3, TXV[n])
    track(f'tx{n}s', net, B, ('U1', str(5 + n)), TXS[n], f'tx{n}a', FAN)
    track(f'tx{n}f', net, F, f'tx{n}a', [(vx, TXJ[n]), (TXL[n], TXJ[n]), (TXL[n], TXV[n])], f'tx{n}b', FAN)
    track(f'tx{n}r', net, B, f'tx{n}b', [], (RTX[n], '1'))

# RX + LED1-LED4 up on B.Cu (lanes L->R: RX, TX8, TX6, TX7 to their vias, LED1, LED2, LED3, LED4).
# RX climbs to JP1 left of Q11 (x 115.2, clear of the J1 tip pad).
track('rx', '/RX', B, ('U1', '11'), [(107.8, 70.3), (115.2, 70.3), (115.2, 65.0)], ('JP1', '2'), FAN)
track('led1', '/CH1_LED', B, ('U1', '15'), [(109.4, 112.0), (110.05, 111.35), (110.05, 72.0)], (RB[1], '1'), FAN)
track('led2', '/CH2_LED', B, ('U1', '16'), [(110.45, 113.45), (110.45, 82.5)], (RB[2], '1'), FAN)
track('led3', '/CH3_LED', B, ('U1', '17'), [(110.85, 113.85), (110.85, 93.0)], (RB[3], '1'), FAN)
# LED4 climbs x 111.9 (right of LED1-LED3, under the J5 tip pad row) and enters R34 from below.
track('led4', '/CH4_LED', B, ('U1', '18'), [(111.9, 114.25), (111.9, 109.65), (115.6, 109.65)], (RB[4], '1'), FAN)

# TX8/TX6/TX7: top pins up on B.Cu to vias in the J4/J5 gap, then F.Cu back down past U1 into
# the right channel (L->R TX6, TX7, TX8) and in from the right at x 114.6.
TXR = {8: [(108.2, 104.7)], 6: [(108.6, 106.0)], 7: [(109.0, 106.75)]}
TXU = {8: (108.85, 104.7), 6: (108.85, 105.5), 7: (109.45, 106.3)}
TXF = {8: [(110.6, 104.7), (110.6, 109.7), (116.0, 109.7)],
       6: [(108.6, 105.75), (108.6, 110.5), (115.2, 110.5)],
       7: [(109.45, 110.1), (115.6, 110.1)]}
TXC = {6: 115.2, 7: 115.6, 8: 116.0}
PIN = {6: '13', 7: '14', 8: '12'}
for n in (6, 7, 8):
    net = f'/CH{n}_TX'
    via(f'tx{n}a', net, *TXU[n])
    via(f'tx{n}b', net, 114.6, TXV[n])
    track(f'tx{n}s', net, B, ('U1', PIN[n]), TXR[n], f'tx{n}a', FAN)
    track(f'tx{n}f', net, F, f'tx{n}a', TXF[n] + [(TXC[n], TXV[n])], f'tx{n}b', FAN)
    track(f'tx{n}r', net, B, f'tx{n}b', [], (RTX[n], '1'))

# ---- U1 fan-out, down side ----------------------------------------------------------------
# TX5: via above-left of U1, F.Cu across the (F-empty) U1 footprint, down the corridor, in from the left.
via('tx5a', '/CH5_TX', 106.85, 112.4)
via('tx5b', '/CH5_TX', 112.3, TXV[5])
track('tx5s', '/CH5_TX', B, ('U1', '10'), [(106.85, 113.45)], 'tx5a', FAN)
track('tx5f', '/CH5_TX', F, 'tx5a', [(107.45, 113.0), (111.85, 113.0), (111.85, TXV[5])], 'tx5b', FAN)
track('tx5r', '/CH5_TX', B, 'tx5b', [], ('R12', '1'))

# UPDI (PA0): via right of U1, F.Cu down the corridor (left of TX5) into the J8/J9 band, then
# B.Cu through the J9 pad-row gap to R11/J11 in the strip left of J10.
via('updia', '/UPDI_PA0', 111.25, 114.85)
via('updib', '/UPDI_PA0', 110.9, 146.0)
track('updis', '/UPDI_PA0', B, ('U1', '19'), [(110.45, 114.65)], 'updia', FAN)
track('updif', '/UPDI_PA0', F, 'updia', [(110.9, 115.2)], 'updib')
track('updir', '/UPDI_PA0', B, 'updib', [(107.2, 146.0), (107.2, 152.2), (102.6, 152.2)], ('R11', '1'))
track('updij', '/UPDI', B, ('R11', '2'), [], ('J11', '1'))

# LED5 local on B.Cu under the UPDI via into R35; LED6-LED8 down the corridor on B.Cu
# (L->R LED8, LED7, LED6), each turning right into its base resistor.
track('led5', '/CH5_LED', B, ('U1', '20'), [(110.45, 115.45), (110.45, 116.0)], (RB[5], '1'), FAN)
track('led6', '/CH6_LED', B, ('U1', '1'), [(109.4, 116.1), (109.9, 116.6), (109.9, 124.5)], (RB[6], '1'), FAN)
track('led7', '/CH7_LED', B, ('U1', '2'), [(109.0, 135.0)], (RB[7], '1'), FAN)
track('led8', '/CH8_LED', B, ('U1', '5'), [(107.8, 116.1), (107.3, 116.6), (107.3, 145.0), (112.2, 145.0)], (RB[8], '1'), FAN)

# ---- +5V trunk: LDO -> F.Cu left channel -> C3 -> U1 (via under pin 4, C1) -----------------
P5 = 0.3
via('p5ldo', '/+5V', 111.55, 161.9)
via('p5c3', '/+5V', 103.545, 125.4)
via('p5u1', '/+5V', 108.2, 116.85)
track('p5a', '/+5V', B, ('U3', '3'), [], 'p5ldo', PWR)
track('p5b', '/+5V', F, 'p5ldo', [(111.55, 147.6), (104.3, 147.6), (103.545, 146.85)], 'p5c3', P5)
track('p5c', '/+5V', B, 'p5c3', [], ('C3', '1'), P5)
track('p5d', '/+5V', F, 'p5c3', [(103.545, 117.0), (103.945, 116.6), (107.95, 116.6)], 'p5u1', P5)
track('p5f', '/+5V', B, ('U1', '4'), [], 'p5u1', FAN)
track('p5g', '/+5V', B, 'p5u1', [], ('C1', '1'), P5)

# ---- GND stitching: U1 exposed pad, edge vias between the jack rows ------------------------
track('gndu1', '/GND', B, ('U1', '3'), [], ('U1', '21'), FAN)
via('gndep', '/GND', 108.6, 114.25)
# The B.Cu GND strip between the CH8_LED/CH7_LED lanes (C1 pad 2) gets its own vias to F.Cu
# rather than relying on the ~0.2 mm pour neck between R17's pads.
via('gndc1a', '/GND', 108.15, 124.0)
via('gndc1b', '/GND', 108.15, 131.0)
for n in range(1, 8):
    via(f'gndl{n}', '/GND', 101.8, JACK[n] + 5.25)

# ---- LED anode rail: +5V on F.Cu, fed from the top so it never crosses the U3 heat sink or
# the F.Cu TX6-TX8 channel: up the left channel from the +5V trunk, across above J2, down
# x 118.6 beside the LED column, touching each anode (pad 2, bottom) in turn. -----------------
ANODE = {n: JACK[n] + 1.27 for n in range(1, 9)}
track('rail0', '/+5V', F, on('p5d', 103.545, 117.0), [(103.545, 70.85), (118.6, 70.85), (118.6, ANODE[1] - 0.4)],
      ('D1', '2'), P5)
for n in range(1, 8):
    track(f'rail{n}', '/+5V', F, (f'D{n}', '2'), [(118.6, ANODE[n] + 0.4), (118.6, ANODE[n + 1] - 0.4)],
          (f'D{n + 1}', '2'), P5)


def zone(name, net, layer, poly):
    ops.append({'op': 'add_zone', 'uuid': uid('zone/' + name), 'net': net, 'layer': layer,
                'polygon': [[r(x), r(y)] for x, y in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.2})


# ---- U3 heat sink: VIN_LDO copper on both layers (the HT75xx SOT-89 tab is pin 2, VIN) -----
# B.Cu: the whole area right of J10 below the J9 pad row (U3, R20, C5, D10 sit on it).
# F.Cu: the whole board below the J9 pad row, around J10/J11 (their GND pins are cleared on
# F.Cu and stay on the B.Cu GND pour). Vias beside the tab (not in the pad, so they do not
# wick solder) and in the B.Cu island under the U3/C4/C5 GND returns tie the two layers.
# The shared add_zone has no priority and KiCad rejects intersecting zones, so each GND pour
# is the complement polygon kept 0.3 mm off its heat sink.
X0, X1, Y0, Y1 = 100.475, 119.525, 59.225, 169.275       # board outline
HS_B = [(111.2, 155.1), (X1, 155.1), (X1, Y1), (111.2, Y1)]
HS_F = [(X0, 153.9), (X1, 153.9), (X1, Y1), (X0, Y1)]
for n, (x, y) in enumerate([(112.6, 158.6), (112.6, 160.0), (116.0, 158.6), (116.0, 160.0), (114.3, 157.2),
                            (113.5, 167.6), (115.5, 167.6), (117.5, 167.6), (118.5, 165.5)]):
    via(f'hs{n}', '/VIN_LDO', x, y)
zone('hs/' + B, '/VIN_LDO', B, HS_B)
zone('hs/' + F, '/VIN_LDO', F, HS_F)

# ---- GND pours: everything else on both layers ---------------------------------------------
GND_B = [(X0, Y0), (X1, Y0), (X1, 154.8), (110.9, 154.8), (110.9, Y1), (X0, Y1)]
GND_F = [(X0, Y0), (X1, Y0), (X1, 153.6), (X0, 153.6)]
zone('gnd/' + B, '/GND', B, GND_B)
zone('gnd/' + F, '/GND', F, GND_F)

if __name__ == '__main__':
    json.dump({'schema_version': 1, 'operations': ops}, sys.stdout, indent=1)
    sys.stdout.write('\n')
