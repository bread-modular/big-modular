"""Fabrication acceptance, mutation guards and actual-CAM library adapter tests."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from hro_fit import verify,corner_margin
from stack_geometry import geometry
from fabrication_contract import validate_stack,via_audit
from routed_checks import routing_contract
from sexp import parse


class FabricationTests(unittest.TestCase):
    def test_complete_tolerance_budget_and_negative_old_aperture(self):
        r=verify(geometry())
        self.assertAlmostEqual(r['minimum_rounded_aperture_corner_margin_mm'],.2334584692,places=8)
        self.assertLess(corner_margin([4.23,28.6,4.2,9.8,.6],[4.28,8.53,28.719,38.281]),-.38)
        for key,value in [('finished_board_thickness_mm',[1.5,1.7]),('aperture_each_wall_error_mm',0),('aperture_centre_registration_each_axis_mm',0)]:
            g=geometry();g['USB_fit_acceptance'][key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):verify(g)

    def test_native_stack_matches_explicit_fabrication_contract(self):
        validate_stack(ROOT/'hardware/big_modular.kicad_pcb')
        validate_stack(ROOT/'hardware/front_panel.kicad_pcb',False)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.kicad_pcb'
            p.write_text((ROOT/'hardware/big_modular.kicad_pcb').read_text().replace('(copper_finish "ENIG")','(copper_finish "None")'))
            with self.assertRaises(AssertionError):validate_stack(p)

    def test_frozen_024_routing_and_all_pad_pose_nets_remain_exact(self):
        r=routing_contract(parse((ROOT/'hardware/big_modular.kicad_pcb').read_text()))
        self.assertEqual(r['tracks_and_vias'],'e82f731cd8abc0346527a49f9b6100125f6a2d2a81d4673149e2b1d943b9d54c')
        self.assertEqual(r['footprints_pin_net_pose'],'ffc28866536f3205db5cec3ce484f12aa6468bf9c47239dd8b0d3006cb899e51')
        self.assertEqual(r['zones'],'be65ab74cc2a816747efb96e2157b47a7b7481a1c52eee616596823b5846e672')
        self.assertEqual(r['outline'],'3571138d472efaf95ccc5d0b96b5f57a3a2b1134993baae5140638b534c4a1c8')

    def test_native_via_disks_not_annular_rings_or_centres(self):
        r=via_audit(ROOT/'hardware/big_modular.kicad_pcb')
        self.assertEqual((r['via_count'],r['barrels_over_exposed_SMD_copper'],r['barrels_over_paste'],r['barrels_at_SMD_boundary_only']),(133,35,35,7))
        # U2 EP end vias are outside its separate central mask window; do not
        # assume every thermal-pad via intersects EXPOSED copper or paste.
        self.assertEqual({h['pad'] for v in r['vias'] for h in v['exposed_SMD_copper_hits'] if h['ref']=='U2'},{'5','6'})
        self.assertTrue(any(h['ref']=='U4' and h['pad']=='25' for v in r['vias'] for h in v['exposed_SMD_copper_hits']))

    def test_release_files_match_manifest_and_archives(self):
        root=ROOT/'production/hro-r1';m=json.loads((root/'manifest.json').read_text())
        for f,v in m['files'].items():self.assertEqual(hashlib.sha256((root/f).read_bytes()).hexdigest(),v['sha256'],f)
        for f,h in m['source_sha256'].items():self.assertEqual(hashlib.sha256((ROOT/f).read_bytes()).hexdigest(),h,f)
        for archive in root.glob('*.zip'):
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip());self.assertFalse(any(n.endswith('.csv') for n in z.namelist()))
                if 'BARE-PCB' in archive.name:self.assertFalse(any('Paste.gbr' in n for n in z.namelist()))
                self.assertIn('SHA256SUMS.txt',z.namelist())

    def test_cam_report_covers_independent_exported_features(self):
        d=json.loads((ROOT/'production/hro-r1/cam-inspection.json').read_text());c=d['carrier'];p=d['passive-panel']
        self.assertEqual(c['closed_outline_loops'],1);self.assertEqual(p['closed_outline_loops'],2)
        self.assertEqual(c['IPC_records_checked'],347);self.assertEqual(c['HRO_SMT_lands_copper_mask_paste'],12)
        self.assertEqual(c['drill_tools_mm_hits']['PTH'],{'0.300':133,'0.600':4,'0.900':2,'1.000':16})
        self.assertEqual(p['drill_tools_mm_hits'],{'PTH':{},'NPTH':{'3.200':5,'3.600':1}})
        self.assertEqual((c['via_barrels_exposed_SMD_Cu'],c['via_barrels_paste']),(35,35))
        self.assertTrue(c['In1_GND_connected_polygon'])
        for v in c['RTN_GND_CAM_isolation'].values():self.assertGreater(v['GND_RTN_gap_mm'],.25)

    def test_gerbonara_region_attribute_adapter_preserves_geometry(self):
        from check_hro_cam import read_gerber,area
        from gerbonara import GerberFile
        data='%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\n%TO.N,RTN*%\nG01*\nG36*\nX0Y0D02*\nX1000000Y0D01*\nX1000000Y1000000D01*\nX0Y1000000D01*\nX0Y0D01*\nG37*\nM02*\n'
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'test.gbr';f.write_text(data);adapted=read_gerber(f);vanilla=GerberFile.open(f)
            self.assertEqual(adapted.objects[0].attrs['.N'],('RTN',))
            self.assertAlmostEqual(area(adapted.objects).area,1)
            self.assertEqual(area(adapted.objects).symmetric_difference(area(vanilla.objects)).area,0)

    def test_open_outline_rejected_by_actual_CAM_checker(self):
        from check_hro_cam import outlines
        from gerbonara import GerberFile,graphic_objects as go,apertures as ap
        from gerbonara.utils import MM
        a=ap.CircleAperture(.05,unit=MM)
        g=GerberFile(objects=[go.Line(0,0,10,0,a,unit=MM),go.Line(10,0,10,10,a,unit=MM)])
        with self.assertRaisesRegex(AssertionError,'open or branching'):outlines(g)

    def test_drill_precision_is_bounded_and_dropped_slot_rejected(self):
        from check_hro_cam import compare_drills
        expected=Counter([('round',10.0005,-20,.3),('slot',1,-4,1,-3,.6)])
        self.assertAlmostEqual(compare_drills([('round',10,-20,.3),('slot',1,-4,1,-3,.6)],expected),.0005)
        for actual in [[('round',10,-20,.3)], [('round',10,-20,.3),('slot',1,-4,1,-2.9,.6)]]:
            with self.assertRaises(AssertionError):compare_drills(actual,expected)

    def test_all_main_overlap_desired_hashes_are_canonical(self):
        d=json.loads((ROOT/'docs/hro-integration.json').read_text())
        self.assertEqual(len(d['overlap']),7)
        for f,v in d['overlap'].items():self.assertEqual(hashlib.sha256((ROOT/f).read_bytes()).hexdigest(),v['desired_sha256'])
        self.assertFalse(any('.history' in f or f.endswith('.lck') for f in d['desired_files_sha256']))


if __name__=='__main__':unittest.main()
