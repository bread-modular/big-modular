#!/usr/bin/env python3
"""READ ONLY: verify saved-main preconditions or user-merged HRO files.

Never stashes, resets, restores, commits, merges, writes main, touches .history or
controls KiCad. The prepared workspace already contains the desired overlap files.
"""
import argparse
import hashlib
import json
import io
from pathlib import Path
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(main,phase):
    main=main.resolve();d=json.loads((ROOT/'docs/hro-integration.json').read_text())
    expected=d['main_saved_files_sha256'] if phase=='before' else d['desired_files_sha256']
    assert all(not any(x.startswith('.') for x in Path(f).parts) and not f.endswith(('.lck','.kicad_prl')) for f in expected)
    errors=[f for f,h in expected.items() if not (main/f).is_file() or sha(main/f)!=h]
    if phase=='before':
        head=subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()
        if head!=d['main_head']:errors.append('MAIN_HEAD_CHANGED')
        for f,v in d['overlap'].items():
            if sha(ROOT/f)!=v['desired_sha256']:errors.append('WORKSPACE_CHANGED:'+f)
    else:
        errors.extend(f for f in d['deleted_paths'] if (main/f).exists())
    backup=subprocess.check_output(['git','show','c82ca1cabf01f529ae536f5afaa8773d7bbc6d29:'+d['backup']['path']],cwd=ROOT)
    assert hashlib.sha256(backup).hexdigest()==d['backup']['sha256']
    with zipfile.ZipFile(io.BytesIO(backup)) as z:
        assert z.testzip() is None
        for f,v in d['overlap'].items():assert hashlib.sha256(z.read(f)).hexdigest()==v['main_saved_sha256']
    assert not errors, 'Fresh snapshot/review required; no main action performed: '+repr(errors)
    return {'phase':phase,'files_verified':len(expected),'overlap_paths':len(d['overlap']),
            'backup_verified':True,'main_writes':False,'status':'hash preconditions pass' if phase=='before' else 'merged file hashes match; fresh native checks/tests still required'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--main',required=True,type=Path)
    p.add_argument('--phase',choices=['before','after'],required=True)
    a=p.parse_args();print(json.dumps(verify(a.main,a.phase),indent=2))
