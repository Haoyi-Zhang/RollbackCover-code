"""Independent small oracle: enumerate syntax, then execute on each world.

No use of belief predecessor, solver, certificates, or checker. The only shared
object is the immutable transition model. This independence is architectural,
not independent authorship or independent external review.
"""
from __future__ import annotations
from itertools import product
from functools import lru_cache
from model import Model

# A program is None (stop), or (action index, tuple of (observation, program)).


@lru_cache(maxsize=128)
def programs(alphabets: tuple[tuple[str, ...], ...], depth: int) -> tuple:
    if depth == 0:
        return (None,)
    smaller = programs(alphabets, depth - 1)
    result = [None]
    for ai, alphabet in enumerate(alphabets):
        for branches in product(smaller, repeat=len(alphabet)):
            result.append((ai, tuple(zip(alphabet, branches))))
    return tuple(result)


def execute(model: Model, world: int, program, remaining: int) -> bool:
    if world not in model.safe:
        return False
    if program is None:
        return world in model.goal
    if remaining == 0:
        return False
    ai, branches_tuple = program
    if not model.edges[ai][world]:
        return False
    branches = dict(branches_tuple)
    for obs, target in model.edges[ai][world]:
        if obs not in branches or not execute(model, target, branches[obs], remaining - 1):
            return False
    return True


def oracle(model: Model, initial: frozenset[int], depth: int) -> tuple[bool, int]:
    # Full observation alphabet, including outcomes not reachable from this query.
    alphabets = tuple(tuple(sorted({obs for row in matrix for obs, _ in row})) for matrix in model.edges)
    count = 0
    for program in programs(alphabets, depth):
        count += 1
        if all(execute(model, w, program, depth) for w in initial):
            return True, count
    return False, count
