"""Recompute all reported counts from exact CSVs; no input sampling or tuning."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from collections import Counter


def analyze(folder: Path) -> dict:
    finite=[]
    for chunk in range(8):
        with (folder/f'finite-{chunk}.csv').open(newline='') as f:
            rows=list(csv.DictReader(f))
        if len(rows)!=5184: raise ValueError('incomplete finite chunk')
        finite.extend(rows)
    with (folder/'network.csv').open(newline='') as f:
        network=list(csv.DictReader(f))
    if len(network)!=13248: raise ValueError('incomplete network suite')
    for row in finite+network:
        if row['oracle_agrees']!='1' or row['checker_agrees']!='1':
            raise ValueError('disagreement is present')
    # No singleton query is invented: the compiled network suite includes it.
    lookup={(x['reference'],x['belief_mask'],x['action_indices'],x['relation'],x['horizon']):int(x['winning']) for x in network}
    singleton_wins=0;false=Counter();by_relation={};by_horizon={}
    for x in network:
        mask=int(x['belief_mask'])
        optimistic=all(lookup[(x['reference'],str(1<<w),x['action_indices'],x['relation'],x['horizon'])] for w in range(4) if mask&(1<<w))
        singleton_wins+=optimistic
        if optimistic and not int(x['winning']): false[(x['relation'],int(x['horizon']))]+=1
        if int(x['winning']) and not optimistic: raise ValueError('downward closure violated')
        for table,key in [(by_relation,x['relation']),(by_horizon,x['horizon'])]:
            table.setdefault(key,{'queries':0,'winning':0})
            table[key]['queries']+=1;table[key]['winning']+=int(x['winning'])
    core=json.loads((folder/'cores-measurement.json').read_text())
    if core['subset_queries']!=501 or core['mismatches']!=0: raise ValueError('core suite incomplete')
    for record in core['records']:
        n=record['hidden_worlds']
        if record!={'hidden_worlds':n,'nonempty_subsets':2**n-1,'winning_proper_subsets':2**n-2,'core_size':n}:
            raise ValueError('core-family row inconsistent')
    faults=json.loads((folder/'fault-cases.json').read_text())
    if len(faults)!=684: raise ValueError('fault-case provenance incomplete')
    data={'principal_exact_queries':len(finite)+len(network)+core['subset_queries'],
          'finite':{'queries':len(finite),'winning':sum(int(x['winning']) for x in finite),'mismatches':0,
                    'syntax_programs_examined':sum(int(x['programs_examined']) for x in finite)},
          'network':{'queries':len(network),'winning':sum(int(x['winning']) for x in network),'mismatches':0,
                     'syntax_programs_examined':sum(int(x['programs_examined']) for x in network),
                     'fault_cases':len(faults),'unsafe_fault_cases':sum(not x['safe_fault_belief'] for x in faults),
                     'fault_cases_with_unsafe_complete_no_fault_schedule':sum(not x['complete_no_fault_schedule_safe'] for x in faults),
                     'unique_reference_beliefs':len({(x['reference'],tuple(x['belief'])) for x in faults}),
                     'by_relation':by_relation,'by_horizon':by_horizon,
                     'clairvoyant_singleton_baseline_wins':singleton_wins,
                     'clairvoyant_false_positives':sum(false.values()),
                     'clairvoyant_false_positives_by_relation_and_horizon':[
                         {'relation':rel,'horizon':k,'queries':num} for (rel,k),num in sorted(false.items())]},
          'cores':{'queries':501,'winning':494,'losing':7,'mismatches':0,'rows':core['records']},
          'scope':'Exact finite checks, not machine-checked general metatheory, deployment evidence, or novelty evidence.'}
    return data


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();data=analyze(args.results)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'principal_exact_queries':data['principal_exact_queries'],'clairvoyant_false_positives':data['network']['clairvoyant_false_positives']}))
if __name__=='__main__':main()
