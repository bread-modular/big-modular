"""Slice both current print files. Never write toolpaths into the print folder."""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from orca_profile import profile

HOLDER = Path(__file__).resolve().parents[1]


def slice_plate(plate):
    work = HOLDER/'research'/'slice'/plate.stem
    walls = 4
    work.mkdir(parents=True, exist_ok=True)
    for kind, name in [('machine', 'Bambu Lab P2S 0.4 nozzle'), ('filament', 'Generic PLA @BBL P2S'),
                       ('process', '0.20mm Standard @BBL P2S')]:
        data = profile(kind, name)
        if kind == 'process':
            data.update(curr_bed_type='Textured PEI Plate', enable_support='0', brim_type='no_brim',
                        wall_loops=str(walls), sparse_infill_density='25%')
        (work / f'{kind}.json').write_text(json.dumps(data))
    with (work / 'slice.log').open('w') as log:
        subprocess.run([os.environ.get('ORCASLICER', 'orcaslicer'), '--load-settings',
                        f'{work}/machine.json;{work}/process.json', '--load-filaments', str(work/'filament.json'),
                        '--slice', '0', '--outputdir', str(work), str(plate)],
                       stdout=log, stderr=log, check=True, cwd=work)
    result = json.loads((work / 'result.json').read_text())
    assert result['return_code'] == 0 and len(result['sliced_plates']) == 1, result
    assert result['wall_loops'] == walls and result['sparse_infill_density'] == 25, result
    warnings = result['sliced_plates'][0]['warning_message']
    assert not warnings, warnings
    gcode = (work / 'plate_1.gcode').read_text(errors='replace')
    assert all(k in gcode for k in ('; filament_type = PLA', '; enable_support = 0', '; brim_type = no_brim'))
    report = {'file': plate.name, 'profile': 'Bambu Lab P2S / 0.4 mm / Generic PLA / textured PEI / '
              f'0.20 mm / {walls} walls / 25% infill / no supports or brim',
              'time': re.search(r'total estimated time: ([^\r\n]+)', gcode)[1],
              'filament_g': float(re.search(r'; filament used \[g\] = ([0-9.]+)', gcode)[1]),
              'plate_warnings': warnings, 'sha256': hashlib.sha256(plate.read_bytes()).hexdigest()}
    return report


if __name__ == '__main__':
    for folder, name in [('print','hanger'), ('print/end-clips','print-this')]:
        plate = HOLDER/folder/(name+'.3mf')
        report = slice_plate(plate)
        (plate.parent/'slice.json').write_text(json.dumps(report, indent=2)+'\n')
        print(name, report['time'], report['filament_g'], flush=True)
