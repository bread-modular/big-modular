#!/usr/bin/env python3
"""Reproduce LDO-R1 prototype bare-PCB artwork using common staging/CLI and native exporters.

NEW output + NEW raw evidence directories only. No routing, assembly CSV, input
writes, commits or uploads. Actual CAM checks use Gerbonara, not a new parser.
See docs/fabrication.md for the specifically inspected common-suite gaps.
"""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from fabrication_contract import validate_stack, via_audit
from check_hro_cam import inspect_cam
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
SHARED=REPO/'opt/kicad-tools/jlcpcb/export.py'
spec=importlib.util.spec_from_file_location('shared_kicad_export',SHARED)
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')

def normalize_metadata(path,carrier):
    text=path.read_text();old=text
    if path.suffix=='.gbrjob':
        d=json.loads(text);d['Header'].pop('CreationDate',None)
        d['GeneralSpecs']['Size']={'X':100.5 if carrier else 9.8,'Y':30.0 if carrier else 128.5}
        d['GeneralSpecs']['ProjectId']['Revision']='LDO-R1' if carrier else 'HRO-R1'
        # These auto-derived fields contain zeros for inner pad clearances; not a
        # manufacturing rule deck. Source native rules remain strict and unchanged.
        d.pop('DesignRules',None)
        d['MaterialStackup']=[v for v in d['MaterialStackup'] if v['Type']!='SolderPaste']
        text=json.dumps(d,indent=2,sort_keys=True)+'\n'
    else:
        text='\n'.join(line for line in text.splitlines() if 'TF.CreationDate' not in line and not line.startswith('Created on '))+'\n'
        text=re.sub(r'(G04 Created by KiCad .*?) date [^\n]*\*',r'\1*',text)
        text=re.sub(r'(; DRILL file KiCad [^\n]*?) date [^\n]*',r'\1',text)
        text=text.replace(',rev?*%',',LDO-R1*%' if carrier else ',HRO-R1*%')
    path.write_text(text)
    return {'file':path.name,'geometry_modified':False,'timestamp_removed':old!=text}


def zip_folder(folder,path):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(folder.rglob('*')):
            if not f.is_file():continue
            info=zipfile.ZipInfo(f.relative_to(folder).as_posix(),date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,f.read_bytes(),compresslevel=9)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names=set(z.namelist());assert names=={f.relative_to(folder).as_posix() for f in folder.rglob('*') if f.is_file()}
        assert all(hashlib.sha256(z.read(n)).hexdigest()==sha(folder/n) for n in names)
        assert not any(n.lower().endswith('.csv') for n in names)
    return {'sha256':sha(path),'members':sorted(names),'CRC_and_member_SHA_verified':True}


def build(out,reports):
    out=out.resolve();reports=reports.resolve();hardware=ROOT/'hardware'
    assert not out.exists() and not reports.exists(),'Both output and evidence paths must be NEW'
    assert hardware not in out.parents and hardware not in reports.parents
    out.mkdir(parents=True);reports.mkdir(parents=True)
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in hardware.rglob('*') if p.is_file() and not any(x.startswith('.') for x in p.relative_to(hardware).parts) and p.suffix not in ['.lck','.kicad_prl','.bak']}
    for name in ['tools/release_hro.py','tools/check_hro_cam.py','tools/fabrication_contract.py','tools/cam-requirements.txt','docs/fabrication.md','docs/usb-fit.json','docs/routed-baseline.json','tools/kicad-project.json']:
        sources[name]=sha(ROOT/name)
    for name in ['docs/schematic.pdf','docs/ldo-revision.md','BOM.csv','docs/pin-net-audit.json','docs/assembly-geometry.json','docs/ldo-evidence/manufacturer-mlcc-data.json','docs/ldo-evidence/capacitor-disposition.json','docs/ldo-evidence/pcb-audit.json']:
        sources[name]=sha(ROOT/name)
    for folder in ['tools','tests']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and p.suffix in ['.py','.json','.txt']:sources[p.relative_to(ROOT).as_posix()]=sha(p)
    for package,version in [('gerbonara','1.6.3'),('shapely','2.1.2')]:assert importlib.metadata.version(package)==version
    for name in ['usb-power','usb-power-panel']:
        pro=json.loads((hardware/(name+'.kicad_pro')).read_text());settings=pro['board']['design_settings']
        assert not settings['drc_exclusions'] and 'ignore' not in settings['rule_severities'].values()
        if name=='usb-power':assert 'ignore' not in pro['erc']['rule_severities'].values()
    validate_stack(hardware/'usb-power.kicad_pcb');validate_stack(hardware/'usb-power-panel.kicad_pcb',False)
    common=[sys.executable,'-B',str(REPO/'opt/kicad-tools/kicad_tools.py'),'check','--config',str(ROOT/'tools/kicad-project.json'),'--reports',str(reports/'carrier')]
    with (reports/'common-check.log').open('w') as log:subprocess.run(common,check=True,stdout=log,stderr=subprocess.STDOUT)
    summary=json.loads((reports/'carrier/summary.json').read_text())
    assert summary['status']=='no_findings_in_requested_checks' and summary['source_unchanged'] and summary['ref_pin_net_parity']['equal']
    for result in summary['findings'].values():assert result['total_including_exclusions']==0
    audit=via_audit(hardware/'usb-power.kicad_pcb')
    reviewed=json.loads((ROOT/'docs/routed-baseline.json').read_text())['inventory']
    assert audit['via_count']==reviewed['vias']
    from verify_ldo_source import verify as verify_source
    from verify_stack import verify as verify_mechanics
    source_check=verify_source(reports/'carrier');mechanics=verify_mechanics()
    write_json(out/'source-parity.json',source_check);write_json(out/'mechanics.json',mechanics)
    write_json(out/'via-audit.json',audit)
    git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    source_state={'git_base_HEAD':git_head,'revision_committed':False,'source_identity':'Exact source_sha256, not HEAD alone; intentional uncommitted workspace revision. Supervisor merges; no commit by exporter.'}
    write_json(out/'source-state.json',source_state)
    cmds=[];normalizations=[]
    with tempfile.TemporaryDirectory(prefix='hro-native-export-') as temp:
        work=Path(temp)
        for key,stem,layers in [
            ('carrier','usb-power','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts'),
            ('passive-panel','usb-power-panel','F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts')]:
            carrier=key=='carrier';folder=out/key;folder.mkdir()
            stage=work/key;stage.mkdir()
            board,_=shared.stage_cli_project(hardware/(stem+'.kicad_pcb'),None,stage)
            def cli(args):
                stdout=shared.run_cli('/usr/bin/kicad-cli',args,board.parent)
                cmds.append([str(v).replace(str(out),'RELEASE').replace(str(stage),'STAGE').replace(str(reports),'EVIDENCE') for v in args])
                with (reports/'export.log').open('a') as f:f.write(' '.join(cmds[-1])+'\n'+stdout+'\n')
            if not carrier:
                cli(['pcb','drc','--severity-all','--all-track-errors','--exit-code-violations','--format','json','--output',reports/'panel-drc.json',board])
            cli(['pcb','export','gerbers','--layers',layers,'--precision','6','--no-protel-ext','--output',str(folder)+os.sep,board])
            cli(['pcb','export','drill','--format','excellon','--drill-origin','absolute','--excellon-units','mm','--excellon-zeros-format','decimal','--excellon-oval-format','alternate','--excellon-separate-th','--generate-report','--report-path',folder/'drill-report.txt','--output',str(folder)+os.sep,board])
            if carrier:
                cli(['pcb','export','ipcd356','--output',folder/'usb-power.d356',board])
                paste=out/'assembly-stencil-support-only';paste.mkdir()
                cli(['pcb','export','gerbers','--layers','F.Paste,B.Paste','--no-protel-ext','--output',str(paste)+os.sep,board])
                # Native paste job incorrectly describes a whole PCB. It is not
                # part of this explicitly separate assembly-support deliverable.
                (paste/'usb-power-job.gbrjob').unlink()
            for f in folder.iterdir():normalizations.append(normalize_metadata(f,carrier))
    for f in (out/'assembly-stencil-support-only').glob('*.gbr'):normalizations.append(normalize_metadata(f,True))
    # All source files must be byte-identical after checks/staging/export.
    assert all(sha(ROOT/f)==h for f,h in sources.items()),'source changed during release'
    cam=inspect_cam(out,hardware,audit);write_json(out/'cam-inspection.json',cam)
    panel=json.loads((reports/'panel-drc.json').read_text())
    assert not panel['violations'] and not panel['unconnected_items']
    record={'status':'bare-PCB artwork ready with the specified ordinary-via fabrication process; not an assembled product qualification',
        'common_native_carrier_findings':summary['findings'],'ref_pin_net_parity_equal':True,
        'panel_DRC_violations':0,'panel_opens':0,'source_unchanged':True,
        'ignored_rules':0,'rule_exclusions':0,**reviewed,
        'via_process':'ordinary 0.300 mm plated through vias; solder-mask tented where artwork permits; no epoxy fill/planarization/copper cap',
        'assembly_side':'single-side front only; no B.Cu components and no B.Paste component apertures',
        'CAM_inspection_passed':True,'source_state':source_state,'source_sha256':sources,'tooling':{'kicad_cli':shared.run_cli('/usr/bin/kicad-cli',['version'],ROOT),
        'common_export_module_sha256':sha(SHARED),'gerbonara':'1.6.3','shapely':'2.1.2'},
        'native_export_commands':cmds,'metadata_normalization':normalizations}
    for key in ['carrier','passive-panel']:
        folder=out/key
        shutil.copyfile(ROOT/'docs/fabrication.md',folder/'FABRICATION-REQUIREMENTS.md')
        spec={'board':key,'release':'LDO-R1','source_sha256':sources[f'hardware/{"usb-power" if key=="carrier" else "usb-power-panel"}.kicad_pcb'],
            'finished_thickness_acceptance_mm':[1.44,1.76],'source_of_requirements':'FABRICATION-REQUIREMENTS.md',
            'native_stack':validate_stack(hardware/f'{"usb-power" if key=="carrier" else "usb-power-panel"}.kicad_pcb',key=='carrier'),
            'CAM_checked':cam[key]}
        write_json(folder/'fabrication-spec.json',spec)
        text=(f'CARRIER ONLY: four-layer FR4 Tg170 / ENIG / all {audit["via_count"]} 0.300 mm plated through vias are ORDINARY (no epoxy fill, planarization or copper cap); solder-mask tented where artwork permits.\n' if key=='carrier' else 'PASSIVE PANEL ONLY: no retained copper / black mask / white front legend / NPTH only / no metal finish.\n')
        if key=='carrier':text+='Exposed-pad/thermal-via barrels are prototype assembly inspection points; mask tenting does not seal a barrel inside an exposed pad.\n'
        text+='READ FABRICATION-REQUIREMENTS.md before quoting or manufacturing. No supplier acceptance is implied.\nGerber/Excellon coordinates: absolute mm, X right / Y up; native KiCad Y is down.\nEdge.Cuts centreline is the final profile; do not machine the outside of its plotted stroke.\nNo assembly BOM/CPL. Empty layers/drill files are intentional and checked.\n'
        (folder/'READ-ME-FIRST.txt').write_text(text)
    lines=['via_UUID\tKiCad_X_mm\tKiCad_Y_down_mm\tCAM_X_mm\tCAM_Y_up_mm\tdrill_mm\tprocess']
    for v in audit['vias']:
        x,y=v['xy_mm'];lines.append(f"{v['uuid']}\t{x:.6f}\t{y:.6f}\t{x:.6f}\t{-y:.6f}\t{v['drill_mm']:.3f}\tordinary plated through via; solder-mask tented where artwork permits; no fill/cap")
    (out/'carrier/via-process.tsv').write_text('\n'.join(lines)+'\n')
    shutil.copyfile(out/'via-audit.json',out/'carrier/via-audit.json')
    (out/'assembly-stencil-support-only/READ-ME-FIRST.txt').write_text('ASSEMBLY / STENCIL SUPPORT ONLY, NOT BARE-PCB FABRICATION.\nSingle-side assembly: all components are FRONT. Native front paste artwork only; B.Paste is intentionally empty. No shell paste on HRO.\nNo assembly qualification, BOM, CPL, stencil thickness/reduction or reflow approval.\n')
    for folder in [out/'carrier',out/'passive-panel',out/'assembly-stencil-support-only']:
        write_json(folder/'source-sha256.json',sources)
        (folder/'SHA256SUMS.txt').write_text(''.join(f'{sha(f)}  {f.name}\n' for f in sorted(folder.iterdir()) if f.is_file()))
    archives={}
    for folder,name in [('carrier','Big-Modular-LDO-R1-CARRIER-4L-STANDARD-VIAS-BARE-PCB.zip'),('passive-panel','Big-Modular-LDO-R1-PASSIVE-PANEL-BARE-PCB.zip'),('assembly-stencil-support-only','Big-Modular-LDO-R1-ASSEMBLY-STENCIL-SUPPORT-ONLY.zip')]:
        archives[name]=zip_folder(out/folder,out/name)
    record['archives']=archives;write_json(out/'release-validation.json',record)
    files={f.relative_to(out).as_posix():{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(out.rglob('*')) if f.is_file()}
    write_json(out/'manifest.json',{'release':'LDO-R1','source_state':source_state,'source_sha256':sources,'files':files,'manifest_self_hash':'excluded to avoid recursion'})
    print(json.dumps({'status':record['status'],'archives':archives,'CAM':cam['carrier']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--reports',type=Path,required=True,help='NEW raw native evidence directory, normally ignored research/')
    a=p.parse_args();build(a.output,a.reports)
