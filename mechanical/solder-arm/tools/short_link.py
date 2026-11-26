"""Short arm link: the 190 mm link at half length (95 mm joint to joint).
FreeCADCmd short_link.py -> print/short-link-95/ (link + its own plate) and research/short-link/.
The 190 mm link and every other print file are never overwritten; joints, bolts, knobs,
bracket, head and base are the same parts.

Trade-off: the head rail is 240 mm long, so on a 95 mm link it cannot turn all the way round
beside the swivel bracket (it hits the bracket, the base or the desk). The head tilts about
about +/-40 degrees from level and does not flip (the shortest link that
still flips is about 160 mm); the link has to be 40 degrees up or more for a level
board. The build checks the working poses below and records, for each link angle, the J3 steps
that are clear by more than 5 mm.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_solder_arm as a
import build_plates as plates
import Part

DIR = 'short-link-95'
LINK_L = 95.0
CLEAR = 5.0           # the full build's head sweep limit to the desk, base and bracket
POSES = {
    # J1, J2 (0 = link upright), J3; board gripped across this side
    'level-40': ((300, 50, 320), (110.0, 29.0, 1.6)),   # link 40 degrees up, board level
    'level-60': ((300, 30, 300), (110.0, 29.0, 1.6)),   # link 60 degrees up, board level
    'tilted': ((300, 50, 290), (91.3, 110.0, 1.6)),     # link 40 degrees up, board tilted 30 degrees, 18HP carrier
    'steep': ((300, 30, 240), (29.0, 110.0, 1.6)),      # link 60 degrees up, board tilted 60 degrees, 6HP carrier by its long edges
}


def clear_steps(proxy, j2, board=(110.0, 29.0, 1.6)):
    """J3 steps with the head > CLEAR from the desk, base and bracket and > 2 mm from the link."""
    steps = []
    for i in range(a.TEETH):
        parts = proxy.assemble((300, j2, i*360/a.TEETH), board)
        head = Part.makeCompound([parts[n] for n in a.HEAD])
        g1 = head.distToShape(Part.makeCompound([parts[n] for n in a.FIXED]))[0]
        g2 = Part.makeCompound([parts[n] for n in a.HEAD[1:]]).distToShape(parts['link'])[0]
        if g1 > CLEAR and g2 > 2.0:
            steps.append({'j3_deg': i*10, 'board_tilt_deg': round(proxy.board_deg), 'gap_mm': round(g1, 1)})
    return steps


def main():
    a.LINK_L = LINK_L
    out = a.OUT/DIR
    out.mkdir(parents=True, exist_ok=True)
    arm = a.Arm()
    proxy = a.Arm(plain=True)
    record = {'status': 'FAIL', 'link_joint_to_joint_mm': LINK_L, 'full_link_mm': 190.0}

    record['poses'] = {}
    for name, (q, board) in POSES.items():
        parts = arm.assemble(q, board)
        plain = proxy.assemble(q, board)
        info = a.interference(plain)
        head = Part.makeCompound([plain[n] for n in a.HEAD])
        fixed = Part.makeCompound([plain[n] for n in a.FIXED])
        c = parts['board'].BoundBox.Center
        info.update({'angles_deg': list(q), 'board_mm': list(board), 'link_above_level_deg': round(arm.link_deg, 1),
                     'board_tilt_deg': round(arm.board_deg, 1), 'board_centre_mm': [round(c.x, 1), round(c.y, 1), round(c.z, 1)],
                     'head_to_desk_base_bracket_mm': round(head.distToShape(fixed)[0], 1)})
        assert info['head_to_desk_base_bracket_mm'] > CLEAR, (name, info)
        record['poses'][name] = info
        print('pose', name, info['board_tilt_deg'], info['head_to_desk_base_bracket_mm'], flush=True)

    record['head_range'] = {}
    for j2 in (30, 50, 60):
        steps = clear_steps(proxy, j2)
        tilts = sorted({s['board_tilt_deg'] for s in steps})
        record['head_range'][f'link_{90 - j2}_deg_up'] = {'clear_board_tilts_deg': tilts, 'steps': steps}
        print('range', 90 - j2, tilts, flush=True)
    assert 0 in record['head_range']['link_40_deg_up']['clear_board_tilts_deg']

    a.OUT = plates.PRINT = plates.OUT = out
    shape = a.print_pose(arm.link)
    info = a.export_part(shape, 'arm-link') | a.overhangs(shape)
    assert info['area_past_50_deg_mm2'] == 0 and info['bridged_ceiling_mm2'] == 0, info
    record['print'] = {'arm-link': info}
    record['plate'] = plates.build_plate('print-this', [['arm-link']], {'arm-link': plates.part_mesh('arm-link')})
    record['status'] = 'CAD_PASS'
    record['physical_load_test'] = False
    (out/'verification.json').write_text(json.dumps(record, indent=2) + '\n')
    print('SHORT_LINK_PASS', flush=True)


# FreeCADCmd may load this file twice (as __main__ and by its stem): run once
if (__name__ == '__main__' or any(Path(a_).resolve() == Path(__file__).resolve() for a_ in sys.argv[1:])) \
        and not getattr(sys, '_short_link_ran', False):
    sys._short_link_ran = True
    main()
