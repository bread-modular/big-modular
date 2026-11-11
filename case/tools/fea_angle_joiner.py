"""Linear static screening of one angle-joiner cheek (gmsh + CalculiX in the FreeCAD AppImage).

  case/tools/fea_angle_joiner.sh                      # the cheek from build_angle_joiner.py
  JOINER_FEA="old=/tmp/old.brep;current" case/tools/fea_angle_joiner.sh
      # label=BREP is any left cheek in assembly axes, a bare label is the generator's cheek
  JOINER_FEA_MESH="1.8,0.5" case/tools/fea_angle_joiner.sh   # finer mesh, convergence check

Model: the LEFT cheek alone, solid isotropic PETG, second-order tetrahedra. Each case is a rigid
body bolted to its four screw seats. The assembly stands on four pads only: the lower case pivots
on its front pads and its back hangs on the cheeks, which stand on the rear feet (no friction
there, and the desk cannot pull). If a load lifts the rear foot, the lower case settles flat on
the desk and the cheek carries the upper case alone: that state is solved instead.

It compares shapes under assumed loads. It is NOT a rating: no layer adhesion, infill, creep,
bolt preload, contact with the side panels, or measured material data.
Raw decks and results go to case/research/angle-joiner/fea/<label>/ (ignored by git).
"""
import json
import math
import os
import resource
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base
import build_angle_joiner as gen
import numpy as np
import Part

E_MPA, NU = 2000.0, 0.38      # assumed solid PETG, in-plane of the layers
# JOINER_FEA_MESH="1.8,0.5" reruns with a finer mesh as a convergence check.
MESH_MAX, MESH_MIN = (float(v) for v in os.environ.get('JOINER_FEA_MESH', '2.6,0.7').split(','))
SEAT_R = base.M3_CB_D/2 + 0.05   # screw hole wall, counterbore wall and head seat
STRESS_EXCLUDE = 7.0          # mm around a screw axis / the foot support: rigid-constraint peaks
G = 9.81
# Assumed service loads on ONE cheek (mm, N). Local points are upper-case (Y, Z).
CASE_MASS_KG = 3.0            # each loaded case; half per cheek
COM = (64.25, 35.0)
TOP_ROW = (115.0, 65.0)       # jacks / knobs near the top of the upper module row
TOP_EDGE = (130.5, 65.0)
PUSH_N, PULL_N, LEAN_N, SIDE_N, DRAG_N = 40.0, 30.0, 50.0, 20.0, 8.0
WEIGHT_N = CASE_MASS_KG*G/2


def run(cmd, cwd, log):
    with open(log, 'w') as f:
        subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, check=True)


def mesh(shape, work):
    shape.exportBrep(str(work/'plate.brep'))
    (work/'plate.geo').write_text(
        'SetFactory("OpenCASCADE");\nMerge "plate.brep";\n'
        f'Mesh.MeshSizeMax = {MESH_MAX};\nMesh.MeshSizeMin = {MESH_MIN};\n'
        'Mesh.MeshSizeFromCurvature = 10;\nMesh.ElementOrder = 2;\n'
        'Mesh.HighOrderOptimize = 2;\nMesh.Algorithm3D = 1;\nMesh.SaveAll = 1;\n')
    gmsh = Path(os.environ['APPDIR'])/'usr'/'bin'/'gmsh'
    run([str(gmsh), 'plate.geo', '-3', '-format', 'inp', '-o', 'mesh.inp', '-nt', '8'],
        work, work/'gmsh.log')
    nodes, elems, mode = {}, [], None
    pending = []
    for line in (work/'mesh.inp').read_text().splitlines():
        if line.startswith('*'):
            key = line.upper().replace(' ', '')
            mode = 'node' if key.startswith('*NODE') else \
                   'tet' if key.startswith('*ELEMENT') and 'C3D10' in key else None
            pending = []
            continue
        if mode == 'node':
            p = line.split(',')
            nodes[int(p[0])] = tuple(float(v) for v in p[1:4])
        elif mode == 'tet':
            pending += [int(v) for v in line.replace(',', ' ').split()]
            if len(pending) >= 11:
                elems.append(pending[1:11])
                pending = []
    assert elems, 'no C3D10 elements'
    used = sorted({n for e in elems for n in e})
    return {n: nodes[n] for n in used}, elems


def model(shape, work, d, layout):
    nodes, elems = mesh(shape, work)
    ids = np.array(list(nodes))
    xyz = np.array([nodes[i] for i in ids])
    lower, upper = layout.mounts(False), layout.mounts(True)

    def near(points, radius):
        hit = np.zeros(len(ids), bool)
        for y, z in points:
            hit |= np.hypot(xyz[:, 1]-y, xyz[:, 2]-z) <= radius
        return hit

    sets = {'LOWER': ids[near(lower, SEAT_R)], 'UPPER': ids[near(upper, SEAT_R)]}
    foot = (xyz[:, 2] < 1e-4) & (np.abs(xyz[:, 1]-gen.FOOT[0]) <= 1.6)
    sets['FOOT'] = ids[foot]
    assert all(len(v) >= 8 for v in sets.values()), {k: len(v) for k, v in sets.items()}
    ref, rot, lref, lrot = (int(ids.max())+k for k in (1, 2, 3, 4))
    centre = np.mean(upper, axis=0)
    pivot = np.array([gen.FRONT_PAD_Y, 0.0])   # lower case front pads
    x_mid = float(xyz[:, 0].min()+gen.PLATE_T/2)
    lines = ['*NODE, NSET=NALL']
    lines += [f'{i},{x:.6f},{y:.6f},{z:.6f}' for i, (x, y, z) in zip(ids, xyz)]
    lines += [f'{n},{x_mid:.6f},{centre[0]:.6f},{centre[1]:.6f}' for n in (ref, rot)]
    lines += [f'{n},{x_mid:.6f},{pivot[0]:.6f},{pivot[1]:.6f}' for n in (lref, lrot)]
    lines.append('*ELEMENT, TYPE=C3D10, ELSET=EALL')
    lines += [f'{k+1},'+','.join(map(str, e)) for k, e in enumerate(elems)]
    for name, members in sets.items():
        lines.append(f'*NSET, NSET={name}')
        lines += [','.join(map(str, members[i:i+12])) for i in range(0, len(members), 12)]
    lines += [f'*NSET, NSET=NREF\n{ref},{rot},{lref},{lrot}',
              f'*RIGID BODY, NSET=UPPER, REF NODE={ref}, ROT NODE={rot}',
              f'*RIGID BODY, NSET=LOWER, REF NODE={lref}, ROT NODE={lrot}',
              '*MATERIAL, NAME=PETG', '*ELASTIC', f'{E_MPA},{NU}',
              '*SOLID SECTION, ELSET=EALL, MATERIAL=PETG']
    (work/'model.inc').write_text('\n'.join(lines)+'\n')
    keep = ~near(lower+upper, STRESS_EXCLUDE)
    keep &= ~((xyz[:, 2] < STRESS_EXCLUDE) & (np.abs(xyz[:, 1]-gen.FOOT[0]) < STRESS_EXCLUDE))
    return {'ids': ids, 'xyz': xyz, 'ref': ref, 'rot': rot, 'lref': lref, 'lrot': lrot,
            'centre': centre, 'pivot': pivot, 'keep': keep, 'foot': sets['FOOT'],
            'nodes': len(ids), 'elements': len(elems)}


def cases(layout):
    """name -> loads [(body, local point, (Fx, Fy, Fz))] and the support state.

    'pads': on the four pads. 'flat': foot lifted, lower case flat on the desk (used
    automatically when the pads state needs the desk to pull the foot down).
    'held-upper' / 'held-lower': the assembly lifted by that case, nothing on the desk.
    """
    c, s = layout.c, layout.s
    dead = [('lower', COM, (0, 0, -WEIGHT_N)), ('upper', COM, (0, 0, -WEIGHT_N))]
    into = (s, -c)   # into the upper module face
    return {
        'dead': (dead, 'pads'),
        'dead+push': (dead+[('upper', TOP_ROW, (0, PUSH_N*into[0], PUSH_N*into[1]))], 'pads'),
        'dead+pull': (dead+[('upper', TOP_ROW, (0, -PULL_N*into[0], -PULL_N*into[1]))], 'pads'),
        'dead+lean': (dead+[('upper', TOP_EDGE, (0, 0, -LEAN_N))], 'pads'),
        'dead+side': (dead+[('upper', TOP_EDGE, (SIDE_N, 0, 0))], 'pads'),
        'dead+foot-drag': (dead+[('foot', None, (DRAG_N, 0, 0))], 'pads'),
        'lift-by-upper': (dead[:1], 'held-upper'),
        'lift-by-lower': (dead[1:], 'held-lower'),
    }


def deck(m, layout, loads, state):
    force = {'upper': np.zeros(3), 'lower': np.zeros(3)}
    moment = {'upper': 0.0, 'lower': 0.0}
    origin = {'upper': m['centre'], 'lower': m['pivot']}
    nodes = {'upper': (m['ref'], m['rot']), 'lower': (m['lref'], m['lrot'])}
    lateral, cload = False, []
    for body, local, f in loads:
        if body == 'foot':
            cload += [f'{n},1,{f[0]/len(m["foot"]):.8f}' for n in m['foot']]
            continue
        y, z = layout.point(*local, body == 'upper')
        force[body] += f
        moment[body] += (y-origin[body][0])*f[2]-(z-origin[body][1])*f[1]
        lateral |= abs(f[0]) > 0
    lines = ['*INCLUDE, INPUT=model.inc', '*STEP', '*STATIC', '*BOUNDARY']
    # Out of plane the second cheek and the two cases hold both bodies square.
    lines += [f'{m["rot"]},2,3', f'{m["lrot"]},2,3', f'{m["lref"]},1,1']
    if not lateral:
        lines.append(f'{m["ref"]},1,1')
    if state == 'pads':        # front pads: pin; rear foot: frictionless roller
        lines += [f'{m["lref"]},2,3', 'FOOT,3,3']
    elif state in ('flat', 'held-lower'):
        lines += [f'{m["lref"]},2,3', f'{m["lrot"]},1,1']
    else:                      # held-upper
        lines += [f'{m["ref"]},1,3', f'{m["rot"]},1,1']
    lines.append('*CLOAD')
    for body in ('upper', 'lower'):
        ref, rot = nodes[body]
        lines += [f'{ref},{k+1},{v:.6f}' for k, v in enumerate(force[body]) if abs(v) > 1e-12]
        if abs(moment[body]) > 1e-12:
            lines.append(f'{rot},1,{moment[body]:.6f}')
    lines += cload+['*NODE PRINT, NSET=NREF', 'U']
    if state == 'pads':
        lines += ['*NODE PRINT, NSET=FOOT, TOTALS=ONLY', 'RF']
    lines += ['*NODE FILE', 'U', '*EL FILE', 'S', '*END STEP']
    down = -(force['upper'][2]+force['lower'][2])
    return '\n'.join(lines)+'\n', down


def read_dat(path, m):
    u, reaction, block = {}, None, None
    for line in path.read_text().splitlines():
        low = line.lower()
        if 'displacements' in low:
            block = 'u'
        elif 'total force' in low:
            block = 'rf'
        elif line.strip() and block:
            p = line.split()
            if block == 'u' and len(p) == 4:
                u[int(p[0])] = [float(v) for v in p[1:]]
            elif block == 'rf' and len(p) == 3:
                reaction = float(p[2])
    return np.array(u[m['ref']]), np.array(u[m['rot']]), reaction


def read_frd(path, m):
    disp, stress, block = {}, {}, None
    for line in path.read_text().splitlines():
        if line.startswith(' -4'):
            block = 'd' if 'DISP' in line else 's' if 'STRESS' in line else None
        elif line.startswith(' -1') and block:
            node = int(line[3:13])
            values = [float(line[13+12*k:25+12*k]) for k in range(6 if block == 's' else 3)]
            (stress if block == 's' else disp)[node] = values
    s = np.array([stress[i] for i in m['ids']])
    mises = np.sqrt(0.5*((s[:, 0]-s[:, 1])**2+(s[:, 1]-s[:, 2])**2+(s[:, 2]-s[:, 0])**2)
                    + 3*(s[:, 3]**2+s[:, 4]**2+s[:, 5]**2))
    u = np.array([disp[i] for i in m['ids']])
    return mises, np.linalg.norm(u, axis=1)


def solve(m, layout, work, name, loads, state):
    job = name.replace('+', '-')+'-'+state
    text, down = deck(m, layout, loads, state)
    (work/f'{job}.inp').write_text(text)
    ccx = Path(os.environ['APPDIR'])/'usr'/'bin'/'ccx'
    for old in (work/f'{job}.dat', work/f'{job}.frd'):
        old.unlink(missing_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS='3')
    with open(work/f'{job}.log', 'w') as f:
        subprocess.run([str(ccx), job], cwd=work, stdout=f, stderr=subprocess.STDOUT,
                       check=True, env=env)
    u, r, reaction = read_dat(work/f'{job}.dat', m)
    mises, total = read_frd(work/f'{job}.frd', m)
    top = np.array(layout.point(*TOP_EDGE, True))-m['centre']
    # Rigid upper body: top edge = reference translation + rotation x lever.
    move = u+np.cross(r, np.array([0.0, top[0], top[1]]))
    k = int(np.argmax(np.where(m['keep'], mises, -1)))
    result = {'support': state,
              'upper_top_edge_move_xyz_mm': [round(float(v), 4) for v in move],
              'upper_top_edge_move_mm': round(float(np.linalg.norm(move)), 4),
              'cheek_max_move_mm': round(float(total.max()), 4),
              'von_mises_max_MPa': round(float(mises[k]), 3),
              'von_mises_max_at_yz_mm': [round(float(v), 1) for v in m['xyz'][k, 1:]],
              'von_mises_peak_at_constraints_MPa': round(float(mises.max()), 3),
              'von_mises_peak_at_yz_mm': [round(float(v), 1)
                                          for v in m['xyz'][int(np.argmax(mises)), 1:]]}
    if state == 'pads':
        result['rear_foot_reaction_up_N'] = round(reaction, 2)
        result['front_pad_reaction_up_N'] = round(down-reaction, 2)
    return result


def pool_size():
    """Parallel solves that fit in memory, from the peak of the solve that just ran alone.

    Eight fine-mesh solves at once ran the machine out of memory (2026-11-11).
    """
    peak_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    with open('/proc/meminfo') as f:
        free_kb = next(int(line.split()[1]) for line in f if line.startswith('MemAvailable'))
    return max(1, min(8, int(0.5*free_kb/peak_kb))), round(peak_kb/1e6, 2)


def analyse(label, shape, d, layout, root):
    work = root/label
    work.mkdir(parents=True, exist_ok=True)
    assert shape.isValid() and len(shape.Solids) == 1, label
    m = model(shape, work, d, layout)
    todo = cases(layout)

    def one(item):
        name, (loads, state) = item
        result = solve(m, layout, work, name, loads, state)
        if state == 'pads' and result['rear_foot_reaction_up_N'] < 0:
            # The desk cannot pull the foot down: it lifts and the lower case settles flat.
            result = solve(m, layout, work, name, loads, 'flat')
        return name, result

    first, *rest = todo.items()
    results = dict([one(first)])
    workers, peak = pool_size()
    with ThreadPoolExecutor(workers) as pool:
        results.update(pool.map(one, rest))
    return {'volume_cm3': round(shape.Volume/1000, 3), 'nodes': m['nodes'],
            'elements': m['elements'], 'peak_solver_memory_so_far_GB': peak, 'parallel_solves': workers,
            'cases': results}


def main():
    d = base.Dims(42, 60, 0.5, base.module_panels())
    layout = gen.Layout(d)
    root = base.CASE/'research'/'angle-joiner'/'fea'
    shapes = {}
    for item in filter(None, os.environ.get('JOINER_FEA', 'current').split(';')):
        label, _, path = item.partition('=')
        if path:
            shapes[label] = Part.Shape()
            shapes[label].read(path)
        else:   # a bare label: the cheek from build_angle_joiner.py
            shapes[label] = gen.plate(d, layout, True)
    report = {'assumptions': {
        'material': f'solid isotropic PETG, E {E_MPA:g} MPa, nu {NU}',
        'mesh': f'C3D10, {MESH_MIN}-{MESH_MAX} mm', 'cheek': 'left, alone',
        'cases': 'rigid bodies on their four screw seats, held square out of plane',
        'supports': 'four pads: lower-case front pads pinned, rear foot frictionless and '
                    'compression only; foot lifted -> lower case flat on the desk',
        'loads_on_one_cheek_N': {'each_case_weight': round(WEIGHT_N, 2), 'push_top_row': PUSH_N,
                                 'pull_top_row': PULL_N, 'lean_top_edge': LEAN_N,
                                 'side_top_edge': SIDE_N, 'foot_dragged_sideways': DRAG_N},
        'stress': f'nodal von Mises, nodes within {STRESS_EXCLUDE:g} mm of a screw axis or the '
                  'foot support reported separately (rigid-constraint peaks)',
        'limits': 'comparison of shapes under assumed loads; not a rating'}, 'shapes': {}}
    for label, shape in shapes.items():
        report['shapes'][label] = analyse(label, shape, d, layout, root)
        print('FEA', label, json.dumps(report['shapes'][label], indent=1), flush=True)
    names = '+'.join(shapes)
    (root/f'summary-{names}.json').write_text(json.dumps(report, indent=2)+'\n')
    print('ANGLE_JOINER_FEA_DONE', flush=True)


if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
