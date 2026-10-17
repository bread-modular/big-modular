#!/usr/bin/env python3
"""Read-only, Git-object-backed completeness and no-circuit-change recovery audit.

The two source commits are deliberately pinned. No checkout, regeneration, native
save, source write, Git staging, network access or other workspace access occurs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOURCE = '8f3c5000b88a09a22e3b49ce209ca87bbc9aeefe'
BASE = 'e4524354cf803d41dba03c64e6bdb860b69d9b0a'
MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
PREFIX = 'modules/usb-power/'
LEGACY_ROOT_PATHS = ('hardware', 'tools', 'tests', 'docs', 'production', 'BOM.csv')


def check_legacy_root_paths(repo=None):
    """Reject old project files, not narrow, Git-ignored local history/cache.

    Inspect only the supplied project root (the script's repository by default),
    never the Git common directory/project base or the targets of symlinks.
    """
    repo = Path(repo) if repo is not None else REPO
    tracked = subprocess.check_output(
        ['git', 'ls-files', '-z', '--', *LEGACY_ROOT_PATHS], cwd=repo,
    ).decode().strip('\0')
    assert not tracked, 'Tracked legacy root paths are forbidden: ' + ', '.join(tracked.split('\0'))

    files, problems = [], []

    def visit(path):
        name = path.relative_to(repo).as_posix()
        if path.is_symlink():
            problems.append(f'{name}: legacy-root symlink (not followed)')
        elif path.is_dir():
            for child in sorted(path.iterdir()):
                visit(child)
        elif path.exists():
            files.append(name)

    for name in LEGACY_ROOT_PATHS:
        visit(repo/name)
    ignored = set()
    if files:
        result = subprocess.run(
            ['git', 'check-ignore', '--no-index', '-z', '--stdin'], cwd=repo,
            input=('\0'.join(files) + '\0').encode(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(result.returncode, result.args,
                                                output=result.stdout, stderr=result.stderr)
        ignored = set(result.stdout.decode().split('\0'))
    for name in files:
        parts = Path(name).parts
        local_artifact = (
            (parts[0] == 'hardware' and len(parts) > 2 and parts[1] == '.history')
            or (parts[0] == 'hardware' and len(parts) == 2 and name.endswith('.kicad_prl'))
            or (parts[0] == 'tools' and len(parts) == 3 and parts[1] == '__pycache__'
                and name.endswith('.pyc'))
        )
        if name not in ignored:
            problems.append(f'{name}: non-ignored legacy/unknown file')
        elif not local_artifact:
            problems.append(f'{name}: ignored, but not an allowed local history/cache artifact')
    assert not problems, (
        'Legacy root files rejected:\n' + '\n'.join(problems)
        + '\nCanonical design/tool/release files belong under ' + PREFIX
        + '; inspect unknown files manually. No files were changed.'
    )


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_bytes(path):
    return os.readlink(path).encode() if path.is_symlink() else path.read_bytes()


def source_inventory():
    result = {}
    for raw in git('ls-tree', '-rz', SOURCE).split(b'\0'):
        if not raw:
            continue
        meta, path = raw.split(b'\t')
        mode, kind, oid = meta.decode().split()
        assert kind == 'blob', (kind, path)
        result[path.decode()] = {'mode': mode, 'blob': oid}
    return result


def destination(path):
    if path.startswith('production/ldo-r1/'):
        return PREFIX + 'jlcpcb/' + path[len('production/ldo-r1/'):]
    if path.startswith('production/'):
        return None  # Retired releases/integration backups remain in Git, not an active archive.
    if path in ('AGENTS.md', 'Code.md', 'README.md', 'BOM.csv') or path.startswith(('hardware/', 'docs/', 'tools/', 'tests/')):
        return PREFIX + path.replace('big_modular.kicad_', 'usb-power.kicad_').replace('front_panel.kicad_', 'usb-power-panel.kicad_')
    return path  # Shared tools, discovery links, LICENSE and .gitignore stay at root.


def renamed_native(path, data):
    if path.endswith('.kicad_sch'):
        return data.replace(b'(project "big_modular"', b'(project "usb-power"')
    if path.endswith('.kicad_pro'):
        return data.replace(b'big_modular', b'usb-power').replace(b'front_panel', b'usb-power-panel')
    return data


def native_identity(path, before, after):
    """Exact bytes modulo ONLY the enumerated filename/project-identity tokens."""
    assert after == renamed_native(path, before), ('unauthorized native delta', path)
    if path.endswith('.kicad_pro'):
        restored = after.replace(b'usb-power-panel', b'front_panel').replace(b'usb-power', b'big_modular')
        assert json.loads(restored) == json.loads(before), ('project rules changed', path)
    elif path.endswith('.kicad_sch'):
        restored = after.replace(b'(project "usb-power"', b'(project "big_modular"')
        assert restored == before, ('schematic presentation/circuit changed', path)
    return {'before_sha256': sha(before), 'after_sha256': sha(after),
            'exact_bytes': before == after, 'equal_modulo_project_identity': True}


def audit_frozen_recovery(record=None, require_tracked=True):
    record = record or json.loads((MODULE/'docs/migration-recovery-manifest.json').read_text())
    assert record['source_commit'] == SOURCE and record['workspace_base'] == BASE
    inventory = source_inventory()
    assert set(record['files']) == set(inventory), 'Incomplete original tracked-file inventory'
    index = {}
    for raw in git('ls-files', '--stage', '-z').split(b'\0'):
        if not raw:
            continue
        meta, name = raw.split(b'\t')
        mode, oid, stage = meta.decode().split()
        assert stage == '0', ('unmerged index entry', name)
        index[name.decode()] = (mode, oid)
    tracked = set(index)

    def check_tracked(name):
        assert name in tracked, ('untracked recovery', name)
        p = REPO/name
        data = file_bytes(p)
        oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        mode = '120000' if p.is_symlink() else ('100755' if p.stat().st_mode & 0o111 else '100644')
        assert index[name] == (mode, oid), ('index/worktree recovery mismatch', name)

    native = {}
    recovered = retired = unchanged = 0
    for old, info in inventory.items():
        entry = record['files'][old]
        assert entry['source_blob'] == info['blob'] and entry['source_mode'] == info['mode'], old
        before = git('cat-file', 'blob', info['blob'])
        assert sha(before) == entry['before_sha256'], old
        target = destination(old)
        assert entry['destination'] == target, ('wrong destination', old)
        if target is None:
            assert entry['disposition'] == 'retired-git-only', old
            assert not (REPO/old).exists(), ('active retired archive', old)
            retired += 1
            continue
        p = REPO/target
        assert p.is_file() or p.is_symlink(), ('missing recovered file', target)
        after = file_bytes(p)
        assert sha(after) == entry['after_sha256'], ('changed recovered file', target)
        if require_tracked:
            check_tracked(target)
        if info['mode'] == '120000':
            assert p.is_symlink(), ('symlink replaced by file', target)
        else:
            assert not p.is_symlink(), ('file replaced by symlink', target)
            assert (int(info['mode'], 8) & 0o111) == (p.stat().st_mode & 0o111), ('file mode changed', target)
        if old.startswith('hardware/'):
            native[old] = native_identity(old, before, after)
        elif old == 'BOM.csv' or old.startswith(('production/ldo-r1/', 'opt/', '.agents/')) or old == 'LICENSE':
            assert before == after, ('immutable asset changed', target)
        elif before != after:
            allowed = (old in ('AGENTS.md', 'Code.md', 'README.md', '.gitignore')
                       or old.startswith(('tools/', 'tests/'))
                       or (old.startswith('docs/') and old.endswith('.md'))
                       or old in ('docs/mechanical-preservation.json', 'docs/ldo-evidence/preserved-hashes.json'))
            assert allowed, ('unapproved evidence change', old)
        unchanged += before == after
        recovered += target.startswith(PREFIX)
    for name in record['required_module_files']:
        assert name.startswith(PREFIX) and '..' not in Path(name).parts, name
        assert (REPO/name).is_file(), ('missing required file', name)
        if require_tracked:
            check_tracked(name)
    extras = git('ls-files', '--others', '--exclude-standard', '-z', '--', PREFIX).decode().split('\0')
    if require_tracked:
        assert not any(extras), ('untracked module files', extras)
        assert set(record['required_module_files']) == {p for p in tracked if p.startswith(PREFIX)}, 'Tracked module inventory differs from recovery ledger'
        assert not any(p.startswith(('hardware/', 'tools/', 'tests/', 'docs/', 'production/')) or p == 'BOM.csv' for p in tracked), 'Legacy project paths still tracked at root'
    check_legacy_root_paths()
    assert not (MODULE/'opt').exists() and not (MODULE/'production').exists()
    return {'status': 'pass', 'mode': 'one-time-frozen-recovery-acceptance',
            'current_circuit_hashes_enforced': True, 'source_commit': SOURCE, 'workspace_base': BASE,
            'original_tracked_files_accounted_for': len(inventory),
            'recovered_module_files_from_source': recovered, 'retired_git_only_files': retired,
            'byte_identical_files': unchanged, 'native_files_compared': len(native),
            'native_identity': native, 'tracked_completeness_checked': require_tracked,
            'required_module_files': len(record['required_module_files'])}


def audit(record=None, require_tracked=True):
    """Ongoing layout/provenance regression, NOT a frozen-current-circuit gate.

    Current hardware/tool/BOM contents may intentionally evolve. Verify the frozen
    recovery receipt against its original Git objects, and current required paths,
    without applying historical content hashes to today's engineering sources.
    """
    record = record or json.loads((MODULE/'docs/migration-recovery-manifest.json').read_text())
    assert record['source_commit'] == SOURCE and record['workspace_base'] == BASE
    inventory = source_inventory()
    assert set(record['files']) == set(inventory), 'Incomplete original recovery receipt'
    tracked = set(git('ls-files', '-z').decode().split('\0'))
    native_records = recovered = retired = 0
    for old, info in inventory.items():
        entry = record['files'][old]
        assert entry['source_blob'] == info['blob'] and entry['source_mode'] == info['mode'], old
        before = git('cat-file', 'blob', info['blob'])
        assert entry['before_sha256'] == sha(before), ('corrupt recovery provenance', old)
        target = destination(old)
        assert entry['destination'] == target, ('corrupt recovery destination', old)
        if target is None:
            assert entry['disposition'] == 'retired-git-only', old
            retired += 1
            continue
        assert (REPO/target).is_file() or (REPO/target).is_symlink(), ('missing migrated path', target)
        if require_tracked:
            assert target in tracked, ('untracked migrated path', target)
        if old.startswith('hardware/'):
            assert entry['after_sha256'] == sha(renamed_native(old, before)), ('corrupt frozen native receipt', old)
            native_records += 1
        elif old == 'BOM.csv' or old.startswith(('production/ldo-r1/', 'opt/', '.agents/')) or old == 'LICENSE':
            assert entry['after_sha256'] == entry['before_sha256'], ('corrupt immutable recovery receipt', old)
        recovered += target.startswith(PREFIX)
    for name in record['required_module_files']:
        assert name.startswith(PREFIX) and '..' not in Path(name).parts, name
        assert (REPO/name).is_file(), ('missing recovery evidence/path', name)
        if require_tracked:
            assert name in tracked, ('untracked recovery evidence/path', name)
    check_legacy_root_paths()
    assert not (MODULE/'opt').exists() and not (MODULE/'production').exists()
    verification = json.loads((MODULE/'docs/migration-verification.json').read_text())
    for name, digest in verification['evidence_sha256'].items():
        assert sha((MODULE/'docs/migration-evidence'/name).read_bytes()) == digest, ('frozen evidence changed', name)
    return {'status': 'pass', 'mode': 'ongoing-layout-and-frozen-provenance-only',
            'current_circuit_hashes_enforced': False, 'source_commit': SOURCE,
            'original_tracked_files_accounted_for': len(inventory),
            'recovered_module_files_from_source': recovered, 'retired_git_only_files': retired,
            'frozen_native_records_verified': native_records,
            'tracked_completeness_checked': require_tracked,
            'required_module_files': len(record['required_module_files'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-recovery', action='store_true',
                        help='One-time recovery acceptance ONLY: exact delivery/index hashes; expected to fail after authorized engineering changes. Not an ongoing circuit gate.')
    args = parser.parse_args()
    result = audit_frozen_recovery() if args.frozen_recovery else audit()
    print(json.dumps(result, indent=2, sort_keys=True))
