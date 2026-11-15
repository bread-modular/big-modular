"""ngspice check of the DRIVE S1 circuit (docs/research.md section 4).

Run from modules/drive:  python3 -B tools/sim_drive.py [--no-plots]
Writes decks, logs and raw data into the ignored research/sim/ and the plots into docs/sim/.

The deck is generated from tools/build_schematic.py circuit(): every resistor, capacitor,
diode, transistor, op amp, OTA and pot is taken from the schematic netlist with its value, so
the simulated circuit is the drawn circuit. Models, not measurements:
- LM13700: one transistor-level half from the datasheet schematic (Wilson mirrors, differential
  pair, linearizing diodes) with generic NPN / lateral PNP models; buffers left out;
- TL072: one-pole macro model (3 MHz, 13 V/us, swing to 1.5 V from the rails, 1.4 mA per amp);
- SS8550: generic PNP (Vaf 40 V); 1N4148 and B5819W stock diode models;
- pots are two resistors, knob position 0 (CCW) .. 1 (CW); the power header is fed with +/-12 V.
"""
import argparse
import re
import subprocess
from pathlib import Path

import numpy as np

import build_schematic as S

MODULE = Path(__file__).resolve().parents[1]
OUT = MODULE / 'research' / 'sim'
PLOTS = MODULE / 'docs' / 'sim'

MODELS = r'''
.model QN NPN(Is=5f Bf=200 Vaf=100 Cje=1p Cjc=0.5p Tf=0.35n Rb=50)
.model QP PNP(Is=2f Bf=50 Vaf=50 Cje=1p Cjc=1p Tf=20n Rb=100)
.model QSS8550 PNP(Is=5.5e-14 Bf=250 Vaf=40 Ikf=1.5 Ise=2e-14 Ne=1.6 Br=10 Rb=5 Rc=0.3 Cje=45p Cjc=20p Tf=0.7n Tr=50n)
.model D4148 D(Is=2.52n Rs=0.568 N=1.752 Cjo=4p M=0.4 tt=20n)
.model D5819 D(Is=3e-6 Rs=0.05 N=1.05 Cjo=110p M=0.5 Bv=40)
.model DCL D(Is=1e-14 N=0.1)
* One half of an LM13700 (datasheet schematic; Darlington buffer omitted)
.subckt OTA IABC DB INP INN OUT VP VN
Q1 IABC n1 VN QN
Q2 TAIL IABC n1 QN
Q3 n1 n1 VN QN
Q4 C4 INN TAIL QN
Q5 C5 INP TAIL QN
Q6 C4 m1 VP QP
Q7 X C4 m1 QP
Q8 m1 m1 VP QP
Q9 C5 m2 VP QP
Q10 OUT C5 m2 QP
Q11 m2 m2 VP QP
Q12 X k1 VN QN
Q13 OUT X k1 QN
Q14 k1 k1 VN QN
Q15 DB DB INP QN
Q16 DB DB INN QN
.ends
* TL072-like op amp
.subckt OPA P N O VP VN
B1 0 x I=0.69m*tanh(V(P,N)*1m/0.69m)
R1 x 0 200Meg
C1 x 0 53p
Vh VP hi 1.5
Vl lo VN 1.5
D1 x hi DCL
D2 lo x DCL
E1 o1 0 x 0 1
Ro o1 O 100
Iq VP VN 1.4m
.ends
'''

KNOBS = {'RV1': 'drive', 'RV2': 'fold', 'RV3': 'tone', 'RV4': 'mix'}


def node(net, ref=None, pin=None):
    if net is None:
        return f'nc_{ref}_{pin}'
    if net == 'GND':
        return '0'
    return net.replace('+', 'P').replace('-', 'N')


def spice_value(v):
    return v[:-1] + 'Meg' if v.endswith('M') else v


def deck(drive=0.0, fold=0.0, tone=1.0, mix=1.0, vin='DC 0', dcv='DC 0', fcv='DC 0', replace=None, extra=''):
    """SPICE deck of circuit(). replace: {ref: line} swaps one part for a source line."""
    knob = dict(drive=drive, fold=fold, tone=tone, mix=mix)
    replace = replace or {}
    lines = ['* DRIVE ' + S.REV + ' (generated from tools/build_schematic.py circuit())', MODELS,
             'VP12 P12V_IN 0 12', 'VN12 N12V_IN 0 -12',
             f'VIN IN 0 {vin}', f'VDCV DCV 0 {dcv}', f'VFCV FCV 0 {fcv}', 'RLOAD OUT 0 100k']
    for p in S.circuit():
        ref, sym, pins = p['ref'], p['sym'], p['pins']
        if ref.startswith('#') or ref.startswith('J'):
            continue
        n = {k: node(v, ref, k) for k, v in pins.items()}
        if ref in replace:
            lines.append(replace[ref])
        elif sym == 'R':
            lines.append(f"R{ref} {n['1']} {n['2']} {spice_value(p['value'])}")
        elif sym == 'C':
            lines.append(f"C{ref} {n['1']} {n['2']} {p['value']}")
        elif sym == 'R_Potentiometer':
            x = min(max(knob[KNOBS[ref]], 1e-4), 1 - 1e-4)
            total = float(p['value'].replace('k', 'e3'))
            lines += [f"R{ref}a {n['3']} {n['2']} {total * (1 - x):.6g}", f"R{ref}b {n['2']} {n['1']} {total * x:.6g}"]
        elif sym == 'TL072' and p['unit'] in (1, 2):
            o, m, pl = {1: ('1', '2', '3'), 2: ('7', '6', '5')}[p['unit']]
            lines.append(f"X{ref}{'AB'[p['unit'] - 1]} {n[pl]} {n[m]} {n[o]} P12V N12V OPA")
        elif sym == 'LM13700' and p['unit'] in (1, 3):
            i, b, pl, m, o = {3: ('1', '2', '3', '4', '5'), 1: ('16', '15', '14', '13', '12')}[p['unit']]
            lines.append(f"X{ref}_{p['unit']} {n[i]} {n[b]} {n[pl]} {n[m]} {n[o]} P12V N12V OTA")
        elif sym == 'Q_PNP_BEC':
            lines.append(f"Q{ref} {n['3']} {n['1']} {n['2']} QSS8550")
        elif sym == '1N4148W':
            lines.append(f"D{ref} {n['2']} {n['1']} D4148")
        elif sym == 'D_Schottky':
            lines.append(f"D{ref} {n['2']} {n['1']} D5819")
        else:
            assert sym in ('TL072', 'LM13700'), (ref, sym)   # supply units, unused buffers
    return '\n'.join(lines) + '\n' + extra + '\n.end\n'


def run(name, text):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.cir').write_text(text)
    res = subprocess.run(['ngspice', '-b', str(OUT / f'{name}.cir')], capture_output=True, text=True)
    (OUT / f'{name}.log').write_text(res.stdout + res.stderr)
    return res.stdout + res.stderr


def kv(text):
    return {k: float(v) for k, v in re.findall(r'^(\S+)\s*=\s*([-+0-9.eE]+)', text, re.M)}


def data(name, cols):
    """wrdata file -> (x, [columns])."""
    a = np.loadtxt(OUT / f'{name}.dat')
    return a[:, 0], [a[:, 2 * i + 1] for i in range(cols)]


def db(x):
    return 20 * np.log10(max(x, 1e-12))


def gain_point(**kw):
    """Operating point + 220 Hz small-signal gains with the MIX knob fully wet."""
    t = run('gain', deck(vin='DC 0 AC 0.1', extra='''.control
op
print @qq2[ic] @rr27[i] @rr20[i] v(p12v) v(n12v) i(vp12) i(vn12) v(u) v(y) v(do) v(fe)
ac lin 1 220 220
print abs(v(u))/0.1 abs(v(out))/0.1 ph(v(out))*57.29578
.endc''', **kw))
    k = kv(t)
    return dict(iabc=-k['@qq2[ic]'], f=k['@rr27[i]'] / k['@rr20[i]'], icell=k['@rr27[i]'], i0=k['@rr20[i]'],
                gain=k['abs(v(out))/0.1'], gu=k['abs(v(u))/0.1'], phase=k['ph(v(out))*57.29578'],
                vp=k['v(p12v)'], vn=k['v(n12v)'], ip=-k['i(vp12)'], in_=k['i(vn12)'], u=k['v(u)'], y=k['v(y)'],
                do=k['v(do)'], fe=k['v(fe)'])


def transfer(fold):
    """Static cell transfer -Y(U): C5 replaced by a swept source at UA."""
    name = f'tf_{fold}'
    run(name, deck(fold=fold, replace={'C5': 'VU UA 0 DC 0'}, extra=f'''.control
dc VU -8 8 0.02
wrdata {OUT}/{name}.dat v(y)
.endc'''))
    u, (y,) = data(name, 1)
    return u, -y


def wave(drive, fold, amp=5.0, freq=220.0, **kw):
    name = f'tr_a{amp:g}_d{drive:g}_f{fold:g}'
    run(name, deck(drive=drive, fold=fold, vin=f'SIN(0 {amp} {freq})', extra=f'''.options reltol=1e-4
.tran 5u 0.4 0.38 5u
.control
run
wrdata {OUT}/{name}.dat v(in) v(out) v(u)
.endc''', **kw))
    t, (vi, vo, vu) = data(name, 3)
    return t, vi, vo, vu


def harmonics(t, y, freq, n=9):
    ts = np.linspace(t[-1] - 4 / freq, t[-1], 4096, endpoint=False)
    ys = np.interp(ts, t, y)
    spec = np.abs(np.fft.rfft(ys)) / len(ys) * 2
    return spec[4:4 * (n + 1):4], float(ys.std())


def step(c12=None):
    """DRIVE CV and FOLD CV 0 -> 2.5 V steps: settling of the two converters."""
    run('step', deck(drive=0.2, fold=0.2, dcv='PULSE(0 2.5 1m 2u 2u 2m 4m)', fcv='PULSE(0 2.5 1m 2u 2u 2m 4m)',
                     extra=f'''.save all @qq2[ic]
.tran 0.5u 6m 0 0.5u
.control
run
wrdata {OUT}/step.dat @qq2[ic] v(fc)-v(if_c)
.endc'''))
    t, (ia, vf) = data('step', 2)
    out = {}
    for name, y in (('I_ABC (DRIVE)', -ia), ('fold cell current', vf / 9.1e3)):
        y0, y1 = y[t < 0.9e-3].mean(), y[(t > 2.8e-3) & (t < 3e-3)].mean()
        up, down = (t > 1e-3) & (t < 3e-3), (t > 3e-3) & (t < 5e-3)
        out[name] = dict(y0=y0, y1=y1, overshoot=(y[up].max() - y1) / (y1 - y0) * 100,
                         undershoot=(y0 - y[down].min()) / (y1 - y0) * 100,
                         t90=t[up][np.argmax((y[up] - y0) >= 0.9 * (y1 - y0))] - 1e-3)
    return out


def tone(pos):
    t = run('tone', deck(tone=pos, replace={'C5': 'VU UA 0 DC 0 AC 0.001'}, extra=f'''.control
ac dec 40 10 100k
let h = abs(v(wet))/abs(v(y))
wrdata {OUT}/tone_{pos}.dat h
meas ac f3 when h=0.7071 fall=1
.endc'''))
    f, (h,) = data(f'tone_{pos}', 1)
    return f, h, kv(t).get('f3')


def noise(drive):
    t = run('noise', deck(drive=drive, vin='DC 0 AC 1', extra='''.control
noise v(out) VIN dec 20 20 20k
setplot noise2
print onoise_total
.endc'''))
    return kv(t)['onoise_total']


def report():
    res = {}
    print('rails and supply current (knobs at 0 / DRIVE + FOLD at max):')
    a, b = gain_point(), gain_point(drive=1, fold=1)
    print(f"  +12V {a['vp']:.2f} V, -12V {a['vn']:.2f} V; {a['ip'] * 1e3:.1f} / {a['in_'] * 1e3:.1f} mA .. "
          f"{b['ip'] * 1e3:.1f} / {b['in_'] * 1e3:.1f} mA (+12 V / -12 V)")
    print('DRIVE knob -> I_ABC, wet small-signal gain IN -> OUT (220 Hz, MIX wet, FOLD 0):')
    res['drive'] = []
    for d in np.linspace(0, 1, 9):
        g = gain_point(drive=float(d))
        res['drive'].append((float(d), g['iabc'], g['gain']))
        print(f"  knob {d:5.3f}: I_ABC {g['iabc'] * 1e6:7.1f} uA, gain x{g['gain']:6.2f} ({db(g['gain']):+5.1f} dB), "
              f"phase {g['phase']:+.1f} deg, U offset {g['u'] * 1e3:+.0f} mV")
    print('DRIVE CV (knob at 0):')
    res['dcv'] = []
    for cv in (-5, -2.5, 0, 1, 2, 3, 4, 5, 8, 12):
        g = gain_point(dcv=f'DC {cv}')
        res['dcv'].append((cv, g['iabc'], g['gain']))
        print(f"  CV {cv:+5.1f} V: I_ABC {g['iabc'] * 1e6:7.2f} uA, gain {db(g['gain']):+5.1f} dB, V(DO) {g['do']:.2f} V")
    print('FOLD knob -> f = fold cell current / I_0:')
    res['fold'] = []
    for f in np.linspace(0, 1, 5):
        g = gain_point(fold=float(f))
        res['fold'].append((float(f), g['f']))
        print(f"  knob {f:4.2f}: f {g['f']:.3f} (cell {g['icell'] * 1e6:5.0f} uA, I_0 {g['i0'] * 1e6:.0f} uA)")
    print('FOLD CV (knob at 0, and knob at max):')
    res['fcv'] = []
    for cv in (-12, -5, 0, 1, 2.5, 5, 6, 8, 12):
        g = gain_point(fcv=f'DC {cv}')
        g1 = gain_point(fold=1, fcv=f'DC {cv}')
        res['fcv'].append((cv, g['f'], g1['f']))
        print(f"  CV {cv:+5.1f} V: f {g['f']:.3f} (V(FE) {g['fe']:+.2f} V); knob at max: f {g1['f']:.3f}")
    print('cell transfer -Y(U), U = VCA output before the 1/11 divider:')
    res['tf'] = {}
    for f in (0, 0.25, 0.5, 0.75, 1):
        u, y = transfer(f)
        res['tf'][f] = (u, y)
        at = lambda x: y[int(np.argmin(abs(u - x)))]  # noqa: E731
        zeros = [round(float(u[j]), 2) for j in range(len(u) - 1) if y[j] * y[j + 1] < 0]
        print(f"  FOLD {f:4.2f}: y(0) {at(0) * 1e3:+4.0f} mV, y(1.1) {at(1.1):+.2f}, y(3.3) {at(3.3):+.2f}, y(7) {at(7):+.2f} V; "
              f"y(-1.1) {at(-1.1):+.2f}, y(-3.3) {at(-3.3):+.2f} V; zero crossings {zeros}")
    print('220 Hz sine in, MIX wet, TONE max: OUT peak, rms, harmonics H1..H9 (V peak):')
    res['waves'] = {}
    for amp in (5.0, 1.0):
        for d in (0, 0.25, 0.5, 0.75, 1):
            for f in (0, 0.5, 1):
                t, vi, vo, vu = wave(d, f, amp)
                res['waves'][(amp, d, f)] = (t, vi, vo)
                h, rms = harmonics(t, vo, 220)
                print(f"  in {amp:g} V pk, DRIVE {d:4.2f}, FOLD {f:3.1f}: OUT {vo.max():+.2f} / {vo.min():+.2f} V, rms {rms:.2f} V, "
                      f"U pk {abs(vu).max():5.2f} V, H " + ' '.join(f'{x:.2f}' for x in h))
    print('MIX (1 V, 220 Hz, DRIVE 0): OUT level and phase against IN')
    for m in (0, 0.5, 1):
        g = gain_point(mix=m)
        print(f"  MIX {m:3.1f}: x{g['gain']:.3f}, {g['phase']:+.1f} deg")
    print('TONE (Y -> WET):')
    res['tone'] = {}
    for pos in (0, 0.25, 0.5, 0.75, 1):
        f, h, f3 = tone(pos)
        res['tone'][pos] = (f, h)
        print(f"  knob {pos:4.2f}: -3 dB at {f3:7.0f} Hz")
    print('converter steps (CV 0 -> 2.5 V, knobs at 0.2):')
    for name, s in step().items():
        print(f"  {name}: {s['y0'] * 1e6:.0f} -> {s['y1'] * 1e6:.0f} uA, t90 {s['t90'] * 1e6:.0f} us, "
              f"overshoot {s['overshoot']:.1f} %, undershoot {s['undershoot']:.1f} %")
    print('output noise, 20 Hz .. 20 kHz, input grounded, MIX wet:')
    for d in (0, 0.5, 1):
        n = noise(d)
        print(f"  DRIVE {d:3.1f}: {n * 1e6:6.0f} uV rms ({db(n / 3.54):.0f} dB re 10 Vpp sine)")
    return res


# Plot colours: the dataviz reference palette (validated: blue / orange categorical pair), one
# blue ramp light -> dark for an ordered quantity (FOLD, TONE), neutral ink for text and grid.
BLUE, ORANGE, GREY = '#2a78d6', '#eb6834', '#8a8985'
RAMP = ['#9cc3f0', '#6ea5e6', '#4488d9', '#2a6cc0', '#174c93']
INK, MUTED, SURFACE, GRID = '#0b0b0b', '#52514e', '#fcfcfb', '#e4e3df'


def style(ax, xlabel=None, ylabel=None, title=None):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    if xlabel:
        ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    if title:
        ax.set_title(title, color=INK, fontsize=10, loc='left')


def plots(res):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    PLOTS.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 4.4), facecolor=SURFACE)
    for (f, (u, y)), col in zip(res['tf'].items(), RAMP):
        ax.plot(u, y, color=col, linewidth=2, label=f'FOLD {f:g}')
        ax.annotate(f'{f:g}', (3.3, y[int(np.argmin(abs(u - 3.3)))]), xytext=(4, 3), textcoords='offset points',
                    color=INK, fontsize=8)
    style(ax, 'VCA output U (V); the knee is 0.57 V', 'cell sum, output polarity (V)',
          'Shaper transfer: tanh soft clip (FOLD 0) to two folds per side (FOLD 1)')
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc='lower right')
    fig.tight_layout()
    fig.savefig(PLOTS / 'transfer.png', dpi=150)
    plt.close(fig)

    drives, folds = (0, 0.25, 0.5, 0.75, 1), (0, 0.5, 1)
    for amp in (5.0, 1.0):
        fig, axes = plt.subplots(len(folds), len(drives), figsize=(12, 6), sharex=True, sharey=True, facecolor=SURFACE)
        for r_, f in enumerate(folds):
            for c_, d in enumerate(drives):
                ax = axes[r_][c_]
                t, vi, vo = res['waves'][(amp, d, f)]
                ms = (t - t[-1] + 2 / 220) * 1e3
                keep = ms >= 0
                ax.plot(ms[keep], vi[keep], color=GREY, linewidth=1, label='IN')
                ax.plot(ms[keep], vo[keep], color=BLUE, linewidth=2, label='OUT (wet)')
                style(ax, 'ms' if r_ == len(folds) - 1 else None, 'V' if c_ == 0 else None, f'DRIVE {d:g}, FOLD {f:g}')
                ax.set_ylim(-6.5, 6.5)
        axes[0][0].legend(frameon=False, fontsize=8, labelcolor=INK, loc='upper right', ncol=2)
        fig.suptitle(f'220 Hz sine, {2 * amp:g} Vpp in, MIX fully wet, TONE at max (ngspice models)', color=INK, fontsize=11, x=0.01, ha='left')
        fig.tight_layout()
        fig.savefig(PLOTS / f'waves-{2 * amp:g}vpp.png', dpi=130)
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), facecolor=SURFACE)
    ax = axes[0][0]
    ax.plot([d for d, _, _ in res['drive']], [db(g) for _, _, g in res['drive']], color=BLUE, linewidth=2, marker='o', markersize=5)
    style(ax, 'DRIVE knob (0 = CCW, 1 = CW)', 'wet gain IN -> OUT (dB)', 'DRIVE knob: even dB steps')
    ax = axes[0][1]
    ax.plot([c for c, _, _ in res['dcv']], [db(g) for _, _, g in res['dcv']], color=BLUE, linewidth=2, marker='o', markersize=5)
    style(ax, 'DRIVE CV (V), knob at 0', 'wet gain IN -> OUT (dB)', 'DRIVE CV: 6.5 dB / V, limited at the top')
    ax = axes[1][0]
    ax.plot([c for c, _, _ in res['fcv']], [f for _, f, _ in res['fcv']], color=BLUE, linewidth=2, marker='o', markersize=5, label='knob at 0')
    ax.plot([c for c, _, _ in res['fcv']], [f for _, _, f in res['fcv']], color=ORANGE, linewidth=2, marker='s', markersize=5, label='knob at max')
    style(ax, 'FOLD CV (V)', 'fold amount f', 'FOLD CV: 0.2 / V, limited at 1.06')
    ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    ax = axes[1][1]
    for (pos, (f, h)), col in zip(res['tone'].items(), RAMP):
        ax.semilogx(f, 20 * np.log10(h), color=col, linewidth=2, label=f'TONE {pos:g}')
    ax.set_ylim(-30, 3)
    style(ax, 'Hz', 'wet path response (dB)', 'TONE: low-pass 650 Hz .. 17 kHz')
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc='lower left')
    fig.tight_layout()
    fig.savefig(PLOTS / 'controls.png', dpi=130)
    plt.close(fig)
    print('plots:', ', '.join(sorted(p.name for p in PLOTS.glob('*.png'))))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--no-plots', action='store_true')
    args = ap.parse_args()
    results = report()
    if not args.no_plots:
        plots(results)
