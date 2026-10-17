#!/usr/bin/env python3
"""Verify integrated LDO-R1 source and PCB against FRESH common native reports.

Requires full PCB parity. Returns explicit measured-versus-screened status and open
qualification gates. The separate full-board/release verifiers remain strict.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from electrical_checks import check,check_capacitor_plan
from ldo_budget import budget
ROOT=Path(__file__).resolve().parents[1]
NEW_REFS={*(f'C{i}' for i in range(48,68)),'U12','U13','D27','D28','R72','R73','R74','R75','R76','R83','R84','R85','C68','C69','C70','C71','C72'}


def verify(reports):
    reports=Path(reports)
    summary=json.loads((reports/'summary.json').read_text())
    assert Path(summary['selection']['project_dir']).resolve()==(ROOT/'hardware').resolve(), 'Native reports belong to a different workspace; rerun checks here'
    assert summary['source_unchanged'] and not summary['errors']
    for name,record in summary['selection']['source_hashes'].items():
        p=Path(name)
        assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256'],('stale native report',name)
    assert summary['findings']['erc']['total_including_exclusions']==0
    erc=json.loads((reports/'erc.json').read_text())
    assert erc['ignored_checks']==[]
    assert set(erc['included_severities'])=={'error','warning','exclusion'}
    result=check(ROOT/'hardware',ROOT/'docs/pin-net-audit.json',ROOT/'BOM.csv')
    expected=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
    expected={(r,p):n for r,ps in expected.items() if not r.startswith('#') for p,n in ps.items()}
    xml=ET.parse(reports/'netlist.xml').getroot();actual={};nc=0
    for net in xml.findall('./nets/net'):
        ns=net.findall('node')
        for node in ns:
            k=(node.get('ref'),node.get('pin'));assert k not in actual
            if expected.get(k,'UNKNOWN') is None:
                assert len(ns)==1 and net.get('name').startswith('unconnected-') and 'no_connect' in node.get('pintype',''),('NC mismatch',k)
                actual[k]=None;nc+=1
            else:actual[k]=net.get('name').rsplit('/',1)[-1]
    assert actual==expected,'Native full pin/no-connect mismatch'
    with (ROOT/'BOM.csv').open() as f:bom={r['Reference']:r for r in csv.DictReader(f)}
    comps={c.get('ref'):c for c in xml.findall('./components/comp')};assert set(comps)==set(bom)
    for r,c in comps.items():
        fields={p.get('name'):p.get('value','') for p in c.findall('property')}
        for k,v in [('Value',c.findtext('value','')),('Footprint',c.findtext('footprint','')),('MPN',fields.get('MPN','')),('LCSC',fields.get('LCSC',''))]:
            assert v==bom[r][k],(r,k,'native field mismatch')
        if r in NEW_REFS:assert fields.get('Manufacturer','')==bom[r]['Manufacturer'],r
    frozen=json.loads((ROOT/'docs/ldo-evidence/preserved-hashes.json').read_text())
    for name,h in frozen.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,('preserved file changed',name)
    parity=summary['ref_pin_net_parity'];assert parity['equal']
    assert summary['status']=='no_findings_in_requested_checks'
    drc=summary['findings']['drc'];assert not drc.get('not_run')
    assert drc['total_including_exclusions']==0
    # Independent exact PCB/BOM/native identity and fields, not only ref counts.
    from sexp import parse,nodes
    pcb=parse((ROOT/'hardware/big_modular.kicad_pcb').read_text())
    footprints={next((q[2] for q in nodes(f,'property') if q[1]=='Reference'),''):f for f in nodes(pcb,'footprint')}
    assert set(footprints)-{''}==set(bom)
    checked=0
    for r,c in comps.items():
        props={q[1]:q[2] for q in nodes(footprints[r],'property')}
        schfields={q.get('name'):q.text or '' for q in c.findall('./fields/field')}
        assert footprints[r][1]==bom[r]['Footprint']
        for field in ['Value','MPN','LCSC']:
            assert props.get(field,'')==bom[r][field],(r,field,'PCB/BOM mismatch');checked+=1
        for field in ['NOTE','Manufacturer','Datasheet']:
            expected_field=c.findtext('datasheet','') if field=='Datasheet' else schfields.get(field,'')
            assert props.get(field,'')==expected_field,(r,field,'PCB/schematic mismatch');checked+=1
    screen=budget()
    # The accepted 043 local-cap plan must actually exist in the frozen source.
    plan=check_capacitor_plan(bom,actual)
    assert plan['status']=='pass',('accepted capacitor plan not present',plan)
    assert screen['ldo_bank_screen_passed']
    assert screen['capacitor_release_gates']['VPROT_local_input_gate']['screen_pass']
    assert screen['capacitor_release_gates']['P5_output_loop_gate']['screen_pass']
    assert screen['MID_and_P5']['upper_with_ripple_below_5p5']
    # KNOWN prototype limitation: do not turn this into a pass.
    assert screen['negative_full_corner_1A_drop_out_pass'] is False
    result.update(status='integrated native electrical and exact-field parity pass; prototype screen only; negative full-temperature 1 A dropout FAIL not waived',
      native_components=len(comps),native_pins_including_NC=len(actual),native_explicit_NCs=nc,
      native_connected_pins=len(actual)-nc,native_ERC_findings=0,native_DRC_findings=0,
      PCB_BOM_schematic_field_checks=checked,PCB_integration_completed=True,
      capacitor_plan=plan,capacitor_plan_implemented=True,capacitor_bench_qualified=False,capacitor_release_gates=screen['capacitor_release_gates'],
      negative_full_corner_1A_drop_out_pass=screen['negative_full_corner_1A_drop_out_pass'],
      MID_peak_with_allocation_V=screen['MID_and_P5']['peak_with_allocation_V'],
      current_rating_claim=None,qualified_quiet_hardware=False,preserved_file_count=len(frozen),DC_budget=screen)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reports',type=Path,required=True,help='Fresh common check directory including full ERC/DRC/XML/parity')
    p.add_argument('--output',type=Path,required=True,help='NEW JSON evidence; never overwrite previous findings')
    a=p.parse_args()
    if a.output.exists():p.error('Output must be NEW')
    result=verify(a.reports);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('DC_budget','PCB_net_mismatches')},indent=2))
