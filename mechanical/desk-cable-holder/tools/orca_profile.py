"""Resolve inherited OrcaSlicer Bambu Lab CLI profiles for mechanical builds."""
import json
import os
from pathlib import Path

BBL = Path(os.environ.get('ORCA_BBL_PROFILES','/opt/orcaslicer/resources/profiles/BBL'))


def profile(kind,name):
    data=json.loads((BBL/kind/(name+'.json')).read_text())
    parent=data.pop('inherits',None)
    return (profile(kind,parent) if parent else {}) | data
