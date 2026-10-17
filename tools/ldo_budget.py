#!/usr/bin/env python3
"""ES1 reproducible DC/tolerance screening, not bench or thermal qualification.

Datasheet electrical-characteristic extrema are used directly; the TPS65131
3% summary is NOT added again. Bias-current signs are bounded conservatively.
Resistor TCR uses the independently recorded catalog +/-25ppm/K at up to 100K
from 25C, including independent opposing drifts. Supplier PDF fetch was blocked;
manufacturer resistor/TCR and capacitor bias evidence remain procurement gates.
"""
from itertools import product
import json
import math
from pathlib import Path


def capacitor_screen():
    """Exact-MPN typical bias + explicit screening factors, never qualification."""
    d=json.loads((Path(__file__).resolve().parents[1]/'docs/ldo-evidence/manufacturer-mlcc-data.json').read_text())
    assert (d['mpn'],d['code'],d['nominal_uF'])==('CL31A226KAHNNNE','C12891',22)
    points=d['dc_bias_V_delta_percent'];out={}
    for name,refs,v,need in [('positive_input',[48,49,50,63],14.8,10),
            ('positive_output',[51,52,53,64,65,66],12.4,20),
            ('negative_input',[54,55,56,67],14.8,10),('negative_output',[57,58,59],12.4,10)]:
        a,b=next((a,b) for a,b in zip(points,points[1:]) if a[0]<=v<=b[0])
        retention=1+(a[1]+(b[1]-a[1])*(v-a[0])/(b[0]-a[0]))/100
        typ=len(refs)*22*retention
        screened=typ*d['tolerance_factor']*d['temperature_screen_factor']*d['aging_allowance_factor']
        out[name]={'refs':['C'+str(i) for i in refs],'bias_V':v,'nominal_uF':22*len(refs),'bias_retention_typical':retention,'typical_uF':typ,'screened_effective_uF':screened,'required_effective_uF':need,'screen_pass':screened>=need}
    return out


def budget():
    factors=[.999*(1-25e-6*100),1.001*(1+25e-6*100)]
    positive=[v*(1+(1.5e6*a+23.2e3*c)/(150e3*b))+i*(1.5e6*a+23.2e3*c)
              for v,a,b,c,i in product([1.189,1.237],factors,factors,factors,[-50e-9,50e-9])]
    negative=[]
    for vr,vfb,a,b,c,d,i in product([1.2,1.225],[-.024,.024],factors,factors,factors,factors,[-50e-9,50e-9]):
        rt=1.6e6*a+150e3*b;ratio=rt/(150e3*c+2.49e3*d)
        negative.append(vr*ratio-vfb*(1+ratio)+i*rt)
    neg_out=[]
    for v,a,b,c,i in product([1.175*.975,1.175*1.025],factors,factors,factors,[-100e-9,100e-9]):
        rt=90.9e3*a+1.21e3*b
        neg_out.append(v*(1+rt/(10e3*c))+i*rt)
    raw_p_nom=1.213*(1+(1.5e6+23.2e3)/150e3)
    raw_n_nom=1.213*(1.6e6+150e3)/(150e3+2.49e3)
    neg_nom=1.175*(1+(90.9e3+1.21e3)/10e3)
    pp=[min(positive),max(positive)];nn=[min(negative),max(negative)]
    outp=[12*.975,12*1.025];outn=[min(neg_out),max(neg_out)]
    # A design ALLOCATION, not a measurement/promise of converter ripple.
    ripple=.1
    hp=pp[0]-ripple-outp[1];hn=nn[0]-ripple-outn[1]
    assert max(pp[1],nn[1])+ripple<15
    assert hp>.45 and hn>.8
    assert min(pp[0],nn[0])-ripple>13 # VIN >= nominal OUT+1V for specified conditions
    losses={}
    for current in [.25,.8,1.]:
        losses[str(current)]={
          'positive_pass_nominal_W':(raw_p_nom-12)*current,
          'negative_pass_nominal_W':(raw_n_nom-neg_nom)*current,
          'positive_pass_corner_W':(pp[1]+ripple-outp[0])*current,
          'negative_pass_corner_W':(nn[1]+ripple-outn[0])*current}
    # Illustrative CCM screen only. 1.8A table limit is specified at particular
    # VIN/VPOS conditions, not a newly guaranteed rail-current rating here.
    screen={}
    vin=5.;vd=.5;f=1.25e6;L=4.7e-6*.8
    for name,duty in [('boost',1-vin/(raw_p_nom+vd)),('inverter',(raw_n_nom+vd)/(vin+raw_n_nom+vd))]:
        di=vin*duty/(f*L)
        screen[name]={'assumed_duty':duty,'inductor_ripple_A':di,
                      'ideal_output_at_1p8A_peak_A':(1.8-di/2)*(1-duty)}
    return {
      'status':'static design screening; NOT qualified hardware',
      'raw_nominal_magnitudes_V':{'positive':raw_p_nom,'negative':raw_n_nom},
      'raw_resistors_ohm':{'R12':1500000,'R75':23200,'R13':150000,'R14':1600000,'R60':150000,'R15':150000,'R76':2490},
      'positive_input_trough_V':pp[0]-ripple,'negative_input_trough_magnitude_V':nn[0]-ripple,
      'raw_feedback_bias_assumption_A':[-50e-9,50e-9],
      'positive_raw_DC_V':pp,'negative_raw_DC_magnitude_V':nn,
      'positive_final_nominal_V':12.,'negative_final_nominal_V':-neg_nom,
      'positive_final_DC_V':outp,'negative_final_DC_magnitude_V':outn,
      'resistor_tolerance_plus_TCR_factors':factors,
      'ripple_transient_allocation_peak_V':ripple,
      'positive_worst_headroom_V':hp,'negative_worst_headroom_V':hn,
      'positive_dropout_max_at_1A_V':.45,'negative_dropout_max_at_1A_V':.8,
      'positive_dropout_reserve_V':hp-.45,'negative_dropout_reserve_V':hn-.8,
      'pass_dissipation_excludes_ground_current':losses,
      'thermal_additional_loss':'Add |VIN| * IGND; no full-load maximum IGND is established. JEDEC thetaJA is not this board.',
      'capacitor_banks':capacitor_screen(),
      'cap_effective_C_verified':False,'cap_ESR_verified':False,
      'cap_prototype_screen_passed':all(v['screen_pass'] for v in capacitor_screen().values()),
      'cap_bank_disposition':'PASS explicit typical-data prototype screen, not a guaranteed full-product or measured minimum. See capacitor-disposition.json.',
      'accuracy_headroom_budget_applicable_to_present_capacitors':'conditional on screened capacitance and stated ripple/temperature/lot assumptions; not bench verified',
      'positive_startup_typ_s_at_nominal_1uF':100000*1e-6*math.log((12+5)/5),
      'negative_startup_typ_s_at_nominal_100nF':.12,
      'screening_only_CCM_at_5V':screen,
      'nominal_efuse_input_power_W_at_9V':9*12000/6040,
      'simultaneous_12V_800mA_rail_output_power_W':2*12*.8,
      'current_rating_claim':None,
      'PCB_integration_completed':True,
      'reverse_and_shutdown_qualification_completed':False,
      'assembly_Basic_policy_exception_approved':False,
    }


if __name__=='__main__':
    print(json.dumps(budget(),indent=2))
