"""Migration is complete, tracked, relocatable, and electrically byte-preserving."""
import json
import hashlib
from unittest.mock import patch
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from migration_audit import SOURCE, BASE, audit, git, native_identity, renamed_native, source_inventory


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
        for p in (REPO/'production', ROOT/'production', REPO/'hardware', REPO/'tools', REPO/'tests', REPO/'docs'):
            self.assertFalse(p.exists(), str(p))

    def test_provenance_rejects_the_older_043_branch_base(self):
        self.assertEqual(git('rev-parse', BASE+'^{tree}'), git('rev-parse', '4c11418d26e5f70c0828252644b141c4627fe421^{tree}'))
        pcb = 'hardware/big_modular.kicad_pcb'
        self.assertNotEqual(git('show', 'b4d301d075f7556b6c06758ccbffcc1a2b1694fa:'+pcb), git('show', SOURCE+':'+pcb))
        record = json.loads((ROOT/'docs/migration-recovery-manifest.json').read_text())
        self.assertEqual(hashlib.sha256(git('show', SOURCE+':'+pcb)).hexdigest(), record['files'][pcb]['after_sha256'])


if __name__ == '__main__':
    unittest.main()
