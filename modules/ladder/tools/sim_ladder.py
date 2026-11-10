"""ngspice sanity check of the LADDER S1 core (docs/research.md section 4).

Run from modules/ladder:  python3 -B tools/sim_ladder.py
Writes decks and logs into the ignored research/sim/. Models, not measurements:
2N3904 (stock SPICE) for the DMMT3904W pairs, ideal op amps (behavioural, rail-limited),
the resonance vactrol's LDR as a fixed resistor (R_LDR swept). Values are the circuit() values.
"""
import math
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'research' / 'sim'
VT = 0.02585

MODEL = '.model Q3904 NPN(Is=6.734f Xti=3 Eg=1.11 Vaf=74.03 Bf=416.4 Ne=1.259 Ise=6.734f Ikf=66.78m ' \
        'Xtb=1.5 Br=.7371 Nc=2 Isc=0 Ikr=0 Rc=1 Cjc=3.638p Mjc=.3085 Vjc=.75 Fc=.5 Cje=4.493p ' \
        'Mje=.2593 Vje=.75 Tr=239.5n Tf=301.2p Itf=.4 Vtf=4 Xtf=2 Rb=10)'


def core(vs, rldr, src):
    """Ladder + expo + vactrol feedback. vs: cutoff summer output (V), rldr: resonance LDR (Ohm),
    src: AIN_BUF source line."""
    return f'''* LADDER core
{MODEL}
.model D4148 D(Is=2.52n Rs=0.568 N=1.752 Cjo=4p M=0.4 tt=20n)
VP P12 0 12
VN N12 0 -12
V5 P5 0 5
{src}
* bias chain (R LB4 4.7k, 1.5k steps), 10u bypass
RB5 P12 LB4 4.7k
RB4 LB4 LB3 1.5k
RB3 LB3 LB2 1.5k
RB2 LB2 LB1 1.5k
RB1 LB1 LB0 1.5k
RB0 LB0 0 1.5k
CB4 LB4 0 10u
CB3 LB3 0 10u
CB2 LB2 0 10u
CB1 LB1 0 10u
CB0 LB0 0 10u
* driver bases
RIN AIN LIN 200k
RBI LIN LB0 1k
RBF LFB LB0 1k
RFG LFB 0 200k
* driver + rungs (A = feedback side, B = input side)
QDA A0 LFB LTAIL Q3904
QDB B0 LIN LTAIL Q3904
Q1A A1 LB1 A0 Q3904
Q1B B1 LB1 B0 Q3904
Q2A A2 LB2 A1 Q3904
Q2B B2 LB2 B1 Q3904
Q3A A3 LB3 A2 Q3904
Q3B B3 LB3 B2 Q3904
Q4A P12 LB4 A3 Q3904
Q4B P12 LB4 B3 Q3904
C1 A0 B0 47n
C2 A1 B1 47n
C3 A2 B2 47n
C4 A3 B3 47n
* followers + difference amp x10
BDIF DIF 0 V=10*(V(B3)-V(A3))
* expo: summer output VS -> 3.9k/100R -> QA base; QB base GND; ref op amp
VS VS 0 {vs}
RD1 VS XB 3.9k
RD2 XB 0 100
RREF P5 XC 9.1k
QA XC XB XE Q3904
QB LTAIL 0 XE Q3904
BREF XO 0 V=max(min(-1e5*V(XC),10.5),-10.5)
CC XO XC 100p
DX XE XD D4148
RX XD XO 4.7k
* resonance: U11B summer (DIF via 3.3k, AIN via 68k, Rf 4.7k || 100p) -> 10u -> LDR -> LFB
BSUM FBO 0 V=max(min(-4.7k*(V(DIF)/3.3k+V(AIN)/68k),10.5),-10.5)
RFO FBO FBR 1
CFO FBR 0 1n
CAC FBR FBAC 10u
RLDR FBAC LFB {rldr}
'''


def run(name, deck):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.cir').write_text(deck)
    res = subprocess.run(['ngspice', '-b', str(OUT / f'{name}.cir')], capture_output=True, text=True)
    (OUT / f'{name}.log').write_text(res.stdout + res.stderr)
    return res.stdout


def ac_sweep(vs, rldr):
    deck = core(vs, rldr, 'VIN AIN 0 DC 0 AC -1') + f'''
.control
op
print v(LTAIL) v(A3) v(B3) v(DIF) v(XE) v(XO) v(LFB) v(LIN) @QB[ic] @QA[ic]
ac dec 60 5 100k
let g = abs(v(DIF))/0.04975
meas ac g0 find g at=10
meas ac gmax max g
let p = ph(v(DIF))
meas ac f3 when g=0.70711 fall=1
.endc
.end
'''
    return run(f'ac_vs{vs}_r{rldr:g}', deck)


def grab(text, key):
    m = re.search(rf'^{key}\s*=\s*([-+0-9.eE]+)', text, re.M)
    return float(m.group(1)) if m else None


def grab_at(text, key):
    m = re.search(rf'^{key}\s*=\s*[-+0-9.eE]+\s+at=\s*([-+0-9.eE]+)', text, re.M)
    return float(m.group(1)) if m else None


def k_of(rldr):
    """Loop gain at DC: 10 (ladder + x10) x 4.7k / 3.3k x 1k / (1k + R_LDR) (1k || 200k at LFB)."""
    rl = 1 / (1 / 1e3 + 1 / 200e3)
    return 10.05 * 4.7 / 3.3 * rl / (rl + rldr)


def main():
    print('cutoff map (k = 0): V_s -> ladder current, -3 dB')
    for vs in (6.0, 4.0, 2.0, 0.0, -0.098):
        t = ac_sweep(vs, 1e9)
        ic = re.search(r'@qb\[ic\]\s*=\s*([-+0-9.eE]+)', t)
        print(f'  V_s {vs:+.3f} V: I_ladder {float(ic.group(1))*1e6:8.2f} uA, f-3dB {grab(t, "f3") or 0:9.1f} Hz, '
              f'pass {grab(t, "g0"):.3f}')
    for vs in (5.0, 2.0, 0.0):
        print(f'resonance (V_s = {vs} V): R_LDR -> passband, peak')
        for rldr in (1e6, 10e3, 5e3, 3.3e3, 2.7e3):
            t = ac_sweep(vs, rldr)
            print(f'  R_LDR {rldr/1e3:7.1f}k (k ~ {k_of(rldr):.2f}): pass {grab(t, "g0"):.3f}, '
                  f'peak {grab(t, "gmax"):7.2f} at {grab_at(t, "gmax") or 0:8.1f} Hz')
    # self-oscillation: no input, LDR at and below the k = 4 point
    for rldr in (2.7e3, 2.2e3, 1.5e3, 1e3, 470, 100):
        deck = core(2.0, rldr, 'VIN AIN 0 PULSE(0 0.2 1m 1u 1u 0.2m 1)') + '''
.tran 2u 160m 0 2u
.control
run
meas tran vpp pp v(DIF) from=140m to=160m
.endc
.end
'''
        t = run(f'osc_{rldr:g}', deck)
        print(f'  R_LDR {rldr/1e3:5.2f}k (k ~ {k_of(rldr):.2f}): DIF p-p 140..160 ms {grab(t, "vpp"):.4f} V '
              f'(FILTER OUT ~{grab(t, "vpp") * 20.6:.1f} Vpp)')


if __name__ == '__main__':
    main()
