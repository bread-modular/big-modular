"""Migration is complete, tracked, relocatable, and electrically byte-preserving."""
import json
import hashlib
from unittest.mock import patch
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from migration_audit import SOURCE, BASE, audit, check_legacy_root_paths, git, native_identity, renamed_native, source_inventory


class MigrationRecoveryTests(unittest.TestCase):
    def test_every_original_tracked_file_has_a_verified_disposition(self):
        # Normal CI must not invoke one-time delivery/current-circuit hash gates.
        with patch('migration_audit.audit_frozen_recovery', side_effect=AssertionError('one-time gate invoked')), patch('migration_audit.native_identity', side_effect=AssertionError('current circuit frozen')):
            result = audit()
        self.assertEqual(result['status'], 'pass')
        self.assertFalse(result['current_circuit_hashes_enforced'])
        self.assertTrue(result['tracked_completeness_checked'])
        self.assertEqual(result['original_tracked_files_accounted_for'], len(source_inventory()))
        self.assertEqual(result['frozen_native_records_verified'], 38)

    def test_essential_native_tool_test_doc_and_shipping_files_are_tracked(self):
        required = [
            'AGENTS.md', 'Code.md', 'README.md', 'BOM.csv',
            'hardware/usb-power.kicad_pro', 'hardware/usb-power.kicad_sch',
            'hardware/usb-power.kicad_pcb', 'hardware/usb-power-panel.kicad_pro',
            'hardware/usb-power-panel.kicad_pcb', 'hardware/fp-lib-table', 'hardware/sym-lib-table',
            'hardware/BigModular.kicad_sym', 'hardware/05_quiet_rails.kicad_sch',
            'tools/kicad-project.json', 'tools/release_hro.py', 'tools/migration_audit.py',
            'tests/test_electrical_design.py', 'tests/test_hro_fabrication.py',
            'tests/test_migration_recovery.py', 'docs/ldo-revision.md', 'docs/mechanics.md',
            'docs/routed-baseline.json', 'docs/pin-net-audit.json', 'docs/schematic.pdf',
            'docs/migration-recovery.md', 'docs/migration-recovery-manifest.json',
            'jlcpcb/README.md', 'jlcpcb/manifest.json', 'jlcpcb/release-validation.json',
            'jlcpcb/assembly/bom.csv', 'jlcpcb/assembly/positions.csv',
        ]
        tracked = set(git('ls-files', '-z').decode().split('\0'))
        for name in required:
            with self.subTest(path=name):
                self.assertTrue((ROOT/name).is_file())
                self.assertIn('modules/usb-power/'+name, tracked)
        self.assertGreaterEqual(len(list((ROOT/'hardware').glob('*.kicad_sch'))), 7)
        self.assertGreaterEqual(len(list((ROOT/'hardware/BigModular.pretty').glob('*.kicad_mod'))), 22)

    def test_frozen_native_receipt_proves_identity_without_pinning_future_circuits(self):
        inventory = source_inventory()
        record = json.loads((ROOT/'docs/migration-recovery-manifest.json').read_text())
        for name, item in inventory.items():
            if not name.startswith('hardware/'):
                continue
            before = git('cat-file', 'blob', item['blob'])
            # Validate the frozen receipt, NOT current authorized engineering bytes.
            delivered = renamed_native(name, before)
            result = native_identity(name, before, delivered)
            self.assertEqual(result['after_sha256'], record['files'][name]['after_sha256'])
            if name.endswith('.kicad_pcb'):
                self.assertTrue(result['exact_bytes'])

    def test_circuit_value_wire_route_and_rule_mutations_fail_closed(self):
        inventory = source_inventory()
        for name, old, new in [
            ('hardware/03_bucks.kicad_sch', b'22u', b'47u'),
            ('hardware/03_bucks.kicad_sch', b'(wire', b'(text'),
            ('hardware/big_modular.kicad_pcb', b'(segment', b'(arc'),
            ('hardware/big_modular.kicad_pro', b'"min_track_width": 0.2', b'"min_track_width": 0.1'),
        ]:
            before = git('cat-file', 'blob', inventory[name]['blob'])
            after = renamed_native(name, before)
            self.assertIn(old, after)
            self.assertTrue(native_identity(name, before, after)['equal_modulo_project_identity'])
            with self.subTest(path=name), self.assertRaises(AssertionError):
                native_identity(name, before, after.replace(old, new, 1))

    def test_profile_and_library_paths_resolve_with_root_shared_tools(self):
        profile = ROOT/'tools/kicad-project.json'
        data = json.loads(profile.read_text())
        for key in ('project_dir', 'board', 'root_schematic'):
            p = (profile.parent/data[key]).resolve()
            p.relative_to(ROOT)
            self.assertTrue(p.exists(), key)
        for name in data['dependencies']:
            self.assertTrue((profile.parent/name).exists())
        for name in ('fp-lib-table', 'sym-lib-table'):
            text = (ROOT/'hardware'/name).read_text()
            for uri in re.findall(r'\(uri "([^"]+)"\)', text):
                self.assertTrue((ROOT/'hardware'/uri.replace('${KIPRJMOD}/', '')).exists())
        self.assertTrue((REPO/'opt/kicad-tools/kicad_tools.py').is_file())
        self.assertFalse((ROOT/'opt').exists())

    def test_active_readme_links_are_valid(self):
        for p in (REPO/'README.md', ROOT/'README.md', ROOT/'jlcpcb/README.md'):
            for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', p.read_text()):
                if '://' in target or target.startswith('#'):
                    continue
                with self.subTest(document=str(p), target=target):
                    self.assertTrue((p.parent/target.split('#')[0]).exists())

    def test_frozen_export_receipt_does_not_claim_new_exports(self):
        # Historical recovery proof stays frozen; a future approved export may
        # legitimately replace current shipping files and their live status.
        report = json.loads((ROOT/'docs/migration-verification.json').read_text())
        self.assertFalse(report['fabrication_exports_regenerated'])
        record = json.loads((ROOT/'docs/migration-recovery-manifest.json').read_text())
        exports = [v for k, v in record['files'].items() if k.startswith('production/ldo-r1/')]
        self.assertEqual(len(exports), 75)
        for entry in exports:
            self.assertEqual(entry['before_sha256'], entry['after_sha256'])
        check_legacy_root_paths()
        self.assertFalse((ROOT/'production').exists())

    def test_provenance_rejects_the_older_043_branch_base(self):
        self.assertEqual(git('rev-parse', BASE+'^{tree}'), git('rev-parse', '4c11418d26e5f70c0828252644b141c4627fe421^{tree}'))
        pcb = 'hardware/big_modular.kicad_pcb'
        self.assertNotEqual(git('show', 'b4d301d075f7556b6c06758ccbffcc1a2b1694fa:'+pcb), git('show', SOURCE+':'+pcb))
        record = json.loads((ROOT/'docs/migration-recovery-manifest.json').read_text())
        self.assertEqual(hashlib.sha256(git('show', SOURCE+':'+pcb)).hexdigest(), record['files'][pcb]['after_sha256'])


class LegacyRootArtifactsTests(unittest.TestCase):
    """Real Git ignore/index checks in disposable, relocated synthetic projects."""

    IGNORES = '.history/\n*.kicad_prl\n__pycache__/\n*.pyc\n'
    CACHES = (
        'hardware/.history/big_modular_20261017.kicad_pcb',
        'hardware/big_modular.kicad_prl',
        'hardware/front_panel.kicad_prl',
        'tools/__pycache__/release_hro.cpython-313.pyc',
    )

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='migration-local-artifacts-')
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.repo = self.temp/'relocated project with spaces'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '--quiet'], cwd=self.repo, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Host-global excludes must not change these synthetic ignore fixtures.
        subprocess.run(['git', 'config', 'core.excludesFile', str(self.repo/'.git/info/exclude')],
                       cwd=self.repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.write('.gitignore', self.IGNORES)

    def write(self, name, content='local user data\n'):
        path = self.repo/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_ignored_legacy_caches_are_allowed_without_changes(self):
        before = {name: self.write(name).read_bytes() for name in self.CACHES}
        check_legacy_root_paths(self.repo)
        # Exercise the ordinary audit's actual root-check call, without creating
        # any legacy artifacts in this workspace or accessing a project base.
        with patch('migration_audit.check_legacy_root_paths',
                   side_effect=lambda: check_legacy_root_paths(self.repo)) as check:
            self.assertEqual(audit()['status'], 'pass')
        check.assert_called_once_with()
        self.assertEqual(before, {name: (self.repo/name).read_bytes() for name in before})

    def test_cache_names_without_git_ignore_are_rejected(self):
        self.write('.gitignore', '')
        for name in self.CACHES:
            self.write(name)
        with self.assertRaises(AssertionError) as error:
            check_legacy_root_paths(self.repo)
        for name in self.CACHES:
            self.assertIn(name + ': non-ignored', str(error.exception))

    def test_git_ignore_negation_rejects_the_unignored_cache(self):
        self.write('.gitignore', self.IGNORES + '!hardware/big_modular.kicad_prl\n')
        for name in self.CACHES:
            self.write(name)
        with self.assertRaises(AssertionError) as error:
            check_legacy_root_paths(self.repo)
        self.assertIn('hardware/big_modular.kicad_prl: non-ignored', str(error.exception))
        self.assertNotIn('hardware/front_panel.kicad_prl', str(error.exception))

    def test_real_legacy_files_are_rejected_even_with_blanket_ignores(self):
        self.write('.gitignore', self.IGNORES +
                   'hardware/\ntools/\ntests/\ndocs/\nproduction/\nBOM.csv\n')
        for name in (
            'hardware/big_modular.kicad_pcb', 'hardware/usb-power.kicad_sch',
            'tools/release_hro.py', 'tools/__pycache__/real_source.py',
            'tests/test_source.py', 'docs/design.md',
            'production/ldo-r1/carrier.zip', 'BOM.csv',
        ):
            with self.subTest(path=name):
                path = self.write(name)
                with self.assertRaises(AssertionError) as error:
                    check_legacy_root_paths(self.repo)
                self.assertIn(name + ': ignored, but not an allowed', str(error.exception))
                self.assertEqual(path.read_text(), 'local user data\n')

    def test_non_ignored_unknown_user_files_have_a_useful_read_only_diagnostic(self):
        name = 'hardware/personal notes.txt'
        path = self.write(name)
        with self.assertRaises(AssertionError) as error:
            check_legacy_root_paths(self.repo)
        self.assertIn(name + ': non-ignored legacy/unknown file', str(error.exception))
        self.assertIn('modules/usb-power/', str(error.exception))
        self.assertIn('No files were changed', str(error.exception))
        self.assertEqual(path.read_text(), 'local user data\n')

    def test_tracked_legacy_source_and_force_tracked_cache_are_rejected(self):
        for name in ('hardware/big_modular.kicad_pcb', 'hardware/big_modular.kicad_prl'):
            with self.subTest(path=name):
                self.write(name)
                # Staging happens only in this synthetic repository, never here.
                subprocess.run(['git', 'add', '--force', '--', name], cwd=self.repo,
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with self.assertRaises(AssertionError) as error:
                    check_legacy_root_paths(self.repo)
                self.assertIn('Tracked legacy root paths are forbidden', str(error.exception))
                self.assertIn(name, str(error.exception))

    def test_legacy_directory_symlink_is_rejected_without_scanning_its_target(self):
        outside = self.temp/'outside simulated project'
        outside.mkdir()
        (outside/'private.txt').write_text('must not be scanned\n')
        (self.repo/'hardware').symlink_to(outside, target_is_directory=True)
        with patch.object(Path, 'iterdir', side_effect=AssertionError('outside scan')):
            with self.assertRaisesRegex(AssertionError, 'hardware: legacy-root symlink'):
                check_legacy_root_paths(self.repo)

    def test_ignored_history_symlink_is_not_an_allowed_cache(self):
        history = self.repo/'hardware/.history'
        history.mkdir(parents=True)
        (history/'broken-link').symlink_to(self.temp/'absent target')
        with self.assertRaisesRegex(AssertionError, 'hardware/.history/broken-link: legacy-root symlink'):
            check_legacy_root_paths(self.repo)


if __name__ == '__main__':
    unittest.main()
