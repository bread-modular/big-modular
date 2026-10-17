#!/usr/bin/env python3
"""SR1 bounded independent-corner / CCM / energy screen, NOT qualification.

100 K resistor excursions; every tolerance and TCR sign independently enumerated.
TPS65131 +/-50/100nA and TPS55340 +/-100nA are sensitivities, NOT guaranteed
full-temperature bias bounds. A 100mV ripple/transient allocation is unmeasured.
"""
from itertools import product
from pathlib import Path
import cmath
import json
import math
from ldo_budget import _screened
ROOT=Path(__file__).resolve().parents[1]


def factors(tol,tcr):
    return [(1+t)*(1+c*100) for t,c in product([-tol,tol],[-tcr,tcr])]
P=factors(.001,25e-6)
B=factors(.01,100e-6)
RIPPLE=.1
AC=.83423  # manufacturer zero-DC 0.01Vrms sensitivity; not validated combined curve
OVERHEAD=.007  # each raw rail, allowance not guaranteed maximum


def corners(r60=15000):
    pos=[v*(1+100000*a/(10000*b))+i*100000*a
         for v,a,b,i in product([1.204,1.254],P,P,[-100e-9,100e-9])]
    out=[v*(1+(90900*a+1200*b+j)/(10000*c))+i*(90900*a+1200*b+j)
         for v,a,b,j,c,i in product([1.175*.975,1.175*1.025],P,B,[0,.1],P,[-100e-9,100e-9])]
    buck=[v*(1+100000*a/(13000*b+510*c))
          for v,a,b,c in product([.581,.611],B,B,B)]
    negative={}
    for nano in [50,100]:
        vals=[v*(1400000*a+r60*b)/(120000*c+1000*d)-vf*(1+(1400000*a+r60*b)/(120000*c+1000*d))+i*(1400000*a+r60*b)
              for v,vf,a,b,c,d,i in product([1.2,1.225],[-.024,.024],P,B,P,B,[-nano*1e-9,nano*1e-9])]
        negative[str(nano)]={'DC_magnitude_V':[min(vals),max(vals)], 'corner_count':len(vals),
            'trough_V':min(vals)-RIPPLE,'peak_V':max(vals)+RIPPLE,
            'headroom_to_N12_high_V':min(vals)-RIPPLE-max(out),
            'accuracy_headroom_screen_pass':min(vals)-RIPPLE-max(out)>=1,
            'recommended_15V_screen_pass':max(vals)+RIPPLE<=15,
            'bias_is_guaranteed_bound':False}
    vrefloads=[(vr-vfb)/(120000*c+1000*d) for vr,vfb,c,d in product([1.2,1.225],[-.024,.024],P,B)]
    n=negative['100'];midpeak=max(buck)+RIPPLE
    return {'positive_nominal_V':1.229*11,'positive_DC_V':[min(pos),max(pos)],
        'positive_corner_count':len(pos),'positive_trough_V':min(pos)-RIPPLE,
        'positive_peak_V':max(pos)+RIPPLE,'positive_accuracy_input_required_V':13.,
        'positive_accuracy_input_screen_pass':min(pos)-RIPPLE>=13,
        'negative_nominal_magnitude_V':1.213*(1400000+r60)/121000,
        'negative_bias_sensitivity_nA':negative,'N12_nominal_V':-1.175*(1+92100/10000),
        'N12_magnitude_DC_V':[min(out),max(out)],'N12_corner_count':len(out),
        'MID_P5_nominal_V':.596*(1+100000/13510),'MID_P5_DC_V':[min(buck),max(buck)],
        'MID_peak_V':midpeak,'MID_below5p5':midpeak<5.5,
        'inverting_switch_span_with_diode_and_2V_ringing_V':midpeak+n['peak_V']+.55+2.,
        'inverting_switch_24V_margin_with_allocations_V':24-(midpeak+n['peak_V']+.55+2.),
        'VREF_load_uA':[min(vrefloads)*1e6,max(vrefloads)*1e6],
        'VREF_nominal_load_uA':1.213/121000*1e6,'VREF_accuracy_test_current_uA':10.,
        'VREF_max_load_guarantee_found':False,
        'VREF_accuracy_note':'TI table tests10uA; computed9.683..10.360uA close to test but no load-regulation/max-drive bound was found. Not an unconditional reference-accuracy guarantee.'}


def caps():
    data=json.loads((ROOT/'docs/ldo-evidence/manufacturer-mlcc-data.json').read_text())
    points=data['dc_bias_V_delta_percent']
    banks=[('positive_input',['C48','C49','C50','C63'],14.,10.),
           ('positive_output',['C51','C52','C53','C64','C65','C66'],12.4,20.),
           ('negative_input',['C54','C55','C56','C67','C74'],15.,10.),
           ('negative_output',['C57','C58','C59','C73'],12.9,10.),
           ('negative_local_output',['C9','C75','C76'],15.,4.7),
           ('boost_local_output',['C77','C78','C79','C80'],14.,4.7),
           ('boost_local_input',['C82','C83','C84'],9.45,10.),
           ('U4_local_input_supplement',['C81'],5.5,4.7)]
    return {name:{'refs':refs,'bias_V':v,'nominal_uF':22*len(refs),
        'DC_tol_temp_aging_uF':_screened(points,22,v,len(refs)),
        'with_AC_sensitivity_uF':_screened(points,22,v,len(refs))*AC,
        'required_uF':need,'screen_pass':_screened(points,22,v,len(refs))*AC>=need,
        'guaranteed_minimum':False} for name,refs,v,need in banks}


def loop():
    """TI Eqs27-39 linear CCM model; no measured phase margin or RSENSE bound.

    Local-only Cmin is pessimistic for bandwidth; include all eight raw caps at
    zero DC for Cmax. Enumerate Gea240..440uS, input, raw, load, C, Rcomp/Ccomp.
    15mohm sense and10Mohm Rea are TYPICAL; no hardware guarantee follows.
    """
    cmin=caps()['boost_local_output']['with_AC_sensitivity_uF']*1e-6
    cmax=8*22e-6*1.1
    ftyp=41600*120**-.97*1000
    fmin=ftyp*(460/577)/(max(B)**.97)
    fmax=ftyp*(740/577)/(min(B)**.97)
    rows=[]
    for gm,vin,vout,iout,cout,rc,cc,cp in product([240e-6,440e-6],[7.9375,9.45],[13.15,13.992],[.407,1.007],[cmin,cmax], [470*min(B),470*max(B)],[.5e-6,1.15e-6],[95e-12,105e-12]):
        rout=vout/iout; fout=1/(math.pi*rout*cout)
        rhp=rout/(2*math.pi*8.16e-6)*(vin/vout)**2
        A=1.229/vout*gm*1e7*vin/(vout*.015)*rout/2
        fp=1/(2*math.pi*1e7*cc);fz=1/(2*math.pi*rc*cc);fp2=1/(2*math.pi*rc*cp)
        def transfer(f):
            return A*(1+1j*f/fz)*(1-1j*f/rhp)/((1+1j*f/fp)*(1+1j*f/fout)*(1+1j*f/fp2))
        lo,hi=1.,100000.
        for _ in range(50):
            mid=math.sqrt(lo*hi)
            if abs(transfer(mid))>1:lo=mid
            else:hi=mid
        fc=math.sqrt(lo*hi);pm=180+cmath.phase(transfer(fc))*180/math.pi
        rows.append((fc,pm,rhp,vin,vout,iout,cout,gm))
    worst=max(rows)
    # Local output bank only used in conservative switching-ripple screen.
    duty=1-7.9375/(13.992+.55)
    di=7.9375*duty/(5.44e-6*fmin)
    peak=(13.992*1.007)/(.85*7.9375)+di/2
    return {'R89_ohm':470,'C86_F':1e-6,'C87_F':100e-12,'R88_plus_R90_ohm':120000,
        'frequency_nominal_Hz':ftyp,'frequency_scaled_sensitivity_Hz':[fmin,fmax],
        'frequency_bound_at120k_guaranteed':False,'CCM_corner_count':len(rows),
        'CCM_crossover_Hz':[min(r[0] for r in rows),max(r[0] for r in rows)],
        'CCM_phase_margin_model_deg':[min(r[1] for r in rows),max(r[1] for r in rows)],
        'min_RHP_zero_Hz':min(r[2] for r in rows),
        'crossover_below14k_and_RHP5_and_fsw10':all(r[0]<min(14000,r[2]/5,fmin/10) for r in rows),
        'Cout_range_F':[cmin,cmax],'Ccomp_range_F':[.5e-6,1.15e-6],
        'Ccomp_range_is_sensitivity_not_manufacturer_guarantee':True,
        'R89_adjustment':'1k and510R initial drafts exceeded14kHz local-only max-gm screen; changed to Basic470R.',
        'boost_duty_adverse':duty,'boost_ripple_A':di,'boost_peak_at1A_plus_overhead_A':peak,
        'boost_peak_below5p25':peak<5.25,'L5_table_Isat_A':11.,'L5_switch_fault_limit_max_A':7.75,
        'local_ripple_at407mA_Vpp':.407*duty/(fmin*cmin),
        'estimated_400mA_step_max_over_consistent_CCM_corners_V':max(.4/(2*math.pi*r[0]*r[6]) for r in rows),
        'instant_400mA_step_within100mV_proven':False,'DCM_loop_measured':False,
        'note':'The broad step envelope exceeds100mV. DC headroom screen does NOT promise no dropout during abrupt full-load steps; bench ramp/load-step gate mandatory.'}


def power():
    c=corners(); rows=[]
    for ip,ineg in [(600,0),(800,0),(0,200),(0,250),(400,200),(500,200),(600,150),(800,150)]:
        for i5 in [100,250]:
            row={'P12_mA':ip,'N12_mA':ineg,'P5_mA':i5,'outputs_W':[12*ip/1000,12*ineg/1000,5*i5/1000]}
            for case in ['nominal','adverse']:
                adverse=case=='adverse';vp=c['positive_peak_V'] if adverse else c['positive_nominal_V'];vn=c['negative_bias_sensitivity_nA']['100']['peak_V'] if adverse else c['negative_nominal_magnitude_V']
                eta=.85 if adverse else .9;inv=.7 if adverse else .8;v5=c['MID_peak_V'] if adverse else c['MID_P5_nominal_V']
                bus=vp*(ip/1000+OVERHEAD)/eta+vn*(ineg/1000+OVERHEAD)/(eta*inv)+v5*i5/1000/eta+.15
                vs=(8.55 if adverse else 9)-.15;current=(vs-math.sqrt(vs*vs-bus))/(.5)
                lp=(vp-(11.7 if adverse else 12))*ip/1000+vp*OVERHEAD
                ln=(vn-(c['N12_magnitude_DC_V'][0] if adverse else abs(c['N12_nominal_V'])))*ineg/1000+vn*OVERHEAD
                row[case]={'input_A':current,'input_W':current*(8.55 if adverse else 9),'VPROT_load_W':bus,
                    'input_1p85A_allocation_pass':current<1.85,'positive_LDO_W':lp,'negative_LDO_W':ln,
                    'positive_theta_max_50C_to125C_C_per_W':75/lp,'negative_theta_max_50C_to125C_C_per_W':75/ln,
                    'negative_peak_TI_A':((c['MID_P5_DC_V'][0]-.1 if adverse else c['MID_P5_nominal_V'])+vn)*(ineg/1000+OVERHEAD)/((c['MID_P5_DC_V'][0]-.1 if adverse else c['MID_P5_nominal_V'])*.64)}
            rows.append(row)
    return {'raw_overhead_allowance_A_each':OVERHEAD,'overhead_is_guaranteed_max':False,
        'eFuse_resistance_ohm':6040,'eFuse_nominal_current_limit_A':12000/6040,
        'current_allocation_A_not_guaranteed_minimum':1.85,'rows':rows,'rated_output_current':None}


def startup():
    # Full nominal zero-bias bulk is conservative for passive charging.
    vin_bulk_uF=98+3*22  # inherited VPROT bulk plus C82..84
    raw_bulk_uF=8*22    # C77..80 + C48..50/C63
    final_pos_uF=6*22
    slope=4.7e-6*24.6/100e-9
    adverse_slope=5.5e-6*25.5/(100e-9*.9*.85)
    return {'eFuse_slope_typ_V_per_s':slope,'eFuse_slope_adverse_screen_V_per_s':adverse_slope,
        'VPROT_bulk_nominal_uF':vin_bulk_uF,'positive_raw_bulk_nominal_uF':raw_bulk_uF,
        'passive_input_plus_raw_precharge_A_typ':(vin_bulk_uF+raw_bulk_uF)*1e-6*slope,
        'passive_including_possible_P12_C_charge_A_adverse':(vin_bulk_uF+raw_bulk_uF+final_pos_uF)*1.1e-6*adverse_slope,
        'boost_SS_typ_s':100e-9*1.8/6e-6,
        'positive_raw_energy_at13p519_J':.5*raw_bulk_uF*1e-6*13.519**2,
        'negative_raw_nominal_uF':8*22,'negative_output_nominal_uF':4*22,
        'full_load_startup_guaranteed':False,'EN_is_disconnect':False,'rail_synchronous_shutdown':False,
        'bench_required':['PD/eFuse dVdt into zero-bias bulk plus running bucks','full-load boost foldback recovery','PRAW short passive L5/D29 current until eFuse latch','MID/NRAW startup and U4 negative current limit','unplug/retry/negative FB NR OUT-to-IN limits','external backdrive prohibited; reverse shunts not isolation']}


def budget():
    c=corners();cp=caps();lp=loop()
    nearby=[{'R60_ohm':v,**corners(v)['negative_bias_sensitivity_nA']['100']} for v in [13000,15000,16000,18000]]
    return {'status':'SR1 schematic-only prototype screens; PCB old/unsynchronized',
        'assumptions':{'resistor_delta_T_K':100,'precision_factors':P,'basic_factors':B,'ripple_allocation_V':RIPPLE,'AC_sensitivity_factor':AC},
        'corners':c,'capacitors':cp,'boost_loop':lp,'power':power(),'startup':startup(),
        'bounded_R60_search':nearby,
        'selection':'15k Basic retained: numerical100nA headroom reserve0.9855mV. 16k gives more balanced margins but catalog C4210 Extended/C22818 Preferred Extended, NOT Basic; not substituted.',
        'all_static_screens_pass':c['positive_accuracy_input_screen_pass'] and all(n['accuracy_headroom_screen_pass'] and n['recommended_15V_screen_pass'] for n in c['negative_bias_sensitivity_nA'].values()) and c['MID_below5p5'] and c['inverting_switch_24V_margin_with_allocations_V']>0 and all(b['screen_pass'] for b in cp.values()) and lp['crossover_below14k_and_RHP5_and_fsw10'],
        'unconditional_accuracy_or_current_guarantee':False,'PCB_parity_claim':False}

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path);args=ap.parse_args()
    result=budget();text=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')
    if not result['all_static_screens_pass']:raise SystemExit('Static screen failed')
