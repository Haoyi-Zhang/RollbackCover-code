"""Antichain provenance for relational rollback frontiers.

A frontier is an inclusion-antichain of bit masks.  Each mask denotes a
minimal set of new-rule commits that can produce a projected trace deviation.
The operations form the finite absorptive (Sperner-family) semiring used by the
monotone update language in forwarding.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import Iterable, Iterator, Sequence

Mask = int
Frontier = tuple[Mask, ...]


def bits(mask: Mask) -> tuple[int, ...]:
    if type(mask) is not int or mask < 0:
        raise ValueError("mask must be a nonnegative integer")
    return tuple(i for i in range(mask.bit_length()) if mask & (1 << i))


def is_subset(left: Mask, right: Mask) -> bool:
    return left & ~right == 0


def minimize(masks: Iterable[Mask], *, width: int | None = None) -> Frontier:
    values = set()
    limit = None if width is None else (1 << width) - 1
    if width is not None and (type(width) is not int or width < 0 or width > 128):
        raise ValueError("width must be an integer in [0,128]")
    for mask in masks:
        if type(mask) is not int or mask < 0:
            raise ValueError("frontier masks must be nonnegative integers")
        if limit is not None and mask & ~limit:
            raise ValueError("frontier mask exceeds declared width")
        values.add(mask)
    ordered = sorted(values, key=lambda x: (x.bit_count(), x))
    kept: list[int] = []
    for mask in ordered:
        if not any(is_subset(other, mask) for other in kept):
            kept.append(mask)
    return tuple(kept)


def valid(frontier: Sequence[Mask], width: int) -> bool:
    try:
        return tuple(frontier) == minimize(frontier, width=width)
    except ValueError:
        return False


def plus(left: Sequence[Mask], right: Sequence[Mask], *, width: int | None = None) -> Frontier:
    """Alternative deviation proofs: antichain union."""
    return minimize((*left, *right), width=width)


def times(left: Sequence[Mask], right: Sequence[Mask], *, width: int | None = None) -> Frontier:
    """Joint deviation requirements: pairwise set union with absorption."""
    if not left or not right:
        return ()
    return minimize((a | b for a in left for b in right), width=width)


def zero() -> Frontier:
    """No deviation witness."""
    return ()


def one() -> Frontier:
    """An unconditional deviation witness."""
    return (0,)


def variable(index: int, width: int) -> Frontier:
    if type(index) is not int or not 0 <= index < width:
        raise ValueError("variable index outside declared width")
    return (1 << index,)


def product(parts: Iterable[Sequence[Mask]], *, width: int | None = None) -> Frontier:
    return reduce(lambda a, b: times(a, b, width=width), parts, one())


def sum_frontiers(parts: Iterable[Sequence[Mask]], *, width: int | None = None) -> Frontier:
    return reduce(lambda a, b: plus(a, b, width=width), parts, zero())


def deviates(frontier: Sequence[Mask], commit_mask: Mask) -> bool:
    """Positive semantics: a deviation occurs when one minimal cause is present."""
    if type(commit_mask) is not int or commit_mask < 0:
        raise ValueError("commit mask must be a nonnegative integer")
    return any(is_subset(edge, commit_mask) for edge in frontier)


def hits(frontier: Sequence[Mask], support: Mask) -> bool:
    """Whether a reset support intersects every minimal deviation set."""
    if type(support) is not int or support < 0:
        raise ValueError("support must be a nonnegative integer")
    return all(edge & support for edge in frontier)


def residual(frontier: Sequence[Mask], chosen_variable: int) -> Frontier:
    """Edges not yet hit after choosing one reset variable."""
    bit = 1 << chosen_variable
    return tuple(edge for edge in frontier if not (edge & bit))


def is_interval(mask: Mask) -> bool:
    if mask <= 0:
        return False
    lo = (mask & -mask).bit_length() - 1
    hi = mask.bit_length() - 1
    return mask == ((1 << (hi - lo + 1)) - 1) << lo


def all_intervals(frontier: Sequence[Mask]) -> bool:
    return all(is_interval(edge) for edge in frontier)


def enumerate_antichains(width: int, *, exclude_empty_cause: bool = False) -> Iterator[Frontier]:
    """Enumerate every antichain of subsets of a small ground set.

    The include branch removes all comparable masks, so each antichain is
    generated exactly once.  This is intended for width <= 5 exhaustive tests.
    """
    if type(width) is not int or not 0 <= width <= 6:
        raise ValueError("exhaustive antichain enumeration supports width in [0,6]")
    universe = tuple(range(1 << width))

    def visit(available: tuple[int, ...], selected: tuple[int, ...]) -> Iterator[Frontier]:
        if not available:
            result = minimize(selected, width=width)
            if not (exclude_empty_cause and 0 in result):
                yield result
            return
        head = available[0]
        yield from visit(available[1:], selected)
        rest = tuple(x for x in available[1:] if not (is_subset(x, head) or is_subset(head, x)))
        yield from visit(rest, selected + (head,))

    yield from visit(universe, ())


@dataclass(frozen=True)
class FrontierStats:
    width: int
    edges: int
    maximum_edge_width: int
    variables_used: int


def statistics(frontier: Sequence[Mask], width: int) -> FrontierStats:
    if not valid(frontier, width):
        raise ValueError("frontier is not a normalized antichain")
    union = 0
    for edge in frontier:
        union |= edge
    return FrontierStats(width, len(frontier), max((e.bit_count() for e in frontier), default=0), union.bit_count())
