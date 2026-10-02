"""Certificate checking by replay, without search or importing synthesis.py.

This is a separately implemented checker, not independently authored or a
machine-checked proof of its own correctness. It recomputes every successor set.
"""
from __future__ import annotations
from typing import Any
from model import Model, horizon


class InvalidCertificate(ValueError):
    pass


def check(model: Model, initial: frozenset[int], bound: int, cert: dict[str, Any]) -> str:
    b = model.belief(initial)
    k = horizon(bound)
    visited = [0]

    def verify(node: Any, expected: frozenset[int], remaining: int) -> str:
        visited[0] += 1
        if visited[0] > 500000:
            raise InvalidCertificate('certificate exceeds the 500000-node checking limit')
        if not isinstance(node, dict):
            raise InvalidCertificate('node is not an object')
        if type(node.get('rank')) is not int or node['rank'] != remaining:
            raise InvalidCertificate('incorrect rank')
        if not isinstance(node.get('belief'), list) or any(type(x) is not int for x in node['belief']) or node['belief'] != sorted(expected):
            raise InvalidCertificate('claimed belief is not the recomputed exact belief')
        kind = node.get('kind')
        common = {'kind', 'rank', 'belief'}
        extras = {
            'win-stop': set(), 'win-step': {'action', 'branches'},
            'lose-unsafe': {'witness'}, 'lose-horizon': {'witness'},
            'lose-step': {'witness', 'refusals'}}
        if not isinstance(kind, str) or kind not in extras or set(node) != common | extras[kind]:
            raise InvalidCertificate('unknown kind or unexpected keys')
        safe = all(w in model.safe for w in expected)
        goal = all(w in model.goal for w in expected)
        if kind == 'lose-unsafe':
            w = node['witness']
            if type(w) is not int or w not in expected or w in model.safe:
                raise InvalidCertificate('invalid unsafe witness')
            return 'lose'
        if not safe:
            raise InvalidCertificate('unsafe belief without an unsafe witness')
        if kind == 'win-stop':
            if not goal:
                raise InvalidCertificate('stop before universal goal')
            return 'win'
        if kind in ('lose-horizon', 'lose-step'):
            w = node['witness']
            if goal or type(w) is not int or w not in expected or w in model.goal:
                raise InvalidCertificate('invalid witness against stopping')
            if kind == 'lose-horizon':
                if remaining != 0:
                    raise InvalidCertificate('premature horizon rejection')
                return 'lose'
        if remaining <= 0:
            raise InvalidCertificate('step without positive rank')

        def enumerate_outcomes(ai: int) -> tuple[set[int], dict[str, frozenset[int]]]:
            blocked = set()
            outcomes: dict[str, set[int]] = {}
            for source in sorted(expected):
                row = model.edges[ai][source]
                if len(row) == 0:
                    blocked.add(source)
                for obs, target in row:
                    outcomes.setdefault(obs, set()).add(target)
            return blocked, {o: frozenset(values) for o, values in outcomes.items()}

        if kind == 'win-step':
            if not isinstance(node['action'], str) or node['action'] not in model.actions:
                raise InvalidCertificate('unknown action')
            ai = model.actions.index(node['action'])
            blocked, outcomes = enumerate_outcomes(ai)
            if blocked:
                raise InvalidCertificate('action not universally enabled')
            branches = node['branches']
            if not isinstance(branches, dict) or set(branches) != set(outcomes):
                raise InvalidCertificate('missing or spurious observation branch')
            for obs, successor in outcomes.items():
                if verify(branches[obs], successor, remaining - 1) != 'win':
                    raise InvalidCertificate('winning node has a losing child')
            return 'win'
        refusals = node['refusals']
        if not isinstance(refusals, dict) or set(refusals) != set(model.actions):
            raise InvalidCertificate('negative certificate does not cover every action')
        for ai, action in enumerate(model.actions):
            r = refusals[action]
            blocked, outcomes = enumerate_outcomes(ai)
            if not isinstance(r, dict):
                raise InvalidCertificate('malformed refusal')
            if set(r) == {'disabled'}:
                if type(r['disabled']) is not int or r['disabled'] not in blocked:
                    raise InvalidCertificate('invalid disabled witness')
            elif set(r) == {'observation', 'child'}:
                # Canonical contract: use a disabled witness whenever one exists.
                if blocked or not isinstance(r['observation'], str) or r['observation'] not in outcomes:
                    raise InvalidCertificate('invalid losing observation')
                if verify(r['child'], outcomes[r['observation']], remaining - 1) != 'lose':
                    raise InvalidCertificate('losing node has a winning refusal')
            else:
                raise InvalidCertificate('malformed refusal keys')
        return 'lose'

    return verify(cert, b, k)


def check_core(model: Model, original: frozenset[int], bound: int, packet: dict[str, Any]) -> None:
    original = model.belief(original)
    if not isinstance(packet, dict) or set(packet) != {'core', 'bound', 'losing', 'deletions'}:
        raise InvalidCertificate('invalid core packet')
    if type(packet['bound']) is not int or packet['bound'] != horizon(bound):
        raise InvalidCertificate('wrong core bound')
    core = model.belief(packet['core'])
    if not core <= original:
        raise InvalidCertificate('core is outside the original belief')
    if check(model, core, bound, packet['losing']) != 'lose':
        raise InvalidCertificate('core is winning')
    if not isinstance(packet['deletions'], dict) or set(packet['deletions']) != {str(w) for w in core}:
        raise InvalidCertificate('missing deletion certificate')
    for w in core:
        sub = core - {w}
        child = packet['deletions'][str(w)]
        if not sub:
            if child != {'empty': True}:
                raise InvalidCertificate('invalid empty restriction')
        elif check(model, sub, bound, child) != 'win':
            raise InvalidCertificate('core is not inclusion-minimal')
