"""Run ALL original SR1 schematic gates against their frozen Git snapshot.
SR2 current native circuit is tested separately; no historical assertions relaxed.
No other worktree is accessed, and no PCB checks/CAM are run.
"""
import io,subprocess,sys,tarfile,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
BASELINE_COMMIT='1e5b31f3a441b030da1b9d1c25427a97b03cbe00'
SR1='0f5b49d4384b7b1a1c3ab3c193042db181d819d1'
class FrozenSR1Tests(unittest.TestCase):
    def test_original_SR1_suite_and_receipt_are_frozen(self):
        for name in ['split-rail-schematic-receipt.json','split-rail-schematic-budget.json','split-rail-catalog.json']:
            old=subprocess.check_output(['git','show',SR1+':modules/usb-power/docs/'+name],cwd=REPO)
            self.assertEqual((ROOT/'docs'/name).read_bytes(),old,name)
        with tempfile.TemporaryDirectory(prefix='sr1-git-fixture-') as tmp:
            blob=subprocess.check_output(['git','archive',SR1,'modules/usb-power'],cwd=REPO)
            with tarfile.open(fileobj=io.BytesIO(blob)) as tf:tf.extractall(tmp,filter='data')
            root=Path(tmp)/'modules/usb-power';path=root/'tests/test_split_rail_schematic.py'
            code=path.read_text();self.assertIn(BASELINE_COMMIT,code)
            code=code.replace('REPO=ROOT.parents[1]','REPO=Path('+repr(str(REPO))+')')
            runner="import sys,unittest\nsys.path.insert(0,"+repr(str(root/'tools'))+")\nns={'__file__':"+repr(str(path))+",'__name__':'frozen_sr1'}\nexec(compile("+repr(code)+",ns['__file__'],'exec'),ns)\ns=unittest.defaultTestLoader.loadTestsFromTestCase(ns['SplitRailSchematicTests'])\nr=unittest.TextTestRunner(verbosity=2).run(s)\nraise SystemExit(not r.wasSuccessful())\n"
            result=subprocess.run([sys.executable,'-B','-c',runner],cwd=REPO,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
