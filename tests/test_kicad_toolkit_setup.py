"""Big Modular's local common-tool wiring; no network or hardware regeneration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "opt/kicad-tools/kicad_tools.py"
PROFILE = ROOT / "tools/kicad-project.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cli(*arguments, script=CLI):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON_COLORS="0")
    return subprocess.run(
        [sys.executable, "-B", str(script), *map(str, arguments)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=90,
    )


class KiCadToolkitSetupTests(unittest.TestCase):
    def test_imported_payload_matches_provenance_without_original_checkout(self):
        record = json.loads((ROOT / "opt/kicad-tools/import-manifest.json").read_text())
        self.assertEqual(record["schema_version"], 1)
        self.assertFalse(record["order_ready"])
        self.assertTrue(record["routing"]["included"])
        self.assertTrue(record["tracemaker"]["included"])
        self.assertFalse(record["tracemaker"]["runtime_included"])
        self.assertGreater(len(record["installed_files_sha256"]), 60)
        for name, expected in record["installed_files_sha256"].items():
            with self.subTest(path=name):
                relative = Path(name)
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                path = ROOT / relative
                self.assertFalse(path.is_symlink())
                self.assertTrue(path.is_file())
                self.assertEqual(digest(path), expected)

    def test_skill_discovery_and_legacy_alias_are_relative_local_links(self):
        record = json.loads((ROOT / "opt/kicad-tools/import-manifest.json").read_text())
        expected = {
            "opt/kicad-jlcpcb": "kicad-tools/jlcpcb",
            ".agents/skills/kicad-workflow": "../../opt/kicad-tools/skills/kicad-workflow",
            ".agents/skills/jlcpcb-assembly": "../../opt/kicad-tools/skills/jlcpcb-assembly",
        }
        self.assertEqual(set(record["symlinks"]), set(expected))
        for name, target in expected.items():
            with self.subTest(link=name):
                path = ROOT / name
                self.assertTrue(path.is_symlink())
                self.assertEqual(os.readlink(path), target)
                self.assertTrue(path.is_dir())
                path.resolve().relative_to(ROOT)
        for skill in ("kicad-workflow", "jlcpcb-assembly"):
            alias = ROOT / ".agents/skills" / skill / "SKILL.md"
            canonical = ROOT / "opt/kicad-tools/skills" / skill / "SKILL.md"
            self.assertEqual(alias.resolve(), canonical)
            self.assertEqual(digest(alias), digest(canonical))

    def test_project_profile_explicitly_selects_carrier_and_local_dependencies(self):
        data = json.loads(PROFILE.read_text())
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual((PROFILE.parent / data["project_dir"]).resolve(), ROOT / "hardware")
        self.assertEqual((PROFILE.parent / data["board"]).resolve(), ROOT / "hardware/big_modular.kicad_pcb")
        self.assertEqual((PROFILE.parent / data["root_schematic"]).resolve(), ROOT / "hardware/big_modular.kicad_sch")
        for name in data["dependencies"]:
            dependency = (PROFILE.parent / name).resolve()
            dependency.relative_to(ROOT)
            self.assertTrue(dependency.exists())

    def test_private_check_dry_run_is_no_write_and_resolves_full_source_selection(self):
        inputs = [p for p in (ROOT / "hardware").rglob("*") if p.is_file()]
        before = {p: digest(p) for p in inputs}
        with tempfile.TemporaryDirectory(prefix="big modular profile test ") as temp:
            output = Path(temp) / "new reports"
            result = run_cli("check", "--config", PROFILE, "--reports", output, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertTrue(report["dry_run"])
            self.assertFalse(report["source_writes"])
            self.assertFalse(report["order_ready"])
            self.assertEqual(Path(report["selection"]["board"]), ROOT / "hardware/big_modular.kicad_pcb")
            self.assertEqual(Path(report["selection"]["root_schematic"]), ROOT / "hardware/big_modular.kicad_sch")
            self.assertEqual(len(report["selection"]["sheet_files"]), 6)
            self.assertFalse(output.exists())
        self.assertEqual({p: digest(p) for p in inputs}, before)

    def test_canonical_and_legacy_cli_help_are_usable(self):
        commands = [
            (CLI, ("--help",)),
            (CLI, ("assembly", "audit", "--help")),
            (CLI, ("assembly", "suggest", "--help")),
            (CLI, ("export", "--help")),
            (CLI, ("pcb", "--help")),
            (CLI, ("schematic", "--help")),
            (CLI, ("route", "--help")),
            (CLI, ("tracemaker", "--help")),
            (ROOT / "opt/kicad-jlcpcb/assembly.py", ("--help",)),
        ]
        for script, arguments in commands:
            with self.subTest(script=str(script), arguments=arguments):
                result = run_cli(*arguments, script=script)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("usage:", result.stdout.lower())

    def test_design_inventory_is_not_silently_treated_as_assembly_bom(self):
        bom = ROOT / "BOM.csv"
        before = digest(bom)
        with tempfile.TemporaryDirectory(prefix="big modular audit test ") as temp:
            result = run_cli(
                "assembly", "audit", "--bom", bom, "--boards", "1",
                "--offline", "--cache-dir", temp,
            )
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("CSV", result.stdout + result.stderr)
            self.assertIn("unexpected kicad csv columns", (result.stdout + result.stderr).lower())
            self.assertEqual(list(Path(temp).iterdir()), [])
        self.assertEqual(digest(bom), before)


if __name__ == "__main__":
    unittest.main()
