"""Support-free OrcaSlicer regression for the desk screw mount; keeps G-code in ignored research/."""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SRC = HERE/'print'/'twin-screw-bridge'
WORK = HERE/'research'/'twin-screws'/'slicing'
BBL = Path(os.environ.get('ORCA_BBL_PROFILES','/opt/orcaslicer/resources/profiles/BBL'))


def profile(kind,name):
    data=json.loads((BBL/kind/(name+'.json')).read_text())
    parent=data.pop('inherits',None)
    return (profile(kind,parent) if parent else {}) | data


def main():
    WORK.mkdir(parents=True,exist_ok=True)
    for kind,name in [('machine','Bambu Lab P2S 0.4 nozzle'),('filament','Generic PLA @BBL P2S'),('process','0.20mm Standard @BBL P2S')]:
        settings=profile(kind,name)
        if kind=='process':
            settings.update(curr_bed_type='Textured PEI Plate',enable_support='0',brim_type='no_brim',wall_loops='5',sparse_infill_density='35%')
        (WORK/(kind+'.json')).write_text(json.dumps(settings))
    plates=[SRC/'01-thread-test.3mf',SRC/'02-common-parts.3mf',*sorted(SRC.glob('*mm/03-jaw-pair.3mf')),*sorted(SRC.glob('*mm/complete-mount.3mf'))]
    assert len(plates)==8
    data={}
    for f in plates:
        rel=f.relative_to(SRC); dest=WORK/rel.with_suffix(''); dest.mkdir(parents=True,exist_ok=True)
        with (dest/'slicer.log').open('w') as log:
            subprocess.run(['orcaslicer','--load-settings',f'{WORK}/machine.json;{WORK}/process.json','--load-filaments',str(WORK/'filament.json'),'--slice','0','--outputdir',str(dest),str(f)],stdout=log,stderr=log,cwd=dest,check=True)
        report=json.loads((dest/'result.json').read_text()); assert report['return_code']==0 and len(report['sliced_plates'])==1 and not report['sliced_plates'][0]['warning_message'],report
        g=(dest/'plate_1.gcode').read_text(errors='replace'); assert '; filament_type = PLA' in g and '; enable_support = 0' in g and report['wall_loops']==5 and report['sparse_infill_density']==35
        t=re.search(r'total estimated time: ([^\r\n]+)',g)[1]; m=float(re.search(r'; filament used \[g\] = ([0-9.]+)',g)[1]); data[str(rel)]={'time':t,'filament_g':m,'warnings':[],'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}; print(rel,t,m,flush=True)
    (SRC/'slices.json').write_text(json.dumps({'profile':'Bambu Lab P2S / 0.4 mm nozzle / Generic PLA / textured PEI / 0.20 mm layers / 5 walls / 35% infill / no supports or brim','plates':data},indent=2)+'\n')


if __name__=='__main__':
    main()
