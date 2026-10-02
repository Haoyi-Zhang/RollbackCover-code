"""Materialize deterministic, owned diagnostic inputs and replayable evidence."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from network import compile_network, hidden_reference_case, nonminimum_core_case
from synthesis import Solver, extract_program, minimal_core, is_winning
from checker import check, check_core
from rr import execute_all


def build(out: Path):
    out.mkdir(parents=True,exist_ok=True)
    cases=[('ambiguous-flip',compile_network(0,('flip-x',)),frozenset({1,3}),1),
           ('read-too-short',compile_network(0,('flip-x','read-x')),frozenset({1,3}),1),
           ('read-and-restore',compile_network(0,('flip-x','read-x')),frozenset({1,3}),2),
           ('idempotent-restore',compile_network(0,('set-x-0',)),frozenset({1,3}),1)]
    m,b=hidden_reference_case();cases.append(('hidden-reference',m,b,2))
    m,b=nonminimum_core_case();cases.append(('minimal-not-minimum',m,b,1))
    summary=[]
    for name,m,b,k in cases:
        c=Solver(m).solve(b,k);verdict=check(m,b,k,c)
        files={f'{name}.problem.json':{'model':m.to_dict(),'initial':sorted(b),'bound':k},f'{name}.certificate.json':c}
        if is_winning(c): files[f'{name}.execution.json']=execute_all(m,b,k,extract_program(c))
        else:
            core=minimal_core(m,b,k);check_core(m,b,k,core);files[f'{name}.core.json']=core
        for filename,data in files.items(): (out/filename).write_text(json.dumps(data,indent=2)+'\n')
        summary.append({'case':name,'verdict':verdict,'bound':k,'initial':sorted(b)})
    (out/'cases.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'diagnostic_cases':len(cases),'output':str(out)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    build(p.parse_args().output)
