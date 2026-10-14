from __future__ import annotations
import json, time, resource
from pathlib import Path
from network import compile_network, lost_acknowledgements, conflict_family
from synthesis import Solver, is_winning, extract_program, minimal_core
from checker import check, check_core
from oracle import oracle


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run() -> dict:
    start, cpu = time.monotonic(), time.process_time()
    scenarios = []
    for actions, bound in [(('flip-x',), 1), (('flip-x', 'read-x'), 1), (('flip-x', 'read-x'), 2),
                           (('set-x-0', 'set-y-0'), 2)]:
        model = compile_network(0, actions)
        initial = frozenset(lost_acknowledgements(0, ('set-y-1', 'set-x-1'))[1]['belief'])
        cert = Solver(model).solve(initial, bound)
        result = is_winning(cert)
        exact, searched = oracle(model, initial, bound)
        require(result == exact, "solver and syntax oracle disagree")
        require(
            check(model, initial, bound, cert) == ('win' if result else 'lose'),
            "certificate checker disagrees with the solver result",
        )
        scenarios.append({'actions': list(actions), 'bound': bound, 'belief': sorted(initial),
                          'winning': result, 'oracle_programs_examined': searched,
                          'program': extract_program(cert) if result else None,
                          'clairvoyant_all_singletons': all(is_winning(Solver(model).solve(frozenset({w}), bound)) for w in initial)})
    require(
        [x['winning'] for x in scenarios] == [False, False, True, True],
        "discriminating pilot outcomes changed",
    )
    require(scenarios[0]['clairvoyant_all_singletons'], "clairvoyant control changed")
    family = []
    for n in (2, 3, 4, 8):
        m, b = conflict_family(n)
        core = minimal_core(m, b, 1)
        check_core(m, b, 1, core)
        require(len(core['core']) == n, f"conflict-family core has size {len(core['core'])}, expected {n}")
        family.append({'hidden_worlds': n, 'core_size': len(core['core'])})
    return {'phase': 'pre-lock discriminating pilot', 'scenarios': scenarios, 'core_family': family,
            'measurements': {'wall_seconds': time.monotonic()-start,
                             'cpu_seconds': time.process_time()-cpu,
                             'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                             'workers': 1},
            'scope': 'finite checks and a separately implemented syntax oracle; no general mechanized proof'}

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=run();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
