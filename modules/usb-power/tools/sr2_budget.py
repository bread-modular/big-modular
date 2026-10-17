#!/usr/bin/env python3
"""SR2 selected-network independent-corner screens, never bench qualification."""
from itertools import product
from pathlib import Path
import json,math,cmath,csv
from split_rail_budget import factors,corners as sr1_corners,loop as positive_loop,caps as sr1_caps
from ldo_budget import _screened,_bias_retention
ROOT=Path(__file__).resolve().parents[1]
P=factors(.001,25e-6);B=factors(.01,100e-6)
# Exact C8678 cached catalog says 500uA@40V, but supplies no temperature.
# One bounded manufacturer-PDF fetch returned no extractable content. Therefore
# these are operating-current sensitivity assumptions, NOT rated hot maxima.
D30_LEAKAGE_A={'nominal':.0005,'adverse':.005}



def budget():
    prior=sr1_corners()
    raw=[v*(1+(100000*a+120000*b+6200*c)/(10000*d))+i*(100000*a+120000*b+6200*c)
         for v,a,b,c,d,i in product([.581,.611],P,P,B,P,[-100e-9,100e-9])]
    nominal=.596*(1+226200/10000);vmin,vmax=min(raw),max(raw)
    points=json.loads((ROOT/'docs/ldo-evidence/manufacturer-mlcc-data.json').read_text())['dc_bias_V_delta_percent']
    c_each=_screened(points,22,15,1)*.83423
    local=7*c_each*1e-6
    fsmin=290e3*.94;fsmax=510e3*1.06;vin=7.9375;iout=.307+D30_LEAKAGE_A['adverse'];eta=.80
    avg=iout*(1+vmax/(vin*eta));d=1-iout/avg;di=vin*d/(22e-6*.8*fsmin)
    peak=avg+di/2;valley=avg-di/2;irms=math.sqrt(avg**2+di**2/12)
    icap=math.sqrt(iout*iout*d/(1-d)+(1-d)*di*di/12)
    ripple_cap=iout*d/(fsmin*local);ripple_esr=peak*.010 # explicit conservative BANK allowance, not measured ESR
    ripple_pp=ripple_cap+ripple_esr
    peakraw=vmax+.1+ripple_pp/2;trough=vmin-.1-ripple_pp/2
    ovmax=1.225*(1+806000*max(B)/(100000*min(B)))+100e-9*806000*max(B)
    en_start=max(1.28*(1+100000*a/(22000*b)) for a,b in product(B,B))
    en_max=max(28*(22000*b)/(100000*a+22000*b)+5e-6*(100000*a*22000*b)/(100000*a+22000*b) for a,b in product(B,B))
    en_residual=max(vmax*(22000*b)/(100000*a+22000*b)+5e-6*(100000*a*22000*b)/(100000*a+22000*b) for a,b in product(B,B))
    # Actual TPS54302 compensator: gm240uS, Rc20k, Cc2.04n, Cp2p.
    # SLVA933 model2 equations16..21; gmps6.8 belongs to TPS54202;
    # 4..10A/V and slope amplitude0.2..1.0V are sensitivity ranges, NOT TPS54302 bounds.
    # No measured phase margin is inferred from TI's different board.
    operating_cmax=12*22e-6*_bias_retention(points,vmin)*1.1*1.15+8.8e-6*1.1
    models=[]
    for vi,vo,io,cap,ind,gmps,slope in product([7.9375,9.45],[vmin,vmax],[.157,.307],[local,operating_cmax],[17.6e-6,26.4e-6],[4.,6.8,10.],[.2,1.]):
        du=vo/(vi+vo);r=vo/io;wp=(1+du)/(r*cap);wz=(1-du)**2*r/(du*ind);wl=(vi+vo)/(slope*gmps*ind)
        gain=vi*r/(vi+2*vo)*gmps;beta=10000/236200
        def transfer(f):
            s=2j*math.pi*f
            comp=240e-6*20000*beta*(1+1/(s*20000*2.04e-9))/(1+s*20000*2e-12)
            return comp*gain*(1-s/wz)/((1+s/wp)*(1+s/wl)*(1+s/(math.pi*fsmin)))
        low,high=1.,fsmin/2
        for _ in range(45):
            mid=math.sqrt(low*high)
            if abs(transfer(mid))>1:low=mid
            else:high=mid
        fc=math.sqrt(low*high);pm=180+cmath.phase(transfer(fc))*180/math.pi
        models.append({'fc_Hz':fc,'phase_margin_deg':pm,'rhp_Hz':wz/(2*math.pi),'slope_pole_Hz':wl/(2*math.pi),'C_F':cap,'L_H':ind,'gmps_A_per_V':gmps,'slope_V':slope,'Vin_V':vi,'Vraw_V':vo,'Iraw_A':io})
    rhp_eff=(1-d)**2*(vmax/iout)/(d*26.4e-6)/(2*math.pi)
    rows=[]
    for ip,im in [(.4,.2),(.4,.3),(.4,.4),(.6,.2),(.0,.3)]:
        row={'P12_mA':ip*1000,'N12_mA':im*1000,'P5_mA':250}
        for adverse in [False,True]:
            vp=prior['positive_peak_V'] if adverse else prior['positive_nominal_V'];vn=peakraw if adverse else nominal
            ep=.85 if adverse else .90;en=.80 if adverse else .90;v5=prior['MID_peak_V'] if adverse else prior['MID_P5_nominal_V']
            leakage=D30_LEAKAGE_A['adverse' if adverse else 'nominal']
            bus=vp*(ip+.007)/ep+vn*(im+.007+leakage)/en+v5*.25/ep+.15;vs=8.55 if adverse else 9
            current=((vs-.15)-math.sqrt((vs-.15)**2-bus))/.5
            ln=(vn-(prior['N12_magnitude_DC_V'][0] if adverse else abs(prior['N12_nominal_V'])))*im+vn*.007
            lp=(vp-(11.7 if adverse else 12))*ip+vp*.007
            row['adverse' if adverse else 'nominal']={'input_A':current,'VPROT_V':vs-.15-.25*current,'bus_W':bus,'allocation_1p85A_pass':current<1.85,'below_nominal_eFuse_limit':current<12000/6040,'D30_leakage_A':leakage,'D30_reverse_dissipation_W':vn*leakage,'negative_LDO_W':ln,'positive_LDO_W':lp,'negative_theta_50C_to125C_C_per_W':75/ln}
        rows.append(row)
    caps={k:v for k,v in sr1_caps().items() if k not in ('negative_local_output','U4_local_input_supplement')}
    caps.update({'IBB_output_local':{'refs':['C6','C37','C70','C71','C9','C75','C76'],'bias_screen_V':15.,'nominal_uF':154,'effective_screen_uF':local*1e6,'remote_caps_counted':False,'guaranteed_minimum':False},
      'IBB_span_bypass':{'refs':['C89','C90','C91','C92'],'LCSC':'C50254','rating_V':50,'nominal_uF':8.8,'bias_TCC_tolerance_screen_uF':4*.99,'extra_AC_factor_assumption':.8,'extra_aging_factor_assumption':.95,'effective_screen_uF':4*.99*.8*.95,'engineering_allocation_uF':2.2,'TI_typical_example_uF':10,'TI_example_is_specified_minimum':False,'startup_current_ripple_qualified':False,'guaranteed_minimum':False,'C7_HF_not_counted':True},
      'IBB_source_to_system_GND':{'refs':['C5','C68'],'rating_V':25,'bias_V':9.45,'effective_screen_uF':_screened(points,22,9.45,2)*.83423}})
    # Whole zero-bias bulk is a deliberately adverse startup sensitivity, NOT
    # constant biased capacitance. Shared eFuse transients need measurement.
    craw=12*22e-6*1.1;cn12=4*22e-6*1.1;cspan=4*2.2e-6*1.1+.1e-6*1.1
    charge_i=(craw*nominal+cn12*12)/.005
    startup_avg=(iout+charge_i)*(1+nominal/(vin*.8))
    c_raw_floor=12*22e-6*.9*.85*.95*.83423
    startup={'softstart_typ_s':.005,'guaranteed_softstart_min_s':None,'raw_bulk_zero_bias_uF':264,'final_N12_bulk_uF':88,
       'constant_C_loaded_charge_current_sensitivity_A':charge_i,'constant_C_peak_sensitivity_A':startup_avg+di/2,
       'full_load_startup_proven':False,
       'positive_NRAW_charge_sharing_no_switch_upper_sensitivity_V':9.45*cspan/(cspan+c_raw_floor),
       'positive_NRAW_nominal_at_EN_start_V':en_start*8.9/(264+8.9),
       'positive_NRAW_limit_V':.3,
       'positive_kick_note':'Without D30, no-switch fast-step upper sensitivity exceeds0.3V, not a prediction with retained eFuse dVdt/active switching. Must measure positive IN/NR/FB/OUT kick and loaded ramp before acceptance; no positive-input compliance claim. D30 is mitigation only; no guaranteed <=+0.3V clamp for arbitrary surge.',
       'mitigation':{'ref':'D30','type':'MDD SS34 / C8678','anode':'NRAW','cathode':'GND','review_basis':'https://www.ti.com/lit/pdf/snva897','guaranteed_positive_clamp_V':None,'startup_waveforms_qualified':False},
       'off_EN_at_zero_VPROT_max_sensitivity_V':en_residual,'off_is_disconnect':False,
       'reverse_path':'Residual NRAW leaves U3 VIN/EN high; L1/SW high-side body diode can return stored rail energy to VPROT. U2 reverse blocking does not isolate local converters. SW1 shuts eFuse, not U3 EN. D28 retained, not a -0.3V differential guarantee.',
       'bench_gates':['cold/full-load start and eFuse retry with actual biased C','positive NRAW and U13 IN/FB/NR/OUT limits','raw/output shorts; eFuse and U3 hiccup interaction','unplug, residual EN, backfeed, prebias (no external supply permitted)']}
    out={'status':'SR2 post-review corrections; dual delta reviews and user ACK pending; PCB unsynchronized','rated_output_current':None,
      'corners':{'enumerated_raw_corners':len(raw),'resistor_deltaT_K':100,'upper_initial_tolerance_pct':100*(220000*.001+6200*.01)/226200,'upper_weighted_TCR_ppm_per_K':(220000*25+6200*100)/226200,'raw_nominal_magnitude_V':nominal,'raw_DC_magnitude_V':[vmin,vmax],'FB_current_sensitivity_nA':100,'FB_current_guaranteed_max':False,'N12_nominal_V':prior['N12_nominal_V'],'N12_DC_magnitude_V':prior['N12_magnitude_DC_V'],'raw_dip_allocation_V':.1,'raw_trough_V':trough,'raw_peak_V':peakraw,'LDO_headroom_V':trough-prior['N12_magnitude_DC_V'][1]},
      'voltage':{'normal_high_input_V':9.45,'normal_static_span_V':9.45+vmax,'OV_max_including100nA_V':ovmax,'OV_is_clamp':False,'OV_threshold_plus_raw_DC_V':ovmax+vmax,'recommended_VIN_SW_max_V':28,'absolute_VIN_SW_max_V':30,'raw_positive_excursion_allocation_V':.1+ripple_pp/2,'OV_turnoff_input_overshoot_allocation_V':.4,'SW_positive_ringing_allocation_V':1.,'allocated_span_V':ovmax+peakraw+.4+1.,'allocated_margin_to28_V':28-(ovmax+peakraw+.4+1.),'transient_allocations_measured':False,'negative_SW_undershoot_recommended_V':-.1,'negative_SW_undershoot_abs_V':-.3,'BOOT_SW_recommended_max_V':5.5,'BOOT_SW_abs_max_V':7,'open_FB_survival_proven':False,'FB_OVP108pct_is_guaranteed_clamp':False},
      'enable':{'top_ohm':100000,'bottom_ohm':22000,'bottom_series_refs_ohm':{'R92':20000,'R93':2000},'domain':'NRAW','start_max_V_ignoring_helpful_pullup':en_start,'max_at28V_with5uA_V':en_max,'bias_allowance_uA':5,'bias_guaranteed_max':False,'recommended_max_V':5.5,'absolute_max_V':7},
      'capacitors':caps,'switch':{'duty_efficiency_screen':d,'frequency_screen_Hz':[fsmin,fsmax],'L_H':[17.6e-6,26.4e-6],'average_A':avg,'ripple_pp_A':di,'peak_A':peak,'valley_A':valley,'RMS_A':irms,'HS_min_A':4.,'LS_min_A':3.1,'HS_fault_max_A':6.,'fault_overshoot_allocation_A':1.,'L1_table_Isat_25C_A':10.,'L1_guaranteed_hot_min_A':None,'fault_screen_margin_A':3.,'output_cap_RMS_A':icap,'capacitive_ripple_pp_V':ripple_cap,'bank_ESR_allowance_ohm':.010,'total_ripple_pp_V':ripple_pp,'minimum_on_s':min(vmin/(9.45+vmin),d)/fsmax,'minimum_off_s':(1-d)/fsmax},
      'negative_loop':{'model':'SLVA933 model2 with actual TPS54302 typical20k/2.04n/2p/240uS; HF pole fs/2 added; C93 DNP, no fitted CFF','gmps_sensitivity_A_per_V':[4,6.8,10],'gmps_6p8_is_TPS54202_not_54302_guarantee':True,'slope_amplitude_sensitivity_V':[.2,1.],'parameters_guaranteed':False,'corners':len(models),'operating_C_screen_F':[local,operating_cmax],'Cmax_note':'All12 raw caps at low raw bias, +10% tolerance/+15%temperature sensitivity, plus full nominal span bypass; zero-bias bulk used only for startup. Not guaranteed combined C.','crossover_Hz':[min(x['fc_Hz'] for x in models),max(x['fc_Hz'] for x in models)],'phase_margin_model_deg':[min(x['phase_margin_deg'] for x in models),max(x['phase_margin_deg'] for x in models)],'worst_phase_corner':min(models,key=lambda x:x['phase_margin_deg']),'min_RHP_Hz':min(x['rhp_Hz'] for x in models),'efficiency_adverse_RHP_Hz':rhp_eff,'crossover_RHP5_screen':'NOT_QUALIFIED','paired_efficiency_adverse_crossover_Hz':None,'RHP5_note':'Ideal-model corners retain paired fc/RHP values but omit adverse efficiency and D30 leakage. The separate efficiency-adverse RHP sensitivity has no matched crossover calculation. No boolean pass and no claim unrelated extrema co-occur. Measure actual loop; C93 is DNP.','measured_phase_margin_deg':None,'DCM_pulse_skip_proven':False},
      'positive_loop_unchanged':positive_loop(),'power':{'eFuse_ILIM_ohm':6040,'nominal_limit_A':12000/6040,'input_allocation_A':1.85,'allocation_basis':'Engineering planning allocation only, not tolerance-bound protection or qualified rating','nominal_eFuse_is_tolerance_bound':False,'conditional_design_target_mA':{'P12':400,'N12':300,'P5_reserve':250},'D30_reverse_leakage':{'catalog':'docs/electrical-catalog.json#C8678','catalog_Ir_A':.0005,'catalog_Vr_V':40,'catalog_temperature_C':None,'operating_assumptions_A':D30_LEAKAGE_A,'temperature_sensitivity_assumed_C':[25,125],'hot_to_nominal_assumed_ratio':10,'temperature_note':'25C nominal proxy and 125C hot 10x sensitivity are explicitly assumed; cached catalog has no temperature, exact PDF fetch yielded no extracted data. No scaling from40V to14V inferred; actual current and hot maximum unknown. Bench gate, not a guaranteed leakage bound.','documented_hot_max_A':None,'guaranteed_operating_max':False},'overhead_A_each':.007,'efficiencies_nominal':[.90,.90,.90],'efficiencies_adverse':[.85,.80,.85],'rows':rows,'guaranteed_rating':False},'startup':startup,
      'mechanical':{'height_max_mm':5.,'allowance_mm':5.1,'pre_solder_arithmetic_margin_mm':.1,'actual_fit_approved':False},'PCB_parity_claim':False,'independent_reviews_completed':False}
    out['normal_static_screens_pass']=out['corners']['LDO_headroom_V']>1 and out['voltage']['allocated_margin_to28_V']>0 and en_max<5.5 and peak<4 and valley<3.1 and rows[1]['adverse']['allocation_1p85A_pass']
    out['normal_static_screen_scope']='Voltage/headroom/EN/switch-current and +400/-300/+5@250mA allocation arithmetic ONLY; excludes loop/startup/thermal/rating qualification.'
    out['qualification_complete']=False
    return out

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args();b=budget();s=json.dumps(b,indent=2)+'\n'
    if a.output:a.output.write_text(s)
    else:print(s,end='')
    if not b['normal_static_screens_pass']:raise SystemExit('SR2 normal static screen failed')
