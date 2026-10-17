#!/usr/bin/env python3
"""Copy this preserved checkpoint into a NEW project and restore pinned 3D resources.

Packaging only: no KiCad invocation, geometry editing, syncing, routing or checks.
The archived checkpoint is never modified. Missing/different resources fail closed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def relative_file(base, name):
    rel = Path(name)
    require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe manifest path: ' + name)
    return base / rel


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path, help='Exclusively NEW project under this repo modules/usb-power/research/')
    ap.add_argument('--model-root', type=Path, default=Path('/usr/share/kicad/3dmodels'), help='Installed KiCad 3D library root; every resource must match its recorded SHA-256')
    args = ap.parse_args()
    output = args.output.resolve()
    research = (ROOT / 'modules/usb-power/research').resolve()
    require(output.is_relative_to(research) and not output.is_relative_to(HERE)
            and output != research and not output.exists(), 'Output must be NEW, inside research, and outside the preserved checkpoint')
    deps = json.loads((HERE / 'DEPENDENCIES.json').read_text())
    manifest = json.loads((HERE / 'CHECKPOINT.json').read_text())
    copies = []
    for name in deps['project_files']:
        source = relative_file(HERE, name)
        expected = manifest['files'][name]['sha256']
        require(source.is_file() and digest(source) == expected, 'Checkpoint file missing/changed: ' + name)
        copies.append((source, relative_file(output, name), expected))
    for item in deps['external_models']:
        source = relative_file(args.model_root.resolve(), item['provider_relative_path'])
        require(source.is_file() and digest(source) == item['sha256'], 'Missing/different pinned model (do not drop it): ' + str(source))
        copies.append((source, relative_file(output, item['project_relative_path']), item['sha256']))
    output.mkdir(parents=True)
    for source, dest, expected in copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        require(digest(dest) == expected, 'Copy hash mismatch: ' + str(dest))
    receipt = {'status': 'UNFINISHED_NOT_FOR_FABRICATION', 'action': 'byte-identical packaging restoration only',
               'checkpoint_candidate_sha256': manifest['candidate_sha256'],
               'restored_candidate_sha256': digest(output / 'usb-power.kicad_pcb'),
               'copied_files': {str(d.relative_to(output)): h for _, d, h in copies},
               'engineering_checks_run': False}
    with (output / 'RESTORE.json').open('x') as f:
        json.dump(receipt, f, indent=2)
        f.write('\n')
    print(output / 'candidate-profile.json')
    print('Restored bytes only; prior DRC remains FAIL. No checks or routing performed.')


if __name__ == '__main__':
    main()
