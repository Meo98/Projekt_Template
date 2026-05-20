// =============================================================
// <PROJEKT> — parametrisches Gehäuse (OpenSCAD)
//
// TEMPLATE: Board-Maße aus KiCad holen, dann hier eintragen.
//   1. Board-Außenmaße: in KiCad → Edit → "Board Setup" oder den
//      Edge.Cuts-Layer ausmessen. Alternativ aus der .kicad_pcb:
//        python3 -c "import re,sys; c=open(sys.argv[1]).read(); \
//          xs=[float(x) for x in re.findall(r'\\((?:start|end)\\s+([0-9.-]+)\\s', c)]; \
//          print('Breite ~', max(xs)-min(xs))" hardware/kicad/<Projekt>.kicad_pcb
//   2. max_component_height: am realen Board mit Messschieber messen
//      (Board-Oberfläche bis Oberkante höchstes Bauteil) + 2-3mm Luft.
//
// Rendern:    openscad case.scad        (F5 Vorschau, F6 Render)
// STL-Export: openscad -o case_unterteil.stl -D 'part="bottom"' case.scad
//             openscad -o case_deckel.stl    -D 'part="top"'    case.scad
// =============================================================

/* [Welches Teil rendern] */
part = "both";  // [both, bottom, top]

/* [Board-Maße — AUS KICAD EINTRAGEN] */
board_w = 100;          // <-- Board-Breite (X) in mm
board_d = 60;           // <-- Board-Tiefe  (Y) in mm
board_thickness = 1.6;  // Standard-PCB-Dicke

/* [MESSEN am realen Board] */
max_component_height = 15;   // <-- höchstes Bauteil über dem Board + Luft
clearance_below = 4;         // Platz unter dem Board für THT-Pins

/* [Gehäuse-Parameter] */
wall = 2.4;            // Wandstärke (robust für FDM-Druck)
clearance = 0.4;       // Spaltmaß ums Board (Toleranz)
standoff_h = clearance_below;
standoff_d = 7;
corner_radius = 3;

/* [Versteckt] */
$fn = 48;
eps = 0.01;

inner_w = board_w + 2*clearance;
inner_d = board_d + 2*clearance;
inner_h = standoff_h + board_thickness + max_component_height;
outer_w = inner_w + 2*wall;
outer_d = inner_d + 2*wall;
outer_h = inner_h + wall;

module rrect(w, d, h, r) {
    hull() for (x=[r, w-r], y=[r, d-r])
        translate([x, y, 0]) cylinder(r=r, h=h);
}

module bottom() {
    difference() {
        rrect(outer_w, outer_d, outer_h, corner_radius);
        translate([wall, wall, wall])
            rrect(inner_w, inner_d, outer_h, max(corner_radius-wall, 0.5));
    }
    // Eck-Standoffs (Board ruht oben drauf). Bei langem Board ggf. mittlere
    // Reihe ergänzen: x-Liste um inner_w/2 erweitern.
    inset = 8;
    for (x=[inset, inner_w-inset], y=[inset, inner_d-inset])
        translate([wall+x, wall+y, wall])
            cylinder(d=standoff_d, h=standoff_h);

    // TODO: Connector-Ausschnitte. Position aus KiCad ablesen (X/Y der
    // Stecker-Footprints) und im difference() oben Material entfernen, z.B.:
    //   translate([outer_w-wall-eps, 20, wall+standoff_h+board_thickness])
    //     cube([wall+2*eps, 15, 10]);
}

module top() {
    lip_h = 5;
    lip_clearance = 0.3;
    difference() {
        union() {
            rrect(outer_w, outer_d, wall, corner_radius);
            translate([wall+lip_clearance, wall+lip_clearance, -lip_h])
                difference() {
                    rrect(inner_w-2*lip_clearance, inner_d-2*lip_clearance, lip_h, 1);
                    translate([wall, wall, -eps])
                        rrect(inner_w-2*wall-2*lip_clearance, inner_d-2*wall-2*lip_clearance, lip_h+2*eps, 1);
                }
        }
        // TODO: Lüftung / Display-Ausschnitt / Beschriftung im Deckel?
    }
}

if (part == "bottom" || part == "both") bottom();
if (part == "top" || part == "both")
    translate([0, 0, (part=="both") ? outer_h + 15 : 0]) top();
