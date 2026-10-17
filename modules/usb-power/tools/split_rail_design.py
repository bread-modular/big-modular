"""SR1 schematic-only split-rail source records. PCB is deliberately unsynchronized.

No active rail sequencer: boost EN follows protected VPROT; LDO EN remains its
own raw input. Passive boost precharge and unsynchronized rails are explicit.
"""
BOOST_PINS = {str(p): 'GND' for p in range(1,18)}
BOOST_PINS.update({'1':'PBOOST_SW','15':'PBOOST_SW','16':'PBOOST_SW',
                   '2':'VPROT','3':'VPROT','4':'PBOOST_SS','7':'PBOOST_COMP',
                   '8':'PBOOST_FB','9':'PBOOST_FREQ'})
BOOST_FOOTPRINT='Texas_RTE0016C_WQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm'


def symbol(chip):
    return chip('TPS55340RTER',[
        (2,'VIN','power_in','L'),(3,'EN','input','L'),
        (4,'SS','passive','L'),(5,'SYNC','input','L'),
        (6,'AGND','power_in','L'),(10,'RSVD_GND','passive','L'),
        (14,'RSVD_GND','passive','L'),(17,'EP_AGND','passive','L'),
        (1,'SW','open_collector','R'),(15,'SW','passive','R'),(16,'SW','passive','R'),
        (8,'FB','input','R'),(7,'COMP','passive','R'),(9,'FREQ','passive','R'),
        (11,'PGND','power_in','R'),(12,'PGND','passive','R'),(13,'PGND','passive','R')],
        'https://www.ti.com/lit/ds/symlink/tps55340.pdf')


def populate(add,rr,cc,dd,L,R,boost):
    sh='06_positive_boost'
    add(sh,'U14',boost,'TPS55340RTER',BOOST_PINS.copy(),'BigModular:'+BOOST_FOOTPRINT,
        'C169167',note='TI RTE pin table: SW1/15/16; reserved10/14 grounded; SYNC5 AGND; EP17 AGND. EN3 follows VPROT, NOT output disconnect. Tie AGND/PGND locally with thermal array; layout worker owns footprint verification. No rail-synchronous shutdown.')
    add(sh,'L5',L,'6.8uH 20% shielded',{'1':'VPROT','2':'PBOOST_SW'},
        'BigModular:L_KOHER_MDA1040','C2847552',note='Same exact MDA1040-6R8M as L1/L4; height max4.0mm; manufacturer Isat table11A/typ12.2A exceeds TPS55340 maximum7.75A fault limit; Irms table6.8A/typ7.8A, DCRmax24.5mohm. Not a guaranteed hot-lot minimum. Saturation/thermal and frontside placement verification pending.')
    dd(sh,'D29','PRAW','PBOOST_SW',note='SS34/C8678 SMA 3A40V Schottky; anode2=PBOOST_SW, cathode1=PRAW. Passive precharge path persists when U14 disabled. eFuse short/latch and diode thermal qualification required; not isolation.')
    for ref,v,a,b,code in [('R86','100k','PRAW','PBOOST_FB','C122538'),
                          ('R87','10k','PBOOST_FB','GND','C95204')]:
        rr(sh,ref,v,a,b,code=code,tolerance='0.1%',note='Authorized narrow precision FB exception:0.1%,25ppm/K. 100k/10k gives13.519V; full-ref/100K independent corners +100nA sensitivity and100mV dip screened, not guaranteed bias/transient bounds.')
    rr(sh,'R88','100k','PBOOST_FREQ','PBOOST_FREQ_SER',code='C25803',note='Basic120k1%,100ppm/K; TI Eq6 nominal~400kHz. Frequency extrema scaled from80k table are sensitivities, not guaranteed120k limits; measure startup foldback recovery.')
    rr(sh,'R90','20k','PBOOST_FREQ_SER','GND',code='C4184',note='Basic20k series with R88=100k; total120k. Each independent1%,100ppm/K.')
    rr(sh,'R89','470','PBOOST_COMP','PBOOST_COMP_RC',code='C23179',note='Basic470R compensation series resistor. With C86=1u and C87=100p; TI Eqs27-39 CCM screen, fc below14kHz with local bias-screened COUT. No measured loop/phase-margin claim.')
    cc(sh,'C85','100n 50V X7R','PBOOST_SS','GND','C14663',note='TI6uA/1.8V soft start ~30ms typical; does NOT limit passive L5/D29 precharge. Full-load startup is unmeasured.')
    cc(sh,'C86','1u 50V X7R','PBOOST_COMP_RC','GND','C28323','0805_2012',note='Type-II compensation series C; 1u nominal, bias near COMP~1..3V. C87 sets high-frequency pole; loop bench gate remains.')
    cc(sh,'C87','100p 50V C0G','PBOOST_COMP','GND','C14858',note='100p compensation high-frequency pole; Basic C0G. Not an output feed-forward capacitor.')
    cc(sh,'C88','100n 50V X7R','VPROT','GND','C14663',note='U14 VIN2 local high-frequency bypass; direct AGND return.')
    for ref in ['C77','C78','C79','C80']:
        cc(sh,ref,'22u 25V X5R','PRAW','GND','C12891','1206_3216',note='Four local boost output C12891; count independently from remote U12 input bank. Combined DC+AC+tolerance/temp/aging sensitivity, ripple/load-step and loop tests required.')
    for ref in ['C82','C83','C84']:
        cc(sh,ref,'22u 25V X5R','VPROT','GND','C12891','1206_3216',note='Three local boost VIN C12891; conservative screen exceeds10uF including AC sensitivity at9.45V. eFuse dVdt/precharge budget includes full zero-bias nominal capacitance.')
