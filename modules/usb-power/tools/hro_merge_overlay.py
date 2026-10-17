#!/usr/bin/env python3
"""Prepare a NEW HRO hardware review overlay, preserving another saved presentation.

Never writes input/current main or commits. Copy the user's freshly saved hardware
closure first; inspect output and native checks before any user-controlled merge.
Only J1 identity/hidden shared pins, three exact footprint filters and stage text
are patched in sheets. Five inherited four-way wire junctions become paired Ts
with unchanged connectivity; all other wires/layout/non-J1 instances retain bytes.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
from sexp import parse,dump,nodes,one,atom
from hro_connector import CONTACT_TO_LAND,SYMBOL,MPN,LCSC,FOOTPRINT,DATASHEET,NOTE
from schematic_connectivity import Connectivity
ROOT=Path(__file__).resolve().parents[1]
FILTERS={'Regulator_Switching_TPS65131RGE':'Texas_RGE0024B_VQFN-24-1EP_4x4mm_P0.5mm_EP2.45x2.45mm',
         'Connector_Generic_Conn_02x08_Odd_Even':'WireLanding_2x08_P2.54mm'}


def spans(text):
    stack=[]
    for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
        if m.group()=='(':stack.append(m.start())
        elif m.group()==')':
            start=stack.pop();yield start,m.end(),len(stack)
    assert not stack


def patch(text, hro_lib):
    edits=[]
    for a,b,depth in spans(text):
        raw=text[a:b]
        if depth not in (1,2) or not re.match(r'\(symbol\s',raw):continue
        form=parse(raw)
        if depth==2 and isinstance(form[1],str):
            name=form[1].split(':')[-1]
            if name=='Connector_USB_C_Receptacle_USB2.0_16P':edits.append((a,b,dump(hro_lib)))
            elif name in FILTERS:
                for prop in nodes(form,'property'):
                    if prop[1]=='ki_fp_filters':prop[2]=FILTERS[name]
                edits.append((a,b,dump(form)))
        elif depth==1:
            props={p[1]:p for p in nodes(form,'property')}
            if props.get('Reference',[None,None,None])[2]!='J1':continue
            assert one(form,'lib_id')[1] in ['BigModular:Connector_USB_C_Receptacle_USB2.0_16P','BigModular:'+SYMBOL]
            one(form,'lib_id')[1]='BigModular:'+SYMBOL
            form[:]=[x for x in form if not(isinstance(x,list) and x[0]=='pin' and x[1] in CONTACT_TO_LAND)]
            for pin in nodes(form,'pin'):
                if pin[1]=='SH':pin[1]='S1'
            updates={'Value':MPN,'MPN':MPN,'LCSC':LCSC,'Footprint':'BigModular:'+FOOTPRINT,'Datasheet':DATASHEET,'NOTE':NOTE,'Manufacturer':'HRO (Korean Hroparts Elec)'}
            for k,v in updates.items():
                if k in props:props[k][2]=v
                else:
                    prop=copy.deepcopy(props['Value']);prop[1]=k;prop[2]=v
                    one(prop,'effects').append(atom('hide'));form.append(prop)
            edits.append((a,b,dump(form)))
    for a,b,replacement in sorted(edits,reverse=True):text=text[:a]+replacement+text[b:]
    text=text.replace('V1 - UNROUTED / PLACEMENT NEXT','V1 - ROUTED HRO CARRIER / PASSIVE FRONT PANEL')
    text=text.replace('All64 footprints synchronized:4 fixed,60 off-board staged; no copper.','All64 footprints synchronized and routed; HRO USB-C; passive front panel.')
    return text


# Native all-severity ERC identified these original upper branches. This exact
# presentation-only repair avoids ignoring four_way_junction across the design.
FOURWAY_UPPER_UUIDS={
 'e8fae952-c7db-5865-86a6-d4b173af8ae7',
 '66aacf82-fb80-5769-b2b1-4d5b679710b9',
 '3f2b5fbf-dc56-5314-8208-207e8040251e',
 '51952140-e44c-55bf-8379-f29da978a5d0',
 '6ee3f58a-b187-5152-89e6-3cb97a2ceeed'}


def split_fourways(text):
    tree=parse(text);wires=nodes(tree,'wire');edits={};new=[]
    def ends(w):return [tuple(round(float(v),6) for v in x[1:]) for x in nodes(one(w,'pts'),'xy')]
    def set_end(w,old,new):
        for xy in nodes(one(w,'pts'),'xy'):
            if tuple(round(float(v),6) for v in xy[1:])==old:xy[1:]=[atom(format(v,'.6f').rstrip('0').rstrip('.')) for v in new]
    for up in wires:
        uid=one(up,'uuid')[1]
        if uid not in FOURWAY_UPPER_UUIDS:continue
        pts=ends(up)
        hits=[pt for pt in pts if sum(pt in ends(w) for w in wires)==4]
        if not hits:continue  # Already split, or user's saved presentation differs.
        assert len(hits)==1;pt=hits[0];far=next(x for x in pts if x!=pt)
        assert far[0]==pt[0] and far[1]<pt[1]-1.27
        east=[w for w in wires if pt in ends(w) and any(x[1]==pt[1] and x[0]>pt[0]+1.27 for x in ends(w))]
        assert len(east)==1;east=east[0]
        q=(pt[0],round(pt[1]-1.27,6));r=(round(pt[0]+1.27,6),pt[1]);corner=(r[0],q[1])
        upnew=copy.deepcopy(up);set_end(upnew,pt,q);edits[uid]=upnew
        enew=copy.deepcopy(east);set_end(enew,pt,r);edits[one(east,'uuid')[1]]=enew
        for ix,(a,b) in enumerate([(q,corner),(corner,r),(pt,r)]):
            form=copy.deepcopy(up);one(form,'pts')[1:]=[[atom('xy'),*[atom(f'{v:g}') for v in a]],[atom('xy'),*[atom(f'{v:g}') for v in b]]]
            one(form,'uuid')[1]=str(uuid.uuid5(uuid.NAMESPACE_URL,'big-modular/hro-two-T/'+uid+'/'+str(ix)));new.append(form)
        junction=next(j for j in nodes(tree,'junction') if tuple(round(float(v),6) for v in one(j,'at')[1:])==pt)
        j=copy.deepcopy(junction);one(j,'at')[1:]=[atom(f'{v:g}') for v in r];one(j,'uuid')[1]=str(uuid.uuid5(uuid.NAMESPACE_URL,'big-modular/hro-two-T/'+uid+'/junction'));new.append(j)
    replacements=[]
    for a,b,depth in spans(text):
        if depth==1 and re.match(r'\(wire\s',text[a:b]):
            w=parse(text[a:b]);uid=one(w,'uuid')[1]
            if uid in edits:replacements.append((a,b,dump(edits[uid])))
    for a,b,value in sorted(replacements,reverse=True):text=text[:a]+value+text[b:]
    if new:
        end=text.rfind(')');text=text[:end]+' '+ ' '.join(dump(x) for x in new)+text[end:]
    return text


def build(source, output):
    source=source.resolve();output=output.resolve()
    if output.exists():raise FileExistsError('Output must be NEW')
    if source==output or source in output.parents:raise ValueError('Output must be outside input closure')
    expected=Connectivity(ROOT/'hardware').named_pins()
    before=Connectivity(source).named_pins()
    assert {k:v for k,v in before.items() if k[0]!='J1'}=={k:v for k,v in expected.items() if k[0]!='J1'}, 'unrelated electrical delta: manual merge needed'
    files=list(source.glob('*.kicad_sch'))+[source/'usb-power.kicad_pro']
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    shutil.copytree(ROOT/'hardware',output,ignore=shutil.ignore_patterns('.*','*.lck','*.kicad_prl','*.bak'))
    lib=parse((ROOT/'hardware/BigModular.kicad_sym').read_text())
    hro=copy.deepcopy(next(s for s in nodes(lib,'symbol') if s[1]==SYMBOL));hro[1]='BigModular:'+SYMBOL
    for p in source.glob('*.kicad_sch'):(output/p.name).write_text(split_fourways(patch(p.read_text(),hro)))
    project=json.loads((source/'usb-power.kicad_pro').read_text())
    for k,v in project['board']['design_settings']['rule_severities'].items():
        if v=='ignore':project['board']['design_settings']['rule_severities'][k]='warning'
    for k,v in project['erc']['rule_severities'].items():
        if v=='ignore':project['erc']['rule_severities'][k]='warning'
    (output/'usb-power.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
    assert Connectivity(output).named_pins()==expected
    assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'input changed during snapshot/patch'
    (output/'presentation-overlay.json').write_text(json.dumps({'source':str(source),'input_sha256':hashes,'status':'NEW review copy only; native checks and user-controlled merge required'},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-hardware',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.input_hardware,a.output)
