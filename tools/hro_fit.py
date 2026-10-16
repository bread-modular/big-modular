"""Independent bounded HRO aperture fit; not a cable/assembled-product qualification."""
import math


def corner_margin(aperture, box, wall=0.10, radius_growth=0.10):
    """Exact signed distance of extreme rectangle corners to the minimum opening.

    wall is inward error of EACH straight wall (width/height can shrink by 2*wall).
    Radius may independently grow; location/registration is already in box.
    A rounded rectangle is convex, so containing four corners contains the box.
    """
    x,y,w,h,r=aperture
    x+=wall; y+=wall; w-=2*wall; h-=2*wall; r+=radius_growth
    assert 0<r<=min(w,h)/2
    margins=[]
    for px in box[:2]:
        for py in box[2:]:
            qx=abs(px-x-w/2)-(w/2-r)
            qy=abs(py-y-h/2)-(h/2-r)
            margins.append(r-math.hypot(max(qx,0),max(qy,0))-min(max(qx,qy),0))
    return min(margins)


def verify(g):
    # Independent acceptance literals: never derive requirements from the builder.
    assert g['panel_mm']==[9.8,128.5,1.6]
    assert g['carrier_X_mm']==[3.1,4.7] and g['carrier_Z_mm']==[2,32]
    assert g['mouth_axis_XYZ_mm']==[6.33,33.5,.8]
    assert g['aperture_XYWHR_mm']==[3.9,28.1,5.0,10.8,.6]
    assert g['USB']['native_origin_xy_mm']==[69.25,103.475]
    assert g['USB']['body_width_depth_height_mm']==[8.94,7.35,3.26]
    budget={
        'finished_board_thickness_mm':[1.44,1.76],
        'aperture_each_wall_error_mm':.10,
        'aperture_centre_registration_each_axis_mm':.10,
        'aperture_radius_mm':[.50,.70],
        'assembled_registration_each_axis_mm':.10,
        'shell_width_plus_mm':.15,'shell_height_plus_mm':.10,
        'seating_plus_X_mm':.05,'squareness_max_deg':.5,
        'tilt_projection_each_axis_mm':.02,
        'in_plane_angular_registration_max_deg':.5,
        'in_plane_rotation_sweep_XY_mm':[.04,.016],
        'outer_profile_each_edge_error_mm':.10,
    }
    assert g['USB_fit_acceptance']==budget, 'unreviewed or missing tolerance budget'
    # Tab anchors are independent of the ambiguous drawing PCB-edge chain.
    assert g['USB']['shell_tab_rows_from_mouth_mm']==[2.6,6.78]
    assert abs((103.475-6.78)-(99.8-3.105))<1e-9
    assert abs((103.475-2.6)-(99.8+1.075))<1e-9
    assert g['USB']['land_row_from_mouth_mm']==7.695
    assert abs((99.8-3.68)-(103.475-7.695)-.34)<1e-9
    copper_to_edge=.8+2.6-1.6/2-2
    drill_to_edge=.8+2.6-1.2/2-2
    assert copper_to_edge>=.599999 and drill_to_edge>=.799999
    # Carrier BACK is the mounting datum. Full finished-thickness deviation moves
    # its component face in X. Assembly and machined-aperture registration are
    # independent, added worst-case, NOT RSS. Panel thickness enters the tilt
    # sweep and Z recess; the guaranteed aperture profile applies THROUGH thickness.
    assert 1.76*math.tan(math.radians(.5))<.02
    assert 4.545*math.sin(math.radians(.5))<.04
    assert 1.73*math.sin(math.radians(.5))<.016
    box=[4.7-.16-.10-.10-.02-.04,
         4.7+.16+3.26+.10+.05+.10+.10+.02+.04,
         33.5-(8.94+.15)/2-.10-.10-.02-.016,
         33.5+(8.94+.15)/2+.10+.10+.02+.016]
    margin=corner_margin(g['aperture_XYWHR_mm'],box)
    assert margin>.22, ('toleranced shell/aperture interference or reserve lost',margin)
    # The predecessor opening MUST fail this complete budget, a useful negative control.
    old_margin=corner_margin([4.23,28.6,4.2,9.8,.6],box)
    assert old_margin<0
    assert g['brackets']['Y_centres_mm']==[22,106.5]
    assert g['LEDs'][0]['panel_XY_diameter_mm']==[6.7,43,3.6]
    assert g['reset_XY_diameter_mm']==[6.4,49.5,3.2]
    assert box[2]>27 and box[3]<43-1.9
    # Largest possible aperture vs smallest outside edge. No unrelated interfaces move.
    ligament=9.8-.10-(3.9+5+.10+.10)
    assert ligament>=.599999
    return {
        'nominal_shell_axis_XYZ_mm':[6.33,33.5,.8],
        'native_anchor_xy_mm':[69.25,103.475],
        'land_row_shift_toward_board_rear_mm':.34,
        'front_shell_copper_to_carrier_edge_mm':round(copper_to_edge,6),
        'front_slot_drill_to_carrier_edge_mm':round(drill_to_edge,6),
        'mouth_recess_from_panel_front_nominal_mm':.8,
        'mouth_recess_from_panel_front_acceptance_mm':[.42,1.18],
        'mouth_in_front_of_panel_rear_acceptance_mm':[.58,1.02],
        'conservative_shell_Xmin_Xmax_Ymin_Ymax_mm':[round(v,6) for v in box],
        'minimum_rounded_aperture_corner_margin_mm':round(margin,9),
        'predecessor_aperture_at_same_extremes_margin_mm':round(old_margin,9),
        'minimum_outer_edge_ligament_mm':round(ligament,6),
        'acceptance_budget':budget,
        'locator_nominal_diametral_clearance_mm':.15,
        'qualification':'Positive bare-board aperture clearance at declared acceptance extremes; not supplier approval. Assembly registration/squareness must be measured, not inferred from loose M3 holes. Cable insertion/overmould, ABS strength/shrinkage, connector sample and LED forming remain physical trials.'}
