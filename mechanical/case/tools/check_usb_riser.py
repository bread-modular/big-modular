"""Stdlib-only topology/hash checks, reusing the existing case mesh checker.

python3 -B mechanical/case/tools/check_usb_riser.py
"""
import hashlib
import json
from pathlib import Path
from check_angle_joiner import check_mesh

CASE=Path(__file__).resolve().parents[1]
REPO=CASE.parents[1]
OUT=CASE/'print'/'accessories'/'usb-riser'


def main():
    (OUT/'mesh-verification.json').unlink(missing_ok=True)
    report=json.loads((OUT/'verification.json').read_text())
    assert report['status']=='PASS'
    for rel,sha in {**report['source_sha256'],**report['export_sha256']}.items():
        path=REPO/rel if rel.startswith('modules/') else CASE/rel
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha,rel+' changed; rebuild the USB riser'
    checks=report['checks']
    assert checks['collisions']['shared_volume_mm3']==0 and checks['assembly_motion']['collisions']==0
    clear=checks['clearances_mm']
    assert clear['plug_to_slot_walls']>=0.5 and clear['plug_over_rail_top']>=1.0
    assert clear['carrier_in_cavity_each_side']>=0.25 and clear['panel_in_pocket_each_side']>=0.2
    # every web between two holes, or a hole and a face, is at least three 0.42 mm lines
    assert min(checks['walls_mm'].values())>=1.26
    hardware=checks['hardware']
    assert hardware['riser_screw_thread_in_rail_spacer_mm']>=3.5
    assert hardware['module_screw_thread_in_spacer_mm']>=3.5
    assert hardware['riser_screws_hidden_under_the_module_panel'] is True
    printing=checks['print']
    assert printing['supports_required'] is False and printing['other_area_past_45_deg_mm2']==0
    assert [b['what'] for b in printing['bridges']]==['USB slot roof'] and printing['bridges'][0]['span_mm']<=15
    meshes={name:check_mesh(name,OUT) for name in report['print']}
    for name,mesh in meshes.items():
        assert mesh['mesh_bounds_mm']==report['print'][name]['print_bounds_mm'],name+' bounds'
    text=json.dumps({'status':'PASS','output_hashes_verified':len(report['export_sha256']),
                     'meshes':meshes},indent=2)+'\n'
    (OUT/'mesh-verification.json').write_text(text)
    print(text)


if __name__=='__main__':
    main()
