"""R1-start regression: 10-pin outputs and explicitly partial manual routing.

Native ERC/DRC remains the separate shared check gate. These tests check the
intentional header geometry and endpoint connectivity without claiming that
converter routing or the full thermal/copper contract is complete.
"""
import sys
import unittest
from collections import defaultdict
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_s8
import circuit_s8
import check_s8_board
import mechanics_s8
import place_s8

BOARD = HERE.parent / 'hardware/usb-power-45w.kicad_pcb'
_REMOVED = []   # SWIG: a removed board item must outlive its board, or its GC corrupts the next LoadBoard


class RoutingR1(unittest.TestCase):
    def setUp(self):
        self.b = pcbnew.LoadBoard(str(BOARD))
        self.fps = {f.GetReference(): f for f in self.b.GetFootprints() if f.GetReference()}

    def test_ten_pin_outputs_and_retained_polarity(self):
        wanted = {str(i): ('-12V' if i <= 2 else 'GND' if i <= 8 else '+12V') for i in range(1, 11)}
        table = {c['ref']: c for c in circuit_s8.circuit()}
        for ref, x in [('J2', 111.75), ('J3', 142.75)]:
            f = self.fps[ref]
            pads = {p.GetNumber(): p for p in f.Pads()}
            self.assertEqual({n: p.GetNetname() for n, p in pads.items()}, wanted)
            self.assertEqual(table[ref]['pins'], wanted)
            self.assertEqual(table[ref]['fields']['MPN'], '61201021621')
            self.assertEqual(f.GetFPID().GetLibItemName(), build_s8.FP_S8['IDC10'])
            self.assertEqual(f.GetOrientationDegrees(), -90)
            for n, p in pads.items():
                row, side = (int(n) - 1) // 2, (int(n) - 1) % 2
                self.assertAlmostEqual(pcbnew.ToMM(p.GetPosition().x), x - row * 2.54, places=5)
                self.assertAlmostEqual(pcbnew.ToMM(p.GetPosition().y), 60.275 + side * 2.54, places=5)
                self.assertAlmostEqual(pcbnew.ToMM(p.GetDrillSize().x), 1.1)
        g = mechanics_s8.geometry()
        self.assertEqual([h['rows'] for h in g['headers']], [5, 5])
        self.assertEqual(g['header']['body_LWH_max_mm'], [20.56, 9.0, 9.25])
        self.assertEqual(g['mating_plug']['proposal_body_LW_mm'], [17.6, 6.2])

    def test_reclaimed_space_and_injection_distance(self):
        for ref in ['C34', 'D2', 'C59', 'C84', 'D27', 'R116']:
            f = self.fps[ref]
            x, y, rot = place_s8.table()[ref]
            self.assertAlmostEqual(pcbnew.ToMM(f.GetPosition().x), x)
            self.assertAlmostEqual(pcbnew.ToMM(f.GetPosition().y), y)
            self.assertEqual(f.GetOrientationDegrees() % 360, rot % 360)
        a = next(p for p in self.fps['D27'].Pads() if p.GetNumber() == '2').GetPosition()
        c = next(p for p in self.fps['R9'].Pads() if p.GetNumber() == '1').GetPosition()
        self.assertLess(pcbnew.ToMM((a - c).EuclideanNorm()), 4.0)

    def test_header_buses_and_local_parts_connected(self):
        # Layer-aware endpoint graph: only THT pads bridge F/B; SMD pads do not.
        def node(layer, v):
            return layer, v.x, v.y
        for net, starts in [('+12V', ['C34.1', 'D2.1', 'C59.1', 'J2.9', 'J2.10', 'J3.9', 'J3.10']),
                            ('-12V', ['C36.2', 'J2.1', 'J2.2', 'J3.1', 'J3.2'])]:
            graph = defaultdict(set)
            def edge(a, c):
                graph[a].add(c)
                graph[c].add(a)
            for t in self.b.GetTracks():
                if t.GetClass() != 'PCB_VIA' and t.GetNetname() == net:
                    edge(node(t.GetLayer(), t.GetStart()), node(t.GetLayer(), t.GetEnd()))
            for f in self.fps.values():
                for p in f.Pads():
                    if p.GetNetname() == net and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                        edge(node(pcbnew.F_Cu, p.GetPosition()), node(pcbnew.B_Cu, p.GetPosition()))
            targets = []
            for endpoint in starts:
                r, n = endpoint.split('.')
                p = next(p for p in self.fps[r].Pads() if p.GetNumber() == n)
                targets.append(node(pcbnew.F_Cu, p.GetPosition()))
            seen, todo = set(), [targets[0]]
            while todo:
                a = todo.pop()
                if a in seen:
                    continue
                seen.add(a)
                todo.extend(graph[a] - seen)
            self.assertTrue(set(targets) <= seen, (net, set(targets) - seen))

    def assert_track_chain(self, net, endpoints):
        cu = check_s8_board.Copper(self.b, self.fps)
        self.assertTrue(any(set(endpoints) <= chain['pads'] for chain in cu.chains(net)),
                        (net, endpoints, [sorted(chain['pads']) for chain in cu.chains(net)]))

    def test_usb_cc_routes(self):
        for name, endpoints in [('CC1', ['J1.A5', 'U1.7']), ('CC2', ['J1.B5', 'U1.6'])]:
            net = '/USB PD, main eFuse and VIN damper/' + name
            self.assert_track_chain(net, endpoints)
            vias = [t for t in self.b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == net]
            self.assertEqual(len(vias), 2)
            for t in self.b.GetTracks():
                if t.GetClass() != 'PCB_VIA' and t.GetNetname() == net:
                    self.assertIn(t.GetLayer(), [pcbnew.F_Cu, pcbnew.B_Cu])
                    self.assertAlmostEqual(pcbnew.ToMM(t.GetWidth()), 0.25)

    def test_main_protection_control_routes(self):
        prefix = '/USB PD, main eFuse and VIN damper/'
        for name, endpoints in [
                ('MAIN_DVDT', ['U5.10', 'C3.1']),
                ('MAIN_OV', ['U5.8', 'R24.1', 'R4.2']),
                ('MAIN_UV', ['U5.7', 'R2.2', 'R3.1']),
                ('UV_TRIM', ['R3.2', 'R114.1']),
                ('MAIN_ILM', ['U5.11', 'R5.1']),
                ('MAIN_IMON', ['U5.14', 'R26.1', 'TP7.1'])]:
            self.assert_track_chain(prefix + name, endpoints)
        self.assert_track_chain('Net-(R29-Pad1)', ['R5.2', 'R29.1'])
        self.assert_track_chain('/RUN', ['U5.13', 'Q10.1'])
        self.assert_track_chain('/MAIN_OK', ['U5.15', 'U5.16', 'R63.2'])
        self.assert_track_chain('GND', ['U5.9', 'U5.12', 'U5.21', 'C2.2', 'C3.2', 'R24.2'])

    def test_tee_junction_chain_negative_control(self):
        # MAIN_OK reaches R63.2 through a via that sits on a B.Cu run (not at its end): the chain model must follow it,
        # and lose R63.2 once that run is cut (in-memory board only, never saved)
        self.assert_track_chain('/MAIN_OK', ['U5.15', 'U5.16', 'R63.2'])
        run = next(t for t in self.b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == '/MAIN_OK'
                   and t.GetLayer() == pcbnew.B_Cu and t.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(95.65), pcbnew.FromMM(89.85)), 0))
        self.b.Remove(run)
        _REMOVED.append((self.b, run))
        with self.assertRaises(AssertionError):
            self.assert_track_chain('/MAIN_OK', ['U5.15', 'U5.16', 'R63.2'])

    def test_back_test_point_screen_negative_controls(self):
        # B-side test points (user direction): off-board and touching courtyards must be caught; only the contract
        # 2.54 mm pair TP26/TP27 may touch (in-memory moves only, never saved)
        outline = pcbnew.SHAPE_POLY_SET()
        self.b.GetBoardPolygonOutlines(outline, True)
        segs = check_s8_board.poly_segs(outline)
        def screen():
            back = {r: f.GetCourtyard(pcbnew.B_CrtYd) for r, f in self.fps.items()
                    if f.IsFlipped() and check_s8_board.is_test_pad(f)}
            return check_s8_board.back_test_points(self.fps, back, outline, segs)
        edge, over = screen()
        self.assertTrue(all(d >= 1.0 for d in edge.values()), edge)
        self.assertEqual(over, [])
        x26 = self.fps['TP26'].GetPosition()
        self.fps['TP9'].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(40.0), pcbnew.FromMM(80.0)))   # off the board
        self.fps['TP10'].SetPosition(x26 + pcbnew.VECTOR2I(0, pcbnew.FromMM(2.0)))              # onto TP26
        edge, over = screen()
        self.assertLess(edge['TP9'], 0)
        self.assertIn(['TP10', 'TP26', ], [o[:2] for o in over])
        self.assertNotIn(['TP26', 'TP27'], [o[:2] for o in over])

    def test_cc_broken_backside_route_is_detected(self):
        net = '/USB PD, main eFuse and VIN damper/CC1'
        self.assert_track_chain(net, ['J1.A5', 'U1.7'])
        track = max((t for t in self.b.GetTracks() if t.GetClass() == 'PCB_TRACK'
                     and t.GetNetname() == net and t.GetLayer() == pcbnew.B_Cu),
                    key=lambda t: t.GetLength())
        self.b.Remove(track)  # negative control: in-memory board only, never saved
        _REMOVED.append((self.b, track))
        with self.assertRaises(AssertionError):
            self.assert_track_chain(net, ['J1.A5', 'U1.7'])

    def test_plane_vias_widths_and_cleanup(self):
        self.assertTrue(check_s8_board.via_policy_rows(BOARD, self.b, self.fps)['ok'])
        ground = [z for z in self.b.Zones() if z.GetZoneName() == 'R1_PGND_In1']
        self.assertEqual(len(ground), 1)
        self.assertEqual(ground[0].GetFilledPolysList(pcbnew.In1_Cu).OutlineCount(), 1)
        self.assertGreater(ground[0].GetFilledPolysList(pcbnew.In1_Cu).Area() / 1e12, 4000)
        thermal = place_s8.thermal_ids()
        keys = set()
        for t in self.b.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                continue
            self.assertNotEqual(t.GetLayer(), pcbnew.In1_Cu)
            a, c = t.GetStart(), t.GetEnd()
            self.assertNotEqual(a, c)
            k = (t.GetLayer(), t.GetNetname(), tuple(sorted([(a.x, a.y), (c.x, c.y)])))
            self.assertNotIn(k, keys)
            keys.add(k)
            if t.m_Uuid.AsString() not in thermal and t.GetNetname() in ('+12V', '-12V'):
                self.assertGreaterEqual(pcbnew.ToMM(t.GetWidth()), 1.5 if t.GetNetname() == '+12V' else 0.8)


if __name__ == '__main__':
    unittest.main()
