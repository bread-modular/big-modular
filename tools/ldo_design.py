"""ES1 post-regulator source records; exact requested TI variants, never TPS7A4701.

Static design only. Capacitor bias/impedance, reverse transients and board thermal
qualification are open gates in docs/ldo-revision.md. No PCB generation here.
"""
FOOTPRINT = 'Texas_RGW0020A_VQFN-20-1EP_5x5mm_P0.65mm_EP3.15x3.15mm'
POSITIVE_PINS = {str(i): None for i in range(1, 22)}
POSITIVE_PINS.update({'1':'P12','20':'P12','3':'P12','5':'GND','6':'GND',
                      '7':'GND','9':'GND','11':'GND','13':'PRAW','14':'P_NR',
                      '15':'PRAW','16':'PRAW','21':'GND'})
NEGATIVE_PINS = {str(i): None for i in range(1, 22)}
NEGATIVE_PINS.update({'1':'N12','20':'N12','3':'N_LDO_FB','7':'GND',
                      '13':'NRAW','14':'N_NR','15':'NRAW','16':'NRAW','21':'GND'})


def symbols(chip):
    # Functional positions intentionally keep input/EN left and OUT/SENSE right.
    # NC/program pins retain true manufacturer numbers and explicit no-connects.
    common=[(15,'IN','power_in','L'),(16,'IN','passive','L'),
            (13,'EN','input','L'),(14,'NR','passive','L'),
            (7,'GND','power_in','L'),(21,'EP_GND','passive','L'),
            (1,'OUT','power_out','R'),(20,'OUT','passive','R')]
    pos=common+[(3,'SENSE','input','R')]
    for n,label in [(4,'6P4V2'),(5,'6P4V1'),(6,'3P2V'),(8,'1P6V'),
                    (9,'0P8V'),(10,'0P4V'),(11,'0P2V'),(12,'0P1V')]:
        pos.append((n,label,'input','R'))
    for n in [2,17,18,19]:pos.append((n,'NC','no_connect','L'))
    neg=[(n,'NR/SS' if n==14 else name,typ,side) for n,name,typ,side in common]+[(3,'FB','input','R')]
    for n in [2,4,5,6,8,9,10,11,12,17,18,19]:
        neg.append((n,'NC','no_connect','L' if n in [2,4,5,6,8,9] else 'R'))
    return (chip('TPS7A4700RGWR',pos,'https://www.ti.com/lit/ds/symlink/tps7a47.pdf'),
            chip('TPS7A3301RGWR',neg,'https://www.ti.com/lit/ds/symlink/tps7a33.pdf'))


def populate(add, rr, cc, dd, R, pos, neg):
    sh='05_quiet_rails'
    add(sh,'U12',pos,'TPS7A4700RGWR',POSITIVE_PINS.copy(),'BigModular:'+FOOTPRINT,
        'C114839',mpn='TPS7A4700RGWR',manufacturer='Texas Instruments',
        note='ANY-OUT ONLY: 5/6/9/11 GND -> 12.000V; 4/8/10/12 float. SENSE3 final P12. EN13 PRAW. NR14 at ~12V. EP21 GND. Not a 1A supply rating.')
    add(sh,'U13',neg,'TPS7A3301RGWR',NEGATIVE_PINS.copy(),'BigModular:'+FOOTPRINT,
        'C90082',mpn='TPS7A3301RGWR',manufacturer='Texas Instruments',
        note='NEGATIVE IN15/16 and EN13=NRAW; OUT1/20=N12; FB3 negative divider; NR14=-1.175V approx; GND7/EP21=GND, never NRAW. No reverse isolation.')
    # Exact C12891: manufacturer DC-bias data rejects the former three-cap
    # positive OUT bank. 4/6/4/3 parallel parts pass the explicit prototype
    # tolerance/temperature/aging screen at 14.8V raw and 12.4V output.
    for refs,net,role in [([48,49,50,63],'PRAW','positive input'),
                          ([51,52,53,64,65,66],'P12','positive output'),
                          ([54,55,56,67],'NRAW','negative input'),
                          ([57,58,59],'N12','negative output')]:
        for i in refs:
            cc(sh,'C'+str(i),'22u 25V X5R',net,'GND','C12891','1206_3216',note=role+f' bank: {len(refs)} parallel CL31A226KAHNNNE. Prototype screen at 14.8V raw/12.4V output includes -10% tolerance, -15% temperature, 5% aging allowance. >=10u effective required; positive output >=20u. Typical data is not a guaranteed minimum; lot/bias/temperature and stability bench acceptance required. X5R maximum85C; low-ESR ceramic, nonpolar. See docs/ldo-evidence/capacitor-disposition.json.')
    cc(sh,'C60','1u 50V X7R','P_NR','GND','C28323','0805_2012',note='Positive NR sees ~12V; >=10n effective mandatory; 1u nominal targets low noise and ~122ms typical startup. Verify bias.')
    cc(sh,'C61','100n 50V X7R','N_NR','GND','C14663',note='Negative NR/SS ~-1.175V: 100n targets ~120ms typical startup, not guaranteed sequencing; 1u would be ~1.2s. Noise tradeoff must be measured.')
    cc(sh,'C62','10n 50V X7R','N12','N_LDO_FB','C57112',note='10n from OUT to FB across entire upper divider. Improves AC; fast N12 collapse may kick FB positive. Absolute-limit/shutdown validation required; see SBVA042 section2.3.')
    for ref,value,a,b,code in [
        ('R72','90.9k','N12','N_LDO_DIV','C728600'),
        ('R73','1.21k','N_LDO_DIV','N_LDO_FB','C705737'),
        ('R74','10k','N_LDO_FB','GND','C95204')]:
        add(sh,ref,R,value+' 0.1%',{'1':a,'2':b},'Resistor_SMD:R_0603_1608Metric',code,
            note='Precision negative divider: (90.9k+1.21k)/10k; -11.997925V before IFB. Extended candidate: Basic-policy exception NOT approved; assembly blocked. 25ppm/K TCR must be verified.')
    dd(sh,'D27','PRAW','P12',note='Reverse discharge shunt: anode2=P12, cathode1=PRAW. Not reverse blocking. Validate input collapse/backdrive and current/energy; no hot-parallel supply.')
    dd(sh,'D28','N12','NRAW',note='Negative reverse discharge shunt: anode2=NRAW, cathode1=N12. SS34 Vf does NOT establish OUT-IN >= -0.3V, nor FB/NR absolute limits. Transient qualification gate remains open; not reverse blocking.')
