// A4.1: TWO IDENTICAL PLAIN L BRACKETS. mm. ABS fit prototype.
// No captive nuts, pockets, roofs, inserts or standoffs. Two bores per part.
// Local origin = assembly X0.1, Y=centre-5, Z1.6. Centres Y22 and Y106.5.
// Upright touches main PCB BACK face X3.1, not its component face.
// Front: M3x8 pan/button screw + loose M3 nut; hole assembly X6.4.
// Side: M3x8 90-degree flat countersunk screw + loose nut on PCB F.Cu side.
// Countersink is in printed plastic ONLY, never in the 1.6mm PCB or panel.
// Use plain nuts AF<=5.5, thickness<=2.4; no washers in these length stacks.
// Print L outline flat as arranged; measure ABS shrinkage and bore fit.
// No STL/slicer/strength/physical-fit qualification is claimed.
$fn=64;
width_x=9.2;
width_y=10;
depth_z=18.4;
wall=3.0;
front_x=6.3;
side_z=13.4;
clearance=3.2;
countersink_diameter=6.0;
countersink_depth=1.4;  // 90 degrees: (6.0-3.2)/2

module bracket() {
    difference() {
        union() {
            cube([width_x,width_y,wall]);
            cube([wall,width_y,depth_z]);
        }
        // Front/panel hole along Z, accessible loose nut above foot.
        translate([front_x,width_y/2,-.1])
            cylinder(h=wall+.2,d=clearance);
        // Side hole along X. Screw head flush with OUTER/left plastic face.
        translate([-.1,width_y/2,side_z]) rotate([0,90,0])
            cylinder(h=wall+.2,d=clearance);
        translate([0,width_y/2,side_z]) rotate([0,90,0])
            cylinder(h=countersink_depth,d1=countersink_diameter,d2=clearance);
    }
}
// Flat L-profile print orientation; local Y is the print height (10mm).
translate([0,depth_z,0]) rotate([90,0,0]) bracket();
translate([width_x+4,depth_z,0]) rotate([90,0,0]) bracket();
