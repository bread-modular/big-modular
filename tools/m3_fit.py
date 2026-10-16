"""A4.1 nominal plain-L fit and tool paths, NOT a tolerance or strength proof."""
import math


def overlap(a,b):
    return all(min(x[1],y[1])-max(x[0],y[0])>1e-7 for x,y in zip(a,b))


def prisms(outline,x_range):
    ys=sorted({v[0] for v in outline})
    for lo,hi in zip(ys,ys[1:]):
        mid=(lo+hi)/2
        zs=sorted(a[1] for a,b in zip(outline,outline[1:]+outline[:1])
                  if a[1]==b[1] and min(a[0],b[0])<mid<max(a[0],b[0]))
        assert len(zs)%2==0
        for z0,z1 in zip(zs[::2],zs[1::2]):yield [x_range,[lo,hi],[z0,z1]]


def verify_access(g,outline):
    b=g['brackets']; bx=g['carrier_X_mm']; panel=g['panel_mm']
    assert len(g['panel_bracket_holes_mm'])==len(g['carrier_holes_YZ_mm'])==2
    assert bx==[3.1,4.7] and panel==[9.8,128.5,1.6]
    assert b['outer_X_mm']==[.1,9.3] and b['outer_Z_mm']==[1.6,20]
    assert b['wall_mm']==3.0 and b['side_web_X_mm']==[.1,3.1]
    assert b['front_foot_Z_mm']==[1.6,4.6]
    assert not any('pocket' in key or 'slot' in key for key in b), 'not a plain L'
    assert b['nut_AF_max_mm']<=5.5 and b['nut_thickness_max_mm']<=2.4
    assert b['side_countersink_angle_deg']==90
    sink=(b['side_countersink_diameter_mm']-b['hole_mm'])/2
    assert b['wall_mm']-sink>=1.5, 'insufficient material behind countersink'
    assert b['side_head_diameter_max_mm']<=b['side_countersink_diameter_mm'], 'side head not seated'
    assert 0<=b['side_head_recess_mm'][0]<=b['side_head_recess_mm'][1]<=.3, 'side head must be flush or slightly recessed'
    front_x=b['front_hole_X_mm']; foot_back=b['front_foot_Z_mm'][1]
    nut_radius=b['nut_AF_max_mm']/math.sqrt(3) # worst rotational swept envelope
    nut_gap=front_x-nut_radius-b['side_web_X_mm'][1]
    assert nut_gap>=.1, 'front nut collides or has insufficient upright clearance'
    assert front_x+nut_radius<=panel[0]-.1, 'front nut outside panel width'
    assert front_x+b['front_head_diameter_max_mm']/2<=panel[0], 'front screw head outside panel width'
    front_exit=b['front_length_mm']-foot_back-b['nut_thickness_max_mm']
    side_tip=[b['outer_X_mm'][0]+r+b['side_length_mm'] for r in b['side_head_recess_mm']]
    side_exit=side_tip[0]-bx[1]-b['nut_thickness_max_mm']
    assert front_exit>=.5 and side_exit>=.5, 'nut not fully engaged / bolt too short'
    assert side_tip[1]<panel[0]-.1, 'side screw tip outside panel width'
    assert b['side_nut_driver_depth_min_mm']>=side_tip[1]-bx[1], 'side nut driver too shallow'
    carrier=list(prisms(outline,bx)); reports=[]
    # Conservative reservations for already placed components; no converter fit claim.
    parts=[[[4.7,8.7],[y-3.8,y+3.8],[-.2,8]] for y in [38,46,54]]
    parts += [[[4.7,8.4],[59,70],[.8,9]], [[4.7,9.2],[86,96],[2.05,10]],
              [[1.3,9.4],[42,72],[25,32]]]
    for i,y in enumerate(b['Y_centres_mm']):
        assert g['panel_bracket_holes_mm'][i]==[front_x,y,3.2]
        assert g['carrier_holes_YZ_mm'][i]==[y,15]
        foot=[b['outer_X_mm'],[y-5,y+5],b['front_foot_Z_mm']]
        web=[b['side_web_X_mm'],[y-5,y+5],[foot_back,20]]
        front_nut=[[front_x-nut_radius,front_x+nut_radius],
                   [y-nut_radius,y+nut_radius],[foot_back,foot_back+b['nut_thickness_max_mm']]]
        nut_entry=[[front_x-nut_radius,30],front_nut[1],front_nut[2]]
        # Small pliers enter from +X, grip NEAR half of front nut across Y flats.
        # Not a rear socket-driver claim: board/web would block that tool.
        front_tool=[b['front_tool_X_mm'],[y-b['front_tool_Y_width_mm']/2,y+b['front_tool_Y_width_mm']/2],b['front_tool_Z_mm']]
        rr=b['side_nut_driver_diameter_max_mm']/2
        side_tool=[[bx[1],30],[y-rr,y+rr],[15-rr,15+rr]]
        front_driver=[[front_x-1.5,front_x+1.5],[y-1.5,y+1.5],[-25,0]]
        side_driver=[[-25,.1],[y-1.5,y+1.5],[13.5,16.5]]
        for solid in carrier:
            assert not overlap(foot,solid), 'bracket foot collides with PCB'
            assert not overlap(web,solid), 'bracket upright collides with PCB'
            for tool in [nut_entry,front_tool,side_tool,front_driver,side_driver]:
                assert not overlap(tool,solid), 'nut or tool path blocked by PCB'
        for tool in [nut_entry,front_tool,side_tool,front_driver,side_driver]:
            for solid in [foot,web]+parts:
                assert not overlap(tool,solid), 'nut or tool path blocked by bracket/component'
        for solid in parts:
            assert not overlap(foot,solid) and not overlap(web,solid), 'bracket hits component'
        reports.append({'Y_mm':y,'loose_nut_access_clear_nominal':True,
                        'front_bolt_exposure_mm':round(front_exit,3),
                        'side_bolt_exposure_min_mm':round(side_exit,3),
                        'front_nut_upright_clearance_mm':round(nut_gap,3),
                        'front_nut_right_X_mm':round(front_x+nut_radius,3),
                        'side_tip_X_range_mm':[round(v,3) for v in side_tip]})
    return {'brackets':reports,'identical_parts':True,'all_fasteners':'M3',
            'plain_L':True,'wall_mm':3,'countersink_in':'printed bracket only; NO FR4 countersink',
            'service_condition':'OUT OF RACK, soldered main PCB retained; front nut held from +X with small pliers, side nut driver +X, screwdrivers -X and -Z',
            'limitation':'Nominal envelopes only. Front-nut clearance is tight (0.125mm). Actual tools, ABS shrinkage, screw seating and printed strength require physical trial.'}
