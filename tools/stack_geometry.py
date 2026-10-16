"""A4.2 simple-L two-board placement contract. mm; panel front Z=0, +Z into case.
No middle PCB, spacers or board-to-board UI headers. Exact native USB unchanged;
retained A4 assembly plane (X3.1..4.7); A4.2 uses plain L + restored SMT reset.
"""
from copy import deepcopy
from interface_contract import LED_RAILS

GEOMETRY = {
    'revision': 'A4.2 LED3 mechanical checkpoint / plain M3 L brackets / placement-only',
    'board_count': 2,
    'panel_mm': [9.8, 128.5, 1.6],
    'rail_holes_mm': [[2.42,3,3.2], [2.42,125.5,3.2]],
    'rail_compatibility': 'Common fixed-strip phase: 7.50 - 5.08 = 2.42; also sliding nuts',
    'rail_head_note': '6mm heads overhang left by 0.58mm; check neighbour. No FR4 countersink.',
    'panel_bracket_holes_mm': [[6.4,22,3.2], [6.4,106.5,3.2]],
    'carrier_X_mm': [3.1,4.7], 'carrier_Y_mm': [14,114.5], 'carrier_Z_mm': [2,32],
    'carrier_holes_YZ_mm': [[22,15], [106.5,15]],
    'carrier_bracket_reliefs_YZ_mm': [[16.5,27.5,10], [101,112,10]],
    'aperture_XYWHR_mm': [4.255,59.35,4.2,9.8,.6],
    'mouth_axis_XYZ_mm': [6.43,64.25,.8],
    'LEDs': [
        {'reference': ref, 'rail': LED_RAILS[ref], 'panel_hole_ref': hole,
         'panel_XY_diameter_mm': [6.7,y,3.6], 'pad1_YZ_mm': [y-1.27,6.37]}
        for ref,hole,y in [('D10','H5',38),('D11','H7',46),('D12','H8',54)]
    ],
    'reset_XY_diameter_mm': [6.4,91,3.2],
    'LED': {
        'type': 'standard RED 3mm round THT LED, leads formed 90 degrees; no proprietary holder',
        'assembly': 'manual; exclude D10/D11/D12 from both JLC assembly BOM and CPL',
        'pin_roles': {'1': 'K (cathode)', '2': 'A (anode)'},
        'footprint': 'LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge',
        'pitch_mm':2.54, 'drill_mm':.9, 'pad_diameter_mm':1.8,
        'axis_above_PCB_mm':2.0, 'nominal_body_base_Z_mm':5.1,
        'nominal_tip_Z_mm':-.2, 'max_body_diameter_mm':3.25,
        'max_flange_diameter_mm':3.8,
        'note':'Generic 5.3mm-long lamp envelope. Select actual LED and form leads in a jig with panel; do not bend at epoxy. No light pipe.'
    },
    'switch': {'reference': 'SW1',
     'mpn': 'TL3340AF160QG',
     'manufacturer': 'E-Switch',
     'LCSC': 'C2886925',
     'type': 'SPST-NO momentary, side-actuated 90 degrees, exposed SMT leads',
     'footprint': 'SW_TL3340AF160QG_HandSolder',
     'peg_row_YZ_mm': [91, 4.1],
     'actuator_axis_height_mm': 1.7,
     'body_height_mm': 3.3,
     'actuator_tip_Z_mm': 2.05,
     'actuator_diameter_mm': 2.0,
     'travel_mm': [0.1, 0.3],
     'pins': {'1': 'RESET_A_PENDING', '2': 'RESET_B_PENDING', '3': 'RESET_A_PENDING', 'MP': ''},
     'note': 'SMT, NOT through-hole. Exposed pads extended rearward for iron access; fine '
             'tip/flux/tweezers required. No buried signal pads. Recessed button, no printed '
             'plunger selected.',
     'body_width_Y_mm': 4.5,
     'body_depth_Z_mm': 2.55,
     'body_Z_mm': [2.9, 5.45],
     'peg_pitch_mm': 4.25,
     'peg_drill_mm': 0.9,
     'datasheet': 'https://configured-product-images.s3.amazonaws.com/2D/specs/TL3340AF160QG.pdf'},
    'led_resistors': {'status': 'R32 axial PCB reservation retired; no resistor populated in this checkpoint',
        'plan': 'Basic SMD preferred; values, references, ratings and controller await electrical brief'},
    'brackets': {
        'quantity':2, 'identical':True, 'shape':'Plain L, no nut traps or inserts',
        'Y_centres_mm':[22,106.5], 'outer_X_mm':[.1,9.3], 'width_Y_mm':10.0,
        'outer_Z_mm':[1.6,20], 'wall_mm':3.0,
        'front_foot_Z_mm':[1.6,4.6], 'side_web_X_mm':[.1,3.1],
        'front_hole_X_mm':6.4, 'side_hole_Z_mm':15, 'hole_mm':3.2,
        'front_bolt':'M3 x 8 pan/button head',
        'side_bolt':'M3 x 8 flat countersunk, 90 degrees; length includes head',
        'front_length_mm':8.0, 'side_length_mm':8.0,
        'side_countersink_diameter_mm':6.0, 'side_countersink_angle_deg':90,
        'side_head_recess_mm':[0,.3],
        'front_head_diameter_max_mm':6.0, 'side_head_diameter_max_mm':6.0,
        'nut_AF_max_mm':5.5, 'nut_thickness_max_mm':2.4,
        'front_thread_exposure_mm':1.0, 'side_thread_exposure_min_mm':1.0,
        'front_tool_X_mm':[6.4,30], 'front_tool_Y_width_mm':10.0,
        'front_tool_Z_mm':[4.6,7.6],
        'side_nut_driver_diameter_max_mm':8.0, 'side_nut_driver_depth_min_mm':4.0,
        'washers':'No washers in specified length stacks. Plain hex nuts, not nyloc.',
        'access':'OUT OF RACK. Loose nuts and holding tool enter from +X. Front driver -Z; flush side driver -X. Main PCB can stay soldered and fitted.',
        'material':'ABS prototype candidate; print L profile flat, measure shrinkage and trial fit',
        'note':'3mm walls; countersink only in PRINTED bracket, never PCB. Front nut has only 0.125mm nominal clearance to upright at worst rotation. No print/strength qualification.'
    },
    'power_output': {
        'main_reference':'J7', 'connector_reference':'J2 (existing off-board circuit symbol)',
        'type':'Keyed/shrouded male IDC 2x8, 2.54mm mating pitch, CABLE MOUNT on insulated flying lead',
        'candidate_mpn':'Wurth 61201625821',
        'launch_pad1_YZ_mm':[48,27], 'launch_pitch_mm':2.54,
        'strain_relief_holes_YZ_mm':[[43.5,27],[70.5,27]], 'strain_relief_drill_mm':2.5,
        'pigtail_length_mm':[75,100],
        'pinout':{'1':'N12','2':'N12','3':'GND','4':'GND','5':'GND','6':'GND','7':'GND','8':'GND','9':'P12','10':'P12','11':'P5','12':'P5','13':'','14':'','15':'','16':''},
        'cable':'16-conductor 1.27mm ribbon, 28AWG stranded copper; ordinary 16-to-16 keyed female IDC power cable at output',
        'placement_reason':'Full shrouded PCB header housing does not fit normal to this 2HP main board. No third PCB: cable-mount connector outside narrow board stack.',
        'warning':'POWER OUTPUT ONLY to unpowered passive distribution. NEVER parallel with a powered rack PSU. No output-current rating or power-up approval.'
    },
    'solder_tail_max_below_B_Cu_mm':1.8,
    'harness_envelope_XYZ_mm':[[.4,9.4],[40,75],[34,50]],
    'harness_status':'Provisional cable budget only; complete populated/cabled depth unverified',
    'electrical_status':'J1 and 88-part circuit unchanged; D10/D11/D12/SW1 are PCB-only isolated reservations on MAIN PCB, not electrically integrated; R32 axial retired',
    'status':'NO routing, fabrication approval, strength test or working reset/LED circuit'
}


def geometry(): return deepcopy(GEOMETRY)
def carrier_xy(y,z): return (round(y+35.75,5),round(104.275-z,5))
def panel_xy(x,y): return (round(x+50,5),round(y+30,5))


def carrier_outline():
    return [(14,2),(16.5,2),(16.5,10),(27.5,10),(27.5,2),
            (101,2),(101,10),(112,10),(112,2),(114.5,2),(114.5,32),(14,32)]
