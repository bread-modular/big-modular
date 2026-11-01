"""TPS3808G01 pin-identity regression (S6 had SENSE=3 / MR=5; TI DBV is MR=3 / SENSE=5).

Run from the repository root (needs kicad-cli; reads, never writes, the module):
  python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v

The old map was self-consistent: symbol, circuit table and verifier table all agreed.
These tests rebuild that state (circuit() and CRIT reverted too) and require the
manufacturer-derived check in verify_design.py to reject it on its own.
"""
import copy
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import circuit45  # noqa: E402
import verify_design  # noqa: E402
from sexp import parse, nodes, one, walk  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
OLD_COMMIT = '077905c'          # last commit with the swapped TPS3808 map
OLD_PINS = {'U10': {'1': 'RESET_N', '2': 'GND', '3': 'POR_SENSE', '4': None, '5': 'RESET_BTN_N', '6': 'V3V3'},
            'U11': {'1': 'START_READY', '2': 'GND', '3': 'START_SENSE', '4': 'START_CT', '5': 'RESET_N', '6': 'V3V3'}}
OLD_CRIT = {'U10': {1: 'RESET_N', 2: 'GND', 3: 'POR_SENSE', 5: 'RESET_BTN_N', 6: 'V3V3'},
            'U11': {1: 'START_READY', 2: 'GND', 3: 'START_SENSE', 4: 'START_CT', 5: 'RESET_N', 6: 'V3V3'}}


def export_netlist(sch, out):
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out), str(sch)],
                   check=True, stdout=subprocess.DEVNULL)
    return out


def symbol_pins(lib_file, name='TPS3808G01'):
    sym = {s[1]: s for s in nodes(parse(Path(lib_file).read_text()), 'symbol')}[name]
    plain = lambda n: n[:-2] if n.endswith('_N') else n
    return {one(p, 'number')[1]: plain(one(p, 'name')[1]) for p in walk(sym, 'pin')}


def old_circuit(pre_s7=False):
    parts = copy.deepcopy(circuit45.circuit())
    for p in parts:
        if p['ref'] in OLD_PINS:
            p['pins'] = dict(OLD_PINS[p['ref']])
    if pre_s7:   # the committed pre-fix hardware still has the second parallel header J3 (removed in S7)
        for p in parts:                  # and the unnamed U4 RT net (S7 names it RT_U4)
            p['pins'] = {n: ('_RT_U4' if v == 'RT_U4' else v) for n, v in p['pins'].items()}
        j2 = next(p for p in parts if p['ref'] == 'J2')
        j2['fields']['Note'] = PRE_S7_HEADER_NOTE
        for k in PRE_S7_J2_DROPPED:                 # S7 R2 added the Wurth MPN/Manufacturer; 077905c had none
            assert j2['fields'].pop(k, None), k
        j3 = copy.deepcopy(j2)
        j3['ref'] = 'J3'
        parts.append(j3)
    return parts


PRE_S7_J2_DROPPED = ('MPN', 'Manufacturer')
PRE_S7_FP = {'IDC16': 'IDC-Header_2x08_P2.54mm_Vertical'}   # 077905c footprint; S7 R2 pins the Wurth 61201621621 land
PRE_S7_HEADER_NOTE = ('Hand-soldered shrouded 16-pin box header, pin 1 = -12V (red stripe). J2 and J3 are in '
                      'parallel: use both cables above ~1.5 A per rail. CV/GATE (13-16) open')


def mutate(src, dst, swap_symbol, swap_nets):
    """swap_symbol: libpart and pin functions use the old SENSE=3/MR=5 names.
    swap_nets: U10/U11 pins 3 and 5 exchange nets (the old circuit table)."""
    tree = ET.parse(src)
    root = tree.getroot()
    if swap_symbol:
        lib = next(p for p in root.iter('libpart') if p.get('part') == 'TPS3808G01')
        names = {x.get('num'): x for x in lib.findall('pins/pin')}
        names['3'].set('name', 'SENSE')
        names['5'].set('name', 'MR_N')
    for node in root.iter('node'):
        if node.get('ref') in OLD_PINS and node.get('pin') in ('3', '5'):
            pin = node.get('pin')
            other = '5' if pin == '3' else '3'
            func = node.get('pinfunction').removesuffix('_' + pin)
            if swap_nets:                       # same net now reaches the other physical pin
                node.set('pin', other)
                pin = other
                if not swap_symbol:             # fixed symbol: the pin keeps its datasheet name
                    func = {'SENSE': 'MR_N', 'MR_N': 'SENSE'}[func]
            elif swap_symbol:                   # old symbol names on unchanged nets
                func = {'SENSE': 'MR_N', 'MR_N': 'SENSE'}[func]
            node.set('pinfunction', f'{func}_{pin}')
    tree.write(dst)
    return dst


@unittest.skipUnless(shutil.which('kicad-cli'), 'kicad-cli required')
class TPS3808PinIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='tps3808-pins-'))
        cls.netlist = export_netlist(HW / 'usb-power-45w-system.kicad_sch', cls.tmp / 'current.xml')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def verify(self, netlist, hardware=HW, root=None):
        return verify_design.verify(netlist, hardware, hierarchy_root=root)

    def old_tables(self, pre_s7=False):
        crit = {**verify_design.CRIT, **OLD_CRIT}
        fp = {**verify_design.FP, **PRE_S7_FP} if pre_s7 else verify_design.FP
        return mock.patch.multiple(verify_design, circuit=lambda: old_circuit(pre_s7), CRIT=crit, FP=fp)

    def test_symbols_match_ti_table(self):
        self.assertEqual(verify_design.TPS3808_DBV, {'1': 'RESET', '2': 'GND', '3': 'MR', '4': 'CT', '5': 'SENSE', '6': 'VDD'})
        for lib in (MODULE / 'tools/USBPOWER45-src.kicad_sym', HW / 'USBPOWER45.kicad_sym'):
            self.assertEqual(symbol_pins(lib), verify_design.TPS3808_DBV, lib)

    def test_current_design_passes(self):
        self.assertTrue(self.verify(self.netlist)['exact_field_pin_NC_pad_parity'])

    def test_old_self_consistent_map_rejected(self):
        bad = mutate(self.netlist, self.tmp / 'old-both.xml', swap_symbol=True, swap_nets=True)
        with self.old_tables():
            with mock.patch.object(verify_design, 'check_tps3808'):   # without it the old map passes
                self.verify(bad)
            with self.assertRaisesRegex(AssertionError, 'TPS3808G01 symbol pin identity'):
                self.verify(bad)

    def test_fixed_symbol_with_old_nets_rejected(self):
        bad = mutate(self.netlist, self.tmp / 'old-nets.xml', swap_symbol=False, swap_nets=True)
        with self.old_tables(), self.assertRaisesRegex(AssertionError, 'TPS3808 role not on'):
            self.verify(bad)

    def test_old_symbol_with_fixed_nets_rejected(self):
        bad = mutate(self.netlist, self.tmp / 'old-symbol.xml', swap_symbol=True, swap_nets=False)
        with self.assertRaisesRegex(AssertionError, 'TPS3808G01 symbol pin identity'):
            self.verify(bad)

    def test_committed_old_hardware_rejected(self):
        """The real pre-fix native schematic, with its own circuit/CRIT tables restored."""
        repo = MODULE.parents[1]
        rel = MODULE.relative_to(repo) / 'hardware'
        ls = subprocess.run(['git', '-C', str(repo), 'ls-tree', '-r', '--name-only', OLD_COMMIT, str(rel)],
                            capture_output=True, text=True)
        if ls.returncode or not ls.stdout.strip():
            self.skipTest(f'git history {OLD_COMMIT} unavailable')
        old_hw = self.tmp / 'old/hardware'
        for name in ls.stdout.split():
            dst = old_hw / Path(name).relative_to(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(subprocess.run(['git', '-C', str(repo), 'show', f'{OLD_COMMIT}:{name}'],
                                           check=True, capture_output=True).stdout)
        old_root = old_hw / 'usb-power-45w.kicad_sch'     # historical filename of the S6 root at that commit
        old = export_netlist(old_root, self.tmp / 'old.xml')
        with self.old_tables(pre_s7=True):
            with mock.patch.object(verify_design, 'check_tps3808'):
                self.verify(old, old_hw, old_root)
            with self.assertRaisesRegex(AssertionError, 'TPS3808G01 symbol pin identity'):
                self.verify(old, old_hw, old_root)


if __name__ == '__main__':
    unittest.main()
