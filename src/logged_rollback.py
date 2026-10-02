"""Replay reverse logged assignments after a single ambiguous acknowledgement.

This is a constructive baseline, not search. It applies only to fully known,
atomic coordinate assignments, an unchanged world outside those coordinates,
and a forward prefix safe through both outcomes of the failed write.
"""
from __future__ import annotations
import argparse, csv, itertools, json, resource, time
from pathlib import Path
from network import WRITES, compile_network, command, safe
from rr import execute_all
from checker import check


def inverse_log(reference: int, schedule: tuple[str, ...]):
    c=reference; log=[]
    for a in schedule:
        coordinate=a.split('-')[1]
        old=(c>>1) if coordinate=='x' else (c&1)
        after=command(c,a)[1]
        log.append({'before':c,'after':after,'undo':f'set-{coordinate}-{old}'})
        c=after
    return log


def plan_certificate(model, b, commands):
    if not commands:
        return {'kind':'win-stop','belief':sorted(b),'rank':0}
    a=commands[0]; ai=model.actions.index(a); posts={}
    for w in b:
        if not model.edges[ai][w]: raise ValueError('disabled logged compensation')
        for o,t in model.edges[ai][w]: posts.setdefault(o,set()).add(t)
    return {'kind':'win-step','belief':sorted(b),'rank':len(commands),'action':a,
            'branches':{o:plan_certificate(model,frozenset(ts),commands[1:]) for o,ts in sorted(posts.items())}}


def program(commands):
    return {'stop':True} if not commands else {'action':commands[0],'branches':{'ack':program(commands[1:])}}


def run(out: Path):
    out.mkdir(parents=True,exist_ok=True); start=time.monotonic();cpu=time.process_time()
    count=included=successful=runs_count=0
    with (out/'logged-assignments.csv').open('w',newline='') as f:
        wr=csv.writer(f);wr.writerow(['reference','schedule','position','belief_mask','safe_prefix','undo_sequence','restored','concrete_runs'])
        for reference in (0,1,3):
            model=compile_network(reference,WRITES)
            for length in (1,2,3):
                for schedule in itertools.product(WRITES,repeat=length):
                    log=inverse_log(reference,schedule);prefix_safe=True
                    for position,entry in enumerate(log):
                        count+=1;prefix_safe=prefix_safe and safe(entry['before']) and safe(entry['after'])
                        b=frozenset({entry['before'],entry['after']})
                        undo=[r['undo'] for r in reversed(log[:position+1])]
                        if prefix_safe:
                            included+=1;c=plan_certificate(model,b,undo)
                            if check(model,b,len(undo),c)!='win':raise AssertionError('logged certificate rejected')
                            executions=execute_all(model,b,len(undo),program(undo))['runs']
                            if not all(e['final']==reference for e in executions):raise AssertionError('exact restoration failed')
                            successful+=1;runs_count+=len(executions)
                            wr.writerow([reference,':'.join(schedule),position,sum(1<<x for x in b),1,':'.join(undo),1,len(executions)])
                        else:
                            wr.writerow([reference,':'.join(schedule),position,sum(1<<x for x in b),0,':'.join(undo),'not-applicable',0])
    result={'failure_cases':count,'safe_prefix_cases':included,'restored_exact_reference':successful,
            'excluded_unsafe_prefix_cases':count-included,'concrete_runs':runs_count,
            'measurements':{'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,
                            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}}
    (out/'logged-assignments-measurement.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
