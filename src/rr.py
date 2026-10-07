"""Offline JSON interface. Every action below is a finite simulation only."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from model import Model, read_json, horizon
from synthesis import Solver, extract_program, is_winning, minimal_core
from checker import check, check_core


def problem(path: Path):
    obj=read_json(path)
    if not isinstance(obj,dict) or set(obj)!={'model','initial','bound'}:
        raise ValueError('problem requires exactly model, initial, and bound')
    model=Model.from_dict(obj['model'])
    return model,model.belief(obj['initial']),horizon(obj['bound'])


def write_new(path: Path, obj, *, max_bytes: int = 16 * 1024 * 1024, compact: bool = False) -> None:
    # Reject oversized publications before creating a destination. Existing
    # evidence is never overwritten, even when the desired contents are equal.
    text = (json.dumps(obj, sort_keys=True, separators=(',', ':')) if compact
            else json.dumps(obj, indent=2))
    encoded = (text + '\n').encode('utf-8')
    if len(encoded) > max_bytes:
        raise ValueError('output exceeds the certificate JSON size limit')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(encoded)


def execute_all(model,initial,bound,program, max_runs=100000):
    runs=[]
    def visit(world,node,k,events):
        if world not in model.safe:raise ValueError('interpreter reached unsafe world')
        if len(runs) >= max_runs:
            raise ValueError('offline interpreter exceeds the completed-run limit')
        if node=={'stop':True}:
            if world not in model.goal:raise ValueError('interpreter stopped outside goal')
            runs.append({'final':world,'events':events});return
        if k<=0:raise ValueError('interpreter exceeded command budget')
        action=node['action'];ai=model.actions.index(action)
        if not model.edges[ai][world]:raise ValueError('interpreter found disabled action')
        for obs,target in model.edges[ai][world]:
            if obs not in node['branches']:raise ValueError('interpreter lacks observation branch')
            visit(target,node['branches'][obs],k-1,events+[{'from':world,'action':action,'observation':obs,'to':target}])
    for w in sorted(initial):visit(w,program,bound,[{'initial':w}])
    return {'mode':'offline finite simulation','runs':runs}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for verb in ['solve','core']:
        q=sub.add_parser(verb);q.add_argument('--input',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    for verb in ['check','execute','check-core']:
        q=sub.add_parser(verb);q.add_argument('--input',type=Path,required=True);q.add_argument('--certificate',type=Path,required=True)
    args=p.parse_args()
    try:
        model,b,k=problem(args.input)
        if args.command=='solve':
            c=Solver(model).solve(b,k);check(model,b,k,c);write_new(args.output,c)
            print(json.dumps({'verdict':'win' if is_winning(c) else 'lose','output':str(args.output)}))
        elif args.command=='core':
            c=minimal_core(model,b,k);check_core(model,b,k,c);write_new(args.output,c)
            print(json.dumps({'core':c['core'],'minimality':'inclusion only'}))
        elif args.command=='check':print(json.dumps({'verdict':check(model,b,k,read_json(args.certificate))}))
        elif args.command=='check-core':
            check_core(model,b,k,read_json(args.certificate));print(json.dumps({'valid':True,'minimality':'inclusion only'}))
        else:
            c=read_json(args.certificate)
            if check(model,b,k,c)!='win':raise ValueError('cannot execute a losing certificate')
            print(json.dumps(execute_all(model,b,k,extract_program(c)),indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError,RecursionError) as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
