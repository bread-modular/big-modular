"""Resolve inherited OrcaSlicer Bambu Lab CLI profiles for mechanical builds."""
import json
import os
from pathlib import Path

# Default: the BBL profiles of the OS package (/opt/orca-slicer-<version>/, newest); ORCA_BBL_PROFILES overrides.
_OS = sorted(Path('/opt').glob('orca-slicer-*/resources/profiles/BBL'))
BBL = Path(os.environ.get('ORCA_BBL_PROFILES') or (_OS[-1] if _OS else '/opt/orca-slicer/resources/profiles/BBL'))


def profile(kind,name):
    path=BBL/kind/(name+'.json')
    if not path.is_file():
        # OrcaSlicer 2.5 ships its system profiles packed (resources/profiles/BBL.opc), not as JSON files.
        raise SystemExit(f'{path} not found: set ORCA_BBL_PROFILES to an unpacked OrcaSlicer BBL profile '
                         'folder (2.4.x layout: machine/, process/, filament/ JSON files)')
    data=json.loads(path.read_text())
    parent=data.pop('inherits',None)
    return (profile(kind,parent) if parent else {}) | data
