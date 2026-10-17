"""Render the reviewed seven-sheet ES1 presentation into a NEW candidate.

Native sheets own reviewed wires/placement. electrical_design owns inventory,
fields and pin intent. Ref/pin/net drift fails closed: circuit changes need an
explicit native schematic edit, never replay the retired eight-sheet generator.
"""
import copy
import json
from pathlib import Path
from sexp import parse, dump, nodes, one, atom
from schematic_connectivity import Connectivity

SHEET_NAMES=('01_input_protection','02_hardgate','03_bucks','04_bipolar','05_quiet_rails','07_output_rails')
SHEET_TITLES=('USB PD input','Autonomous hardware window and retry','Independent buck converters','Direct bipolar rails','Quiet bipolar post-regulators','Board output and power LED')


def render(hw,sheets,lib,uid,source=None):
    source=source or Path(__file__).resolve().parents[1]/'hardware'
    parts={d['ref']:d for sh in sheets.values() for d in sh['parts']}
    graph=Connectivity(source)
    assert set(graph.refs)==set(parts), 'Native presentation inventory differs; explicit schematic edit required'
    assert graph.named_pins()=={(r,p):n for r,d in parts.items() for p,n in d['nets'].items()}, 'Native presentation pin/net drift'
    for name in ('usb-power',)+SHEET_NAMES:
        original=(source/(name+'.kicad_sch')).read_text()
        tree=parse(original)
        embedded=one(tree,'lib_symbols')
        if embedded:
            for i,sym in enumerate(embedded[1:],1):
                kind=sym[1].split(':',1)[-1]
                if kind in ('TPS7A4700RGWR','TPS7A3301RGWR'):
                    replacement=copy.deepcopy(lib[kind]);replacement[1]=sym[1];embedded[i]=replacement
        for symbol in nodes(tree,'symbol'):
            props={p[1]:p for p in nodes(symbol,'property')}
            d=parts[props['Reference'][2]]
            updates={'Value':d['value'],'Footprint':d['fp'],'MPN':d['mpn'],'LCSC':d['lcsc'],'NOTE':d['note'],'Datasheet':d['datasheet']}
            if d.get('manufacturer'):updates['Manufacturer']=d['manufacturer']
            if d['ref']=='D10':
                one(symbol,'dnp')[1]=atom('yes')
                updates['JLCPCB Exclude']='yes'
                updates['JLCPCB Audit Requirements']=json.dumps({'reason':'D10 is DNP by user; no fitted purchasing or assembly.'})
            if d['ref'] in ('J1','SW1'):
                # Explicitly source these SMT interfaces; supplier mixed shell/J-lead
                # process acceptance is separate, not a hidden manual exclusion.
                updates['JLCPCB Exclude']='no'
                updates['JLCPCB Audit Requirements']=json.dumps({'assembly':'jlcpcb','reason':'Economy catalog candidate; supplier process/preview approval pending.'})
            for key,value in updates.items():
                if key not in props:
                    prop=copy.deepcopy(props['Value']);prop[1]=key;prop[2]=value
                    prop[-1].append(atom('hide'));symbol.append(prop)
                else:props[key][2]=value
        if name=='usb-power':
            for text in nodes(tree,'text'):
                if 'J7 is the physical output boundary' in text[1]:
                    text[1]='J7 is the physical output boundary: one manual harness.\nTop USB/retry/3mm LED are placed together in the native boards.\nLDO-R1: quiet +/-12V, capacitor-bank revision; prototype bench qualification pending.'
        # Stage wording is factual; engineering limits remain in the engineering notes.
        content=dump(tree).replace('UNROUTED V1 / NOT A MANUFACTURING RELEASE','V1 - UNROUTED / PLACEMENT NEXT')
        content=content.replace('UNROUTED / NOT A MANUFACTURING RELEASE','V1 - UNROUTED / PLACEMENT NEXT')
        if name in ('usb-power','04_bipolar','05_quiet_rails'):
            content=content.replace('V1 - ROUTED HRO CARRIER / PASSIVE FRONT PANEL','LDO-R1 PROTOTYPE / PASSIVE FRONT PANEL')
            for old in ('ES1 SOURCE ONLY / PCB INTEGRATION PENDING','ES1 ELECTRICAL SOURCE / PCB INTEGRATION PENDING','PCB INTEGRATION PENDING - NOT FOR FABRICATION','ES1 source only'):
                content=content.replace(old,'LDO-R1 PROTOTYPE / BENCH QUALIFICATION PENDING')
        final_tree=parse(content)
        if name in ('usb-power','04_bipolar','05_quiet_rails') and one(final_tree,'title_block'):
            one(one(final_tree,'title_block'),'rev')[1]='LDO-R1'
        rendered=dump(final_tree)+'\n'
        # A user's native KiCad formatting is not a reason to rewrite their sheet.
        from native_sheet_patch import rewrite
        rendered=rewrite(original,parse(rendered))
        (hw/(name+'.kicad_sch')).write_text(rendered)
