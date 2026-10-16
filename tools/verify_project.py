#!/usr/bin/env python3
"""Independent electrical/mechanical regression; never operational approval."""
from pathlib import Path
import json,sys,itertools,subprocess,xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).parent))
from electrical_checks import check
from verify_stack import verify
root=Path(__file__).resolve().parent.parent
result=check(root/'hardware',root/'docs/pin-net-audit.json',root/'BOM.csv')
# Native connectivity is checked independently of the generator and graph.
xml=root/'reports/electrical-checkpoint/verified-native/netlist.xml'
if not xml.exists():raise FileNotFoundError('Run the final common native check first: '+str(xml))
actual={}
for net in ET.parse(xml).getroot().findall('./nets/net'):
 name=net.get('name').rsplit('/',1)[-1]
 for n in net.findall('node'):actual[(n.get('ref'),n.get('pin'))]=name
expected=json.loads((root/'docs/pin-net-audit.json').read_text());count=0
for ref,pins in expected.items():
 if ref.startswith('#'):continue
 for p,n in pins.items():
  if n is not None:assert actual.get((ref,p))==n,('native pin',ref,p,n,actual.get((ref,p)));count+=1
# Keep the hardware UV/OV resistor/tolerance envelope independent of firmware.
def bounds(rt,threshold):
 vals=[v*(1+rt*a/(100e3*b))+i*rt*a for v,a,b,i in itertools.product(threshold,[.99,1.01],[.99,1.01],[-100e-9,100e-9])]
 return [min(vals),max(vals)]
uvr=bounds(562e3,[1.175,1.225]);uvf=bounds(562e3,[1.08,1.125]);ovr=bounds(806e3,[1.17,1.225]);ovf=bounds(806e3,[1.085,1.125])
assert uvf[0]>5.5 and uvr[1]<8.55 and ovr[1]<15 and ovf[0]>9.45
assert 10e-6*10e3*1.01<.55
assert .611*(1+100e3*1.001/(12.9e3*.999))<5.5
info=subprocess.check_output(['pdfinfo',str(root/'docs/schematic.pdf')],text=True)
assert next(l.split()[-1] for l in info.splitlines() if l.startswith('Pages:'))=='8'
stack=verify(root/'hardware',root/'docs/assembly-geometry.json')
result.update(native_connected_pins=count,boards=stack['boards'],mechanics=stack['mechanics'],UV_rising=uvr,UV_falling=uvf,OV_rising=ovr,OV_falling=ovf,firmware_target_build='BLOCKED: avr-gcc unavailable',source_scope='schematic only; mechanical PCBs preserved')
(root/'reports/geometry-and-net-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
