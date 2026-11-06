"""S9.2 item 4: design-derived models. Everything here is read from a connectivity view of the DESIGN - the exported
native netlist (kicad-cli XML of hardware/*.kicad_sch) or the generator table (tools/circuit_s8.py) - so the
U4-enable truth table and the 3 A startup plant change when a pin, a net or a value changes. Negative controls in
tools/test_s8.py move single pins in a copy of the netlist and must make these checks fail.

Device data are kept here independently of the symbols (pin roles by MPN):
  2N7002 (onsemi/Nexperia SOT-23): 1 G, 2 S, 3 D; VGS(th) 1.0-2.5 V at 250 uA; IDSS <= 1 uA (25 C) used as the
      off-leakage bound; a gate driven from 3.3 V logic (V3V3 +2 %) sets VG <= 3.366 V.
  MMBT3906 (onsemi): 1 B, 2 E, 3 C; hFE >= 60 at 0.1 mA; VCE(sat) <= 0.25 V; VEB <= 0.35 V is treated as OFF (collector
      leakage bound 5 uA, the S9.1 qualification bound), VEB(on) 0.6-0.85 V.
  LMR38020 (TI SNVSC40E): EN pin 2, IC ground pins 1/9; enable above 1.4 V (max rising), disable below 0.95 V.
  TPS552892-Q1 (TI SLVSGT7): VOUT 11, ISP 12, ISN 13; ISP tied to ISN disables the output current limit (Table 5-1).
  TPS16630 (TI SLVSET9G): UVLO pin 7 / OVP pin 8, thresholds 1.176-1.224 V rising, 1.09-1.15 V falling, 150 nA.
  BAV199LT1G (onsemi BAV199LT1/D): 1 anode, 2 cathode, 3 common (series pair); IR <= 5 nA at 70 V (25 C), <= 80 nA at
      150 C; VF <= 0.9 V at 1 mA.
S9.3: the U4 enable chain gains a third series switch whose gate is an RC from the P12_OK monitor (sequencing()), and each
converter has an FB-injection soft start (soft_start_network()); the 3 A plant integrates both (PhysicalStartup).
"""
import itertools
import math
import xml.etree.ElementTree as ET

ROLES = {
    '2N7002': {'1': 'G', '2': 'S', '3': 'D'},
    'MMBT3906LT1G': {'1': 'B', '2': 'E', '3': 'C'},
    'LMR38020FDDAR': {'2': 'EN', '1': 'GND', '9': 'GND', '3': 'VIN', '5': 'FB'},
    'TPS552892QWRYQRQ1': {'11': 'VOUT', '12': 'ISP', '13': 'ISN', '7': 'VIN', '1': 'EN', '14': 'FB', '17': 'AGND'},
    'TPS16630PWPR': {'7': 'UVLO', '8': 'OVP', '13': 'SHDN', '18': 'OUT'},
    'BAV199LT1G': {'1': 'A', '2': 'K', '3': 'COM'},
}
NMOS = dict(vth=(1.0, 2.5), ileak=1e-6, gate_high=3.3 * 1.02)
PNP = dict(hfe_min=60.0, vcesat=0.25, veb_off=0.35, veb_on=(0.6, 0.85), ileak=5e-6)
EN_U4 = dict(on_max=1.4, off_min=0.95)
R_TOL = {'0.1%': (.999 * .9975, 1.001 * 1.0025)}           # 0.1 % + 25 ppm x 100 C; default 1 % + 1 % TCR
R_TOL_DEFAULT = (.99 * .99, 1.01 * 1.01)


def parse_value(s):
    s = s.strip()
    mult = {'k': 1e3, 'M': 1e6, 'u': 1e-6, 'n': 1e-9, 'm': 1e-3}
    return float(s[:-1]) * mult[s[-1]] if s[-1] in mult else float(s)


class Design:
    """pins {(ref, pin): short net name or None}, values {ref: str}, fields {ref: {name: value}}."""

    def __init__(self, pins, values, fields):
        self.pins, self.values, self.fields = pins, values, fields
        self.nets = {}
        for key, net in pins.items():
            if net is not None:
                self.nets.setdefault(net, set()).add(key)

    @classmethod
    def from_xml(cls, path):
        root = ET.parse(path).getroot()
        pins, values, fields = {}, {}, {}
        for c in root.findall('components/comp'):
            ref = c.get('ref')
            values[ref] = c.findtext('value')
            fields[ref] = {f.get('name'): f.text or '' for f in c.findall('fields/field')}
        for n in root.findall('nets/net'):
            name = n.get('name')
            short = None if name.startswith('unconnected-') else name.split('/')[-1]
            if short and short.startswith('Net-('):
                short = name                          # unnamed local net: keep the unique full name
            for d in n.findall('node'):
                pins[(d.get('ref'), d.get('pin'))] = short
        return cls(pins, values, fields)

    @classmethod
    def from_table(cls, parts):
        pins, values, fields = {}, {}, {}
        for p in parts:
            if p['ref'].startswith('#'):
                continue
            values[p['ref']] = p['value']
            fields[p['ref']] = dict(p['fields'])
            for n, net in p['pins'].items():
                pins[(p['ref'], n)] = net
        return cls(pins, values, fields)

    def mpn(self, ref):
        return self.fields.get(ref, {}).get('MPN') or self.values.get(ref)

    def net(self, ref, pin):
        return self.pins.get((ref, str(pin)))

    def value(self, ref):
        return parse_value(self.values[ref])

    def tol(self, ref):
        return R_TOL.get(self.fields.get(ref, {}).get('Tolerance'), R_TOL_DEFAULT)

    def refs_by_mpn(self, mpn):
        return sorted(r for r in self.values if self.mpn(r) == mpn)

    def role_pin(self, ref, role):
        table = ROLES[self.mpn(ref)]
        return next(p for p, r in table.items() if r == role)

    def on_net(self, net):
        """[(ref, pin)] of electrical parts on a net (test pads and flags are copper/ERC only)."""
        return sorted(k for k in self.nets.get(net, ()) if not k[0].startswith(('TP', '#')))

    def resistors_on(self, net):
        out = []
        for ref, pin in self.on_net(net):
            if ref.startswith('R') and len([k for k in self.pins if k[0] == ref]) == 2:
                other = self.net(ref, '2' if pin == '1' else '1')
                out.append((ref, other))
        return out


# ---------------------------------------------------------------------------------------------------------------------
# U4 enable network: structure extracted from the design, then bounded over every input combination and tolerance.
# ---------------------------------------------------------------------------------------------------------------------
def enable_structure(d):
    """Trace the U4 EN network from the netlist. Raises AssertionError for an unmodelled structure."""
    u4 = d.refs_by_mpn('LMR38020FDDAR')
    assert len(u4) == 1, ('one LMR38020 expected', u4)
    u4 = u4[0]
    en = d.net(u4, d.role_pin(u4, 'EN'))
    gnd_ic = d.net(u4, d.role_pin(u4, 'GND'))
    en_parts = [k for k in d.on_net(en) if k[0] != u4]
    assert all(r.startswith('R') for r, _ in en_parts), ('EN net: only resistors expected', en_parts)
    to_gnd = [(r, o) for r, o in d.resistors_on(en) if o == gnd_ic]
    to_drive = [(r, o) for r, o in d.resistors_on(en) if o != gnd_ic]
    assert len(to_gnd) == 1 and len(to_drive) == 1, ('EN divider expected', to_gnd, to_drive)
    r_bot, (r_top, c_net) = to_gnd[0][0], to_drive[0]
    pnps = [r for r, p in d.on_net(c_net) if d.mpn(r) == 'MMBT3906LT1G' and d.role_pin(r, 'C') == p]
    assert len(pnps) == 1, ('one PNP collector on the EN divider top expected', d.on_net(c_net))
    q = pnps[0]
    e_net, b_net = d.net(q, d.role_pin(q, 'E')), d.net(q, d.role_pin(q, 'B'))
    pullups = [r for r, o in d.resistors_on(b_net) if o == e_net]
    sinks = [(r, o) for r, o in d.resistors_on(b_net) if o != e_net]
    others = [k for k in d.on_net(b_net) if k[0] != q and k[0] not in pullups and k[0] not in [s for s, _ in sinks]]
    assert not others, ('unmodelled part on the PNP base', others)
    chains = []
    for r_sink, node in sinks:
        chain, defaults, cur, seen = [], {}, node, set()
        while cur not in ('GND',) and cur not in seen:
            seen.add(cur)
            devs = [rr for rr, pp in d.on_net(cur) if d.mpn(rr) == '2N7002' and d.role_pin(rr, 'D') == pp]
            res = [(rr, o) for rr, o in d.resistors_on(cur) if rr != r_sink]
            if cur != node:
                defaults[cur] = [(rr, o) for rr, o in res]
            if not devs:
                break
            assert len(devs) == 1, ('one NMOS per chain node expected', cur, devs)
            m = devs[0]
            chain.append({'ref': m, 'drain': cur, 'gate': d.net(m, d.role_pin(m, 'G')),
                          'source': d.net(m, d.role_pin(m, 'S'))})
            cur = chain[-1]['source']
        chains.append({'R': r_sink, 'top': node, 'end': cur, 'nmos': chain, 'defaults': defaults})
    return {'U4': u4, 'EN': en, 'U4_GND': gnd_ic, 'R_top': r_top, 'R_bot': r_bot, 'PNP': q, 'emitter': e_net,
            'base': b_net, 'pullups': pullups, 'sinks': chains}


def _sources(own, run, main, p12, bus, vpd):
    """Scenario voltages of the nets the enable network may touch (any other boundary net is unmodelled). S9.3: P12_OK is
    the U18 delivered-+12V monitor (open collector, pull-up from V3V3): high only with own input (V3V3 alive) and +12V
    above its threshold, whether the converter or a live bus holds it there."""
    return {'GND': 0.0, 'VPD': vpd if own else 0.0, 'V3V3': 3.3 if own else 0.0,
            'RUN': NMOS['gate_high'] if run else 0.0, 'MAIN_LED_OK': NMOS['gate_high'] if main else 0.0,
            'P12_OK': NMOS['gate_high'] if own and p12 else 0.0,
            '-12V': -12.6 if bus else 0.0, '+12V': 12.6 if bus else (12.08 if own and main else 0.0),
            'VIN': (vpd - 1.0) if own and main else 0.0}


def sequencing(d, s=None):
    """S9.3: the RC-delayed gate of a switch in the U4 enable sink chain, traced from the netlist. A gate net that holds
    exactly one resistor (to its source net), one capacitor to GND and the switch gate is a delayed copy of the source
    net; the source must be pulled up from V3V3 (open-collector monitor). Returns None when no chain switch has one.
    tau_on = (pull-up + R) x C (the open collector releases), tau_off = R x C (it sinks), corners 1 % / 10 %."""
    s = s or enable_structure(d)
    for ch in s['sinks']:
        for m in ch['nmos']:
            g = m['gate']
            others = [k for k in d.on_net(g) if k[0] != m['ref']]
            res = d.resistors_on(g)
            caps = sorted({r for r, _ in others if r.startswith('C')})
            if len(res) != 1 or len(caps) != 1 or len(others) != 2:
                continue
            cref = caps[0]
            if 'GND' not in {d.net(cref, '1'), d.net(cref, '2')}:
                continue
            r, src_net = res[0]
            pull = [rr for rr, o in d.resistors_on(src_net) if o == 'V3V3']
            if len(pull) != 1:
                continue
            rv, cv, pv = d.value(r), d.value(cref), d.value(pull[0])
            return {'Q': m['ref'], 'gate': g, 'source': src_net, 'R': r, 'C': cref, 'pullup': pull[0],
                    'R_ohm': rv, 'C_F': cv, 'pullup_ohm': pv,
                    'tau_on_s': [(pv + rv) * cv * .98 * .9, (pv + rv) * cv, (pv + rv) * cv * 1.02 * 1.1],
                    'tau_off_s': [rv * cv * .98 * .9, rv * cv, rv * cv * 1.02 * 1.1]}
    return None


def _chain_bound(ch, src, v_e, lo):
    """(full_sink, max off-state sink current, undefined nodes) of one sink chain for the scenario sources.
    A switch with gate >= VGS(th) max (source at ~0 V) is fully on; gate <= VGS(th) min is off (leakage only). Switches
    above an open one act as source followers: their source node is <= their gate voltage, so the chain current is
    bounded by that node's default resistors. A chain node with no default whose lower switch is not fully on has
    no DC definition (leakage only) and is reported."""
    gates = []
    for m in ch['nmos']:
        assert m['gate'] in src, ('unmodelled NMOS gate net', m['gate'])
        gates.append(src[m['gate']])
    for r, o in ch['defaults'].get(ch['top'], []):
        assert o in src, ('unmodelled default target', r, o)
    i = sum(max(0.0, v_e - src[o]) / lo(r) for r, o in ch['defaults'].get(ch['top'], []))    # bypass of the switches
    if ch['end'] != 'GND' and ch['end'] not in src:
        return False, i, [f"chain ends on {ch['end']}"]
    if ch['nmos'] and all(g >= NMOS['vth'][1] for g in gates):
        return True, i, []
    if not ch['nmos']:
        return True, i, []                                          # resistor straight to a source: unqualified sink
    v_cap, floating = v_e, []
    for j, m in enumerate(ch['nmos']):
        off = gates[j] <= NMOS['vth'][0]
        if off:
            i += NMOS['ileak']
        else:
            v_cap = min(v_cap, gates[j])
        node = m['source']
        if node == 'GND' or node in src:
            break
        dflt = ch['defaults'].get(node, [])
        lower_not_on = j + 1 < len(gates) and gates[j + 1] < NMOS['vth'][1]
        if not dflt and lower_not_on:
            floating.append(f"{node} (no DC default while {ch['nmos'][j + 1]['ref']} is off)")
        if off:
            break
        for r, o in dflt:
            assert o in src, ('unmodelled default target', r, o)
            i += max(0.0, v_cap - src[o]) / lo(r)
    return False, i, floating


def enable_model(d, vpd_corners=(12.26, 16.5, 19.44)):
    """Truth table of U4 enable from the extracted structure. For every (own input, RUN, MAIN_LED_OK, live bus) row and
    VPD corner: Q1 off-bound (sink current x pull-up), full-sink saturation check, EN relative to the U4 ground with
    resistor tolerances, node definition. Required: enabled iff own AND RUN AND MAIN_LED_OK, never undefined."""
    s = enable_structure(d)
    seq = sequencing(d, s)
    val = d.value
    lo = lambda r: val(r) * d.tol(r)[0]      # noqa: E731
    hi = lambda r: val(r) * d.tol(r)[1]      # noqa: E731
    r_pu_lo = 1 / sum(1 / lo(r) for r in s['pullups']) if s['pullups'] else math.inf
    r_pu_hi = 1 / sum(1 / hi(r) for r in s['pullups']) if s['pullups'] else math.inf
    rows, violations = [], []
    for own, run, main, p12, bus in itertools.product((False, True), repeat=5):
        states, floating = set(), set()
        en_lo, en_hi, veb_max = math.inf, -math.inf, 0.0
        for vpd in vpd_corners:
            src = _sources(own, run, main, p12, bus, vpd)
            if seq is not None:
                src[seq['gate']] = src[seq['source']]      # settled RC: the delayed gate follows its source
            for net in (s['emitter'], s['U4_GND']):
                assert net in src, ('unmodelled drive net', net)
            v_e, v_g4 = src[s['emitter']], src[s['U4_GND']]
            full_r, i_off = [], 0.0
            for ch in s['sinks']:
                full, i, fl = _chain_bound(ch, src, v_e, lo)
                floating |= set(fl)
                if full:
                    full_r.append(hi(ch['R']))
                i_off += i
            if full_r and v_e > PNP['veb_on'][0]:
                r_s = min(full_r)
                i_b = (v_e - PNP['veb_on'][1]) / r_s - PNP['veb_on'][1] / r_pu_lo - i_off * 0
                i_c = (v_e - PNP['vcesat'] - v_g4) / (lo(s['R_top']) + lo(s['R_bot']))
                if i_c > 0 and i_b * PNP['hfe_min'] >= i_c:
                    state = 'on'
                    e_lo = (v_e - PNP['vcesat'] - v_g4) * lo(s['R_bot']) / (hi(s['R_top']) + lo(s['R_bot']))
                    e_hi = (v_e - v_g4) * hi(s['R_bot']) / (lo(s['R_top']) + hi(s['R_bot']))
                else:
                    state, e_lo, e_hi = 'uncertain', 0.0, max(0.0, (v_e - v_g4)) * hi(s['R_bot']) / (lo(s['R_top']) + hi(s['R_bot']))
            else:
                veb = 0.0 if v_e <= 0 else i_off * r_pu_hi
                veb_max = max(veb_max, veb)
                if veb <= PNP['veb_off']:
                    state, e_lo, e_hi = 'off', 0.0, PNP['ileak'] * hi(s['R_bot'])
                else:
                    state, e_lo, e_hi = 'uncertain', 0.0, max(0.0, v_e - v_g4)
            states.add(state)
            en_lo, en_hi = min(en_lo, e_lo), max(en_hi, e_hi)
        if states == {'on'} and en_lo >= EN_U4['on_max']:
            enabled = True
        elif states == {'off'} and en_hi <= EN_U4['off_min']:
            enabled = False
        else:
            enabled = 'undefined'
        rows.append({'own_input': own, 'run': run, 'main_status': main, 'p12_good': p12, 'bus_live': bus,
                     'U4_enabled': enabled,
                     'Q1': sorted(states), 'EN_relative_V': [round(en_lo, 3), round(en_hi, 3)],
                     'Q1_VEB_off_bound_V': round(veb_max, 4), 'undefined_nodes': sorted(floating)})
        required = own and run and main and p12
        tag = f'own={own} run={run} main={main} p12={p12} bus={bus}'
        if enabled != required:
            violations.append(f'{tag}: U4_enabled={enabled}, required {required}')
        if floating:
            violations.append(f'{tag}: undefined node {sorted(floating)}')
    return {'structure': {k: v for k, v in s.items() if k != 'sinks'} | {
                'sink_chains': [{'R': ch['R'], 'series_nmos': [[m['ref'], m['gate']] for m in ch['nmos']], 'end': ch['end'],
                                 'node_defaults': {n: [r for r, _ in v] for n, v in ch['defaults'].items()}}
                                for ch in s['sinks']],
                'sequencing': None if seq is None else {k: seq[k] for k in ('Q', 'gate', 'source', 'R', 'C', 'pullup')}},
            'truth_table': rows, 'violations': violations, 'pass': not violations,
            'off_VEB_max_V': max(r['Q1_VEB_off_bound_V'] for r in rows),
            'method': ('Structure traced from the design connectivity (LMR38020 EN pin -> divider -> PNP collector -> base '
                       'pull-ups and series NMOS sink chain -> GND; S9.3: the RC-delayed P12_OK gate of the top switch, '
                       'evaluated settled); bounds over VPD 12.26/16.5/19.44 V, resistor '
                       'tolerance + TCR, NMOS VGS(th) 1.0-2.5 V with 1 uA leakage, PNP hFE >= 60, VEB <= 0.35 V off and '
                       '5 uA leakage. With a switch open the switches above it are source followers (node <= gate), so '
                       'the chain current is bounded by the node defaults; a chain node with no DC default is undefined. '
                       'Required: U4 enabled iff own input AND RUN AND MAIN_LED_OK AND +12V good (P12_OK).')}


# ---------------------------------------------------------------------------------------------------------------------
# 3 A startup plant parameters, all from the design connectivity.
# ---------------------------------------------------------------------------------------------------------------------
def _series_to(d, start, end, skip):
    """Series resistor path start -> end through two-member intermediate nets; returns [refs] or None."""
    path, cur, prev = [], start, skip
    for _ in range(6):
        res = [(r, o) for r, o in d.resistors_on(cur) if r not in prev]
        if not res:
            return None
        if len(res) != 1:
            return None
        r, o = res[0]
        path.append(r)
        prev = set(prev) | {r}
        if o == end:
            return path
        cur = o
    return None


def divider(d, ic_ref, role, top_net):
    """Top/bottom resistor sets of a pin's divider (top to top_net, bottom to GND), from connectivity."""
    pin_net = d.net(ic_ref, d.role_pin(ic_ref, role))
    tops = [r for r, o in d.resistors_on(pin_net) if o == top_net]
    if not tops:                                          # series top (e.g. R28 + R4 via _OV_TOP)
        for r, o in d.resistors_on(pin_net):
            path = _series_to(d, o, top_net, {r})
            if path is not None:
                tops = [r] + path
                break
    bottom = None
    for r, o in d.resistors_on(pin_net):
        if r in tops:
            continue
        bottom = [r] if o == 'GND' else ([r] + (_series_to(d, o, 'GND', {r}) or []))
    return {'pin_net': pin_net, 'top': tops, 'bottom': bottom}


def threshold_band(d, div, v_th, leak=150e-9):
    """(min, nom, max) VPD-referred threshold of a TPS1663 comparator divider over resistor tolerances and leakage."""
    t = [d.value(r) for r in div['top']]
    b = [d.value(r) for r in div['bottom']]
    tlo = sum(d.value(r) * d.tol(r)[0] for r in div['top'])
    thi = sum(d.value(r) * d.tol(r)[1] for r in div['top'])
    blo = sum(d.value(r) * d.tol(r)[0] for r in div['bottom'])
    bhi = sum(d.value(r) * d.tol(r)[1] for r in div['bottom'])
    return [v_th[0] * (1 + tlo / bhi) - leak * thi, v_th[1] * (1 + sum(t) / sum(b)), v_th[2] * (1 + thi / blo) + leak * thi]


def current_limit(d):
    """+12V output current limit from the U2 ISP/ISN connectivity: the part bridging the two sense nets is the shunt and
    must sit in the force path VOUT -> +12V. ISP and ISN on one net (or no shunt between them) = CC disabled."""
    u2 = d.refs_by_mpn('TPS552892QWRYQRQ1')
    assert len(u2) == 1, u2
    u2 = u2[0]
    isp, isn, vout = (d.net(u2, d.role_pin(u2, r)) for r in ('ISP', 'ISN', 'VOUT'))
    out = {'ISP_net': isp, 'ISN_net': isn, 'VOUT_net': vout}
    if isp == isn:
        return {**out, 'limited': False, 'why': 'ISP and ISN on one net: TPS552892 output current limit disabled'}
    shunts = sorted({r for r, _ in d.on_net(isp)} & {r for r, _ in d.on_net(isn)} - {u2})
    if len(shunts) != 1:
        return {**out, 'limited': False, 'why': f'no single shunt between ISP and ISN ({shunts})'}
    r = shunts[0]
    pins = {p: d.net(r, p) for (rr, p) in d.pins if rr == r}
    force = sorted(n for n in pins.values() if n not in (isp, isn))
    kelvin = len(pins) == 4
    in_path = (vout in pins.values()) and ('+12V' in pins.values())
    rv = d.value(r)
    tcr = float((d.fields[r].get('TCR') or '75ppm').removesuffix('ppm')) * 1e-6
    tol = float((d.fields[r].get('Tolerance') or '1%').removesuffix('%')) / 100
    resid = 0.002 if kelvin else 0.0
    r_lo, r_hi = rv * (1 - tol) * (1 - tcr * 100) * (1 - resid), rv * (1 + tol) * (1 + tcr * 100) * (1 + resid)
    return {**out, 'limited': in_path, 'shunt': r, 'kelvin_4_terminal': kelvin, 'force_nets': force,
            'R_ohm': rv, 'icc_A': [0.048 / r_hi, 0.050 / rv, 0.052 / r_lo],
            'why': 'VSNS 48-52 mV over the shunt (tolerance, TCR x 100 C, Kelvin residual)' if in_path
                   else 'shunt not in the VOUT -> +12V force path'}


def banks(d):
    """Capacitor counts (C1206 22u / 10u) to GND on the converter nets, from connectivity."""
    def count(net, value):
        return sorted(r for r, p in d.on_net(net) if r.startswith('C') and d.values.get(r) == value
                      and 'GND' in {d.net(r, '1'), d.net(r, '2')})
    return {'P12_VOUT': count('P12_VOUT', '22u'), '+12V': count('+12V', '22u'),
            '-12V': count('-12V', '22u'), 'VIN': count('VIN', '10u')}


# S9.3 soft-start data per converter (internal reference ramp, reference band) and the injection-part screens.
SS_IC = {
    'TPS552892QWRYQRQ1': dict(vref=(1.188, 1.2, 1.212), tss_ms=(2.5, 3.6, 5.0),
                              source='TI SLVSGT7 6.5: tSS 2.5/3.6/5 ms, VREF 1.188-1.212 V (no SS pin)'),
    'LMR38020FDDAR': dict(vref=(0.985, 1.0, 1.015), tss_ms=(2.0, 4.0, 6.0),
                          source='TI SNVSC40E 7.5: tSS 4 ms typical only (no min/max): 2-6 ms screen; VREF 0.985-1.015 V'),
}
# Css: X7R 0603 25 V (CL10B474KA8NNNC) at up to 12 V: +-10 % tolerance, DC-bias retention 0.45-1.0 (engineering screen,
# not a manufacturer minimum), X7R +-15 % over temperature, 7 % ageing. Injection-diode drop: BAV199 at 10-200 uA.
CSS_SCREEN = dict(tol=0.10, bias=(0.45, 1.0), temp=(0.85, 1.15), aging=(0.93, 1.0))
VD_INJ_V = (0.45, 0.6, 0.9)
D10_DROP_V = 0.75                 # SS1060 screen at 3-5 A (s8_calcs INPUT_PATH; the S9.2 plant used 0.6 V)
AUX_W = 0.5                       # always-on logic, LDO, monitors from VPD (before D10/U5)


def css_corners(c):
    k = CSS_SCREEN
    return [c * (1 - k['tol']) * k['bias'][0] * k['temp'][0] * k['aging'][0], c, c * (1 + k['tol']) * k['bias'][1]
            * k['temp'][1] * k['aging'][1]]


def soft_start_network(d, ic):
    """S9.3: the FB-injection soft start of converter `ic`, traced from the netlist. A BAV199 pair with its cathode (K)
    on the FB net injects from node X (COM); its anode (A) is the clamp reference. Css runs from X to the output side of
    the FB divider (the net of the FB resistor that is not the IC ground side), the bleed resistor from X to the clamp
    reference. Returns the network with tau = Rtop x Css corners, or None (bare internal soft start)."""
    fb = d.net(ic, d.role_pin(ic, 'FB'))
    data = SS_IC[d.mpn(ic)]
    k = [r for r, p in d.on_net(fb) if d.mpn(r) == 'BAV199LT1G' and d.role_pin(r, 'K') == p]
    fb_res = d.resistors_on(fb)
    if len(k) != 1 or len(fb_res) != 2:
        return None
    dio = k[0]
    x, clamp = d.net(dio, d.role_pin(dio, 'COM')), d.net(dio, d.role_pin(dio, 'A'))
    caps = [(r, d.net(r, '2' if d.net(r, '1') == x else '1')) for r, _ in d.on_net(x) if r.startswith('C')]
    top = [(r, o) for r, o in fb_res if any(o == co for _, co in caps)]
    bleed = [r for r, o in d.resistors_on(x) if o == clamp]
    if len(caps) != 1 or len(top) != 1 or len(bleed) != 1:
        return None
    css, out = caps[0]
    rtop = top[0][0]
    rbot = next(r for r, _ in fb_res if r != rtop)
    c = css_corners(d.value(css))
    vset = data['vref'][1] * (1 + d.value(rtop) / d.value(rbot))
    return {'IC': ic, 'FB': fb, 'diode': dio, 'X': x, 'clamp': clamp, 'Css': css, 'out_net': out, 'bleed': bleed[0],
            'R_top': rtop, 'R_bot': rbot, 'R_top_ohm': d.value(rtop), 'R_bot_ohm': d.value(rbot),
            'bleed_ohm': d.value(bleed[0]), 'Css_F': c, 'vref_V': list(data['vref']), 'tss_ms': list(data['tss_ms']),
            'setpoint_V': vset, 'tau_ms': [d.value(rtop) * cc * 1e3 for cc in c],
            'initial_charge_rate_V_per_ms': [vset / (d.value(rtop) * cc * 1e3) for cc in c], 'source': data['source']}


def startup_params(d):
    """Everything the 3 A startup plant needs, derived from the design. S9.3: the soft-start networks and the U4
    sequencing gate."""
    u5 = d.refs_by_mpn('TPS16630PWPR')[0]
    uv, ov = divider(d, u5, 'UVLO', 'VPD'), divider(d, u5, 'OVP', 'VPD')
    u2, u4 = d.refs_by_mpn('TPS552892QWRYQRQ1')[0], d.refs_by_mpn('LMR38020FDDAR')[0]
    return {'U5': u5, 'UVLO_divider': uv, 'OVP_divider': ov,
            'U5_on_V': threshold_band(d, uv, (1.176, 1.2, 1.224)), 'U5_off_V': threshold_band(d, uv, (1.09, 1.122, 1.15)),
            'OVP_rise_V': threshold_band(d, ov, (1.176, 1.2, 1.224)), 'OVP_fall_V': threshold_band(d, ov, (1.09, 1.122, 1.15)),
            'current_limit': current_limit(d), 'banks': banks(d),
            'U5_SHDN_net': d.net(u5, d.role_pin(u5, 'SHDN')), 'U2_EN_net': d.net(u2, d.role_pin(u2, 'EN')),
            'soft_start': {'+12V': soft_start_network(d, u2), '-12V': soft_start_network(d, u4)},
            'sequencing': sequencing(d)}


class SoftStart:
    """Commanded output of one converter during start-up. Without an injection network: the internal reference ramp
    (setpoint x t / tSS). With the S9.3 FB injection (Css from the output to X, diode X -> FB with drop vd, bleed rb from X
    to the divider ground, clamp diode ground -> X): while the diode conducts the error amplifier holds FB at the ramping
    reference, so Css*d(Vout - X)/dt = (Vset(t) - Vout)/Rtop + X/Rb with X = Vref(t) + vd; otherwise the output follows
    Vset(t) up to Vc + Vref + vd. Disabled: Css discharges through the clamp as the output falls, X bleeds to 0 V."""

    def __init__(self, net, setpoint, tss_ms, fast):
        self.net, self.vset_end, self.tss = net, setpoint, tss_ms
        if net:
            self.css = net['Css_F'][0 if fast else 2]
            self.rtop, self.rb = net['R_top_ohm'], net['bleed_ohm']
            self.vd = VD_INJ_V[2 if fast else 0]
            self.vref = net['vref_V'][1]
        self.vc, self.y, self.t_on = 0.0, 0.0, None

    def target(self, t, enabled, v_out, h):
        n = self.net
        if not enabled:
            self.t_on = None
            if n:
                x = v_out - self.vc
                if x < -0.6:
                    self.vc = v_out + 0.6                       # clamp diode empties Css as the rail falls
                elif x > 0:
                    self.vc += x / self.rb / self.css * h * 1e-3
            self.y = v_out
            return None
        if self.t_on is None:
            self.t_on, self.y = t, v_out
        frac = min(1.0, (t - self.t_on) / self.tss)
        vset = self.vset_end * frac
        if not n:
            return vset
        vref = self.vref * frac
        xlim = vref + self.vd
        if v_out < self.y - 0.05:                               # output held back (current limit): follow the rail
            self.y = v_out
            self.vc = min(self.vc, v_out - xlim) if v_out - self.vc > xlim else self.vc
        x = self.y - self.vc
        if x >= xlim - 1e-9 and self.y < vset:                  # injection diode conducts
            self.vc += ((vset - self.y) / self.rtop + xlim / self.rb) / self.css * h * 1e-3
            self.y = self.vc + xlim
        else:
            if x > 0:
                self.vc += min(x, xlim) / self.rb / self.css * h * 1e-3
            self.y = min(vset, self.vc + xlim)
        return self.y


class PhysicalStartup:
    """Netlist-parameterised energy-balance plant of the input path for the 3 A source scenarios (S1). A USB PD source
    with open-circuit voltage v_cv, cable resistance r_cable and a STRICT constant-current limit source_A (no overload
    allowance) feeds VPD -> D10 (0.75 V screen) -> U5 -> VIN; the 0.5 W always-on logic draws from VPD and counts against
    the source limit. U5: UVLO/hysteresis from the netlist divider (worst-case HIGH corners: latest turn-on, earliest
    turn-off), 1.83 ms turn-on delay, 2.27 V/ms dVdT ramp, 9-16 us turn-off. Converters as power sinks: +12V follows its
    commanded output (SoftStart: the netlist FB-injection network, or the bare internal tSS ramp when the netlist has
    none), output current clamped by the netlist R109 limit (icc max corner; no shunt between ISP/ISN = only the 9 A
    inductor limit); -12V the same with the LMR38020 limit (ILS 2.8 A + ripple/2)(1-D); both stop below their VIN UVLO
    and restart their soft start on recovery. S9.3: U4 additionally waits for the netlist sequencing gate (RC from the
    P12_OK monitor, threshold band and Q16 VGS(th) at the corner). corner 'fast' = shortest tSS, smallest Css, earliest
    sequencing, lowest monitor threshold (largest and most overlapping charge currents); 'slow' = the opposite (latest
    rails). Loads resistive or constant current at the published split, rack 0.44 mF per rail, onboard banks at the
    cap-study HIGH corner (largest charge), VIN bank at the LOW corner (least hold-up). Efficiencies 0.93 / 0.85. A
    screen, not a device-accurate model."""

    def __init__(self, params, eff, i12=2.4, in12=0.33, source_A=3.0, r_cable=0.25, rack_F=0.44e-3, corner='fast',
                 load='resistive', p12_ok_V=None):
        fast = corner == 'fast'
        cl = params['current_limit']
        self.icc = cl['icc_A'][2] if cl['limited'] else 9.0
        self.on_V, self.off_V = params['U5_on_V'][2], params['U5_off_V'][2]
        self.c_vin = eff['VIN'][0] + eff['damper'][0]
        self.c12, self.cn = eff['+12V'][1] + rack_F, eff['-12V'][1] + rack_F
        self.i12, self.in12, self.load = i12, in12, load
        self.r12 = 12.08 / i12 if i12 else math.inf
        self.rn = 11.989 / in12 if in12 else math.inf
        self.src_A, self.r_cable = source_A, r_cable
        ss = params.get('soft_start') or {}
        self.ss12 = SoftStart(ss.get('+12V'), 12.08, SS_IC['TPS552892QWRYQRQ1']['tss_ms'][0 if fast else 2], fast)
        self.ssn = SoftStart(ss.get('-12V'), 11.989, SS_IC['LMR38020FDDAR']['tss_ms'][0 if fast else 2], fast)
        self.seq = params.get('sequencing')
        if self.seq:
            self.seq_v3 = 3.3 * (1.02 if fast else 0.98)
            self.seq_tau = (self.seq['tau_on_s'][0 if fast else 2] * 1e3, self.seq['tau_off_s'][0 if fast else 2] * 1e3)
            self.seq_vth = NMOS['vth'][0 if fast else 1]
        self.p12_ok_V = p12_ok_V if p12_ok_V is not None else 9.98
        self.vg = 0.0
        self.vin = self.v12 = self.vn = 0.0
        self.u5 = False; self.u5_t = None; self.ramp = False; self.full = False
        self.run12 = self.runn = False
        self.peak_demand_A = 0.0; self.t_over_A = 0.0; self.dropouts = 0; self.i_src = 0.0; self.i_u5 = 0.0
        self.t_p12 = self.t_u4 = None
        self.p12_charge_at_u4_A = None

    def _load(self, v, r, i):
        if self.load == 'constant_current':
            return i if v > 0.5 else 0.0
        return v / r

    def step(self, t_ms, dt_ms, powered, v_cv, run, en12, enn):
        h = 0.01                                               # ms sub-step
        r_ser, drop = self.r_cable + 0.053, D10_DROP_V
        for k in range(int(round(dt_ms / h))):
            t = t_ms + k * h
            v_src = v_cv if powered else 0.0
            i_aux = AUX_W / max(v_src, 1.0) if powered and v_src > 4.0 else 0.0
            v0 = max(0.0, v_src - drop - i_aux * self.r_cable)
            # S9.3 sequencing: P12_OK (U18 monitor) -> R/C -> Q16 gate; U4 needs the logic enables AND the gate
            p12_ok = powered and self.v12 >= self.p12_ok_V
            if p12_ok and self.t_p12 is None:
                self.t_p12 = t
            seq_on = True
            if self.seq:
                tau = self.seq_tau[0] if p12_ok else self.seq_tau[1]
                self.vg += ((self.seq_v3 if p12_ok else 0.0) - self.vg) * (1 - math.exp(-h / tau))
                seq_on = self.vg >= self.seq_vth
            self.run12 = en12 and self.vin >= (2.6 if self.run12 else 3.0)
            was_n = self.runn
            self.runn = enn and seq_on and self.vin >= (3.7 if self.runn else 4.2)
            y12 = self.ss12.target(t, self.run12, self.v12, h)
            l12 = self._load(self.v12, self.r12, self.i12)
            i12 = min(self.icc, max(0.0, l12 + self.c12 * (y12 - self.v12) / 0.2e-3)) if self.run12 else 0.0
            if self.runn and not was_n and self.t_u4 is None:
                self.t_u4 = t
                self.p12_charge_at_u4_A = round(max(0.0, i12 - l12), 4) if self.run12 else 0.0
            yn = self.ssn.target(t, self.runn, self.vn, h)
            ln = self._load(self.vn, self.rn, self.in12)
            if self.runn:
                dd = max(self.vn, 1.0) / (max(self.vin, 1.0) + max(self.vn, 1.0))
                ilim = (2.8 + self.vin * dd / (15e-6 * 0.79e6) / 2) * (1 - dd)
                inn = min(ilim, max(0.0, ln + self.cn * (yn - self.vn) / 0.2e-3))
            else:
                inn = 0.0
            p_in = self.v12 * i12 / 0.93 + self.vn * inn / 0.85
            i_conv = p_in / max(self.vin, 2.0)
            lim_u5 = max(0.0, self.src_A - i_aux)                # the source limit covers U5 AND the logic
            # U5 state from the VPD it sees: open-circuit when off, the loaded node when on
            if not self.u5 or self.ramp:
                vpd = v_src - (self.i_u5 + i_aux) * self.r_cable
            else:
                vpd = min(v_src - (self.i_u5 + i_aux) * self.r_cable, self.vin + drop + self.i_u5 * 0.053)
            if self.u5 and (not run or not powered or vpd < self.off_V):
                self.u5, self.ramp, self.full, self.u5_t = False, False, False, None
                self.dropouts += 1
            if not self.u5:
                vpd_open = v_src - i_aux * self.r_cable
                if run and powered and vpd_open >= self.on_V:
                    self.u5_t = t if self.u5_t is None else self.u5_t
                    if t - self.u5_t >= 1.83:
                        self.u5, self.ramp = True, True
                else:
                    self.u5_t = None
            if self.u5:
                # CV operating point for this load: VIN^2 - v0 VIN + R P = 0 (upper root), if within the CC limit
                disc = v0 * v0 - 4 * r_ser * p_in
                vin_cv = (v0 + math.sqrt(disc)) / 2 if disc >= 0 else 0.0
                i_cv = (v0 - vin_cv) / r_ser if disc >= 0 else math.inf
                if self.ramp:
                    want = self.c_vin * 2.27e3 + i_conv
                    self.i_u5 = min(want, lim_u5, 4.7)
                    self.vin = min(self.vin + (self.i_u5 - i_conv) / self.c_vin * h * 1e-3, vin_cv if disc >= 0 else self.vin)
                    if disc >= 0 and self.vin >= vin_cv - 0.05:
                        self.ramp, self.full = False, True
                elif disc >= 0 and i_cv <= lim_u5 and self.vin >= vin_cv - 0.05:
                    self.vin, self.i_u5 = vin_cv, i_cv                              # constant voltage
                else:
                    avail = min(lim_u5, max(0.0, (v0 - self.vin) / r_ser))        # current limit / recovery
                    self.i_u5 = avail
                    self.vin = max(0.0, self.vin + (avail - i_conv) / self.c_vin * h * 1e-3)
                    if disc >= 0:
                        self.vin = min(self.vin, vin_cv)
                self.vin = max(0.0, self.vin)
            else:
                self.i_u5 = 0.0
                self.vin = max(0.0, self.vin - i_conv / self.c_vin * h * 1e-3)
            self.i_src = self.i_u5 + i_aux
            if self.u5:
                need = (p_in + AUX_W) / max(v_src - drop, 1.0)
                self.peak_demand_A = max(self.peak_demand_A, need)
                if need > self.src_A:
                    self.t_over_A += h
            self.v12 = max(0.0, self.v12 + (i12 - self._load(self.v12, self.r12, self.i12)) / self.c12 * h * 1e-3)
            self.vn = max(0.0, self.vn + (inn - self._load(self.vn, self.rn, self.in12)) / self.cn * h * 1e-3)
        vpd = ((min(v_cv - self.i_src * self.r_cable, self.vin + drop + self.i_u5 * 0.053) if self.u5 and not self.ramp
                else v_cv - self.i_src * self.r_cable) if powered else 0.0)
        return {'vpd': vpd, 'vin': self.vin, 'v12': self.v12, 'vn12': self.vn, 'i_src': self.i_src, 'u5': self.u5,
                'fet_full': self.full, 'p12_ok': powered and self.v12 >= self.p12_ok_V, 'u4_on': self.runn,
                'u2_on': self.run12, 'seq_gate_V': self.vg}


def monitor_bands(d):
    """S9.3: U18 rail-monitor thresholds (P12_OK: +12V via R75/R76 against REF_GOOD = V3V3 x R74/(R73+R74); N12_OK: the
    REF_GOOD-offset -12V divider R80/R81/R82) over V3V3 +-2 %, the resistors at 1 % + 1 % TCR and the LM2901B 5.5 mV
    offset: (min, nom, max) in volts of rail magnitude."""
    v = d.value
    lo, hi = R_TOL_DEFAULT
    out = {'P12_OK_V': [], 'N12_OK_V': []}
    combos = list(itertools.product((0.98, 1.0, 1.02), (lo, 1.0, hi), (lo, 1.0, hi), (lo, 1.0, hi), (lo, 1.0, hi),
                                    (-0.0055, 0.0, 0.0055)))
    p12, n12 = [], []
    for v3, a73, a74, a75, a76, e in combos:
        r0 = 3.3 * v3 * v('R74') * a74 / (v('R73') * a73 + v('R74') * a74)
        p12.append((r0 + e) * (1 + v('R75') * a75 / (v('R76') * a76)))
        rs = v('R80') * a75 + v('R81') * a76
        n12.append(3.3 * v3 * v('R82') * a73 / rs - (r0 + e) * (1 + v('R82') * a73 / rs))
    r0n = 3.3 * v('R74') / (v('R73') + v('R74'))
    out['P12_OK_V'] = [min(p12), r0n * (1 + v('R75') / v('R76')), max(p12)]
    out['N12_OK_V'] = [min(n12), 3.3 * v('R82') / (v('R80') + v('R81')) - r0n * (1 + v('R82') / (v('R80') + v('R81'))),
                       max(n12)]
    return out


def plant_inputs(d):
    """Netlist-derived inputs of the 3 A plant: startup_params + bank effective capacitance (cap-study bias model) +
    rail-monitor thresholds (U18 dividers; nominal and band) + the U4 enable split into its logic gates and the S9.3
    sequencing gate (handled inside the plant)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'capacitor-study'))
    import cap_study as cs
    prm = startup_params(d)
    b = prm['banks']
    damp_net = d.net('R92', '2')
    n_damp = len([r for r, p in d.on_net(damp_net) if r.startswith('C') and 'GND' in {d.net(r, '1'), d.net(r, '2')}])
    eff = {'+12V': cs.mlcc(len(b['P12_VOUT']) + len(b['+12V']), 22, '22u25V_1206', 12.2),
           '-12V': cs.mlcc(len(b['-12V']), 22, '22u25V_1206', 12.2),
           'VIN': cs.mlcc(len(b['VIN']), 10, '10u50V_1206', 20.0), 'damper': cs.mlcc(max(n_damp, 0), 10, '10u50V_1206', 20.0)}
    bands = monitor_bands(d)
    chains = enable_structure(d)['sinks']
    seq = prm['sequencing']
    gates = sorted({m['gate'] for ch in chains for m in ch['nmos']} - ({seq['gate']} if seq else set())) \
        if all(ch['nmos'] for ch in chains) else ['V3V3']
    return {'params': prm, 'eff': eff, 'U4_gates': gates, 'U4_seq': seq,
            'P12_OK_V': bands['P12_OK_V'][1], 'N12_OK_V': bands['N12_OK_V'][1], 'monitor_bands': bands}
