"""A positive, acyclic update language with antichain provenance semantics.

The language describes projected deviations rather than ordinary packet
forwarding.  `New(i,p)` contributes p only when update atom i committed;
`Choice` combines packet classes or alternative bad traces.  The denotation in
the absorptive antichain semiring is compositional and its Boolean projection
agrees with the direct operational evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Union

from frontier import Frontier, bits, one, plus, times, variable, zero


@dataclass(frozen=True)
class Allow:
    pass


@dataclass(frozen=True)
class Drop:
    pass


@dataclass(frozen=True)
class New:
    variable: int
    body: "Expr"


@dataclass(frozen=True)
class Choice:
    branches: tuple["Expr", ...]


Expr = Union[Allow, Drop, New, Choice]


def validate(expr: Expr, width: int) -> None:
    if isinstance(expr, (Allow, Drop)):
        return
    if isinstance(expr, New):
        if type(expr.variable) is not int or not 0 <= expr.variable < width:
            raise ValueError("update guard outside declared width")
        validate(expr.body, width)
        return
    if isinstance(expr, Choice):
        for branch in expr.branches:
            validate(branch, width)
        return
    raise ValueError("unknown update-language term")


def denote(expr: Expr, width: int) -> Frontier:
    validate(expr, width)
    if isinstance(expr, Allow):
        return zero()
    if isinstance(expr, Drop):
        return one()
    if isinstance(expr, New):
        return times(variable(expr.variable, width), denote(expr.body, width), width=width)
    if isinstance(expr, Choice):
        result = zero()
        for branch in expr.branches:
            result = plus(result, denote(branch, width), width=width)
        return result
    raise AssertionError("validated expression has unknown type")


def evaluate(expr: Expr, commit_mask: int, width: int) -> bool:
    """Return True exactly when a projected deviation is produced."""
    validate(expr, width)
    if type(commit_mask) is not int or not 0 <= commit_mask < (1 << width):
        raise ValueError("commit mask outside declared width")
    if isinstance(expr, Allow):
        return False
    if isinstance(expr, Drop):
        return True
    if isinstance(expr, New):
        return bool(commit_mask & (1 << expr.variable)) and evaluate(expr.body, commit_mask, width)
    if isinstance(expr, Choice):
        return any(evaluate(branch, commit_mask, width) for branch in expr.branches)
    raise AssertionError("validated expression has unknown type")


def guard_chain(edge: int) -> Expr:
    body: Expr = Drop()
    for variable_index in reversed(bits(edge)):
        body = New(variable_index, body)
    return body


def compile_frontier(frontier: Iterable[int]) -> Expr:
    return Choice(tuple(guard_chain(edge) for edge in frontier))


def node_count(expr: Expr) -> int:
    if isinstance(expr, (Allow, Drop)):
        return 1
    if isinstance(expr, New):
        return 1 + node_count(expr.body)
    if isinstance(expr, Choice):
        return 1 + sum(node_count(branch) for branch in expr.branches)
    raise ValueError("unknown update-language term")
