"""Render the reviewed six-sheet V1 presentation into a NEW candidate.

Native sheets own reviewed wires/placement. electrical_design owns inventory,
fields and pin intent. Ref/pin/net drift fails closed: circuit changes need an
explicit native schematic edit, never replay the retired eight-sheet generator.
"""
import copy
import json
from pathlib import Path
from sexp import parse, dump, nodes, one, atom
from schematic_connectivity import Connectivity

SHEET_NAMES=('01_input_protection','02_hardgate','03_bucks','04_bipolar','07_output_rails')
SHEET_TITLES=('USB PD input','Autonomous hardware window and retry','Independent buck converters','Direct bipolar rails','Board output and power LED')


def render(hw,sheets,lib,uid):
    source=Path(__file__).resolve().parents[1]/'hardware'
    parts={d['ref']:d for sh in sheets.values() for d in sh['parts']}
    graph=Connectivity(source)
    assert set(graph.refs)==set(parts), 'Native presentation inventory differs; explicit schematic edit required'
    assert graph.named_pins()=={(r,p):n for r,d in parts.items() for p,n in d['nets'].items()}, 'Native presentation pin/net drift'
    for name in ('big_modular',)+SHEET_NAMES:
        original=(source/(name+'.kicad_sch')).read_text()
        tree=parse(original)
        for symbol in nodes(tree,'symbol'):
            props={p[1]:p for p in nodes(symbol,'property')}
            d=parts[props['Reference'][2]]
            updates={'Value':d['value'],'Footprint':d['fp'],'MPN':d['mpn'],'LCSC':d['lcsc'],'NOTE':d['note'],'Datasheet':d['datasheet']}
            if d.get('manufacturer'):updates['Manufacturer']=d['manufacturer']
            for key,value in updates.items():
                if key not in props:
                    prop=copy.deepcopy(props['Value']);prop[1]=key;prop[2]=value
                    prop[-1].append(atom('hide'));symbol.append(prop)
                else:props[key][2]=value
        if name=='big_modular':
            for text in nodes(tree,'text'):
                if 'J7 is the physical output boundary' in text[1]:
                    text[1]='J7 is the physical output boundary: one manual harness.\nTop USB/retry/3mm LED are placed together in the native boards.\nAll64 footprints synchronized and routed; HRO USB-C; passive front panel.'
        # Stage wording is factual; engineering limits remain in the engineering notes.
        content=dump(tree).replace('UNROUTED V1 / NOT A MANUFACTURING RELEASE','V1 - UNROUTED / PLACEMENT NEXT')
        content=content.replace('UNROUTED / NOT A MANUFACTURING RELEASE','V1 - UNROUTED / PLACEMENT NEXT')
        content=content.replace('V1 - UNROUTED / PLACEMENT NEXT','V1 - ROUTED HRO CARRIER / PASSIVE FRONT PANEL')
        rendered=content+'\n'
        # A user's native KiCad formatting is not a reason to rewrite their sheet.
        if parse(rendered)==parse(original):rendered=original
        (hw/(name+'.kicad_sch')).write_text(rendered)
