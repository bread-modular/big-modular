"""Stdlib-only topology/hash checks, reusing the existing case mesh checker.

python3 -B case/tools/check_middle_brace.py
"""
import hashlib
import json
from pathlib import Path
from check_angle_joiner import check_mesh

CASE=Path(__file__).resolve().parents[1]
OUT=CASE/'print'/'side panels'/'middle-frame'/'top-brace'


def main():
    (OUT/'mesh-verification.json').unlink(missing_ok=True)
    report=json.loads((OUT/'verification.json').read_text())
    assert report['status']=='PASS'
    for rel,sha in {**report['source_sha256'],**report['export_sha256']}.items():
        assert hashlib.sha256((CASE/rel).read_bytes()).hexdigest()==sha,rel+' changed; rebuild the brace'
    for rel,sha in report['faceplate_source_sha256'].items():
        assert hashlib.sha256((CASE.parent/rel).read_bytes()).hexdigest()==sha,rel+' changed; rebuild the brace'
    assert report['dimensions']['rail_pad_thickness_mm']==report['dimensions']['source_faceplate_thickness_mm']
    assert report['dimensions']['rail_pad_width_mm']==report['dimensions']['source_rail_width_mm']
    footprints=report['checks']['screw_arms_within_saved_rail_footprints']
    assert len(footprints)==4
    for arm in footprints.values():
        assert arm['screw_arm_y_bounds_mm']==arm['rail_y_bounds_mm']
        assert arm['screw_arm_width_mm']==arm['rail_width_mm']
        assert arm['outside_rail_footprint_mm3']==0
    tabs=report['checks']['faceplate_flush_screw_tabs']
    assert len(tabs)==12 and all(t['top_above_module_face_mm']==0 for t in tabs)
    meshes={name:check_mesh(name,OUT) for name in report['print']}
    text=json.dumps({'status':'PASS','output_hashes_verified':len(report['export_sha256']),
                     'meshes':meshes},indent=2)+'\n'
    (OUT/'mesh-verification.json').write_text(text)
    print(text)


if __name__=='__main__':
    main()
