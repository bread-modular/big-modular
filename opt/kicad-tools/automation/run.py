#!/usr/bin/env python3
"""Inspect / plan / apply safe offline PCB edits on separate candidates."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from api import Error, apply, inspect, plan, promote


def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__)
    sub=cli.add_subparsers(dest='command',required=True)
    for name in ('inspect','plan','apply','promote'):
        parser=sub.add_parser(name)
        parser.add_argument('--pcbnew-python',default='python3')
        if name!='inspect': parser.add_argument('--kicad-cli',default='kicad-cli')
        if name not in ('apply','promote'):
            parser.add_argument('--config')
            parser.add_argument('--project-dir')
            parser.add_argument('--board')
            parser.add_argument('--schematic')
        if name=='plan':
            parser.add_argument('--ops',required=True)
            parser.add_argument('--allow-draft-opens',action='store_true',help='Only connectivity opens may yield draft; CLI draft exit is 1')
        if name=='apply':
            parser.add_argument('--plan',required=True)
            parser.add_argument('--ops',help='Optional original ops file; hashes always checked')
            parser.add_argument('--output',required=True,help='Exclusively NEW candidate outside every source/input directory')
        if name=='promote':
            parser.add_argument('--candidate',required=True,help='Accepted candidate directory containing result.json')
            parser.add_argument('--plan',help='Plan whose source board is the destination; verifies the source hash')
            parser.add_argument('--to',help='Destination board (default: the plan source board)')
            parser.add_argument('--dry-run',action='store_true',help='Report model rebindings; write nothing')
    args=cli.parse_args(argv)
    try:
        if args.command=='apply':
            result=apply(args.plan,args.output,operations=args.ops,python=args.pcbnew_python,kicad_cli=args.kicad_cli)
            code={'accepted':0,'draft':1,'rejected':1,'failed':2}[result['status']]
        elif args.command=='promote':
            result=promote(args.candidate,args.to,plan_file=args.plan,dry_run=args.dry_run)
            code=0
        else:
            selection={k:getattr(args,k) for k in ('project_dir','board','schematic','config')}
            result=inspect(python=args.pcbnew_python,**selection) if args.command=='inspect' else plan(args.ops,python=args.pcbnew_python,kicad_cli=args.kicad_cli,allow_draft_opens=args.allow_draft_opens,**selection)
            code=0
    except (Error,OSError,ValueError,TypeError,KeyError) as error:
        result={'schema_version':1,'status':'error','error':str(error),'accepted':False}; code=2
    print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
    return code


if __name__=='__main__': sys.exit(main())
