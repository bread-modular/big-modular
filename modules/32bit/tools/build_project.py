"""Write the 32bit S4 KiCad project files (hardware/32bit{,-mcu}.kicad_pro, panel .kicad_pro).

Run from modules/32bit:  python3 -B tools/build_project.py

Settings start from the accepted modules/32bit project (same KiCad 10 defaults, ERC/DRC
severities, Default + Power net classes) with this module's names, its rail net classes and the
repository's 1.0 mm copper-to-edge clearance (root AGENTS.md). Re-running overwrites them: once a
board is being routed by hand, edit its .kicad_pro in KiCad instead.
"""
import copy
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
TEMPLATE = MODULE.parents[0] / 'usb-audio/hardware/usb-audio-mcu.kicad_pro'
PANEL_TEMPLATE = MODULE.parents[0] / 'usb-audio/panels/front-pcb/usb-audio-panel.kicad_pro'

RAILS = {'32bit-mcu': ['GND', '+3V3', 'VBUS', 'VDD_SPI']}


def project(name, rails):
    d = json.loads(TEMPLATE.read_text())
    d['meta']['filename'] = f'{name}.kicad_pro'
    d['board']['design_settings']['rules']['min_copper_edge_clearance'] = 1.0
    # ESP32-S3 QFN-56 land: nine 0.2 mm thermal vias in the exposed pad (as modules/32bit S3)
    d['board']['design_settings']['rules']['min_through_hole_diameter'] = 0.2
    # the usb-audio MCU board template already carries the Default / Power / USB_HS classes
    d['net_settings']['netclass_patterns'] = [p for p in d['net_settings']['netclass_patterns']
                                              if p['netclass'] == 'USB_HS']
    d['net_settings']['netclass_patterns'] += [{'netclass': 'Power', 'pattern': r} for r in rails]
    d['schematic']['top_level_sheets'] = [dict(d['schematic']['top_level_sheets'][0],
                                               filename=f'{name}.kicad_sch', name=name)]
    return d


def main():
    """The carrier project (hardware/32bit.kicad_pro) is the routed modules/usb-audio S5 carrier's, copied
    with the board (tools/carrier_from_usb_audio.py); only the MCU board and the panel are written here."""
    hw = MODULE / 'hardware'
    for name, rails in RAILS.items():
        d = project(name, rails)
        sheet = d['schematic']['top_level_sheets'][0]
        # the root sheet UUID must match the generated schematic
        sch = (hw / f'{name}.kicad_sch').read_text()
        sheet['uuid'] = sch.split('(uuid "', 1)[1].split('"', 1)[0]
        (hw / f'{name}.kicad_pro').write_text(json.dumps(d, indent=2) + '\n')
    p = json.loads(PANEL_TEMPLATE.read_text())
    p['meta']['filename'] = '32bit-panel.kicad_pro'
    (MODULE / 'panels/front-pcb/32bit-panel.kicad_pro').write_text(json.dumps(p, indent=2) + '\n')
    print('project files written')


if __name__ == '__main__':
    main()
