"""ngspice sanity check of the LADDER core, the S5 OTA resonance and the CV / LED loop
(docs/research.md section 4).

Run from modules/ladder:  python3 -B tools/sim_ladder.py
Writes decks and logs into the ignored research/sim/. Models, not measurements:
2N3904 (stock SPICE) for the DMMT3904W pairs, ideal op amps (behavioural, rail-limited),
the LM13700 half as a plain differential pair with ideal mirrors (gm = I_ABC / 2 VT, no
linearizing diodes, no buffer), 2N3906 for the MMBT5401. Values are the circuit() values.
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


OTA = '''.model QOTA NPN(Is=1e-15 Bf=500 Vaf=100)
.model DOTA D(Is=1e-15)
.subckt OTA INP INN IABC OUT VP VN
VSEN IABC X1 0
DA X1 X2 DOTA
DB X2 VN DOTA
Q1 C1 INP E QOTA
Q2 C2 INN E QOTA
FT E VN VSEN 1
V1 VP C1 0
V2 VP C2 0
F1 VP OUT V1 1
F2 OUT VN V2 1
RO OUT 0 50meg
.ends
'''


def core(vs, iabc, src, vos=0.0):
    """Ladder + expo + OTA feedback. vs: cutoff summer output (V), iabc: LM13700 bias current (A),
    src: AIN_BUF source line, vos: OTA input offset (V)."""
    return f'''* LADDER core
{MODEL}
{OTA}
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
* resonance: U9B summer (DIF via 3.3k, AIN via 68k, Rf 4.7k || 100p) -> C20 10u -> R39 10k / R42 1k
* -> U8A (+), R43 1k on (-) -> OTA_O (R48 100k to GND) -> C22 10u -> LFB
BSUM FBO 0 V=max(min(-4.7k*(V(DIF)/3.3k+V(AIN)/68k),10.5),-10.5)
RFO FBO FBR 1
CFO FBR 0 1n
C20 FBR FBAC 10u
R39 FBAC OTP 10k
R42 OTP 0 1k
R43 OTN OTX 1k
VOS OTX 0 {vos}
IABC 0 ABC {iabc}
XU8 OTP OTN ABC OTO P12 N12 OTA
R48 OTO 0 100k
C22 OTO LFB 10u
'''


def iabc_conv(pos, cv):
    """RES knob + RES CV -> I_ABC: U7B inverting sum (R40 / R41 100k into the virtual ground), Q9
    emitter on the T-network node RES_E (R49 47k back to the sum, R50 9.1k to GND): I_ABC =
    I_in x (1 + 47k / 9.1k). D8 clamps a negative sum (Q9 off). The LM13700 bias pin is two
    diodes above -12V_F (11.7 V rails behind the Schottkys)."""
    return f'''* LADDER S5 resonance control current
.model Q3906 PNP(Is=1.41f Xti=3 Eg=1.11 Vaf=18.7 Bf=180.7 Ne=1.5 Ise=0 Ikf=80m Xtb=1.5 Br=4.977 Nc=2 Isc=0 Ikr=0 Rc=2.5 Cjc=9.728p Mjc=.5776 Vjc=.75 Fc=.5 Cje=8.063p Mje=.3677 Vje=.75 Tr=33.42n Tf=179.3p Itf=.4 Vtf=4 Xtf=6 Rb=10)
.model D4148 D(Is=2.52n Rs=0.568 N=1.752 Cjo=4p M=0.4 tt=20n)
.model DOTA D(Is=1e-15)
VN N12 0 -11.7
V5 P5 0 5
RPA P5 W {50e3 * (1 - pos) + 1}
RPB W 0 {50e3 * pos + 1}
VCV CV 0 {cv}
R40 W X 100k
R41 CV X 100k
BU7 O 0 V=max(min(2e5*(0-V(X)),10.2),-10.2)
D8 O X D4148
R49 X E 47k
R50 E 0 9.1k
Q9 C O E Q3906
VSEN C PIN 0
DA PIN P2 DOTA
DB P2 N12 DOTA
.control
op
print v(E) v(O) i(VSEN)
.endc
.end
'''


# CV LED brightness loads behind the solder jumpers JP1..JP3 (R6, R7, R8), Ohm.
LED_STEPS = (47e3, 22e3, 10e3)


def cv_led(depth, jumpers=(0, 0, 0)):
    """CV input: J3 -> R9 39k -> DEPTH pot 50k -> U4A with the two panel LEDs anti-parallel in its
    loop (D11 positive, D12 negative), CV_S -> R14 47k (into the summer's virtual ground) and the
    jumpered loads R6 / R7 / R8. Generic red LED model (1.8 V at 2 mA) for both."""
    load = sum(j / r for j, r in zip(jumpers, LED_STEPS)) + 1e-12
    return f'''* LADDER S5 CV x DEPTH buffer + CV LEDs
.model D4148 D(Is=2.52n Rs=0.568 N=1.752 Cjo=4p M=0.4 tt=20n)
.model LEDR D(Is=1.5e-18 N=2 Rs=5)
VCV CVIN 0 0
R9 CVIN TOP 39k
RPA TOP W {50e3 * (1 - depth) + 1}
RPB W 0 {50e3 * depth + 1}
BU4 O 0 V=max(min(1e5*(V(W)-V(S)),10.5),-10.5)
VLED O OL 0
D11 OL S LEDR
VNEG S SL 0
D12 SL O LEDR
RJP S 0 {1 / load}
R14 S 0 47k
.control
dc VCV -12 12 1
print v(W) v(S) v(O) i(VLED) i(VNEG)
.endc
.end
'''


def run(name, deck):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.cir').write_text(deck)
    res = subprocess.run(['ngspice', '-b', str(OUT / f'{name}.cir')], capture_output=True, text=True)
    (OUT / f'{name}.log').write_text(res.stdout + res.stderr)
    return res.stdout


def ac_sweep(vs, iabc):
    deck = core(vs, iabc, 'VIN AIN 0 DC 0 AC -1') + f'''
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
    return run(f'ac_vs{vs}_i{iabc * 1e6:g}u', deck)


def grab(text, key):
    m = re.search(rf'^{key}\s*=\s*([-+0-9.eE]+)', text, re.M)
    return float(m.group(1)) if m else None


def grab_at(text, key):
    m = re.search(rf'^{key}\s*=\s*[-+0-9.eE]+\s+at=\s*([-+0-9.eE]+)', text, re.M)
    return float(m.group(1)) if m else None


def k_of(iabc):
    """Loop gain at DC: 10 (ladder + x10) x 4.7k / 3.3k x 1k / 11k x gm x (1k || 200k || 100k at AC),
    gm = I_ABC / 2 VT."""
    rl = 1 / (1 / 1e3 + 1 / 200e3 + 1 / 100e3)
    return 10.05 * 4.7 / 3.3 / 11 * iabc / (2 * VT) * rl


def op_value(text, name):
    m = re.search(rf'^{re.escape(name)}\s*=\s*([-+0-9.eE]+)', text, re.M | re.I)
    return float(m.group(1))


def main():
    print('cutoff map (k = 0): V_s -> ladder current, -3 dB')
    for vs in (6.0, 4.0, 2.0, 0.0, -0.098):
        t = ac_sweep(vs, 1e-9)
        ic = re.search(r'@qb\[ic\]\s*=\s*([-+0-9.eE]+)', t)
        print(f'  V_s {vs:+.3f} V: I_ladder {float(ic.group(1))*1e6:8.2f} uA, f-3dB {grab(t, "f3") or 0:9.1f} Hz, '
              f'pass {grab(t, "g0"):.3f}')
    for vs in (5.0, 2.0, 0.0):
        print(f'resonance (V_s = {vs} V): I_ABC -> passband, peak')
        for iabc in (1e-9, 50e-6, 100e-6, 130e-6, 150e-6):
            t = ac_sweep(vs, iabc)
            print(f'  I_ABC {iabc*1e6:6.1f} uA (k ~ {k_of(iabc):.2f}): pass {grab(t, "g0"):.3f}, '
                  f'peak {grab(t, "gmax"):7.2f} at {grab_at(t, "gmax") or 0:8.1f} Hz')
    # self-oscillation: no input, I_ABC around and above the k = 4 point (knob full = 0.31 mA,
    # knob full + 12 V RES CV = 1.04 mA)
    for vs, span in ((5.0, 0.4), (2.0, 0.16), (0.0, 0.06)):
        print(f'self-oscillation (V_s = {vs} V, kick then no input)')
        for iabc in (150e-6, 170e-6, 200e-6, 310e-6, 1.04e-3):
            deck = core(vs, iabc, 'VIN AIN 0 PULSE(0 0.2 1m 1u 1u 0.2m 1)') + f'''
.tran 2u {span} 0 2u
.control
run
meas tran vpp pp v(DIF) from={span * 0.875} to={span}
meas tran vin pp v(OTP) from={span * 0.875} to={span}
.endc
.end
'''
            t = run(f'osc_vs{vs}_i{iabc * 1e6:g}u', deck)
            print(f'  I_ABC {iabc*1e6:6.0f} uA (k ~ {k_of(iabc):.2f}): OUT ~{grab(t, "vpp") * 20.6:.2f} Vpp, '
                  f'OTA input {grab(t, "vin") * 1e3:.1f} mVpp')
    print('OTA input offset -> DC shift at LAD_DIF / OUT before C23 (V_s = 2 V): none, C22 blocks it')
    for vos in (0.4e-3, 4e-3):
        for iabc in (160e-6, 310e-6):
            t = run(f'vos{vos * 1e3:g}m_i{iabc * 1e6:g}u', core(2.0, iabc, 'VIN AIN 0 DC 0', vos=vos) + '''
.control
op
print v(DIF) v(OTO)
.endc
.end
''')
            print(f'  V_os {vos*1e3:.1f} mV, I_ABC {iabc*1e6:.0f} uA: LAD_DIF {op_value(t, "v(dif)")*1e3:+.2f} mV, '
                  f'OTA_O {op_value(t, "v(oto)")*1e3:+.1f} mV; a fast full RES step couples '
                  f'~{vos * iabc / (2 * VT) * 985 * 10 * 20.6:.2f} V into OUT, decaying in ~0.1 s (C23)')
    print('RES knob / RES CV -> I_ABC (U7B + Q9)')
    for pos, cv in ((0, 0), (0.25, 0), (0.5, 0), (0.75, 0), (1, 0), (0, 5), (0, -5), (1, -2.5), (1, 5), (1, 12)):
        t = run(f'iabc_p{pos:g}_cv{cv:g}', iabc_conv(pos, cv))
        i = op_value(t, 'i(vsen)')
        print(f'  knob {pos:4.2f}, RES CV {cv:+5.1f} V: I_ABC {i*1e6:7.1f} uA (k ~ {k_of(i):.2f}), '
              f'RES_E {op_value(t, "v(e)"):+.2f} V')
    cv_led_table()


def cv_led_table():
    print('CV x DEPTH buffer + CV LEDs: CV -> V(CV_S), LED currents (D11 positive / D12 negative), '
          'cutoff shift (octaves = 2.128 x V / 0.717)')

    def table(depth, jumpers):
        rows = {}
        for line in run(f'cv_led_{depth:g}_{"".join(map(str, jumpers))}', cv_led(depth, jumpers)).splitlines():
            f = line.split()
            if len(f) > 2 and f[0].isdigit():  # the print table wraps: one block per few columns
                rows.setdefault(round(float(f[1])), []).extend(float(v) for v in f[2:])
        return rows

    for depth in (1.0, 0.5, 0.1):
        rows = table(depth, (0, 0, 0))
        for cv in (-12, -5, -1, 0, 1, 2, 5, 8, 10, 12):
            w, s, o, i, n = rows[cv]
            print(f'  jumpers open, DEPTH {depth:.1f}, CV {cv:+3d} V: CV_S {s:+.3f} V, U4A out {o:+.2f} V, '
                  f'D11 {i * 1e6:6.2f} uA, D12 {n * 1e6:6.2f} uA, {s * 2.128 / 0.717:+.2f} oct')
    print('brightness steps (DEPTH full): JP1 JP2 JP3 -> LED current at 5 V / 12 V CV')
    for code in range(8):
        jumpers = (code & 1, code >> 1 & 1, code >> 2 & 1)
        rows = table(1.0, jumpers)
        print(f'  {jumpers[0]} {jumpers[1]} {jumpers[2]}: +5 V {rows[5][3] * 1e6:6.1f} uA, -5 V {rows[-5][4] * 1e6:6.1f} uA, '
              f'+12 V {rows[12][3] * 1e6:7.1f} uA (U4A out {rows[12][2]:+.2f} V)')


if __name__ == '__main__':
    main()
