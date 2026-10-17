#!/usr/bin/env python3
"""A4.2 original dimensioned two-board and angle-bracket drawings; NEW output only."""
from pathlib import Path
from html import escape
import argparse
import json
import subprocess
import shutil
from stack_geometry import geometry,carrier_outline


class Drawing:
    def __init__(self,title,subtitle):
        self.a=['<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297">',
                '<style>text{font-family:DejaVu Sans,sans-serif;fill:#19334b}</style>',
                '<rect x="5" y="5" width="410" height="287" fill="white" stroke="#375775" stroke-width=".4"/>']
        self.text(12,15,title,5);self.text(12,23,subtitle,2.8)
    def text(self,x,y,t,size=2.7):self.a.append(f'<text x="{x}" y="{y}" font-size="{size}">{escape(t)}</text>')
    def lines(self,x,y,ls,size=2.7,step=4.5):
        for i,t in enumerate(ls):self.text(x,y+i*step,t,size)
    def rect(self,x,y,w,h,c='none',dash=False,r=0):
        self.a.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" stroke="#375775" stroke-width=".25"'+(' stroke-dasharray="1.5 1"' if dash else '')+(f' rx="{r}"' if r else '')+'/>')
    def line(self,x,y,x2,y2,dash=False):
        self.a.append(f'<path d="M{x},{y} L{x2},{y2}" fill="none" stroke="#375775" stroke-width=".25"'+(' stroke-dasharray="1.5 1"' if dash else '')+'/>')
    def poly(self,points,c='none'):
        self.a.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="{c}" stroke="#375775" stroke-width=".25"/>')
    def circle(self,x,y,r,c='white'):
        self.a.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" stroke="#375775" stroke-width=".25"/>')
    def save(self,out,name):
        self.a.append('</svg>');(out/(name+'.svg')).write_text('\n'.join(self.a)+'\n')
        subprocess.run(['rsvg-convert','-f','pdf','-o',str(out/(name+'.pdf')),str(out/(name+'.svg'))],check=True)


def assembly(out,g):
    j=g['mouth_axis_XYZ_mm'][1]; sw=g['reset_XY_diameter_mm'][1]; led=g['LEDs'][0]['panel_XY_diameter_mm'][1]
    d=Drawing('V1 TOP USB / SINGLE POWER LED | TWO BOARDS + TWO PLAIN M3 L BRACKETS','Front panel + perpendicular main PCB. No middle board, spacers or UI headers. mm. ROUTED HRO CARRIER; BARE-PCB ARTWORK, NOT BENCH QUALIFICATION.')
    s=1.35; fx=18; fy=43
    d.text(15,35,'FRONT PANEL',3.3)
    d.rect(fx,fy,9.8*s,128.5*s,'#f1dfb6')
    for x,y,di in g['rail_holes_mm']+g['panel_bracket_holes_mm']+[led['panel_XY_diameter_mm'] for led in g['LEDs']]+[g['reset_XY_diameter_mm']]:
        d.circle(fx+x*s,fy+y*s,di*s/2)
    x,y,w,h,r=g['aperture_XYWHR_mm'];d.rect(fx+x*s,fy+y*s,w*s,h*s,'white',r=r*s)
    for yy,t in [(3,'Rail X2.42 / dia3.2'),(22,'M3 bracket X6.4 / Y22'),(led,f'D10 +5V / X6.7 / Y{led:g} / dia3.6'),(j,'HRO USB axis X6.33'),(sw,f'Retry X6.4 / Y{sw:g} / dia3.2'),(106.5,'M3 bracket X6.4 / Y106.5'),(125.5,'Rail Y125.5 / dia3.2')]:
        d.line(fx+9.8*s,fy+yy*s,36,fy+yy*s);d.text(37,fy+yy*s+1,t,2.5)
    d.lines(15,227,['9.8 x 128.5 x 1.6 FR4','Round corner rail holes retained.','6mm rail screw heads overhang .58mm.','Check adjacent panels; no countersink.'])
    # Side elevation, Y down and Z right; see real relief shape rather than box.
    zx=119; zy=43
    d.text(116,35,'SIDE / YZ ELEVATION',3.3)
    d.rect(zx,zy,1.6*s,128.5*s,'#f1dfb6')
    d.poly([(zx+z*s,zy+y*s) for y,z in carrier_outline()],'#d6e3f1')
    for yc in [22,106.5]:
        d.rect(zx+1.6*s,zy+(yc-5)*s,3*s,10*s,'#e8b396')
        d.rect(zx+4.6*s,zy+(yc-5)*s,15.4*s,10*s,'#e8b396',True)
        d.circle(zx+15*s,zy+yc*s,1.6*s)
    for yy,zz,w,h,c in [(led,-.2,6.57,3.8,'#da7777'),(j,.8,8.42,9.64,'#c7ccd2'),(sw,2.05,4.85,6.2,'#c7ccd2')]:
        d.rect(zx+zz*s,zy+(yy-h/2)*s,w*s,h*s,c)
    d.lines(165,58,['Main PCB: 100.5 x 30 x 1.6','Front edge Z2; rear Z32','Current local cutbacks end at Z10','For this foot + loose M3 hardware','PCB depth behind panel rear: 30.4','NOT finished cabled depth.'],2.6)
    d.line(zx+32*s,zy+j*s,184,zy+j*s,True)
    d.lines(166,146,['J7: 16 numbered solder-through lands','Keyed 2x8 MALE IDC on flying lead','75-100mm lead, strain-relieved','Connector not squeezed into 2HP.','No third PCB.'],2.6)
    d.lines(117,224,['HRO land imported; mouth Y33.5 / Z0.8; NO 3D model.',
                     'PCB BACK X3.1 / component face X4.7.',
                     'Web on PCB BACK; foot on front panel REAR (Z1.6).',
                     'Screws normal to each face; PCB not fed through L.',
                     'Uncut FR4/foot overlap: X3.1..4.7, Z2..4.6.',
                     'Y17..27 / 101.5..111.5; current configuration only.',
                     'Cutbacks clear THIS L + M3 nut/tool access.',
                     'Z10 retained, not a proven minimum.',
                     '90-degree face mounts do not inherently need notches.',
                     'Notch-free 2HP here needs changed hardware; not selected.',
                     'USB and LED/reset openings follow the shown axes.'],2.6)
    d.text(268,35,'MAIN PCB / COMPONENT SIDE',3.3)
    px=271; py=43
    d.poly([(px+z*s,py+(y-14)*s) for y,z in carrier_outline()],'#d6e3f1')
    for y,z in g['carrier_holes_YZ_mm']:d.circle(px+z*s,py+(y-14)*s,1.6*s)
    for y,z in g['power_output']['strain_relief_holes_YZ_mm']:d.circle(px+z*s,py+(y-14)*s,1.25*s)
    for yy,zz,w,h,label in [(led,6.37,6,4.34,'D10 / RED +5V POWER'),(j,5.01,8.42,9.64,'J1 / USB-C'),(sw,4.1,4.85,6.2,'SW1 / 90 deg SMT')]:
        d.rect(px+(zz-w/2)*s,py+(yy-14-h/2)*s,w*s,h*s,'#c7ccd2')
        d.line(px+(zz+w/2)*s,py+(yy-14)*s,322,py+(yy-14)*s)
        d.text(324,py+(yy-14)*s+1,label,2.5)
    for row in range(8):
        for col in range(2):d.circle(px+(27+col*2.54)*s,py+(48+row*2.54-14)*s,.65*s)
    d.lines(269,191,['D10 ONLY: RED 3mm +5V POWER THT, formed 90 deg.','SW1: E-Switch TL3340AF160QG, SMT.','Three signal pads + two solder anchors.','Front-side fine-tip soldering; 2 locating holes.','3.3mm body height; axis X6.4, recessed Z2.05.','Pins1+3 common; pin2 other contact. No plunger.'],2.6)
    d.lines(269,229,['12 V power output pin pairs:','1-2: -12V | 3-8: GND | 9-10: +12V','11-12: +5V | 13-16: NOT CONNECTED','POWER OUTPUT, not a rack power input!','Do not connect to another active PSU.'],2.6)
    d.text(12,282,'Routed HRO. D10: P5 -> R32 1k -> LED -> GND. No blink/controller. L1/L4 max4.0mm +0.25 assembly budget; L2/L3 max4.7 +0.25. Physical trial/bench validation pending.',2.7)
    d.save(out,'assembly')


def brackets(out,g):
    d=Drawing('A4.1 | PLAIN L BRACKET - PRINT TWO IDENTICAL PARTS',
              '3mm walls, two holes, no nut traps or inserts. ABS prototype. M3x8 front + M3x8 countersunk side; four loose M3 nuts.')
    ox=25; oz=50; k=7
    def rect(x,z,w,h,c='none',dash=False):d.rect(ox+x*k,oz+z*k,w*k,h*k,c,dash)
    def poly(pts,c):d.poly([(ox+x*k,oz+z*k) for x,z in pts],c)
    d.text(15,35,'XZ SECTION THROUGH BOTH HOLES',3.2)
    rect(-.1,-1.6,9.8,1.6,'#f1dfb6')
    poly([(0,0),(9.2,0),(9.2,3),(3,3),(3,18.4),(0,18.4)],'#e8b396')
    rect(3,8.4,1.6,20,'#d6e3f1')
    rect(6.3-1.6,0,3.2,3,'white')
    rect(0,13.4-1.6,3,3.2,'white')
    poly([(0,10.4),(1.4,11.8),(1.4,15),(0,16.4)],'white')
    rect(6.3-3.175,3,6.35,2.4,'#b8b8b8')
    rect(4.6,13.4-3.175,2.4,6.35,'#b8b8b8')
    rect(4.8,-1.6,3,8,'none',True)
    rect(0,11.9,8,3,'none',True)
    d.lines(101,46,['Local origin = assembly X0.1 / Z1.6','Overall 9.2 X x 10 Y x 18.4 Z','BOTH legs are 3.0mm thick.','Upright on PCB BACK face (B.Cu X3.1).','Foot on front panel REAR face (Z1.6).','Screws normal to faces; PCB not fed through L.','Plain nuts sit OUTSIDE the printed L.','No slots, captive pockets, roofs or inserts.'],2.7)
    d.lines(101,83,['HOLES / LOCAL DIMENSIONS','Front: X6.3 / Y5.0, diameter3.2','Side: Y5.0 / Z13.4, diameter3.2','Side countersink: diameter6.0 x 90 deg','Depth1.4; leaves1.6 of straight bore.','Countersink PLASTIC ONLY, never FR4.'],2.7)
    d.lines(101,121,['FASTENERS','Front M3x8 pan/button, head <=6 dia','Side M3x8 flat countersunk (90 deg)','Side length includes head; seat it flush.','4 loose plain M3 nuts: AF<=5.5, h<=2.4','No washers or tall nyloc nuts.','Minimum nominal thread exit: 1.0 each.'],2.7)
    d.lines(101,164,['FIT LIMITS','Front nut-to-upright: only 0.125 nominal','Nut swept right edge X9.575 (panel9.8)','Side head flush to0.3mm below face','Side screw tip X8.1..8.4','Measure ABS shrinkage and actual nuts.'],2.7)
    d.lines(101,203,['CURRENT CARRIER CUTBACKS AT FRONT FOOT',
                     'Y16.5..27.5 / 101..112 to Z10.',
                     'Uncut PCB meets foot at Z2..4.6.',
                     'Specific to this L + loose M3 nuts/tools.',
                     'Z10 retained; not a proven minimum.',
                     '90-degree face mounts need not have notches.',
                     'Notch-free 2HP here needs changed hardware.',
                     'No alternative hardware selected or drawn.'],2.6)
    d.text(263,35,'HOLE COORDINATES / MOUNTING',3.2)
    d.lines(263,47,['Panel: X6.4, Y22 / Y106.5, diameter3.2','Main PCB: same Y, Z15, diameter3.2','Bracket pitch:84.5; panel holes moved +1.5 X.','PCB plane and main mounting holes unchanged.','Foot normal to panel REAR (+Z screw).','Web normal to PCB BACK (+X screw).'],2.8)
    d.text(263,77,'PANEL-REAR MATING FACE / LOCAL XY',3.1)
    ax=273; ay=84; q=6
    d.rect(ax,ay,9.2*q,10*q,'#e8b396');d.circle(ax+6.3*q,ay+5*q,1.6*q)
    d.line(ax+3*q,ay,ax+3*q,ay+10*q,True)
    d.lines(335,103,['Hole (6.3,5.0)','9.2 x 10 face','Dashed: 3mm wall'],2.5)
    d.text(263,157,'OUTER SIDE / LOCAL YZ',3.1)
    sx=273; sy=164
    d.rect(sx,sy,18.4*4,10*4,'#e8b396')
    d.circle(sx+13.4*4,sy+5*4,3*4,'none');d.circle(sx+13.4*4,sy+5*4,1.6*4)
    d.text(263,213,'Hole (Y5.0,Z13.4); outer circle is countersink.',2.7)
    d.lines(15,256,['SERVICE OUT OF RACK: hold front nut with small pliers from +X; side nut with 5.5mm nut driver from +X.','Drive screws from panel front (-Z) and bracket outer side (-X). Soldered PCB can stay fitted.','Print L profile flat. ABS is a candidate, not strength approval. Trial screw seating, nut/tool access and shrinkage.'],2.6)
    d.text(263,235,'Source: hardware/mechanics/corner_braces.scad',2.5)
    d.text(263,243,'SCAD only; no tested STL or physical print.',2.5)
    d.save(out,'m3-brackets')



def usb_detail(out,g):
    d=Drawing('HRO TYPE-C-31-M-12 | USB FIT AND DATUM REVIEW',
              'Exact Bread local lands + primary HRO body drawing. NO verified STEP model. This is a dimensioned envelope, not physical qualification.')
    d.lines(16,40,[
      'Panel X across / Y down / Z into case. Carrier F.Cu X4.7; board front Z2.',
      'HRO shell: 8.94 wide x 7.35 deep x 3.26 high (drawing). Nominal shell axis X6.33.',
      'Mating face Z0.8, Y33.5. Native footprint anchor (69.25,103.475), rotation 0 degrees.',
      'Datum anchors: front shell tab 2.60 from face; rear 6.77 drawing / 6.78 local.',
      'Ambiguous drawing vertical 0.50/1.64/4.18/5.79 chain is NOT used to invent a PCB-edge datum.',
      'Local pad row: 7.695 from mouth; local land length 1.45, not claimed manufacturer-dimensioned.',
      'Old GCT land row was 7.355 from mouth: HRO moves row 0.34 rearward; shell slot centres stay.',
      'Local bosses: dia0.65 NPTH, nominal molded boss dia0.50; no peg shrinking.',
      'Local shell drills: two 0.6 x1.7 rear and two 0.6 x1.2 front plated slots; no shell paste.',
      'Front slot: nominal drill-to-board-edge 0.80; copper-to-board-edge 0.60.',
      'A1/B12, A4/B9, A9/B4, A12/B1 share four wide PCB lands. S1 shell is GND.',
      'A5=CC1, B5=CC2; all four data and two SBU contacts remain explicit NC.'],3.1,6)
    x,y,w,h,r=g['aperture_XYWHR_mm'];scale=8;ox=30;oy=145
    d.rect(ox,oy,9.8*scale,18*scale,'#f1dfb6')
    d.rect(ox+x*scale,oy+(y-25)*scale,w*scale,h*scale,'white',r=r*scale)
    d.rect(ox+4.7*scale,oy+(33.5-8.94/2-25)*scale,3.26*scale,8.94*scale,'#c7ccd2')
    from hro_fit import verify
    fit=verify(g);box=fit['conservative_shell_Xmin_Xmax_Ymin_Ymax_mm']
    d.rect(ox+box[0]*scale,oy+(box[2]-25)*scale,(box[1]-box[0])*scale,(box[3]-box[2])*scale,'none',True)
    d.lines(125,150,[
      'FRONT VIEW: GRAY NOMINAL / DASHED WORST-CASE SHELL',
      f'Aperture: X{x:.2f}, Y{y:.2f}, W{w:.2f}, H{h:.2f}, R{r:.2f} mm.',
      'Delta from 024: X -0.33, Y -0.50, width +0.80, height +1.00.',
      'Each machined wall +/-0.10; centre registration +/-0.10 X/Y.',
      'Corner radius 0.50..0.70; profile acceptance THROUGH thickness.',
      'BOTH finished boards 1.60 +/-0.16 mm, including coating.',
      'Carrier back-face datum fixed: thickness error moves shell in X.',
      'Assembly registration +/-0.10 X/Y; seating +0.05 X.',
      'Shell width +0.15, height +0.10; all errors add worst-case.',
      'Squareness <=0.5 deg; +/-0.02 tilt sweep through max1.76 panel.',
      f"Minimum modeled corner clearance: {fit['minimum_rounded_aperture_corner_margin_mm']:.3f} mm.",
      'In-plane angular registration <=0.5 deg; sweep +/-.040 X / .016 Y.',
      'Assembly registration must be measured; M3 freeplay is not proof.',
      'Panel9.8 x128.5 / carrier100.5 x30; D10/SW1/J7/brackets fixed.',
      'Mouth recess 0.42..1.18; ahead of rear face 0.58..1.02 mm.',
      'Cable insertion/overmould, ABS and actual assembled trial pending.',
      'Bare-PCB aperture fit is NOT product/strength/bench qualification.',
      'Fabrication process requirements: docs/fabrication.md.'],3,6)
    d.save(out,'usb-fit')


def scad_envelope(out,g):
    from hro_fit import verify
    verify(g)  # Frozen assembly envelope must not silently diverge from geometry.
    # No fake connector STEP: translucent bounding box is visibly an envelope.
    holes=g['rail_holes_mm']+g['panel_bracket_holes_mm']+[q['panel_XY_diameter_mm'] for q in g['LEDs']]+[g['reset_XY_diameter_mm']]
    text='// GENERATED by tools/build_mechanics.py; dimensions mm. NOT a connector model.\n'
    text+='// Physical cable/bracket/LED-forming validation remains required.\nuse <corner_braces.scad>;\n$fn=64;\n'
    text+=f'outline={json.dumps(carrier_outline())};\nholes={json.dumps(holes)};\n'
    x,y,w,h,r=g['aperture_XYWHR_mm']
    text+=f'// Finished thickness1.44..1.76; machined aperture wall +/-0.10, centre +/-0.10, R0.50..0.70.\n'
    text+=f'module aperture(){{translate([{x}+{r},{y}+{r}])offset(r={r})square([{w}-{2*r},{h}-{2*r}]);}}\n'
    text+='color("gold")linear_extrude(1.6)difference(){square([9.8,128.5]);aperture();for(h=holes)translate([h[0],h[1]])circle(d=h[2]);}\n'
    text+='color("darkgreen")translate([3.1,0,0])multmatrix([[0,0,1,0],[1,0,0,0],[0,1,0,0],[0,0,0,1]])linear_extrude(1.6)difference(){polygon(outline);for(h=[[22,15,3.2],[106.5,15,3.2],[43.5,27,2.5],[70.5,27,2.5]])translate([h[0],h[1]])circle(d=h[2]);}\n'
    text+='// Gray block: drawing-based HRO body envelope, NOT a STEP/mating model.\ncolor([.7,.7,.7,.5])translate([4.7,33.5-8.94/2,.8])cube([3.26,8.94,7.35]);\n'
    text+='for(y=[22,106.5])color("orange")translate([.1,y-5,1.6])bracket();\n'
    (out/'assembly-envelope.scad').write_text(text)
    shutil.copyfile(Path(__file__).resolve().parents[1]/'hardware/mechanics/corner_braces.scad',out/'corner_braces.scad')


def build(out):
    out.mkdir(parents=True,exist_ok=False);g=geometry()
    (out/'assembly-geometry.json').write_text(json.dumps(g,indent=2)+'\n')
    from hro_fit import verify
    (out/'usb-fit.json').write_text(json.dumps(verify(g),indent=2)+'\n')
    assembly(out,g);brackets(out,g);usb_detail(out,g);scad_envelope(out,g)
    subprocess.run(['pdfunite',str(out/'assembly.pdf'),str(out/'usb-fit.pdf'),str(out/'assembly-combined.pdf')],check=True)
    (out/'assembly-combined.pdf').replace(out/'assembly.pdf')
    print('Created A4.2 two-board and M3 bracket drawings:',out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    build(p.parse_args().output)
