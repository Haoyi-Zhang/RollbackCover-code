"""Generic ambiguity-robust rollback boundary for finite update batches.

A truth table records *good* commit sets.  Bit ``h`` is one exactly when the
configuration in which update atoms in mask ``h`` committed satisfies the
relational goal.  Resetting support ``r`` maps a hidden state ``h`` to
``h & ~r``.  The central collapse used by the paper is exact precisely when
``good`` is downward closed (equivalently, deviation is upward closed).
"""
from __future__ import annotations

from itertools import combinations
from typing import Iterable

from frontier import Frontier, hits, minimize


def _validate(width: int, good_table: int) -> int:
    if type(width) is not int or not 0 <= width <= 6:
        raise ValueError("truth-table utilities support width in [0,6]")
    if type(good_table) is not int or good_table < 0:
        raise ValueError("good table must be a nonnegative integer")
    states = 1 << width
    if good_table >> states:
        raise ValueError("good table exceeds declared width")
    return states


def is_good(good_table: int, state: int, width: int) -> bool:
    states = _validate(width, good_table)
    if type(state) is not int or not 0 <= state < states:
        raise ValueError("state outside declared width")
    return bool(good_table & (1 << state))


def table_from_good(states: Iterable[int], width: int) -> int:
    limit = 1 << width
    table = 0
    for state in states:
        if type(state) is not int or not 0 <= state < limit:
            raise ValueError("state outside declared width")
        table |= 1 << state
    _validate(width, table)
    return table


def downward_closed(good_table: int, width: int) -> bool:
    states = _validate(width, good_table)
    for state in range(states):
        if not is_good(good_table, state, width):
            continue
        subset = state
        while True:
            if not is_good(good_table, subset, width):
                return False
            if subset == 0:
                break
            subset = (subset - 1) & state
    return True


def endpoint_correct(good_table: int, width: int, support: int) -> bool:
    states = _validate(width, good_table)
    if type(support) is not int or not 0 <= support < states:
        raise ValueError("support outside declared width")
    full = states - 1
    return is_good(good_table, full & ~support, width)


def robust_correct(good_table: int, width: int, support: int) -> bool:
    states = _validate(width, good_table)
    if type(support) is not int or not 0 <= support < states:
        raise ValueError("support outside declared width")
    return all(is_good(good_table, hidden & ~support, width) for hidden in range(states))


def endpoint_robust_equivalent(good_table: int, width: int) -> bool:
    states = _validate(width, good_table)
    return all(endpoint_correct(good_table, width, support) == robust_correct(good_table, width, support)
               for support in range(states))


def bad_frontier(good_table: int, width: int) -> Frontier:
    states = _validate(width, good_table)
    return minimize((state for state in range(states) if not is_good(good_table, state, width)), width=width)


def boundary_witness(good_table: int, width: int) -> tuple[int, int, int] | None:
    """Return (good_endpoint, bad_subset, support) when downward closure fails."""
    states = _validate(width, good_table)
    full = states - 1
    for endpoint in range(states):
        if not is_good(good_table, endpoint, width):
            continue
        subset = endpoint
        while True:
            if not is_good(good_table, subset, width):
                support = full & ~endpoint
                if not endpoint_correct(good_table, width, support) or robust_correct(good_table, width, support):
                    raise AssertionError("constructed boundary witness is inconsistent")
                return endpoint, subset, support
            if subset == 0:
                break
            subset = (subset - 1) & endpoint
    return None


def minimum_state_repair(frontier: Frontier, width: int, hidden: int) -> int:
    """Minimum number of resets with perfect knowledge of one hidden state."""
    if type(hidden) is not int or not 0 <= hidden < (1 << width):
        raise ValueError("hidden state outside declared width")
    variables = [i for i in range(width) if hidden & (1 << i)]
    for size in range(len(variables) + 1):
        for choice in combinations(variables, size):
            support = sum(1 << i for i in choice)
            if not any((edge & (hidden & ~support)) == edge for edge in frontier):
                return support
    raise AssertionError("resetting every committed update must remove every nonempty cause")


def perfect_observation_worst_case(frontier: Frontier, width: int) -> int:
    """Worst reset count of an oracle that knows the exact hidden state."""
    return max(minimum_state_repair(frontier, width, hidden).bit_count()
               for hidden in range(1 << width))


def available_recovery(frontier: Frontier, available_support: int, width: int) -> tuple[bool, int | None]:
    """Check whether available reset commands hit every frontier edge.

    Returns a disjoint minimal cause as a complete unrecoverability witness.
    """
    if type(available_support) is not int or not 0 <= available_support < (1 << width):
        raise ValueError("available support outside declared width")
    for edge in frontier:
        if edge & available_support == 0:
            return False, edge
    return True, None
