#!/usr/bin/env python3
"""Original dimensioned nominal assembly drawing; no third-party artwork is embedded."""
from pathlib import Path
from html import escape
import json, subprocess
ROOT=Path(__file__).resolve().parent.parent
D=ROOT/'docs'
geometry={
 'panel_mm':[9.8,128.5,1.6], 'rail_slots_mm':[[7.5,3,3.2,3.2],[7.5,125.5,3.2,3.2]],
 'rail_compatibility':'Doepfer x=7.5 circular 3.2 holes; 0.7mm FR4 web and ordinary screw-head overhang are unresolved blockers',
 'panel_bracket_holes_mm':[[4.9,45,2.2],[4.9,83.5,2.2]],
 'carrier_holes_YZ_mm':[[45,6],[83.5,6],[45,52],[83.5,52]],
 'carrier_X_mm':[1.57,3.17], 'carrier_Y_mm':[14,114.5], 'carrier_Z_mm':[2,62],
 'aperture_XYWHR_mm':[2.725,59.35,4.2,9.8,0.6], 'mouth_axis_XYZ_mm':[4.9,64.25,0.8],
 'interposers':{'quantity':2,'material':'machined aluminium, bare-FR4 contact / no copper under blocks',
   'X_mm':[3.17,8.97],'Y_centres_mm':[45,83.5],'height_Y_mm':8,'Z_mm':[1.6,10],
   'panel_thread_axis_X_mm':4.9,'carrier_thread_axis_Z_mm':6,
   'threads':'M2 x 0.4 blind; full thread 2.6 min, total depth 2.8 max including tip',
   'screw':'4 x M2 x 4 low-head; head height <=1.2, diameter <=3.8; exact product unselected',
   'nominal_engagement_mm':2.4},
 'harness_envelope_XYZ_mm':[[0.4,9.4],[40,75],[65,87]],
 'status':'DIMENSIONED PROPOSAL ONLY; screw selection, tolerance/strength and cable/plug fit unqualified'
}
(D/'assembly-geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
a=['<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297">',
 '<defs><marker id="arr" markerWidth="5" markerHeight="5" refX="2.5" refY="2.5" orient="auto-start-reverse"><path d="M0,0 L5,2.5 L0,5" fill="#444"/></marker></defs>',
 '<style>text{font-family:DejaVu Sans,sans-serif;fill:#172b40} .dim{stroke:#555;stroke-width:.2;fill:none;marker-start:url(#arr);marker-end:url(#arr)} .axis{stroke:#b54836;stroke-width:.25;stroke-dasharray:2 1}</style>',
 '<rect x="5" y="5" width="410" height="287" fill="white" stroke="#24384b" stroke-width=".4"/>']
def text(x,y,s,size=2.5,color=None):
    col=f' style="fill:{color}"' if color else ''
    a.append(f'<text x="{x}" y="{y}" font-size="{size}"{col}>{escape(s)}</text>')
def lines(x,y,ss,size=2.5,step=4):
    for i,s in enumerate(ss):text(x,y+i*step,s,size)
def rect(x,y,w,h,fill='none',stroke='#284c69',dash=False,rx=0):
    a.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width=".3"'+(' stroke-dasharray="2 1"' if dash else '')+'/>')
def line(x1,y1,x2,y2,cl='',color='#284c69'):
    a.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width=".25" class="{cl}"/>')
def circ(x,y,r):a.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="#284c69" stroke-width=".3"/>')
def dim(x1,y1,x2,y2,s,tx=None,ty=None):
    line(x1,y1,x2,y2,'dim');text((x1+x2)/2 if tx is None else tx,(y1+y2)/2-1 if ty is None else ty,s,2.3)
text(11,14,'BIG MODULAR | 2HP NOMINAL ASSEMBLY | A1 WIP',5)
text(11,21,'INCOMPLETE / NON-OPERATIONAL. Drawing is a fit-test proposal, NOT fabrication or mechanical qualification.',3,color='#a52b20')
text(11,27,'All dimensions mm. Panel origin: upper left front; X right, Y down, Z inward. Dimensions govern; do not scale prints.',2.6)
# Front: panel XY. Scale 1.25 to keep all three physical views comparable.
s=1.25; fx,fy=30,43
text(16,34,'FRONT (looking +Z)',3.2)
rect(fx,fy,9.8*s,128.5*s,'#f4ead0')
for X,Y,W,H in geometry['rail_slots_mm']:
    rect(fx+(X-W/2)*s,fy+(Y-H/2)*s,W*s,H*s,'white',rx=H*s/2)
for Y in [3,125.5]:
    a.append(f'<circle cx="{fx+7.5*s}" cy="{fy+Y*s}" r="{3*s}" fill="none" stroke="#b54836" stroke-width=".25" stroke-dasharray="1 1"/>')
for X,Y,d in geometry['panel_bracket_holes_mm']:circ(fx+X*s,fy+Y*s,d*s/2)
x,y,w,h,r=geometry['aperture_XYWHR_mm'];rect(fx+x*s,fy+y*s,w*s,h*s,'white',rx=r*s)
line(fx+4.9*s,fy-3,fx+4.9*s,fy+132*s,'axis')
dim(fx,fy-3,fx+9.8*s,fy-3,'9.80',fx,fy-5)
dim(fx-9,fy,fx-9,fy+128.5*s,'128.50',8,123)
dim(fx-4,fy+3*s,fx-4,fy+125.5*s,'122.50',9,135)
for Y,label in [(3,'Y=3.00'),(45,'Y=45.00'),(64.25,'Y=64.25 axis'),(83.5,'Y=83.50'),(125.5,'Y=125.50')]:
    line(fx+9.8*s,fy+Y*s,53,fy+Y*s);text(54,fy+Y*s+1,label,2.4)
lines(46,56,['2 x hole diameter 3.2','centres X=7.50','0.70 web to right edge','M3 HEAD FIT BLOCKER'],2.4,4)
lines(46,164,['USB opening','4.20 x 9.80 R0.60','X=2.725..6.925','Y=59.35..69.15'],2.3,4)
lines(12,216,['Panel: FR4 1.60 (not Doepfer 2 mm Al).','A 6 mm M3 head overhangs right by 0.7.','Ø2.2 bracket holes X=4.9, Y=45 / 83.5.'],2.5,4)
# Side YZ: the carrier outline and supports really map to the two PCB files.
bx,by=116,43
text(108,37,'SIDE (looking -X)',3.2)
rect(bx,by,1.6*s,128.5*s,'#f4ead0')
rect(bx+2*s,by+14*s,60*s,100.5*s,'#d8ece1')
for Y in [45,83.5]:
    rect(bx+1.6*s,by+(Y-4)*s,8.4*s,8*s,'#b9c7d5')
    for Z in [6,52]:circ(bx+Z*s,by+Y*s,1.1*s)
    # Panel screws: four mm shank, head ahead of face; actual axis shown.
    rect(bx-1.2*s,by+(Y-1.9)*s,1.2*s,3.8*s,'#647587')
    line(bx,by+Y*s,bx+4*s,by+Y*s)
# USB shell nominal projection, mouth and insertion arrow.
rect(bx+.8*s,by+59.78*s,7.6*s,8.94*s,'#ead5cf')
line(bx-14,by+64.25*s,bx+9*s,by+64.25*s,'axis')
text(bx-17,by+64.25*s-3,'INSERT +Z',2.3)
line(bx-10,by+64.25*s,bx+.8*s,by+64.25*s,'dim')
rect(bx+65*s,by+40*s,22*s,35*s,'none',dash=True)
lines(bx+65*s+2,by+48*s,['HARNESS','unselected','to Z=87'],2.3,4)
line(bx+52*s,by+45*s,bx+52*s,by+83.5*s,'axis')
text(bx+33*s,by+90*s,'Tie / strain relief at Z=52',2.3)
text(bx+13*s,by+105*s,'Carrier Y=14..114.5',2.4)
dim(bx,by-3,bx+62*s,by-3,'Z=62 back edge',bx+24,by-5)
dim(bx+2*s,by+120*s,bx+62*s,by+120*s,'60.00 PCB depth',bx+18,by+118*s)
lines(106,216,['Carrier: 100.5 x 60 x 1.6; plane YZ.','Front support holes (Y,Z): (45,6), (83.5,6).','Rear holes (45,52), (83.5,52): tie only; not rail mounts.'],2.5,4)
# Top projection XZ; mouth axis remains normal to face, NOT sideways.
tx,ty=253,48
text(248,37,'TOP (looking +Y)',3.2)
rect(tx,ty,1.6*s,9.8*s,'#f4ead0')
rect(tx+2*s,ty+1.57*s,60*s,1.6*s,'#d8ece1')
rect(tx+.8*s,ty+3.17*s,7.6*s,3.31*s,'#ead5cf')
rect(tx+1.6*s,ty+3.17*s,8.4*s,5.8*s,'none',dash=True)
rect(tx+65*s,ty+.4*s,22*s,9*s,'none',dash=True)
line(tx-9,ty+4.9*s,tx+15*s,ty+4.9*s,'axis')
dim(tx,ty+17,tx+87*s,ty+17,'87 provisional cable envelope',tx+22,ty+21)
lines(248,77,['Panel Z=0..1.6; carrier front Z=2 (0.4 rear gap).','PCB bottom X=1.57; component face X=3.17.','USB mouth (X,Y,Z)=(4.90,64.25,0.80).','Plug axis +Z; plug shell fit / overmould NOT qualified.'],2.6,4)
# Enlarged interposer XZ section at either Y centre.
text(248,104,'2 x RIGHT-ANGLE INTERPOSER BLOCKS',3.2)
text(248,109,'Solid machined aluminium; no bent/soldered FR4 brackets.',2.5)
k=5.5;dx,dy=247,117
# local absolute X,Z projection: X to right, Z down
rect(dx,dy,9.8*k,1.6*k,'#f4ead0')
rect(dx+1.57*k,dy+2*k,1.6*k,11*k,'#d8ece1')
rect(dx+3.17*k,dy+1.6*k,5.8*k,8.4*k,'#b9c7d5')
# Blind threaded holes (major diameter envelope); thread engagement 2.4.
rect(dx+3.9*k,dy+1.6*k,2*k,2.8*k,'white')
rect(dx+3.17*k,dy+5*k,2.8*k,2*k,'white')
# Screw bodies + heads, front axial and side axial
rect(dx+3.9*k,dy,2*k,4*k,'#7d8793')
rect(dx+3*k,dy-1.2*k,3.8*k,1.2*k,'#7d8793')
rect(dx+1.57*k,dy+5*k,4*k,2*k,'#7d8793')
rect(dx+.37*k,dy+4.1*k,1.2*k,3.8*k,'#7d8793')
dim(dx+3.17*k,dy+14*k,dx+8.97*k,dy+14*k,'5.80 X width',dx+15,dy+14*k+4)
dim(dx+10.5*k,dy+1.6*k,dx+10.5*k,dy+10*k,'8.40',dx+10.5*k+1,dy+7*k)
lines(318,120,['Each block: X 5.80 x Y 8.00 x Z 8.40.','Origin at (3.17,Yc-4,1.6), Yc=45 / 83.5.','Panel hole: Xlocal=1.73, Ylocal=4, axis Z.','Carrier hole: Ylocal=4, Zlocal=4.40, axis X.','Both M2 x 0.4 blind taps.','Full thread >=2.6; TOTAL depth <=2.8,','including drill point. Flat-bottom process.','4 x M2 x 4; engagement nominal 2.4.','Side head h<=1.2, diameter <=3.8.','Exact low-head screw is UNSELECTED.','Faces/axes target +/-0.05; block +/-0.10.','Bare FR4 contact; copper keepout required.','Two support points, Y separation 38.50.'],2.35,4.2)
lines(248,204,['Panel/PCB thickness tolerance changes engagement and alignment.','Screw heads remain inside X=0.37..8.97 nominal (2HP width 9.8).','Keep Y<10 and Y>118.5 free for rail access; PCB begins at Y=14.','No independent USB shell cradle supplied: stakes -> PCB -> blocks.','Insertion force / cable torque / FR4 flex MUST be tested.'],2.45,4)
line(10,232,410,232)
lines(11,239,['MOUNTING DECISION: Doepfer A100FP.gif shows x=7.5, d=3.2, y=3 from both edges; pitch 122.5.',
 'CORRECTED rail holes to x=7.5, diameter 3.2: 0.7 FR4 web. A 5 x 3.2 slot runs off-panel, so NOT used.',
 'Standard 6 mm M3 heads overhang by 0.7: adjacent-module conflict. Narrow head / panel strength NOT resolved.',
 'M3 x 6 through 1.6 panel + 0.5 washer leaves 3.9 nominal thread reach: verify actual rail depth; do not bottom out.',
 'Assembly: tap blocks -> bolt to bare carrier -> solder J1 stakes -> loosely bolt panel -> align USB aperture -> tighten -> fit tie/harness -> rack.',
 'Profile/aperture target +/-0.10; only 0.43/0.445 nominal shell clearance per side. Trial plugs / worst-case stack remain blockers.',
 'Sources: doepfer.de/a100_man/A100FP.gif + a100m_e.htm; GCT USB4105 drawing geometry retained from A0. See mechanics.md.'],2.55,5)
a.append('</svg>')
(D/'assembly.svg').write_text('\n'.join(a)+'\n')
subprocess.run(['rsvg-convert','-f','pdf','-o',str(D/'assembly.pdf'),str(D/'assembly.svg')],check=True)
print('Created original three-view assembly SVG/PDF and geometry JSON; nominal proposal only.')
