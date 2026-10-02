from __future__ import annotations
import argparse, csv, json, time, resource, itertools
from pathlib import Path
from model import Model
from synthesis import Solver, is_winning, minimal_core, extract_program
from checker import check, check_core
from oracle import oracle, programs
from network import compile_network, lost_acknowledgements, conflict_family, ACTIONS, WRITES, safe


def measure(start: float, cpu: float) -> dict:
    return {'wall_seconds': time.monotonic() - start, 'cpu_seconds': time.process_time() - cpu,
            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'workers': 1}


def decode(code: int, base: int, digits: int) -> list[int]:
    result=[]
    for _ in range(digits):
        result.append(code % base);code//=base
    return result


def check_query(model: Model, b: frozenset[int], k: int, solver: Solver) -> tuple[bool, int]:
    cert = solver.solve(b, k)
    winning = is_winning(cert)
    exact, count = oracle(model, b, k)
    if winning != exact:
        raise AssertionError(f'oracle mismatch: {model.to_dict()}, {sorted(b)}, {k}')
    if check(model, b, k, cert) != ('win' if winning else 'lose'):
        raise AssertionError('certificate verdict mismatch')
    return winning, count


def finite_chunk(out: Path, chunk: int) -> None:
    if not 0 <= chunk < 8:
        raise ValueError('finite chunk must be 0..7')
    start, cpu = time.monotonic(), time.process_time()
    path=out / f'finite-{chunk}.csv';tmp=path.with_suffix('.csv.tmp')
    count=wins=programs_checked=0
    with tmp.open('w', newline='') as f:
        wr=csv.writer(f);wr.writerow(['transition_code','observation_map','role_code','belief_mask','horizon','winning','oracle_agrees','checker_agrees','programs_examined'])
        for tc in range(chunk*32,(chunk+1)*32):
            rows=decode(tc,4,4)
            for observation in (0,1):
                matrix=[]
                for a in range(2):
                    row=[]
                    for w in range(2):
                        mask=rows[a*2+w]
                        row.append(tuple((str(t) if observation else 'ack',t) for t in range(2) if mask & (1<<t)))
                    matrix.append(tuple(row))
                for rc in range(9):
                    roles=decode(rc,3,2)
                    model=Model(('w0','w1'),('a0','a1'),tuple(matrix),frozenset(w for w in range(2) if roles[w]>0),frozenset(w for w in range(2) if roles[w]==2))
                    solver=Solver(model)
                    for mask in (1,2,3):
                        b=frozenset(w for w in range(2) if mask & (1<<w))
                        for k in (0,1,2):
                            win, n=check_query(model,b,k,solver)
                            wr.writerow([tc,observation,rc,mask,k,int(win),1,1,n])
                            count+=1;wins+=win;programs_checked+=n
    tmp.replace(path)
    result={'suite':'exhaustive-two-world','chunk':chunk,'queries':count,'winning':wins,
            'losing':count-wins,'oracle_programs_examined':programs_checked,'mismatches':0,
            'measurements':measure(start,cpu)}
    (out/f'finite-{chunk}-measurement.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


def network_suite(out: Path) -> None:
    start,cpu=time.monotonic(),time.process_time()
    provenance=[];keys=set()
    for ref in (0,1,3):
        for length in (1,2,3):
            for schedule in itertools.product(WRITES,repeat=length):
                records=lost_acknowledgements(ref,schedule)
                no_fault_safe=all(r['safe_fault_belief'] for r in records)
                for record in records:
                    provenance.append({'reference':ref,'schedule':list(schedule),**record,'complete_no_fault_schedule_safe':no_fault_safe})
                    keys.add((ref,tuple(record['belief'])))
    (out/'fault-cases.json').write_text(json.dumps(provenance,indent=2)+'\n')
    actions=[a for size in (1,2,3) for a in itertools.combinations(ACTIONS,size)]
    count=wins=checked=0;by_relation={};by_horizon={}
    path=out/'network.csv';tmp=path.with_suffix('.csv.tmp')
    with tmp.open('w',newline='') as f:
        wr=csv.writer(f);wr.writerow(['reference','belief_mask','action_indices','relation','horizon','winning','oracle_agrees','checker_agrees','programs_examined'])
        for ref in (0,1,3):
            for action_set in actions:
                for relation in ('identity','erase-relay'):
                    model=compile_network(ref,action_set,relation);solver=Solver(model)
                    for r,bs in sorted(keys):
                        if r!=ref:continue
                        b=frozenset(bs);mask=sum(1<<x for x in b)
                        for k in (0,1,2):
                            win,n=check_query(model,b,k,solver)
                            wr.writerow([ref,mask,':'.join(str(ACTIONS.index(a)) for a in action_set),relation,k,int(win),1,1,n])
                            count+=1;wins+=win;checked+=n
                            for table,key in [(by_relation,relation),(by_horizon,str(k))]:
                                table.setdefault(key,{'queries':0,'winning':0});table[key]['queries']+=1;table[key]['winning']+=win
    tmp.replace(path)
    result={'suite':'two-forwarding-node-network','queries':count,'winning':wins,'losing':count-wins,
            'fault_cases':len(provenance),'distinct_reference_beliefs':len(keys),'action_subsets':len(actions),
            'unsafe_fault_cases':sum(not r['safe_fault_belief'] for r in provenance),
            'unsafe_complete_schedules_fault_cases':sum(not r['complete_no_fault_schedule_safe'] for r in provenance),
            'by_relation':by_relation,'by_horizon':by_horizon,'oracle_programs_examined':checked,
            'mismatches':0,'measurements':measure(start,cpu)}
    (out/'network-measurement.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


def core_suite(out: Path) -> None:
    start,cpu=time.monotonic(),time.process_time();records=[];total=0
    for size in range(2,9):
        model,b=conflict_family(size);solver=Solver(model);wins=0
        for mask in range(1,1<<size):
            sub=frozenset(w for w in range(size) if mask&(1<<w))
            win,_=check_query(model,sub,1,solver)
            if win!=(mask!=(1<<size)-1):raise AssertionError('conflict family falsified')
            wins+=win;total+=1
        packet=minimal_core(model,b,1);check_core(model,b,1,packet)
        (out/f'core-{size}.json').write_text(json.dumps({'model':model.to_dict(),'initial':sorted(b),'certificate':packet},indent=2)+'\n')
        records.append({'hidden_worlds':size,'nonempty_subsets':(1<<size)-1,'winning_proper_subsets':wins,'core_size':len(packet['core'])})
    result={'suite':'unbounded-width-family-instances','subset_queries':total,'records':records,'mismatches':0,'measurements':measure(start,cpu)}
    (out/'cores-measurement.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument('suite',choices=['finite','network','cores']);p.add_argument('--chunk',type=int,default=0);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.suite=='finite':finite_chunk(args.output,args.chunk)
    elif args.suite=='network':network_suite(args.output)
    else:core_suite(args.output)

if __name__=='__main__':main()
