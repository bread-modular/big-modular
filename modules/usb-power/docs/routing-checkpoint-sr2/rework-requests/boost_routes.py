#!/usr/bin/env python3
"""Explicit manually chosen boost connections -> common operations JSON.
No search/path-finding/router. Coordinates below are individually reviewed.
"""
import json
from pathlib import Path
import uuid
HERE=Path(__file__).resolve().parent
N=uuid.uuid5(uuid.NAMESPACE_URL,'usb-power/sr2-rework072/manual-boost-v1')
ops=[]
notes=[]

def pad(ref,num):return {'pad':{'ref':ref,'number':str(num)}}
def route(label,net,width,a,b,points=(),layer='F.Cu',reason=''):
    uid=str(uuid.uuid5(N,label))
    ops.append({'op':'add_polyline','uuid':uid,'net':net,'layer':layer,'width_mm':width,'start':a,'end':b,'waypoints':list(points)})
    notes.append({'label':label,'uuid':uid,'net':net,'reason':reason})
    return uid

def via(label,net,xy,diam=.65):
    uid=str(uuid.uuid5(N,label));ops.append({'op':'add_via','uuid':uid,'net':net,'at':xy,'diameter_mm':diam,'drill_mm':.3});return {'uuid':uid}

B='/Direct 9V positive boost/'
route('input-bank','/VPROT',1.2,pad('C82',1),pad('C83',1),reason='Input-bank positive spine on front copper; avoid return-pad row')
route('inductor-input','/VPROT',1.2,pad('C83',1),pad('L5',1),[[109.325,78.8]],reason='Short input-capacitor to inductor path around bank return pads')
route('switch-main',B+'PBOOST_SW',1.2,pad('L5',2),pad('D29',2),[[126.35,78.8]],reason='Wide 45-degree inductor-to-rectifier switching path; no vias')
sw=route('switch-fanout',B+'PBOOST_SW',.25,pad('U14',16),pad('D29',2),[[129.05,82.9],[128.4,82.25],[128,82.25]],reason='QFN limited-width fanout; trunk overlaid wider up to 82.25 mm')
route('switch-trunk-overlay',B+'PBOOST_SW',1.0,pad('D29',2),{'track':str(uuid.uuid5(uuid.UUID(sw),'3')),'at':[128,82.25]},reason='Widen long trunk without widening adjacent QFN pad escapes')
route('switch-pin15',B+'PBOOST_SW',.25,pad('U14',15),pad('U14',16),reason='Adjacent parallel switch pads')
route('switch-pin1',B+'PBOOST_SW',.25,pad('U14',1),pad('U14',16),[[128.4,83.0]],reason='Short left/top switch-pad tie clear of exposed grounded pad')
route('vin-decouple','/VPROT',.25,pad('C88',1),pad('U14',2),[[127.8,84.475],[127.8,84.15]],reason='Local VIN decoupler, not main inductor load-current feed')
route('enable-vin','/VPROT',.25,pad('U14',2),pad('U14',3),reason='EN tied to VIN as frozen schematic specifies')
route('soft-start',B+'PBOOST_SS',.25,pad('U14',4),pad('C85',1),[[128,85.55],[127.775,85.55]],reason='Direct quiet SS connection south/west, away from switching node')
route('comp-to-r',B+'PBOOST_COMP',.25,pad('U14',7),pad('R89',1),[[130.05,86.325],[129.2,86.325]],reason='Short analog COMP fanout south of IC')
route('comp-c',B+'PBOOST_COMP',.25,pad('R89',1),pad('C87',1),[[131.05,87.175]],reason='Local compensation C parallel at same COMP point')
route('comp-series',B+'PBOOST_COMP_RC',.25,pad('R89',2),pad('C86',1),[[129.2,90.65]],reason='Compensation series branch, no shared high-current copper')
route('fb-divider',B+'PBOOST_FB',.25,pad('R86',2),pad('R87',1),reason='Compact feedback-divider junction')
route('fb-sense',B+'PBOOST_FB',.25,pad('U14',8),pad('R86',2),[[131.05,86.3],[132.725,86.3]],reason='Dedicated feedback sense outside switch loop; output Kelvin source still to be routed')
route('freq',B+'PBOOST_FREQ',.25,pad('U14',9),pad('R88',1),[[132,85.15],[132,82.525]],reason='Frequency resistor path east of grounded IC pins, not switch pins')
route('freq-series',B+'PBOOST_FREQ_SER',.25,pad('R88',2),pad('R90',1),[[133.2,79.5]],reason='Frozen two-resistor timing network')
# Deliberate returns to the existing In1.Cu ground plane, ordinary 0.3-mm drills.
route('ep-to-pgnd','/GND',.3,pad('U14',17),pad('U14',14),reason='Local exposed-pad to power-ground tie')
route('pgnd-top','/GND',.3,pad('U14',14),pad('U14',13),reason='Top power-ground pins paired')
route('pgnd-east','/GND',.3,pad('U14',13),pad('U14',12),reason='Ground-only perimeter tie')
route('pgnd-east11','/GND',.3,pad('U14',12),pad('U14',11))
route('pgnd-east10','/GND',.3,pad('U14',11),pad('U14',10))
route('agnd-to-ep','/GND',.3,pad('U14',6),pad('U14',17),reason='Quiet analog return directly to exposed ground pad')
route('agnd-bottom','/GND',.3,pad('U14',5),pad('U14',6))
g1=via('pgnd-via1','/GND',[130.9,81.8]);g2=via('pgnd-via2','/GND',[131.65,81.8])
route('pgnd-via-feed','/GND',.5,pad('U14',13),g1,[[130.9,82.65]],reason='Two parallel ground vias near boost switch return, outside QFN lands')
route('pgnd-vias','/GND',.6,g1,g2)
route('ss-ground','/GND',.4,pad('U14',5),pad('C85',2),[[128.8,86.075]],reason='Local analog return, not daisy-chained with switch path')
g3=via('quiet-via1','/GND',[127.575,88.3])
route('ss-plane','/GND',.5,pad('C85',2),g3)
route('comp-ground','/GND',.4,pad('C87',2),pad('C86',2),[[131.1,90.65]])
route('fb-ground','/GND',.4,pad('R87',2),pad('C87',2),[[131.35,89.025]],reason='Quiet divider return through local ground, no power-loop current')
g4=via('quiet-via2','/GND',[132,90.0])
route('comp-plane','/GND',.5,pad('C86',2),g4,[[131.25,90.75]])
g5=via('freq-via','/GND',[136.525,78.5])
route('freq-ground','/GND',.4,pad('R90',2),g5)

if __name__=='__main__':
    for name,data in [('boost-001.routes.json',{'schema_version':1,'operations':ops}),('boost-001.intent.json',{'method':'manual explicit routes, no autorouter','accepted_placement_preserved':'L5 (119.8,78.8),0,F.Cu','routes':notes,'not_complete':'PRAW output/Kelvin feed, remaining input/return and negative converter routing pending; these connections alone are not a complete supply'})]:
        with (HERE/name).open('x') as f:json.dump(data,f,indent=2);f.write('\n')
    print(len(ops),'explicit operations')
