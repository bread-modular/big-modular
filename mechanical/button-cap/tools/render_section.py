"""Section drawing of the button cap on the switch, old one-piece cap beside it (matplotlib).

python3 -B mechanical/button-cap/tools/render_section.py
Reads cad/dimensions.json (written by build_button_cap.py); writes renders/button-cap-section.png.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

OUT = Path(__file__).resolve().parents[1]
D = json.loads((OUT / 'cad/dimensions.json').read_text())
P, H = D['plunger'], D['head']
FRONT = D['panel_front_Z']['FR4']
PANEL, SWITCH, CAP, HEAD = '#2f6f4f', '#8a8f96', '#e8a13a', '#d9542b'


def sym(ax, x0, half_profile, color):
    """Mirror a (r, z) half profile around the axis x0."""
    pts = [(x0 + r, z) for r, z in half_profile] + [(x0 - r, z) for r, z in reversed(half_profile)]
    ax.add_patch(Polygon(pts, closed=True, fc=color, ec='#222', lw=0.8))


def base(ax, x0):
    ax.add_patch(Rectangle((x0 - 7, -1.6), 14, 1.6, fc='#1d5a3a', ec='#222', lw=0.8))      # carrier
    ax.add_patch(Rectangle((x0 - 3, 0), 6, 3.1, fc=SWITCH, ec='#222', lw=0.8))             # switch body
    sym(ax, x0, [(1.7, 3.1), (1.6, 7.0)], '#3a3d42')                                       # stem
    for side in (-1, 1):                                                                   # panel, Ø4.2 hole
        ax.add_patch(Rectangle((x0 + side * 2.1, 10.0), side * 4.9, FRONT - 10.0, fc=PANEL, ec='#222', lw=0.8))


def plunger(ax, x0, tip_top):
    rs, rf, rt = P['socket_D'] / 2, P['flange_D'] / 2, P['tip_D'] / 2
    z0, z1 = P['flange_Z']
    roof = P['socket_Z'][1]
    for side in (-1, 1):
        ax.add_patch(Polygon([(x0 + side * rs, z0), (x0 + side * rf, z0), (x0 + side * rf, z1),
                              (x0 + side * rt, z1), (x0 + side * rt, tip_top), (x0, tip_top), (x0, roof),
                              (x0 + side * rs, roof)], closed=True, fc=CAP, ec='#222', lw=0.8))


fig, ax = plt.subplots(figsize=(9, 6.2), dpi=160)
base(ax, 0)
plunger(ax, 0, 13.5)
ax.text(0, -3.2, 'before: one-piece cap\nØ3.6 tip, 1.9 mm proud', ha='center', va='top', fontsize=10)
for i, (name, hd) in enumerate(D['heads'].items()):
    x0 = 17 + 17 * i
    r, rs = hd['D'] / 2, H['socket_D'] / 2
    base(ax, x0)
    plunger(ax, x0, P['tip_Z'][1])
    z0, z1 = H['Z']
    roof = P['tip_Z'][1]
    for side in (-1, 1):
        ax.add_patch(Polygon([(x0 + side * rs, z0), (x0 + side * (r - 0.3), z0), (x0 + side * r, z0 + 0.3),
                              (x0 + side * r, z1 - 0.8), (x0 + side * (r - 0.8), z1), (x0, z1), (x0, roof),
                              (x0 + side * rs, roof)], closed=True, fc=HEAD, ec='#222', lw=0.8))
    ax.text(x0, -3.2, f'{name} head Ø{hd["D"]:g}\n{H["gap_to_panel_front"]["FR4"]:g} mm gap, '
            f'top {H["top_above_panel_front"]["FR4"]:g} mm proud', ha='center', va='top', fontsize=10)
ax.annotate('panel (FR4 1.6)', (-7, 10.8), (-9.5, 14.5), fontsize=9, arrowprops={'arrowstyle': '-', 'lw': 0.6})
ax.annotate('tact switch', (-3, 1.5), (-9.5, 4.5), fontsize=9, arrowprops={'arrowstyle': '-', 'lw': 0.6})
ax.set_xlim(-10, 44)
ax.set_ylim(-7, 18)
ax.set_aspect('equal')
ax.axis('off')
ax.set_title('Push-button cap, section through the switch axis (mm, nominal)', fontsize=11)
(OUT / 'renders').mkdir(exist_ok=True)
fig.savefig(OUT / 'renders/button-cap-section.png', bbox_inches='tight', facecolor='white')
print('wrote renders/button-cap-section.png')
