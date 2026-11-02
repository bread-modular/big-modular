"""S9.1 review-fix engineering screens. No measured/production qualification is implied.
TI SLVSGT7 Eq.19-23 (full complex gain, not the above-zero crossover shortcut).
Clamp ratings: Littelfuse SMBJ datasheet; EN: TI SNVSC40E; WSLP: Vishay doc 30122.
"""
import itertools
import math

RACK_MAX_F = 440e-6


def input_qualification(val):
    # Independent resistor limits: 0.1% +25 ppm*100C on R2/R3, 1% +1% on R114.
    p = (.999*.9975, 1.001*1.0025)
    b = (.99*.99, 1.01*1.01)
    rt = [val('R2')*x for x in p]
    rb = [val('R3')*x + val('R114')*y for x,y in zip(p,b)]
    leak = 150e-9*rt[1]
    def band(v):
        return [v[0]*(1+rt[0]/rb[1])-leak,
                v[1]*(1+val('R2')/(val('R3')+val('R114'))),
                v[2]*(1+rt[1]/rb[0])+leak]
    on, off = band((1.176,1.2,1.224)), band((1.09,1.122,1.15))
    return {'on_V': on, 'off_V': off, 'loaded_start_margin_V': 13.5-on[2],
            'unloaded_start_margin_V': 14.25-on[2], 'running_margin_V': 13.5-off[2],
            'resistors': 'R2=100k 0.1%/25ppm; R3=10k 0.1%/25ppm + R114=510R 1%/100ppm',
            'cable': '13.5 V at module = 14.25 V source minimum minus 0.75 V cable at 3 A (0.25 ohm loop)',
            'recommended_falling_11V8_not_guaranteed': True,
            'why': 'Even perfect resistors cannot meet both recommendations: rising<=13 requires divider factor<=13/1.224=10.621; falling>=11.8 requires >=11.8/1.09=10.826. Actual falling minimum is reported, never relabelled 11.8 V.'}


def enable(val):
    """EN voltage RELATIVE TO U4 ground (-12V). Disabled leakage is a design/test bound, not a TI maximum."""
    lo, hi = .99*.99, 1.01*1.01
    flo = val('R18')*lo/(val('R17')*hi+val('R18')*lo)
    fhi = val('R18')*hi/(val('R17')*lo+val('R18')*hi)
    on = input_qualification(val)['on_V'][0]
    return {'logic': 'QUALIFY = RUN AND MAIN_LED_OK = RUN AND MAIN_OK AND V20_OK; Q14 and Q15 series sink',
            'drive_source': 'Q1 emitter VPD upstream of D10; never +12V or VIN',
            'equation': 'EN_N - V(-12V) = QUALIFY ? (VPD - VCEsat - V(-12V))*R18/(R17+R18) : Ileak*R18',
            'off_pullup': 'R112 ties Q1 base to VPD if either sink is off; R18 pulls EN to U4 ground',
            'enable_high_max_V': 1.4, 'disable_low_min_V': .95,
            'startup_min_relative_V': round((on-.30)*flo,3),
            'running_max_relative_V': round((16.5+12.6)*fhi,3),
            'off_leakage_test_bound_uA': 5, 'off_relative_max_V': round(5e-6*val('R18')*hi,3),
            'truth_table': [{'own_input':own,'run':run,'main_status':pg,'bus_live':bus,
                             'U4_enabled':bool(own and run and pg)}
                            for own,run,pg,bus in itertools.product((False,True),repeat=4)],
            'does_not_block_reverse_power_while_enabled': True,
            'supply_loss_response': 'MAIN_OK has falling deglitch; until it drops a powered converter can sink a bus. Clamp test bounds that finite interval; never parallel a running module.'}


def loop(val, eff, vin_floor, op):
    """Complex outer loop with explicit Cpre--R109--Cpost and a cable+Crack branch.
    At zero rack impedance this reduces to TI Eq.19-23. A one-period delay and
    fsw/10 inner-loop pole are conservative sensitivity additions, not TI bounds.
    RLOAD/2 in boost reproduces Eq.20; buck uses RLOAD. Constant-current / constant-
    power active loads and arbitrary cable resonances require their own study.
    """
    import numpy as np
    f=np.logspace(0,6.4,4096); s=2j*np.pi*f
    worst_pm={'phase_margin_deg':1e9}; worst_gm={'gain_margin_dB':1e9}
    fc_min,fc_max=1e9,0.; bad=[]; count=0
    for vin,vo,io,c,cr,rc,lc,rcmp,ccmp,gm in itertools.product(
            (vin_floor,12.5,16.5,21.),(op['setpoint_V'][0],op['setpoint_V'][2]),
            (.05,1.2,op['i_pub']),(eff['+12V'][0],sum(eff['+12V'][:2])/2,eff['+12V'][1]),(0.,47e-6,220e-6,RACK_MAX_F),
            (.08,.25),(0.,.25e-6,.5e-6),(.9801,1.0201),(.765,1.265),(.7,1.3)):
        count+=1
        rl=vo/io; boost=vin<vo; d=max(0.,1-vin/vo)
        yp=s*(c*.75)  # zero ESR is conservative; no help from ESR zero assumed
        yd=s*(c*.25)+(2 if boost else 1)/rl
        if cr: yd+=1/(rc+s*lc+1/(s*cr))
        zfb=1/(yp*(1+val('R109')*yd)+yd)
        wrhp=rl*(1-d)**2/op['L']
        plant=(1-d)/.055*zfb*(1-s/wrhp if boost else 1)
        comp=190e-6*gm*1.2/vo*(val('R111')*rcmp+1/(s*val('C83')*ccmp))
        gain=plant*comp/(1+s/(2*np.pi*op['fsw_Hz'][0]/10))*np.exp(-s/op['fsw_Hz'][0])
        db=20*np.log10(np.abs(gain)); phase=np.unwrap(np.angle(gain))*180/np.pi
        crosses=np.where((db[:-1]>=0)&(db[1:]<0))[0]
        corner={'vin':vin,'vo':round(vo,3),'io':io,'bank_uF':round(c*1e6,2),
                'rack_uF':cr*1e6,'cable_R':rc,'cable_L_uH':lc*1e6,
                'R111_factor':rcmp,'C83_factor':ccmp,'GEA_factor':gm}
        if not len(crosses): bad.append({'reason':'no descending unity crossing','corner':corner}); continue
        for j in crosses:
            t=db[j]/(db[j]-db[j+1]); fc=math.exp(math.log(f[j])*(1-t)+math.log(f[j+1])*t)
            pm=180+phase[j]*(1-t)+phase[j+1]*t
            fc_min=min(fc_min,fc); fc_max=max(fc_max,fc)
            if pm<worst_pm['phase_margin_deg']: worst_pm={'phase_margin_deg':round(float(pm),2),'fc_Hz':round(fc),'corner':corner}
            if pm<=45 or fc>min(op['fsw_Hz'][0]/10,wrhp/(2*math.pi*5) if boost else 1e9):
                bad.append({'reason':'phase/crossover limit','pm':float(pm),'fc':fc,'corner':corner})
        pcs=np.where((phase[:-1]>-180)&(phase[1:]<=-180))[0]
        for j in pcs:
            t=(-180-phase[j])/(phase[j+1]-phase[j]); margin=-(db[j]*(1-t)+db[j+1]*t)
            if margin<worst_gm['gain_margin_dB']:worst_gm={'gain_margin_dB':round(float(margin),2),'corner':corner}
            if margin<=10:bad.append({'reason':'gain margin','gm':float(margin),'corner':corner})
    return {'R111_ohm':val('R111'),'C83_F':val('C83'),
            'zero_Hz':round(1/(2*math.pi*val('R111')*val('C83'))),
            'cases':count,'worst_phase':worst_pm,'worst_gain':worst_gm,
            'crossover_Hz':{'minimum':round(fc_min),'maximum':round(fc_max)},
            'violations':bad,'pass':not bad,
            'published_envelope':{'external_C_uF':[0,440],'bank_effective_uF':[round(x*1e6,1) for x in eff['+12V'][:2]],
                'cable_loop_R_ohm':[.08,.25],'cable_loop_L_uH':[0,.5],'load_A':[.05,op['i_pub']],
                'load_type':'passive resistive small-signal load; no arbitrary negative-impedance active rack guarantee'},
            'method':'TI Eq19-23; exact PI (no crossover shortcut), split bank/R109/cable branch, all listed corner products; one-period delay + fsw/10 pole. GEA +/-30% is sensitivity, not a datasheet limit.',
            'release_test':'Bode at VIN corners, bank/rack corners and 0.05A/rating: PM>45 deg, GM>10 dB, no sustained ringing; no-load FPWM and active rack impedances measured separately. Not performed.'}


def qualification(val, eff, op):
    """Resource/current checks independent of the logic timing model; does not claim to model internal CC arbitration."""
    bus_power=3*13.5-.75*3-.053*9-.5
    peak_p=12.08*op['icc_A'][2]/.93
    peak_n=11.989*1.051/.85
    rows=[]
    for wp in (0.,15.,25.,33.):
        # Worst efficiency mix: -12V first, then positive.
        wn=min(wp,11.989*.8); pp=wp-wn
        required=wn/.85+pp/.93
        e=.5*((eff['+12V'][1]+RACK_MAX_F)*op['setpoint_V'][2]**2/.93+
              (eff['-12V'][1]+440e-6)*12.624**2/.85)
        head=bus_power-required
        rows.append({'delivered_W':wp,'converter_budget_W':round(bus_power,3),
                     'steady_converter_W':round(required,3),'charging_energy_J':round(e,4),
                     'energy_limited_minimum_charge_ms':round(1000*e/head,1) if head>0 else None})
    return {'source_limit_A':3.,'source_min_V':14.25,'cable_loop_R_ohm':.25,
            'unconstrained_peak_input_A':round((peak_p+peak_n+.5)/(13.5-.75-.053*3),3),
            'unconstrained_positive_alone_A':round(peak_p/12.5,3),
            'meaning':'3 A source limiting MUST be tested; output CC does not enforce the PD input contract. Energy times are lower bounds, not startup guarantees.',
            'resource_rows':rows,
            'matrix':[
                {'id':'S1','condition':'Cold start, 14.25 V source +0.25 ohm cable, exact 3.00 A constant-current limit; 0/0.44 mF external each rail; 0/15/25/33 W load; both delay corners; log all attempts',
                 'pass':'Single attempt: both rail monitors good within 250 ms of first enable; ARMED by 0.90 s; no V3V3/POR reset, no source restart, <=3.00 A steady input; no retry hidden from record'},
                {'id':'S2','condition':'Same loads with a PD source hard-resetting on >3 A; include 5 V phase and V3V3 fully collapsed to 0 V',
                 'pass':'A single hard reset is counted and disqualifies that source/load combination for guaranteed start; no success by discarding earlier failed attempts'},
                {'id':'S3','condition':'Persistent rail short, uninterrupted source, then manual RESET and separate full power removal/reapplication',
                 'pass':'Each power epoch with input held must fault within 0.90 s+2 ms of first enable, hold RUN low until explicit reset, and fault again with short present'},
                {'id':'S4','condition':'Ten automatic input hard resets every 200 ms while short remains, V3V3 collapsed in each off interval',
                 'pass':'Qualification result must be FAIL_REPEATED_POWER_RESET, never a pass from a final successful cycle; fixture latches power OFF on the second autonomous reset'},
            ],
            'power_reset_policy':'STARTED and FAULT are volatile. Full V3V3/POR loss legitimately clears both; S8.5 one-shot preserved, not falsely advertised as nonvolatile. Automatic retrying sources are outside qualified envelope. Fixture counts epochs and must stop retries; hardware nonvolatile lockout remains absent.',
            'bench_status':'NOT PERFORMED; source/load qualification is open'}


def qualify_epochs(events):
    """Qualification verdict from captured reset events. Never erase evidence on re-arming."""
    automatic=sum(x['cause']=='source_hard_reset' for x in events)
    if automatic>=2:return 'FAIL_REPEATED_POWER_RESET'
    if automatic:return 'FAIL_SOURCE_RESET'
    if any(x.get('fault_present') and not x.get('fault_latched') for x in events):return 'FAIL_MASKED_FAULT'
    return 'PASS'


def residuals(val, eff, ov, cs):
    cg=cs.mlcc(7,10,'10u50V_1206',20.)[:2]
    cn=cs.mlcc(2,10,'10u50V_1206',20.)[:2]
    steps=[-12.6*cn[0]/(cn[0]+cg[1]),-12.6*cn[1]/(cn[1]+cg[0])]
    energy=.5*cg[1]*(16.5**2-4**2)
    peak_p=math.sqrt(ov['+12V']['guard_V'][2]**2+2*energy/eff['+12V'][0])
    peak_n=math.sqrt(ov['-12V']['guard_V'][2]**2+2*energy/eff['-12V'][0])
    clamps={'D24':{'net':'VIN','MPN':'SMBJ16A','stand_off_V':16,'breakdown_V':[17.8,19.7],
                   'rated_clamp_V':26.,'rated_peak_A':23.1,'peak_pulse_W':600,'waveform_us':'10/1000',
                   'pulse_budget':{'max_injection_A':1.,'max_duration_ms':20.,'worst_power_W':26.,'max_energy_J':.52,
                       'initial_temperature_max_C':50,'minimum_repeat_interval_s':200,
                       'basis':'Finite 1A x 26V x 20ms engineering budget. Datasheet pulse curve screen ~100W at 20ms after 50C derating; 600W rating applies ONLY to 10/1000us. No universal joule rating or continuous 26W claim.'},
                   'protects':'U2 VIN/SW1 42V abs /36V operating; 50V VIN bank and C25/C26 (26+12.6=38.6V); U5 OUT 60V',
                   'limitations':'Rated clamp is at 25C and specified waveform, not a measured PCB spike bound. Qualified fixture requires VIN<28V incl ringing at 25/50C. Sustained enabled reverse power is NOT safe.'},
            'D25':{'net':'VIN negative','MPN':'BAT54SLT1G','reverse_max_V':30,
                   'forward_bound_V_25C':.24,'current_for_bound_uA':100,
                   'scope':'Bus slew <=1 V/s at 25C (<=26.5uA displacement current from 2x10u+100n rated high C). Not a cold/fast-hotplug clamp.'},
            'D26':{'net':'P12_VOUT','MPN':'SMBJ14A','stand_off_V':14,'breakdown_V':[15.6,17.2],
                   'rated_clamp_V':23.2,'rated_peak_A':25.9,'peak_pulse_W':600,'waveform_us':'10/1000',
                   'VIN_bank_energy_J':round(energy,5),'guard_delay_energy_screen_J':round(16.5*4.7*20e-6,5),
                   'protects':'U2 VOUT/SW2/ISP/ISN 25V abs and local 25V MLCCs; not a 16V downstream guarantee',
                   'limitations':'Finite pulse backstop only; external rail source must be removed by fixture. No fuse coordination / crowbar or sustained shunt claim.'}}
    dc=sum(12.6/(val(a)+val(b))*1e3 for a,b in [('R8','R9'),('R93','R94'),('R75','R76')])+.020
    reverse={'decision':'ACCEPTED architecture: no series reverse blocking (owner). S9.1 removes the self-enable defect in hardware; that defect is NOT an accepted event.',
        'rule':'No powered parallel supplies or unrestricted hotplug. Unpowered/latched-off injection is qualified ONLY under T1 conditions, not a procedural excuse for self-enabling.',
        'plus12_path':{'dc_total_mA':round(dc,3),'hot_plug_bank_charge_mJ':[round(.5*c*12.6**2*1000,2) for c in eff['+12V'][:2]],
                      'power_stage':'Disabled four-switch boost HS blocks bus-to-VIN power transfer; divider current/leakage and capacitor charging remain.'},
        'minus12_passive':{'unclamped_VIN_step_V':[round(x,2) for x in steps],
                          'fast_step_residual':'D24 forward/internal diodes can clamp around -1.4V, outside U2 -0.3V minimum. D25 reduces it but is NOT guaranteed below 0.3V at high current/cold. Unrestricted hard hotplug remains UNQUALIFIED and is not a passing acceptance test.',
                          'qualified_slew_V_per_s':1,'qualified_temperature_C':25,'qualified_negative_floor_V':-.3},
        'minus12_active':{'finding':'FIXED: Q1 emitter is own VPD; base sink requires RUN AND MAIN_LED_OK through Q14/Q15. R112 defaults off. Bus voltage alone cannot enable U4.',
                          'enabled_parallel_risk':'FPWM still sinks if enabled against a higher external rail. -0.9A is TYPICAL only, not a worst-case bound; no finite-energy TVS can absorb an unlimited live bus.',
                          'enable_logic':enable(val)},
        'clamps':clamps,
        'bench_test':{'status':'proposed bench acceptance, NOT PERFORMED',
          'conditions':['T1-A: no USB input, +/-12.0 and +/-12.6V external bus, 1A source limit, 0.44mF each rail; ramp <=1V/s at 25C, hold 10s; log EN_N relative to -12V, U4 SW, VIN and bus currents',
                        'T1-B: same with USB present and FAULT latched/RUN low; verify off-state once MAIN_OK deglitch expires and capture the preceding <=20ms interval',
                        'T1-C: only negative rail applied with same bounded slew; repeat rail order',
                        'T1-D: inject a positive 1A, <=20ms pulse into VIN (compliance 28V, automatic disconnect), 25/50C, >=200s between pulses. This separately tests D24 energy/clamp; never assume the now-disabled U4 will generate this pulse'],
          'pass_criteria':['T1-A/C: EN_N minus -12V <=0.11V settled (<=0.5V transient), zero U4 switching; VIN -0.3..1V after 100ms settled; each bus current <10mA after 100ms',
                           'T1-B: same EN/switching/current criteria after 20ms; VIN may retain own-input charge, must remain -0.3..28V, not climb from bus power',
                           'T1-D: VIN <=28V incl ringing, measured integral(V*I*dt)<=0.52J, clamp current ends by 20ms, no leakage increase >10uA after cooling; normal restart and regulation after RESET',
                           'All: automatic overvoltage disconnect at VIN 28V, negative excursion abort at -0.3V (fast comparator, not human reaction). An abort is a FAIL, not a pass.'],
          'excluded':'Hard hotplug, temperatures below25C for D25 forward-drop guarantee, >1A or >20ms sustained injection, and powered parallel supplies require new protection/qualification.'}}
    over={'decision':'ACCEPTED architecture: no voltage-triggered fuse/crowbar; crowbar vs eFuse deferred/open. S9.1 D26 is a finite-energy transient backstop, not continuous shunt protection.',
          'guard_V':{'+12V':ov['+12V']['guard_V'],'-12V_magnitude':ov['-12V']['guard_V']},
          'response':'U20 presets FAULT and opens U5; it does NOT disconnect an external rail source or immediately discharge stored energy.',
          'why_no_fuse':['A fuse responds to current, not voltage.','No SCR/fuse crowbar is fitted.',
                         'D24/D26 TVS pulse ratings do not authorize sustained reverse power.','No per-rail eFuse/disconnect is fitted.'],
          'VIN_bank_energy_mJ':round(energy*1000,3),
          'peak_screens_V':{'+12V_bank_only_no_load_before_D26':round(peak_p,2),'+12V_D26_rated_clamp_25C':23.2,
                            '-12V_bank_only_no_load':round(peak_n,2),
                            '+12V_with_typical_rack':round(math.sqrt(ov['+12V']['guard_V'][2]**2+2*energy/(eff['+12V'][1]+RACK_MAX_F)),2),
                            '-12V_with_typical_rack':round(math.sqrt(ov['-12V']['guard_V'][2]**2+2*energy/(eff['-12V'][1]+RACK_MAX_F)),2)},
          'limitations':'Energy screens are NOT guaranteed peaks. Internal U2 OVP 24.5V is never used as an ideal clamp. No-load output can exceed16V; -12V has no positive-magnitude clamp. Unrelated failed-short components and unlimited external supplies are excluded.',
          'bench_test':{'status':'proposed bench acceptance, NOT PERFORMED',
             'conditions':['T2-A: input16.5V; 0.44mF +0.5A/rail; externally ramp +12V from12 to16.5V at<=1V/ms, <=1A, total injection<=10ms (including ramp), hold<=1ms at16.5V; fixture removes injection automatically after trigger; scope>=100MS/s',
                           'T2-B: R8 open at13.5/16.5V input, 3A source; no external C/no load, then0.44mF+0.5A; capture500ms with independent voltage/current abort',
                           'T2-C: R14 open, same conditions; no assumed LMR38020 output OVP',
                           'T2-D: RUN held low/logic powered, +14.0V and -13.0V external for10min; safely BELOW the minimum guard thresholds; no-trip only refers to OV_N, not RUN',
                           'T2-E: at+15.2V / -13.9V a trip is ALLOWED (inside tolerance bands); repeat guaranteed trip at+15.8V / -14.5V with <=1V/ms slew, <=1A source and >=50us hold (record actual waveform)'],
             'pass_criteria_this_module':['With >=0.5V rail overdrive beyond each measured trip, OV_N low/FAULT set/RUN low <=20us; MAIN LED off. Keep FAULT latched10s after injection removed, reset explicitly only after fault repair',
                'Externally driven rail remains externally driven until fixture removal: NEVER require it off while injection remains. After removal connect1k/1W discharge load; both rails below1V within2s at <=0.44mF external C',
                'T2-B/C: observed positive rail peak<=24.0V and negative magnitude<=24.0V for the500ms capture; positive duration above16V<=100ms with specified1k discharge; D26 pulse energy<=0.10J; normal regulation after repair/RESET',
                'T2-D OV_N stays high. T2-E band points may trip or not; above-band points MUST trip. Automatic abort at+24V / -24V / VIN28V, source removed in<=2us; any abort fails qualification, no human-only protection'],
             'downstream_qualification':['Without a separate rail protector, downstream modules must tolerate16.5V/10s and sub-threshold +15.3V/-14.1V continuously, and up to24V magnitude/100ms or their measured actual exposure if worse. Ordinary16V caps are NOT thereby qualified; incompatible modules excluded until crowbar/eFuse decision.']}}
    return {'reverse_current':reverse,'rail_overvoltage':over}
