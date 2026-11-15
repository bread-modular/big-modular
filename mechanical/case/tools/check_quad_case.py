"""Stdlib-only topology/hash checks of the 2 x 2 case set, reusing the existing mesh checker.

python3 -B mechanical/case/tools/check_quad_case.py
Does not build CAD. Writes print/quad-case/mesh-verification.json only after PASS.
"""
import hashlib
import json
from pathlib import Path
from check_angle_joiner import check_mesh

CASE = Path(__file__).resolve().parents[1]
OUT = CASE/'print'/'quad-case'


def main():
    (OUT/'mesh-verification.json').unlink(missing_ok=True)
    report = json.loads((OUT/'verification.json').read_text())
    assert report['status'] == 'PASS'
    for rel, sha in report['export_sha256'].items():
        assert hashlib.sha256((CASE/rel).read_bytes()).hexdigest() == sha, rel+' changed; rebuild the quad case'
    checks = report['checks']
    assert all(v == 0 for v in checks['stock_geometry_outside_the_joint_diff_mm3'].values())
    assert checks['joint']['side_panel_wall_between_closed_notches_mm'] >= 2
    assert checks['joint']['middle_wall_between_rail_sockets_mm'] >= 2
    stand = checks['on_the_angle_joiner']
    assert stand['plate_hardware']['thread_engagement_mm'] >= 4
    assert stand['set_lowest_point_above_desk_mm'] > 5
    for name, part in report['print'].items():
        assert part['free_bed_per_side_mm'] >= 4, name+' leaves too little bed'
    meshes = {name: check_mesh(name, OUT) for name in report['print']}
    text = json.dumps({'status': 'PASS', 'output_hashes_verified': len(report['export_sha256']),
                       'meshes': meshes}, indent=2)+'\n'
    (OUT/'mesh-verification.json').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
