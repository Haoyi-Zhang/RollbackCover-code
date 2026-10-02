"""Bounded belief synthesis; checker.py does not import this module."""
from __future__ import annotations
from model import Model, horizon
from typing import Any


class Solver:
    def __init__(self, model: Model) -> None:
        self.model = model
        self.cache: dict[tuple[frozenset[int], int], dict[str, Any]] = {}

    def solve(self, initial: frozenset[int], bound: int) -> dict[str, Any]:
        self.model.belief(initial)
        horizon(bound)
        return self._solve(initial, bound)

    def _solve(self, b: frozenset[int], k: int) -> dict[str, Any]:
        key = (b, k)
        if key in self.cache:
            return self.cache[key]
        node: dict[str, Any] = {'belief': sorted(b), 'rank': k}
        m = self.model
        if not b <= m.safe:
            node.update(kind='lose-unsafe', witness=min(b - m.safe))
        elif b <= m.goal:
            node.update(kind='win-stop')
        elif k == 0:
            node.update(kind='lose-horizon', witness=min(b - m.goal))
        else:
            refusals: dict[str, Any] = {}
            for ai, a in enumerate(m.actions):
                blocked = [w for w in b if not m.edges[ai][w]]
                if blocked:
                    refusals[a] = {'disabled': min(blocked)}
                    continue
                posts: dict[str, set[int]] = {}
                for w in b:
                    for obs, target in m.edges[ai][w]:
                        posts.setdefault(obs, set()).add(target)
                children = {obs: self._solve(frozenset(posts[obs]), k-1) for obs in sorted(posts)}
                if all(c['kind'].startswith('win-') for c in children.values()):
                    node.update(kind='win-step', action=a, branches=children)
                    break
                obs = next(o for o, child in children.items() if child['kind'].startswith('lose-'))
                refusals[a] = {'observation': obs, 'child': children[obs]}
            else:
                node.update(kind='lose-step', witness=min(b - m.goal), refusals=refusals)
        self.cache[key] = node
        return node


def is_winning(certificate: dict[str, Any]) -> bool:
    return certificate['kind'].startswith('win-')


def minimal_core(model: Model, initial: frozenset[int], bound: int) -> dict[str, Any]:
    """Deletion-minimal, NOT cardinality-minimum, losing initial-world subset."""
    solver = Solver(model)
    if is_winning(solver.solve(initial, bound)):
        raise ValueError('winning beliefs have no losing core')
    core = set(initial)
    for w in sorted(initial):
        candidate = frozenset(core - {w})
        if candidate and not is_winning(solver.solve(candidate, bound)):
            core.remove(w)
    b = frozenset(core)
    deletions = {}
    for w in sorted(b):
        sub = b - {w}
        # Empty restriction has no possible initial execution, hence vacuous success.
        deletions[str(w)] = {'empty': True} if not sub else solver.solve(sub, bound)
    return {'core': sorted(b), 'bound': bound, 'losing': solver.solve(b, bound), 'deletions': deletions}


def extract_program(certificate: dict[str, Any]) -> dict[str, Any]:
    if certificate['kind'] == 'win-stop':
        return {'stop': True}
    if certificate['kind'] == 'win-step':
        return {'action': certificate['action'], 'branches': {
            obs: extract_program(child) for obs, child in certificate['branches'].items()}}
    raise ValueError('only winning certificates extract to programs')
