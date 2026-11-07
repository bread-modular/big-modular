"""Render the verified section/mesh data without a GUI (system Python + matplotlib)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1]/'research/usb-brace-v5'
data = json.loads((OUT/'render-data.json').read_text())
colors = {'panel': '#49566a', 'saddle': '#e6a13a', 'nuts': '#a8afb9', 'screws': '#777f8d',
          'MCU_board': '#23846a', 'carrier': '#526d55', 'J101': '#b7c1ca'}
fig = plt.figure(figsize=(19, 8), facecolor='#f7f9fb')
ax = fig.add_subplot(131)
ax.set_facecolor('#f7f9fb')
# Paint wire interiors by nesting depth to preserve genuine holes, including USB mouth.
from matplotlib.path import Path as MPath
for name in ('panel', 'saddle', 'carrier', 'MCU_board', 'J101'):
    wires = data['x15.0'].get(name, [])
    def area(w):
        a=np.array(w); return abs(np.sum(a[:-1,0]*a[1:,1]-a[1:,0]*a[:-1,1]))
    ordered=sorted(wires, key=area, reverse=True)
    prior=[]
    for wire in ordered:
        depth=sum(MPath(w).contains_point(wire[0]) for w in prior)
        face=colors.get(name,'#888') if depth%2 == 0 else '#f7f9fb'
        ax.add_patch(Polygon(wire, closed=True, facecolor=face, edgecolor='#263238', linewidth=.8))
        prior.append(wire)
ax.annotate('6.0 mm front stop\nblocks PULL', xy=(10.65,4.1), xytext=(13.2,7.2),
            arrowprops={'arrowstyle':'->','color':'#9c6408'}, fontsize=11, color='#805300')
ax.annotate('Rear jaw blocks PUSH\n0.15 mm clearance', xy=(10.7,2.25), xytext=(14.0,.7),
            arrowprops={'arrowstyle':'->','color':'#9c6408'}, fontsize=11, color='#805300')
ax.annotate('3.0 mm tongue reach\n(recessed above)', xy=(12.7,1.6), xytext=(12.5,-2.5),
            arrowprops={'arrowstyle':'->','color':'#23846a'}, fontsize=10, color='#23846a')
ax.text(11,11.1,'PANEL', color='white', weight='bold', fontsize=10)
ax.text(13,-.9,'Carrier (not clamped)', color='white', fontsize=9)
ax.annotate('',xy=(7.75,4),xytext=(7.75,10),arrowprops={'arrowstyle':'<->','color':'#303642'})
ax.text(7.55,7,'6 mm',rotation=90,va='center',ha='right',fontsize=11)
ax.set_xlim(7.0,21.3);ax.set_ylim(-3.5,15)
ax.set_aspect('equal'); ax.set_xlabel('Panel Y (mm, down from top edge)');ax.set_ylabel('Stack Z (mm, toward front)')
ax.set_title('A. Centre cross-section — 6 mm stop',loc='left',weight='bold',pad=15)
ax.grid(alpha=.12)

# Nut section: actual exported geometry, with its unobstructed top-edge approach.
ax2=fig.add_subplot(132)
ax2.set_facecolor('#f7f9fb')
for name in ('panel', 'saddle', 'MCU_board', 'nuts', 'screws'):
    wires = data['x23.2'].get(name, [])
    ordered=sorted(wires, key=area, reverse=True)
    prior=[]
    for wire in ordered:
        depth=sum(MPath(w).contains_point(wire[0]) for w in prior)
        ax2.add_patch(Polygon(wire, closed=True,
            facecolor=colors[name] if depth%2 == 0 else '#f7f9fb',
            edgecolor='#263238', linewidth=.8))
        prior.append(wire)
ax2.annotate('Load hex nut from top edge',xy=(9.8,7.05),xytext=(5.8,7.05),
             arrowprops={'arrowstyle':'->','color':'#b54b21','lw':2},
             fontsize=10,rotation=90,ha='center',va='center',color='#b54b21')
ax2.annotate('5.5 mm AF x 2.7 mm nut',xy=(12,7),xytext=(13.1,9.7),
             arrowprops={'arrowstyle':'->'},fontsize=10)
ax2.annotate('3.1 mm entry height',xy=(8.5,5.3),xytext=(13.2,4.6),
             arrowprops={'arrowstyle':'->'},fontsize=10)
ax2.text(13,2.8,'MCU board',color=colors['MCU_board'],fontsize=10)
ax2.set_xlim(5.1,21.3);ax2.set_ylim(-3.5,15)
ax2.set_aspect('equal');ax2.grid(alpha=.12)
ax2.set_xlabel('Panel Y (mm, down from top edge)')
ax2.set_title('B. Nut loading — load before fitting bracket',loc='left',weight='bold',pad=15)

ax3=fig.add_subplot(133,projection='3d')
ax3.set_facecolor('#f7f9fb')
all_polys=[]; all_colors=[]
for name,item in data['mesh'].items():
    if name not in colors: continue
    verts=np.array(item['vertices'])
    if name=='panel':verts[:,2]+=10
    if name=='screws':verts[:,2]+=10
    polys=verts[np.array(item['faces'])]
    all_polys.extend(polys)
    from matplotlib.colors import to_rgb
    rgb=np.array(to_rgb(colors[name]))
    normal=np.cross(polys[:,1]-polys[:,0],polys[:,2]-polys[:,0])
    norm=np.linalg.norm(normal,axis=1);norm[norm==0]=1
    light=np.array([.3,-.4,.8]); light/=np.linalg.norm(light)
    shades=.65+.35*np.abs((normal/norm[:,None])@light)
    all_colors.extend(rgb[None,:]*shades[:,None])
coll=Poly3DCollection(all_polys,facecolors=all_colors,edgecolors='none',alpha=1,zsort='average')
ax3.add_collection3d(coll)
ax3.set_xlim(0,30);ax3.set_ylim(2,27);ax3.set_zlim(-2,28)
ax3.view_init(elev=23,azim=-66)
ax3.set_box_aspect((30,25,30));ax3.set_axis_off()
ax3.set_title('C. Exploded — same panel and screw holes',loc='left',weight='bold',pad=15)
fig.legend(handles=[Patch(color=colors[n],label=l) for n,l in [('panel','Printed panel'),('saddle','One-piece saddle'),
 ('MCU_board','USB/MCU PCB'),('nuts','M3 hardware')]],loc='lower center',ncol=4,bbox_to_anchor=(.5,.085),frameon=False)
fig.suptitle('USB-AUDIO • BOLTED MCU EDGE SADDLE (v5)',fontsize=19,weight='bold',y=.97)
fig.text(.5,.035,'CAD prototype only • No PCB drilling • 6.0 mm measured gap • 2 × M3x6 + measured 5.5 AF × 2.7 mm nuts',ha='center',fontsize=12)
fig.subplots_adjust(left=.055,right=.98,top=.87,bottom=.18,wspace=.16)
fig.savefig(OUT/'design.png',dpi=150)
fig.savefig(HERE/'usb-brace-v5-design.png',dpi=150)
print(OUT/'design.png')
