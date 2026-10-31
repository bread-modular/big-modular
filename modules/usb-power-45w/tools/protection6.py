"""S6 additions: rail disconnects, retained fault latch, delivered-voltage status.

Imported by circuit45 only after its original S5 power stages are constructed.
All new signal nets are explicitly named so the existing native drawing engine
can join local label stubs. No PCB placement/routing is generated here.
"""


def extend(c, part, two, res, cap):
    by = {p['ref']: p for p in c}
    raw = {'+12V': 'P12_RAW', '+5V': 'P5_RAW', '-12V': 'N12_RAW'}
    # Converter feedback, bypass/bulk, clamps, local SMD LEDs and inverter ground
    # remain on the converter side. Only header pins retain the delivered rails.
    for p in c:
        if p['ref'] not in {'J2', 'J3'}:
            p['pins'] = {n: raw.get(v, v) for n, v in p['pins'].items()}
    for ref in ('C34','C35','C36'):
        by[ref]['fields']['Note'] = 'RAW converter-side bulk before the new rail protection; keep with converter output network, NOT after the switch.'
    for ref in ('D5','D6','D7'):
        by[ref]['fields']['Note'] = 'Local SMD RAW-rail presence only; separate protected-output panel LEDs are on page 07.'
    by['C2']['fields']['Note'] = 'U5 IN local bypass. S6 also has 1u input bypass on always-on logic LDO; qualify attach current including LDO output charging.'
    by['U5']['pins'].update({'13': 'RUN', '15': 'MAIN_OK', '16': 'MAIN_OK'})
    by['U5']['fields']['Note'] += '; S6 FLT + PGOOD wired-AND at 3.3 V; common RUN disconnect.'
    for u in ['U2', 'U3']:
        by[u]['pins']['2'] = 'MAIN_OK'
    # Eliminate the old VIN-referenced PGOOD divider and raw-voltage FLT pullup.
    c[:] = [p for p in c if p['ref'] not in {'R6', 'R7', 'R25', 'R22', 'D8'}]
    by['SW1']['pins'] = {'1': 'RESET_BTN_N', '3': 'RESET_BTN_N', '2': 'GND', 'MP': None}
    by['SW1']['fields']['Note'] = 'Common RESET: clears both latches, disables all series switches while pressed; >=20 ms supervisor holdoff after release. External capacitors are not force-discharged.'
    by['TP5']['pins']['1'] = 'MAIN_OK'; by['TP5']['value'] = 'MAIN_OK'
    by['TP6']['pins']['1'] = 'FAULT_LATCH'; by['TP6']['value'] = 'FAULT_LATCH'

    def efuse(u, at, vin, out, prefix):
        p = prefix
        c.append(part(u, 'TPS16630PWP', 'TPS16630PWPR', 'PWP20', at, 0,
                      {'1': vin, '2': vin, '3': vin, '4': None, '5': None, '6': vin,
                       '7': p+'_UV', '8': p+'_OV', '9': 'GND', '10': p+'_DVDT', '11': p+'_ILIM',
                       '12': None, '13': 'RUN', '14': None, '15': p+'_OK', '16': p+'_OK',
                       '17': None, '18': out, '19': out, '20': out, '21': 'GND'},
                      LCSC='C1849461', MPN='TPS16630PWPR', Manufacturer='Texas Instruments',
                      Note='Same IC as main eFuse. MODE open = local latch-off; common RUN resets it. 6.8k gives 2.647 A typical, screened 2.335-2.971 A. Not a guaranteed 2.5 A continuous rating. No reverse-current blocking.'))
    efuse('U6', (703.58, 63.5), 'P12_RAW', '+12V', 'P12')
    efuse('U7', (957.58, 63.5), 'P5_RAW', '+5V', 'P5')
    for base, x, p, vin, out, uvtop, uvbot, ovtop, ovbot in [
            (30, 635, 'P12', 'P12_RAW', '+12V', '100k', '13k', '100k', '10k'),
            (39, 889, 'P5', 'P5_RAW', '+5V', '33k', '12k', '33k', '9.1k')]:
        # Main current path is drawn through the IN/OUT banks; setting networks
        # below it have independent, named divider connections.
        rr = lambda k: 'R'+str(base+k)
        topnet = p+'_OV_SER' if p == 'P12' else vin
        c.append(res(rr(0), uvtop, (x, 119.38), vin, p+'_UV'))
        c.append(res(rr(1), uvbot, (x, 137.16), p+'_UV', 'GND'))
        c.append(res(rr(2), ovtop, (x+27.94,119.38), topnet, p+'_OV'))
        c.append(res(rr(3), ovbot, (x+27.94,137.16), p+'_OV', 'GND'))
        c.append(res(rr(4), '6.8k', (x+55.88,119.38), p+'_ILIM', 'GND', Note='Rail overload threshold; include IC, resistor tolerance and temperature, not exact amperes.'))
        c.append(res(rr(5), '10k', (x+83.82,119.38), 'V3V3', p+'_OK', Note='Wired AND: FLT, PGOOD and delivered-voltage comparator.'))
        c.append(res(rr(6), '10k', (x+111.76,119.38), out, 'GND', Note='Output bleed; no guaranteed discharge time for arbitrary external capacitance.'))
        c.append(res(rr(7), '100k', (x+139.7,119.38), 'RUN', 'GND', Note='SHDN default-off; shared with master pulldown.'))
        if p == 'P12':
            c.append(res(rr(8), '10k', (x+27.94,101.6), vin, topnet, Note='OVP top total 110k: 14.4 V nominal.'))
        cb = 37 if p == 'P12' else 40
        c.append(cap('C'+str(cb), '100n', 'C0603', (x+167.64,119.38), p+'_DVDT', 'GND', Note='~0.5 V/ms controlled output ramp; startup/load capacitance must be qualified.'))
        c.append(cap('C'+str(cb+1), '1u', 'C0603', (x+195.58,119.38), out, 'GND', Note='After rail eFuse, at output/header. Converter compensation capacitors stay upstream.'))
        c.append(cap('C'+str(cb+2), '100n', 'C0603', (x+223.52,119.38), vin, 'GND'))
    # Protected-rail polarity clamps (existing D2-D4 stay on the raw rails).
    for d, at, a, b in [('D12',(787.4,78.74),'+12V','GND'), ('D13',(1041.4,78.74),'+5V','GND'),
                         ('D14',(1041.4,393.7),'GND','-12V')]:
        c.append(two(d,'D_Schottky','SS34','SMA',at,a,b,rot=270,LCSC='C8678',MPN='SS34',Manufacturer='MDD',
                     Note='Output polarity clamp; does not protect against external power-source backfeed.'))

    # Negative hot-swap controller. VEE is the raw negative rail, not system GND.
    c.append(part('U8','LM5067MM','LM5067MM-2/NOPB','MSOP10',(703.58,276.86),0,
                  {'1':'N_VCC','2':'N_UV','3':'N_OV','4':'N_PWR','5':'N12_RAW','6':'N_TIMER',
                   '7':'N_SENSE_PIN','8':'N_GATE','9':'N_OUT_PIN','10':'N_PGD'},
                  LCSC='C181592',MPN='LM5067MM-2/NOPB',Manufacturer='Texas Instruments',
                  Note='Negative rail controller + Q4. 50 mV / 50 mOhm = 1 A nominal; 44-56 mV and resistor corners matter. Internal retry is overridden by the common retained latch after startup qualification.'))
    c.append(part('Q4','FQD13N06L','FQD13N06LTM','DPAK',(817.88,276.86),0,
                  {'1':'N_GATE','2':'-12V','3':'N_SENSE'},LCSC='C236914',MPN='FQD13N06LTM',Manufacturer='onsemi',
                  Note='G1 D2/tab S3. SENSE resistor on source side. Linear SOA reviewed against ~3.1 W power limit; validate fault pulses and board temperature. No reverse blocking.'))
    for ref,x in [('R48',784.86),('R49',800.1)]:
        c.append(two(ref,'R','0.1','R1206',(x,304.8),'N_SENSE','N12_RAW',LCSC='C25334',MPN='1206W4F100LT5E',Manufacturer='UNI-ROYAL',Tolerance='1%',
                     Note='Parallel pair = 50 mOhm. 250 mW each, Kelvin sense at the common terminals; nominal 25 mW each at 1 A.'))
    for ref,x in [('R50',635),('R51',650.24)]:
        c.append(two(ref,'R','10k','R1206',(x,243.84),'VIN','N_VCC',LCSC='C17902',MPN='1206W4F1002T5E',Manufacturer='UNI-ROYAL',Tolerance='1%',
                     Note='Parallel 5k VCC feed from VIN, not GND: guarantees headroom for the 13 V internal shunt at -12 V. Check at least 2 mA over qualified rails.'))
    c.append(cap('C43','1u','C0603',(673.1,243.84),'N_VCC','N12_RAW'))
    c.append(res('R52','68k',(635,335.28),'GND','N_UV'))
    c.append(res('R53','33k',(635,353.06),'N_UV','N12_RAW',Note='UV on ~9.15 V magnitude, off ~7.65 V; output-valid monitor is stricter.'))
    c.append(res('R54','47k',(662.94,335.28),'GND','N_OV'))
    c.append(res('R55','10k',(662.94,353.06),'N_OV','N12_RAW',Note='OV disconnect ~14.25 V magnitude; hysteresis from LM5067.'))
    c.append(res('R56','22k',(690.88,335.28),'N_PWR','N12_RAW',Note='P_LIMIT = 22k / (142000 x .05) = 3.10 W typical.'))
    c.append(cap('C44','1u','C0603',(718.82,335.28),'N_TIMER','N12_RAW',Note='~0.67 s insertion / ~42 ms fault timer typical. Full corner/startup/SOA screening in docs.'))
    c.append(res('R57','100k',(746.76,335.28),'N_GATE','N_SENSE',Note='Gate-source default-off bleed; not a replacement for controller fast pull-down.'))
    c.append(cap('C45','1u','C0603',(1031.24,353.06),'GND','-12V'))
    c.append(res('R58','10k',(1059.18,353.06),'GND','-12V',Note='Delivered negative rail bleed; not an active discharge.'))

    # Isolated level shifting preserves the system ground bus. U16 forces UVLO
    # low when RUN=0; U17 reports negative-controller PGD fault to 3.3-V logic.
    c.append(part('U16','LTV354','LTV-354T','OPTO4',(914.4,276.86),0,
                  {'1':'NEG_OFF_LED','2':'NEG_OFF_K','3':'N12_RAW','4':'N_UV'},
                  LCSC='C119090',MPN='LTV-354T',Manufacturer='Lite-On',Note='OFF command isolator. AC input LED; transistor E3 to NRAW, C4 to UVLO.'))
    for ref,x in [('R59',878.84),('R60',894.08)]:
        c.append(res(ref,'1k',(x,243.84),'V3V3','NEG_OFF_LED',Note='Parallel = 500 ohm; ~4 mA optical drive.'))
    c.append(part('Q5','2N7002','2N7002','SOT23',(911.86,309.88),0,{'1':'NOT_RUN','2':'GND','3':'NEG_OFF_K'},
                  LCSC='C8545',MPN='2N7002',Manufacturer='Jiangsu Changjing Electronics Technology Co., Ltd.',Note='Turns on U16 LED when RUN is low; no direct logic connection to negative VEE.'))
    c.append(part('U17','LTV354','LTV-354T','OPTO4',(1016,276.86),0,
                  {'1':'N_PGD_LED','2':'N_PGD','3':'GND','4':'N12_STATUS'},
                  LCSC='C119090',MPN='LTV-354T',Manufacturer='Lite-On',Note='PGD low relative to NRAW lights LED and pulls N12_OK low. Comparator also checks absolute delivered negative voltage.'))
    c.append(res('R61','10k',(980.44,243.84),'GND','N_PGD_LED',Note='~1 mA from system GND into PGD during negative-controller fault.'))
    c.append(res('R62','100k',(1049.02,243.84),'V3V3','N12_STATUS',Note='Low collector load for minimum optocoupler CTR at 1 mA; validate temperature/aging.'))

    c.append(res('R89','33',(756.92,271.78),'N_SENSE','N_SENSE_PIN',Note='LM5067 Fig 9-11 pin protection: Kelvin signal only, not load path. Typical 6 uA bias causes ~0.2 mV offset.'))
    c.append(res('R90','10k',(756.92,289.56),'-12V','N_OUT_PIN',Note='OUT reverse-excursion current limiting. On-state 0.1 uA bias gives ~1 mV error; disabled 50 uA can shift reading ~0.5 V.'))
    for d, net, y in [('D19','N_SENSE_PIN',375.92),('D20','N_OUT_PIN',398.78)]:
        c.append(part(d,'BAT54S','BAT54SLT1G','SOT23',(840.74,y),0,{'1':'N12_RAW','2':net,'3':net},
                      LCSC='C19726',MPN='BAT54SLT1G',Manufacturer='onsemi',Note='One diode used as VEE-to-pin negative clamp; other diode shorted. 30 V part for this local 12 V rail, NOT a 100 V input application. Validate reverse-collapse/clamp pulse limits.'))
    c.append(part('U19','LVC1G17','SN74LVC1G17DBVR','SOT235',(800.1,591.82),0,
                  {'1':None,'2':'N12_STATUS','3':'GND','4':'N12_OK','5':'V3V3'},
                  LCSC='C7836',MPN='SN74LVC1G17DBVR',Manufacturer='Texas Instruments',Note='Schmitt input accepts slow 100k optocoupler pull-up; clean logic to latch and LED gate.'))
    c.append(cap('C58','100n','C0603',(843.28,591.82),'V3V3','GND'))

    # Always-on 60 V logic supply: fault memory survives main-eFuse shutdown.
    c.append(part('U9','TPS7A1633DGN','TPS7A1633DGNR','DGN8',(60.96,462.28),0,
                  {'1':'V3V3','2':None,'3':None,'4':'GND','5':'VPD','6':None,'7':None,'8':'VPD','9':'GND'},
                  LCSC='C181239',MPN='TPS7A1633DGNR',Manufacturer='Texas Instruments',Note='60 V always-on logic LDO before main eFuse. Fixed version DNC pin2 remains NC. Thermally qualify logic+LED load.'))
    c.append(cap('C46','1u','C0603',(27.94,454.66),'VPD','GND',Note='Attach capacitance remains below 10 uF nominal; input layout must be checked.'))
    c.append(cap('C47','10u','C1206',(96.52,454.66),'V3V3','GND',Note='>=2.2u effective LDO output capacitance.'))
    c.append(res('R63','10k',(96.52,482.6),'V3V3','MAIN_OK',Note='Main FLT and PGOOD wired AND, now 3.3-V logic.'))
    c.append(res('R64','10k',(124.46,482.6),'RUN','GND',Note='Default-off for SHDN pins before logic power is valid.'))

    # POR/manual RESET and separate qualified-input startup timer.
    c.append(part('U10','TPS3808G01','TPS3808G01DBVR','SOT236',(177.8,462.28),0,
                  {'1':'RESET_N','2':'GND','3':'POR_SENSE','4':None,'5':'RESET_BTN_N','6':'V3V3'},
                  LCSC='C19653',MPN='TPS3808G01DBVR',Manufacturer='Texas Instruments',Note='2.916 V nominal logic POR, 20 ms typical holdoff (CT open); asynchronous reset of both latches.'))
    c.append(res('R65','47k',(149.86,497.84),'POR_SER','POR_SENSE'))
    c.append(res('R91','15k',(149.86,480.06),'V3V3','POR_SER',Note='62k total POR top: 2.916 V nominal; adequate margin below minimum 3.3-V LDO output.'))
    c.append(res('R66','10k',(149.86,515.62),'POR_SENSE','GND'))
    c.append(res('R67','10k',(177.8,497.84),'V3V3','RESET_N'))
    c.append(res('R68','10k',(205.74,497.84),'V3V3','RESET_BTN_N'))
    c.append(cap('C48','100n','C0603',(233.68,497.84),'V3V3','GND'))
    c.append(part('U11','TPS3808G01','TPS3808G01DBVR','SOT236',(302.26,462.28),0,
                  {'1':'START_READY','2':'GND','3':'START_SENSE','4':'START_CT','5':'RESET_N','6':'V3V3'},
                  LCSC='C19653',MPN='TPS3808G01DBVR',Manufacturer='Texas Instruments',Note='Timer begins only at RUN and >=20-V-class input. 1u gives ~5.7 s qualification, not reset by individual bad rails.'))
    c.append(res('R69','33k',(274.32,497.84),'TIMER_GO','START_SENSE'))
    c.append(res('R70','10k',(274.32,515.62),'START_SENSE','GND'))
    c.append(cap('C49','1u','C0603',(302.26,497.84),'START_CT','GND'))
    c.append(res('R71','10k',(330.2,497.84),'V3V3','START_READY'))
    c.append(cap('C50','100n','C0603',(358.14,497.84),'V3V3','GND'))

    c.append(part('U12','HC74_DUAL','SN74HC74DR','SO14',(66.04,607.06),0,
                  {'1':'RESET_N','2':'V3V3','3':'START_READY','4':'V3V3','5':'ARMED','6':None,'7':'GND',
                   '8':'NOT_FAULT','9':'FAULT_LATCH','10':'V3V3','11':'FAULT_CLK','12':'V3V3','13':'RESET_N','14':'V3V3'},
                  LCSC='C6762',MPN='SN74HC74DR',Manufacturer='Texas Instruments',Note='A stores ARMED until RESET; B stores FAULT until RESET. Input loss after arming must not erase ARMED. No firmware.'))
    c.append(part('U13','HC08_QUAD','SN74HC08DR','SO14',(205.74,607.06),0,
                  {'1':'RESET_N','2':'NOT_FAULT','3':'RUN','4':'ARMED','5':'BAD_FILTERED','6':'FAULT_CLK','7':'GND',
                   '8':'TIMER_GO','9':'RUN','10':'V20_OK','11':'MAIN_LED_OK','12':'MAIN_OK','13':'V20_OK','14':'V3V3'},
                  LCSC='C337768',MPN='SN74HC08DR',Manufacturer='Texas Instruments',Note='RUN=RESET_N & NOT_FAULT; fault clock=ARMED & filtered bad; timer=RUN & V20_OK; main LED=main status & input voltage.'))
    c.append(part('U14','HC20_DUAL','SN74HC20DR','SO14',(345.44,607.06),0,
                  {'1':'MAIN_LED_OK','2':'P12_OK','3':None,'4':'P5_OK','5':'N12_OK','6':'ANY_BAD','7':'GND',
                   '8':'NOT_RUN','9':'RUN','10':'RUN','11':None,'12':'RUN','13':'RUN','14':'V3V3'},
                  LCSC='C2867684',MPN='SN74HC20DR',Manufacturer='Texas Instruments',Note='Four-input NAND combines independent good signals; second NAND inverts RUN for negative switch disable.'))
    c.append(part('U15','LVC1G17','SN74LVC1G17DBVR','SOT235',(462.28,607.06),0,
                  {'1':None,'2':'BAD_RC','3':'GND','4':'BAD_FILTERED','5':'V3V3'},
                  LCSC='C7836',MPN='SN74LVC1G17DBVR',Manufacturer='Texas Instruments',Note='Schmitt buffer on 10k/100n filter; suppresses short status glitches. Hardware current limiting remains immediate.'))
    c.append(res('R72','10k',(429.26,566.42),'ANY_BAD','BAD_RC'))
    c.append(cap('C51','100n','C0603',(457.2,566.42),'BAD_RC','GND'))
    for i,x in enumerate([66.04,205.74,345.44,462.28],52):
        c.append(cap('C'+str(i),'100n','C0603',(x,655.32),'V3V3','GND'))

    # Voltage presence is measured AFTER each series protection element. The
    # thresholds intentionally indicate usable/present rails, not precision +/-5%.
    c.append(part('U18','LM2901_QUAD','LM2901DR','SO14',(708.66,591.82),0,
                  {'1':'P12_OK','2':'P5_OK','3':'V3V3','4':'REF_GOOD','5':'MON_P5','6':'REF_GOOD','7':'MON_P12',
                   '8':'MON_N12','9':'REF_GOOD','10':'REF_GOOD','11':'MON_20','12':'GND','13':'V20_OK','14':'N12_STATUS'},
                  LCSC='C7932',MPN='LM2901DR',Manufacturer='Texas Instruments',Note='Output-valid comparators. Main/P12/P5 use signal on + input; N12 uses offset negative sense on - input. One input remains in common-mode range. Clamp negative sense.'))
    c.append(res('R73','3.3k',(635,660.4),'V3V3','REF_GOOD'))
    c.append(res('R74','1k',(635,678.18),'REF_GOOD','GND'))
    c.append(cap('C56','100n','C0603',(657.86,678.18),'REF_GOOD','GND'))
    c.append(cap('C57','100n','C0603',(680.72,678.18),'V3V3','GND'))
    c.append(res('R75','120k',(711.2,660.4),'+12V','MON_P12'))
    c.append(res('R76','10k',(711.2,678.18),'MON_P12','GND'))
    c.append(res('R77','33k',(744.22,642.62),'+5V','MON_P5_SER'))
    c.append(res('R78','12k',(744.22,660.4),'MON_P5_SER','MON_P5'))
    c.append(res('R79','10k',(744.22,678.18),'MON_P5','GND'))
    c.append(res('R80','100k',(777.24,642.62),'V3V3','MON_N_SER'))
    c.append(res('R81','10k',(777.24,660.4),'MON_N_SER','MON_N12'))
    c.append(res('R82','470k',(777.24,678.18),'MON_N12','-12V'))
    c.append(part('D15','BAT54S','BAT54SLT1G','SOT23',(820.42,678.18),0,
                  {'1':'GND','2':'V3V3','3':'MON_N12'},LCSC='C19726',MPN='BAT54SLT1G',Manufacturer='onsemi',Note='Clamp offset negative-sense node to logic rails; resistor current is microamps. Validate cold negative-voltage excursions.'))
    c.append(res('R83','220k',(855.98,660.4),'VPD','MON_20'))
    c.append(res('R84','10k',(855.98,678.18),'MON_20','GND'))
    c.append(res('R85','10k',(883.92,660.4),'V3V3','V20_OK'))

    # Four user-facing LEDs. Existing D8 is now MAIN status, not +5V presence.
    # All use 3.3-V status drive; no LED borrows power from a different output rail.
    # Q10 gates the common return with RUN so latched OFF cannot look healthy due
    # to residual charge or backfeeding. Local original SMD D5/6/7 indicate raw rails.
    for d,r,q,x,status,label in [('D8','R22','Q6',937.26,'MAIN_LED_OK','MAIN'),
                                 ('D16','R86','Q7',993.14,'P12_OK','+12V'),
                                 ('D17','R87','Q8',1049.02,'P5_OK','+5V'),
                                 ('D18','R88','Q9',1104.9,'N12_OK','-12V')]:
        an,cat='_PANEL_'+label+'_A','_PANEL_'+label+'_K'
        c.append(res(r,'1k',(x,591.82),'V3V3',an,Note='~1 mA red 3 mm panel LED; status, not raw voltage.'))
        c.append(two(d,'LED',label+' LED','LED3EDGE',(x,607.06),cat,an,rot=90,
                     Note='Hand-soldered 3 mm horizontal panel LED. '+label+' status; OFF on invalid output or common latched shutdown.'))
        c.append(part(q,'2N7002','2N7002','SOT23',(x-2.54,627.38),0,{'1':status,'2':'LED_RETURN','3':cat},
                      LCSC='C8545',MPN='2N7002',Manufacturer='Jiangsu Changjing Electronics Technology Co., Ltd.',Note='LED current only; gate driven by corresponding valid/status net.'))
    c.append(part('Q10','2N7002','2N7002','SOT23',(1013.46,695.96),0,{'1':'RUN','2':'GND','3':'LED_RETURN'},
                  LCSC='C8545',MPN='2N7002',Manufacturer='Jiangsu Changjing Electronics Technology Co., Ltd.',Note='Common LED enable: all status LEDs off when RESET/FAULT has disabled rails.'))

    # PWR_FLAG declares real power arriving through passive feed/switch paths;
    # it is not an assertion that the rail is on during shutdown.
    for ref,net,at in [('#FLG08','N_VCC',(685.8,220.98)),('#FLG09','-12V',(1041.4,419.1))]:
        c.append(part(ref,'PWR_FLAG','PWR_FLAG',None,at,0,{'1':net}))
    for i,(net,x) in enumerate([('RUN',25.4),('ARMED',60.96),('FAULT_LATCH',96.52),('P12_OK',132.08),('P5_OK',167.64),('N12_OK',203.2),('V20_OK',238.76),('V3V3',274.32)],9):
        c.append(part('TP'+str(i),'TestPoint',net,'TP',(x,721.36),0,{'1':net},Note='Copper-only diagnostic; no assembly component.'))
    return c


def extra_drawing():
    w=[]
    for u in ['U6','U7']:
        w += [[u+'.1',u+'.3'],[u+'.18',u+'.20']]
    for a,b in [('R30.2','R31.1'),('R32.2','R33.1'),('R38.2','R32.1'),
                ('R39.2','R40.1'),('R41.2','R42.1'),('R52.2','R53.1'),('R54.2','R55.1'),
                ('R91.2','R65.1'),('R65.2','R66.1'),('R69.2','R70.1'),('R73.2','R74.1'),('R75.2','R76.1'),
                ('R77.2','R78.1'),('R78.2','R79.1'),('R80.2','R81.1'),('R81.2','R82.1'),('R83.2','R84.1')]:
        w.append([a,b])
    for r,d,q in [('R22','D8','Q6'),('R86','D16','Q7'),('R87','D17','Q8'),('R88','D18','Q9')]:
        w += [[r+'.2',d+'.2'],[d+'.1',q+'.3']]
    return w


TEXTS6 = [
 ((609.6,25.4),'S6: PER-RAIL OUTPUT DISCONNECTS',2.2),
 ((609.6,30.48),'U6/U7 = same TPS16630 as main. 2.647 A nominal; screened 2.335-2.971 A. MODE open = local latch.',1.5),
 ((635,180.34),'Feedback, compensation, bulk and SMD indicator LEDs remain upstream on RAW rails. Headers receive protected rails only.',1.5),
 ((609.6,205.74),'NEGATIVE RAIL: LM5067 + 60 V N-MOSFET; GND BUS IS NEVER SWITCHED',2),
 ((609.6,210.82),'1.0 A nominal (0.863-1.143 A screened); ~3.1 W MOSFET power limit; local restart overridden by common RUN.',1.5),
 ((635,441.96),'N_VCC referenced to N12_RAW. Optical OFF command and PGD translation; no direct negative logic into 3.3 V.',1.5),
 ((25.4,419.1),'ALWAYS-ON FAULT MEMORY / MANUAL RESET (NO MCU)',2),
 ((25.4,424.18),'RUN = RESET_N & !FAULT. Arm once after valid 20-V-class input + startup window; only RESET/power cycle clears.',1.5),
 ((25.4,551.18),'QUALIFICATION: ~5.7 s typical startup window. Once ARMED, input/rail/status loss latches every output OFF.',1.5),
 ((25.4,556.26),'10k/100n + Schmitt filter rejects short status glitches. Internal eFuse/FET protection is active during startup.',1.5),
 ((25.4,744.22),'RESET disconnects all outputs but is NOT active capacitor discharge. Fault LED pattern is not retained: all four turn off after common shutdown.',1.5),
 ((609.6,530.86),'DELIVERED-RAIL VOLTAGE MONITORS AND FOUR PANEL LEDS',2),
 ((609.6,535.94),'Typical valid thresholds: +12 >9.98 V, +5 >4.22 V, -12 < -10.05 V; input >17.65 V. Not precision regulation indicators.',1.5),
 ((609.6,723.9),'D8 MAIN = main PGOOD/FLT + input-valid + RUN. D16/D17/D18 = protected-rail status + RUN.',1.5),
 ((609.6,728.98),'All four OFF on latched fault/reset; main also OFF with 5/9/12/15 V only. D5/D6/D7 are retained local RAW LEDs.',1.5),
 ((25.4,782.32),'SCHEMATIC ONLY: validate capacitive startup, fault timing, LM5067 SOA, loss of each rail, reset, LED truth table and thermal behavior.',1.8),
 ((25.4,787.4),'Not for paralleling supplies. Neither rail eFuses nor negative switch provide reverse blocking; caps/backfeed may hold output voltages after disconnect.',1.5),
]
