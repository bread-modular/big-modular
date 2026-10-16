"""A4 native stack regressions. No routing, downloads or manufacturing exports."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from sexp import parse, nodes
from stack_geometry import geometry


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def usb_node(path):
    return next(f for f in nodes(parse(path.read_text()),'footprint')
                if any(p[1:3]==['Reference','J1'] for p in nodes(f,'property')))


class StackGeometryTests(unittest.TestCase):
    def test_single_led_revision_preserves_all_other_mechanics(self):
        record=json.loads((ROOT/'docs/mechanical-preservation.json').read_text())
        for name,digest in record.items():self.assertEqual(sha(ROOT/name),digest,name)
        from stack_geometry import physical_fingerprint
        original=json.loads((ROOT/'docs/mechanical-baseline.json').read_text())
        tree=parse((ROOT/'hardware/big_modular.kicad_pcb').read_text())
        for ref in ['J1','J7']:
            fp=next(f for f in nodes(tree,'footprint') if any(p[1:3]==['Reference',ref] for p in nodes(f,'property')))
            self.assertEqual(physical_fingerprint(fp),original['physical'][ref])

    def test_drawing_and_builder_share_current_geometry(self):
        self.assertEqual(json.loads((ROOT/'docs/assembly-geometry.json').read_text()),geometry())
        g=geometry()
        self.assertEqual(g['panel_bracket_holes_mm'],[[6.4,y,3.2] for y in [22,106.5]])
        self.assertEqual(g['carrier_Z_mm'],[2,32])
        self.assertEqual(g['carrier_X_mm'],[3.1,4.7])
        self.assertEqual(g['brackets']['quantity'],2)
        self.assertNotIn('middle_Z_mm',g)
        self.assertNotIn('headers',g)
        self.assertNotIn('spacers',g)
        self.assertIn('64 current',g['electrical_status'])

    def test_native_geometry_ui_power_pin_order_and_no_routing(self):
        # Separate process contains native KiCad's SWIG lifetimes and diagnostics.
        result=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'tools/verify_stack.py')],
                              capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['mechanics']['power_pin_checks'],16)
        self.assertEqual(report['mechanics']['actual_NPTH_geometry_checks'],10)
        self.assertFalse(report['fabrication_ready'])
        self.assertEqual(len(report['boards']),2)

    def test_new_candidate_regeneration_preserves_sources_and_matches_outputs(self):
        inputs=[p for p in (ROOT/'hardware').rglob('*') if p.is_file()]
        before={p:sha(p) for p in inputs}
        with tempfile.TemporaryDirectory(prefix='big modular stack ') as tmp:
            out=Path(tmp)/'candidate'
            cmd=['/usr/bin/python3','-B',str(ROOT/'tools/build_stack.py'),'--output',str(out)]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads((out/'assembly-geometry.json').read_text()),geometry())
            for name in ['big_modular','front_panel']:
                self.assertEqual((out/'hardware'/f'{name}.kicad_pcb').read_bytes(),
                                 (ROOT/'hardware'/f'{name}.kicad_pcb').read_bytes(),name)
            check=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'tools/verify_stack.py'),
                                  '--hardware',str(out/'hardware'),'--geometry',str(out/'assembly-geometry.json')],
                                 capture_output=True,text=True,timeout=60)
            self.assertEqual(check.returncode,0,check.stdout+check.stderr)
            again=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
            self.assertNotEqual(again.returncode,0)
        self.assertEqual({p:sha(p) for p in inputs},before)

    def test_legacy_full_builder_cannot_restore_the_deep_board(self):
        before={p:sha(p) for p in (ROOT/'hardware').rglob('*') if p.is_file()}
        result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/build_project.py')],
                              capture_output=True,text=True,timeout=30)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('legacy full regeneration is disabled',result.stderr)
        self.assertEqual({p:sha(p) for p in before},before)

    def test_ui_refs_are_integrated_and_board_synced(self):
        audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
        for ref in ['D10','R32','SW1','J7']:
            self.assertIn(ref,audit)
        self.assertNotIn('D11',audit);self.assertNotIn('D12',audit)
        board=(ROOT/'hardware/big_modular.kicad_pcb').read_text()
        self.assertNotIn('RESET_A_PENDING',board);self.assertIn('EF_SHDN',board)
        self.assertNotIn('RESET_B_PENDING',board);self.assertIn('RTN',board)
        self.assertFalse((ROOT/'hardware/middle_plate.kicad_pcb').exists())

    def test_top_cluster_and_magnetic_envelopes(self):
        from stack_geometry import verify_ui_clearances
        g=geometry(); gaps=verify_ui_clearances(g)
        self.assertEqual(g['mouth_axis_XYZ_mm'],[6.43,33.5,.8])
        self.assertEqual(g['reset_XY_diameter_mm'],[6.4,43,3.2])
        self.assertEqual(g['LEDs'][0]['panel_XY_diameter_mm'],[6.7,49.5,3.6])
        self.assertEqual(gaps['L1/L4_normal_budget_margin'],.85)
        self.assertEqual(gaps['L2/L3_normal_budget_margin'],.15)
        g['magnetics']['L1/L4']['height_max_mm']=6.5
        with self.assertRaises(AssertionError):verify_ui_clearances(g)

    def test_all_64_pcb_fields_paths_and_staging(self):
        import csv
        from sexp import one
        from schematic_connectivity import Connectivity
        tree=parse((ROOT/'hardware/big_modular.kicad_pcb').read_text())
        fps={next(p[2] for p in nodes(f,'property') if p[1]=='Reference'):f for f in nodes(tree,'footprint')}
        rows={r['Reference']:r for r in csv.DictReader((ROOT/'BOM.csv').read_text().splitlines())}
        self.assertEqual(set(fps)-{''},set(rows))
        self.assertEqual(len(rows),64)
        graph=Connectivity(ROOT/'hardware')
        for ref,row in rows.items():
            f=fps[ref];props={p[1]:p[2] for p in nodes(f,'property')}
            self.assertEqual(f[1],row['Footprint']);self.assertEqual(props['Value'],row['Value'])
            self.assertEqual(props.get('MPN',''),row['MPN']);self.assertEqual(props.get('LCSC',''),row['LCSC'])
            self.assertTrue(one(f,'path')[1].endswith('/'+one(graph.refs[ref][1],'uuid')[1]))
            if ref not in ['J1','J7','D10','SW1']:
                self.assertEqual(props['Placement'],'STAGED_OFF_BOARD_UNPLACED')
                self.assertGreater(float(one(f,'at')[1]),160)
        self.assertEqual(fps['R32'][1],'BigModular:R_0603_1608Metric')



if __name__=='__main__':unittest.main()
