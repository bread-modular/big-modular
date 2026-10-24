"""Write the USB-AUDIO KiCad project files (hardware/usb-audio{,-mcu}.kicad_pro, panel .kicad_pro).

Run from modules/usb-audio:  python3 -B tools/build_project.py

Settings start from the accepted modules/32bit project (same KiCad 10 defaults, ERC/DRC
severities, Default + Power net classes) with this module's names, its rail net classes and the
repository's 1.0 mm copper-to-edge clearance (root AGENTS.md). Re-running overwrites them: once a
board is being routed by hand, edit its .kicad_pro in KiCad instead.
"""
import copy
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
TEMPLATE = MODULE.parents[0] / '32bit/hardware/32bit.kicad_pro'
PANEL_TEMPLATE = MODULE.parents[0] / '32bit/panels/front-pcb/32bit-panel.kicad_pro'

RAILS = {'usb-audio': ['GND', '+3V3', '+3V3_C', '+5VA', '+12V', '-12V', '+12V_F', '-12V_F'],
         'usb-audio-mcu': ['GND', '+3V3', 'VBUS']}


def project(name, rails):
    d = json.loads(TEMPLATE.read_text())
    d['meta']['filename'] = f'{name}.kicad_pro'
    d['board']['design_settings']['rules']['min_copper_edge_clearance'] = 1.0
    d['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': r} for r in rails]
    if name.endswith('-mcu'):
        usb = copy.deepcopy(next(c for c in d['net_settings']['classes'] if c['name'] == 'Default'))
        usb.update(name='USB_HS', priority=1, diff_pair_width=0.2, diff_pair_gap=0.2, track_width=0.2)
        d['net_settings']['classes'].append(usb)
        d['net_settings']['netclass_patterns'] += [{'netclass': 'USB_HS', 'pattern': p}
                                                   for p in ('/USB_DP', '/USB_DM')]
    d['schematic']['top_level_sheets'] = [dict(d['schematic']['top_level_sheets'][0],
                                               filename=f'{name}.kicad_sch', name=name)]
    return d


def main():
    hw = MODULE / 'hardware'
    for name, rails in RAILS.items():
        d = project(name, rails)
        sheet = d['schematic']['top_level_sheets'][0]
        # the root sheet UUID must match the generated schematic
        sch = (hw / f'{name}.kicad_sch').read_text()
        sheet['uuid'] = sch.split('(uuid "', 1)[1].split('"', 1)[0]
        (hw / f'{name}.kicad_pro').write_text(json.dumps(d, indent=2) + '\n')
    p = json.loads(PANEL_TEMPLATE.read_text())
    p['meta']['filename'] = 'usb-audio-panel.kicad_pro'
    (MODULE / 'panels/front-pcb/usb-audio-panel.kicad_pro').write_text(json.dumps(p, indent=2) + '\n')
    print('project files written')


if __name__ == '__main__':
    main()
