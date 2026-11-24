"""Section of the top clip at the screw (X25) with carrier, panel and rail: docs/fit/top-clip-section.png.

Run from modules/motion: python3 -B panels/top-clip/render_section.py (matplotlib).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

MODULE = Path(__file__).resolve().parents[2]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
C = GEO['top_clip']
rear = GEO['stack_Z_mm']['panel_rear_seat']
edge = GEO['main_pcb']['outline_mm'][1]
t = GEO['main_pcb']['thickness_mm']
fig, ax = plt.subplots(figsize=(6, 7))


def rect(y0, y1, z0, z1, **kw):
    ax.add_patch(Rectangle((y0, z0), y1 - y0, z1 - z0, **kw))


rect(-2, GEO['rail_clear_gap_Y_mm'][0], rear - 13.5, rear, color='#bbbbbb', label='skiff rail (Y < 8.0)')
rect(0, 20, rear, rear + GEO['panel_pcb_thickness_mm'], color='#2b2b2b', label='panel')
rect(edge, 20, -t, 0, color='#2e7d32', label='carrier (top edge Y9.25)')
rect(edge, edge + 1.0, -t - 0.05, 0.05, fill=False, hatch='///', ec='#a5d6a7', lw=0, label='1 mm keep-out strip')
clip = dict(color='#ef6c00', alpha=0.9)
b = C['boss']
rect(C['back_Y'], C['shoulder_inner_Y'], 0, rear, **clip, label='printed top clip')
rect(C['back_Y'], C['spine_face_Y'], C['nose_Z'][0], 0, **clip)
rect(C['back_Y'], C['nose_inner_Y'], *C['nose_Z'], **clip)
rect(C['shoulder_inner_Y'], b['Y'][1], b['Z_bottom'], rear, **clip)
sy = C['screw_XY'][1]
r = C['screw_hole_D'] / 2
rect(sy - r, sy + r, C['screw_hole_bottom_Z'], rear, color='white')
rect(sy - 1.5, sy + 1.5, rear + 1.6 - 8, rear + 1.6, color='#1565c0', alpha=0.6, label='M3x8 screw (FR4 panel)')
rect(sy - 2.85, sy + 2.85, rear + 1.6, rear + 3.25, color='#1565c0', alpha=0.6)
ax.set_xlim(4, 18)
ax.set_ylim(-5, 15)
ax.set_aspect('equal')
ax.set_xlabel('panel Y (mm, down)')
ax.set_ylabel('Z (mm, carrier F.Cu = 0, panel rear = 10)')
ax.set_title('MOTION top clip, section at X25 (screw)')
ax.legend(loc='lower right', fontsize=7)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(MODULE / 'docs/fit/top-clip-section.png', dpi=130)
