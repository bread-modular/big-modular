"""Authorized SR2 schematic-only U3 inverting buck-boost source records."""
REMOVED_REFS={'U4','L2','L3','D2','D3','C8','C10','C11','C12','C13','C14','C15','C16','C17','C81','R12','R13','R14','R16','R38','R40','R60','R75','R76','#FLG04','#FLG05','#FLG06'}
INPUT_REFS=('C5','C68')
SPAN_REFS=('C89','C90','C91','C92')
OUTPUT_REFS=('C6','C37','C70','C71','C9','C75','C76')
PINS={'1':'NRAW','2':'NINV_SW','3':'VPROT','4':'NINV_FB','5':'NINV_EN','6':'NINV_BOOT'}


def populate(add,rr,cc,dd,L,BUCK):
    sh='04_bipolar'
    add(sh,'U3',BUCK,'TPS54302DDCR',PINS.copy(),'Package_TO_SOT_SMD:SOT-23-6','C311983',
        note='SR2 direct VPROT IBB: GND1=NRAW, VIN3=VPROT, SW2 via L1 to SYSTEM GND. TI SLVA933 section5 explicitly includes TPS54302. EN/FB referenced to NRAW, never system ground. 28V recommended/30V absolute span, not an OVP clamp. Prototype screens only.')
    add(sh,'L1',L,'22uH 20% shielded',{'1':'NINV_SW','2':'GND'},'BigModular:L_Bourns_SRP1245A','C1848803',
        note='SRP1245A-220M, Isat10A at20% L drop/25C, Irms6.5A at40C rise, DCR58mohm max. 10A NOT hot guaranteed minimum. Height max5.0mm versus5.1mm allowance leaves0.1mm BEFORE solder. Manufacturer lands14.2 overall/8 gap/5 width; separate PCB fit/hot-fault gate, not fit approval. Stock16 dated handoff, not reserved.')
    for ref in INPUT_REFS:
        cc(sh,ref,'22u 25V X5R','VPROT','GND','C12891','1206_3216',note='Retained two-part VPROT-to-SYSTEM-GND source bank; never across VPROT-to-NRAW span. Separate from C89..92 local50V bypass.')
    for ref in SPAN_REFS:
        cc(sh,ref,'2.2u 50V X7R','VPROT','NRAW','C50254','1206_3216',note='IC-local VIN3-to-GND1(NRAW) bypass: FOUR C50254 plus C7. 8.8u nominal,3.01u illustrative combined bias/TCC/tol/AC/aging screen; NOT guaranteed minimum. No25V parts across this span.')
    cc(sh,'C7','100n 50V X7R','VPROT','NRAW','C14663',note='U3 local HF bypass, VIN-to-NRAW, NOT system GND. Not counted toward minimum effective bulk.')
    cc(sh,'C35','100n 50V X7R','NINV_BOOT','NINV_SW','C14663',note='Bootstrap capacitor to SW2, NOT system GND or NRAW.')
    for ref in OUTPUT_REFS:
        cc(sh,ref,'22u 25V X5R','NRAW','GND','C12891','1206_3216',note='Seven local U3 output C12891, systemGND-to-NRAW. Reused former MID/U4 caps. Screen DC+AC/temp/tolerance/aging; remote U13 input5caps not counted as local ripple bank. Loop/thermal qualification remains.')
    for ref,v,a,b,code,tol in [('R9','100k','GND','NINV_DIV1','C122538','0.1%'),('R15','120k','NINV_DIV1','NINV_DIV2','C705720','0.1%'),('R84','6.2k','NINV_DIV2','NINV_FB','C4260','1%'),('R10','10k','NINV_FB','NRAW','C95204','0.1%')]:
        rr(sh,ref,v,a,b,code=code,tolerance=tol,note='IBB upper100k+120k precision25ppm +6.2k Basic100ppm=226.2k; lower10k precision. Independent corners, no cancellation. Upper weighted0.124668%,27.0557ppm/K, not entirely0.1%. Existing Extended codes reused; see sr2-schematic-budget.json.')
    dd(sh,'D30','GND','NRAW',note='Startup positive-NRAW mitigation: anode2=NRAW, cathode1=SYSTEM GND. Same MDD SS34 C8678/SMA as D27/D28/D29. TI SNVA897 review rationale; NOT a guaranteed +0.3V clamp at arbitrary surge. Measure U13 IN/NR/FB/OUT startup waveforms. Reverse leakage loads NRAW; temperature sensitivity explicitly assumed in sr2-schematic-budget.json.')
    cc(sh,'C93','DNP CFF / TBD','GND','NINV_FB','C57112',dnp=True,note='DNP/not purchased/not fitted. 0603 tuning footprint across ENTIRE upper R9+R15+R84 divider, system GND to NINV_FB. Existing Basic C57112/0603B103K500NT 10n50V identity is a metadata placeholder ONLY, not a selected tuning value. No fitted CFF or loop-stability claim; future value requires measured loop review.')
    rr(sh,'R91','100k','VPROT','NINV_EN',code='C25803',note='EN upper Basic100k; R92+R93=20k+2k to NRAW. No connection to EF_SHDN/RTN/retired BI_EN. 5uA EN bias is a sensitivity, not guaranteed max. EN can remain high with residual negative rail; not output disconnect.')
    rr(sh,'R92','20k','NINV_EN','NINV_EN_LO',code='C4184',note='EN lower leg20k+2k Basic series to NRAW only; reuses existing C4184/C22975 types instead of C31850 with missing Economy evidence. Startup<=7.34V ignoring helping pullup; 28V span+5uA bias screen below5.5V. Off/residual/reverse-path bench qualification required.')

    rr(sh,'R93','2k','NINV_EN_LO','NRAW',code='C22975',note='Series bottom EN member with R92=20k:22k total, each Basic1%100ppm. Existing Economy-evidenced C22975 reused; no new22k type or guessed eligibility.')
