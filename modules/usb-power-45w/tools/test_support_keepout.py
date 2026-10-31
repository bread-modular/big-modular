"""M3 support keep-out regression (R2 seed drew outline r3.6 + hole r1.7; it reloads seamed).

Run from the repository root (needs pcbnew; writes only to a temp dir, never to hardware/):
  python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v

Both tests build a scratch 4-layer board with the five Stack_M3_Spacer_Top footprints at the
stack_r2.STANDOFFS centres and an all-layer GND pour over them, add the keep-outs, fill, save,
reload and run tools/check_support_copper.py on the reloaded file. The tools/build_stack.py
sectors must give zero copper in r1.7..3.6; the old outline + hole construction must fail.
"""
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_stack as bs  # noqa: E402
import check_support_copper as csc  # noqa: E402
import stack_r2 as st  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]


def scratch(path, keepout):
    import pcbnew
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    gnd = pcbnew.NETINFO_ITEM(b, 'GND')
    b.Add(gnd)
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    for k, (y, z) in enumerate(st.STANDOFFS, 1):
        f = io.FootprintLoad(str(bs.LIB), 'Stack_M3_Spacer_Top')
        f.SetFPID(pcbnew.LIB_ID('USBPOWER45', 'Stack_M3_Spacer_Top'))
        b.Add(f)
        f.SetReference('')
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(y + 35.75), pcbnew.FromMM(104.275 - z)))
        keepout(b, csc.nat(y, z), f'MHT{k}')
    for lay in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(lay)
        z.SetNet(gnd)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((45, 60), (160, 60), (160, 105), (45, 105)):
            o.Append(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill([z for z in b.Zones() if not z.GetIsRuleArea()])
    pcbnew.SaveBoard(str(path), b)
    return csc.check(path, refill=True)


def old_ring(b, centre, prefix):
    """The R2 seed construction (outline r3.6 + hole r1.7, 36 vertices each)."""
    import pcbnew
    zone = pcbnew.ZONE(b)
    zone.SetIsRuleArea(True)
    for fn in (zone.SetDoNotAllowTracks, zone.SetDoNotAllowVias, zone.SetDoNotAllowPads,
               zone.SetDoNotAllowZoneFills):
        fn(True)
    zone.SetLayerSet(pcbnew.LSET.AllCuMask())
    zone.SetZoneName(f'{prefix}_copper_keepout_r{st.STANDOFF_CU_R}')
    o = zone.Outline()
    o.NewOutline()
    for r, s in ((st.STANDOFF_CU_R, 1), (1.7, -1)):
        if s < 0:
            o.NewHole()
        for a in range(36):
            t = s * 2 * math.pi * a / 36
            o.Append(pcbnew.VECTOR2I(pcbnew.FromMM(centre[0] + r * math.cos(t)),
                                     pcbnew.FromMM(centre[1] + r * math.sin(t))))
    b.Add(zone)


class SupportKeepout(unittest.TestCase):
    def test_sectors_round_trip_clean(self):
        with tempfile.TemporaryDirectory() as d:
            r = scratch(Path(d) / 'seed-top.kicad_pcb', bs.add_support_keepout)
        self.assertEqual(r['problems'], [])
        self.assertEqual(len(r['supports']), 5)
        for s in r['supports']:
            self.assertEqual(len(s['keepout']['zones']), bs.KEEPOUT_SECTORS)
            self.assertEqual(s['keepout']['grid_points_uncovered'], 0)
            self.assertGreaterEqual(min(v[0] for v in s['nearest'].values()), csc.R_OUT)

    def test_old_outline_plus_hole_is_seamed(self):
        with tempfile.TemporaryDirectory() as d:
            r = scratch(Path(d) / 'old-top.kicad_pcb', old_ring)
        self.assertEqual(len(r['supports']), 5)
        for s in r['supports']:
            self.assertGreater(s['keepout']['grid_points_uncovered'], 0)
            self.assertTrue(any(h['d_min'] < csc.R_OUT for h in s['hits']))

    def test_seed_refuses_routed_top(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, BUILD_STACK_OUT=d)
            p = subprocess.run([sys.executable, '-B', str(MODULE / 'tools/build_stack.py'), '--side', 'top'],
                               env=env, capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('carries copper', p.stderr)
            self.assertFalse(any(Path(d).rglob('*.kicad_pcb')))


if __name__ == '__main__':
    unittest.main()
