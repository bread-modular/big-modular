"""Stdlib-only topology/hash checks, reusing the existing case mesh checker.

python3 -B mechanical/case/tools/check_cable_holder.py
"""
import hashlib
import json
from pathlib import Path
from check_angle_joiner import check_mesh

CASE=Path(__file__).resolve().parents[1]
OUT=CASE/'print'/'cable-holder'


def main():
    (OUT/'mesh-verification.json').unlink(missing_ok=True)
    report=json.loads((OUT/'verification.json').read_text())
    assert report['status']=='PASS'
    for rel,sha in {**report['source_sha256'],**report['export_sha256']}.items():
        assert hashlib.sha256((CASE/rel).read_bytes()).hexdigest()==sha,rel+' changed; rebuild the cable holder'
    checks=report['checks']
    # The cover stays inside the frame: its outer face is the plain cover's, 2.2 mm behind the edge.
    for groove in checks['panel']['grooves'].values():
        assert groove['collisions']==0 and groove['outer_face_behind_frame_edge_mm']>0
    assert checks['panel']['slides_in_from_the_bottom']=='PASS'
    assert checks['panel']['print']['supports_required'] is False
    for name in ('joiner-60','stand-40'):
        holder=checks[name]
        assert all(seat['collisions']==0 for seat in holder['seated'].values())
        motion=holder['profile_motion']
        assert motion['held_without_lifting_the_tip'] is True and motion['tip_lift_to_release_deg']>=10
        assert holder['print']['supports_required'] is False
        assert holder['print']['area_past_45_deg_mm2']==0
    for scene in (checks['joiner-60']['on_angle_joiner'],checks['stand-40']['on_stand_row_2']):
        assert all(scene[k]['collisions']==0 for k in ('panel','holder_left','holder_right','holder_centre'))
        assert scene['two_holders_gap_mm']>0
        assert all(c['clearance_over_first_60_mm']>=5 for c in scene['cables'])
    meshes={name:check_mesh(name,OUT) for name in report['print']}
    text=json.dumps({'status':'PASS','output_hashes_verified':len(report['export_sha256']),
                     'meshes':meshes},indent=2)+'\n'
    (OUT/'mesh-verification.json').write_text(text)
    print(text)


if __name__=='__main__':
    main()
