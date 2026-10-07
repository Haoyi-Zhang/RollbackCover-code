"""Exact rollback-support synthesis and independently replayable certificates."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable, Sequence

from frontier import Frontier, all_intervals, bits, hits, is_interval, minimize, residual, valid


class InvalidSupportCertificate(ValueError):
    pass


@dataclass
class SearchMetrics:
    decision_nodes: int = 0
    proof_nodes: int = 0
    reductions: int = 0


def mask_from_variables(values: Iterable[int], width: int) -> int:
    mask = 0
    seen = set()
    for value in values:
        if type(value) is not int or not 0 <= value < width:
            raise ValueError("variable outside declared width")
        if value in seen:
            raise ValueError("duplicate variable")
        seen.add(value)
        mask |= 1 << value
    return mask


def variables_from_mask(mask: int) -> list[int]:
    return list(bits(mask))


def _remove_hit(frontier: Sequence[int], variable: int) -> Frontier:
    bit = 1 << variable
    return tuple(edge for edge in frontier if not edge & bit)


def _forced_reduce(frontier: Frontier, chosen: int, budget: int, metrics: SearchMetrics) -> tuple[Frontier, int, int] | None:
    current = frontier
    support = chosen
    remaining = budget
    while True:
        if 0 in current:
            return None
        singletons = sorted({edge.bit_length() - 1 for edge in current if edge.bit_count() == 1})
        if not singletons:
            return current, support, remaining
        for variable in singletons:
            bit = 1 << variable
            if support & bit:
                continue
            support |= bit
            remaining -= 1
            metrics.reductions += 1
            if remaining < 0:
                return None
            current = _remove_hit(current, variable)


def greedy_support(frontier: Sequence[int], width: int) -> int:
    f = minimize(frontier, width=width)
    if 0 in f:
        raise ValueError("unconditional deviation is unrecoverable")
    support = 0
    remaining = f
    while remaining:
        candidates = set(v for edge in remaining for v in bits(edge))
        variable = min(candidates, key=lambda v: (-sum(bool(edge & (1 << v)) for edge in remaining), v))
        support |= 1 << variable
        remaining = _remove_hit(remaining, variable)
    return support


def interval_support(frontier: Sequence[int], width: int) -> int:
    f = minimize(frontier, width=width)
    if 0 in f or not all_intervals(f):
        raise ValueError("frontier is not a family of nonempty intervals")
    support = 0
    intervals = sorted(f, key=lambda edge: (edge.bit_length() - 1, (edge & -edge).bit_length() - 1))
    for edge in intervals:
        if not edge & support:
            right = edge.bit_length() - 1
            support |= 1 << right
    return support


def _packing(frontier: Sequence[int]) -> tuple[int, ...]:
    return _packing_canonical(sorted(frontier, key=lambda e: (e.bit_count(), e)))


def _packing_canonical(frontier: Sequence[int]) -> tuple[int, ...]:
    """Pack a canonical frontier; filtering hit edges preserves its order."""
    chosen: list[int] = []
    used = 0
    for edge in frontier:
        if not edge & used:
            chosen.append(edge)
            used |= edge
    return tuple(chosen)


def _decision(frontier: Frontier, width: int, budget: int, metrics: SearchMetrics, memo: dict[tuple[Frontier, int], int | None]) -> int | None:
    metrics.decision_nodes += 1
    key = (frontier, budget)
    if key in memo:
        return memo[key]
    reduced = _forced_reduce(frontier, 0, budget, metrics)
    if reduced is None:
        memo[key] = None
        return None
    current, forced, remaining = reduced
    if not current:
        memo[key] = forced
        return forced
    if remaining <= 0 or len(_packing_canonical(current)) > remaining:
        memo[key] = None
        return None
    edge = min(current, key=lambda e: (e.bit_count(), e))
    candidates = sorted(bits(edge), key=lambda v: (-sum(bool(other & (1 << v)) for other in current), v))
    for variable in candidates:
        child = _decision(_remove_hit(current, variable), width, remaining - 1, metrics, memo)
        if child is not None:
            result = forced | (1 << variable) | child
            memo[key] = result
            return result
    memo[key] = None
    return None


def find_support(frontier: Sequence[int], width: int, budget: int, *, metrics: SearchMetrics | None = None) -> int | None:
    if type(budget) is not int or budget < 0:
        raise ValueError("budget must be a nonnegative integer")
    f = minimize(frontier, width=width)
    m = metrics if metrics is not None else SearchMetrics()
    support = _decision(f, width, budget, m, {})
    if support is not None and support.bit_count() > budget:
        raise AssertionError("internal solver returned an oversized support")
    return support


def optimal_support(frontier: Sequence[int], width: int, *, metrics: SearchMetrics | None = None) -> int:
    f = minimize(frontier, width=width)
    if 0 in f:
        raise ValueError("unconditional deviation has no rollback support")
    m = metrics if metrics is not None else SearchMetrics()
    upper = greedy_support(f, width).bit_count() if f else 0
    lower = len(_packing_canonical(f))
    for budget in range(lower, upper + 1):
        candidate = find_support(f, width, budget, metrics=m)
        if candidate is not None:
            return candidate
    raise AssertionError("full reset support should hit every nonempty edge")


def brute_force_support(frontier: Sequence[int], width: int) -> int:
    f = minimize(frontier, width=width)
    if 0 in f:
        raise ValueError("unconditional deviation has no rollback support")
    for size in range(width + 1):
        for values in combinations(range(width), size):
            mask = sum(1 << v for v in values)
            if hits(f, mask):
                return mask
    raise AssertionError("full support must work")


def _negative_proof(frontier: Frontier, budget: int, metrics: SearchMetrics) -> dict[str, Any] | None:
    metrics.proof_nodes += 1
    if not frontier:
        return None
    if 0 in frontier:
        return {"kind": "unconditional", "edge": []}
    packing = _packing_canonical(frontier)
    if len(packing) > budget:
        return {"kind": "packing", "edges": [variables_from_mask(e) for e in packing]}
    if budget == 0:
        edge = min(frontier, key=lambda e: (e.bit_count(), e))
        return {"kind": "zero-budget", "edge": variables_from_mask(edge)}
    edge = min(frontier, key=lambda e: (e.bit_count(), e))
    children: dict[str, Any] = {}
    for variable in bits(edge):
        child = _negative_proof(_remove_hit(frontier, variable), budget - 1, metrics)
        if child is None:
            return None
        children[str(variable)] = child
    return {"kind": "branch", "edge": variables_from_mask(edge), "children": children}


def make_optimality_certificate(frontier: Sequence[int], width: int) -> dict[str, Any]:
    f = minimize(frontier, width=width)
    metrics = SearchMetrics()
    support = optimal_support(f, width, metrics=metrics)
    optimum = support.bit_count()
    lower = None if optimum == 0 else _negative_proof(f, optimum - 1, metrics)
    if optimum > 0 and lower is None:
        raise AssertionError("failed to construct complete lower-bound proof")
    return {
        "width": width,
        "frontier": [variables_from_mask(e) for e in f],
        "support": variables_from_mask(support),
        "optimum": optimum,
        "lower_bound_budget": optimum - 1,
        "lower_bound": lower,
        "metrics": {
            "decision_nodes": metrics.decision_nodes,
            "proof_nodes": metrics.proof_nodes,
            "forced_reductions": metrics.reductions,
        },
    }


def _parse_frontier(values: Any, width: int) -> Frontier:
    if not isinstance(values, list):
        raise InvalidSupportCertificate("frontier must be a list")
    masks = []
    for edge in values:
        if not isinstance(edge, list):
            raise InvalidSupportCertificate("each frontier edge must be a list")
        try:
            masks.append(mask_from_variables(edge, width))
        except ValueError as exc:
            raise InvalidSupportCertificate(str(exc)) from exc
    f = tuple(masks)
    if not valid(f, width):
        raise InvalidSupportCertificate("frontier is not a normalized antichain")
    return f


def _check_negative(frontier: Frontier, budget: int, proof: Any, width: int) -> int:
    if not isinstance(proof, dict) or not isinstance(proof.get("kind"), str):
        raise InvalidSupportCertificate("malformed negative proof")
    kind = proof["kind"]
    if kind == "unconditional":
        if set(proof) != {"kind", "edge"} or proof["edge"] != [] or 0 not in frontier:
            raise InvalidSupportCertificate("invalid unconditional leaf")
        return 1
    if kind == "zero-budget":
        if set(proof) != {"kind", "edge"} or budget != 0:
            raise InvalidSupportCertificate("invalid zero-budget leaf")
        edge = mask_from_variables(proof["edge"], width)
        if edge not in frontier or edge == 0:
            raise InvalidSupportCertificate("zero-budget witness is not a remaining edge")
        return 1
    if kind == "packing":
        if set(proof) != {"kind", "edges"} or not isinstance(proof["edges"], list):
            raise InvalidSupportCertificate("malformed packing leaf")
        edges = [mask_from_variables(edge, width) for edge in proof["edges"]]
        if len(edges) <= budget or any(edge not in frontier or edge == 0 for edge in edges):
            raise InvalidSupportCertificate("packing does not exceed the budget")
        used = 0
        for edge in edges:
            if edge & used:
                raise InvalidSupportCertificate("packing edges are not pairwise disjoint")
            used |= edge
        return 1
    if kind == "branch":
        if set(proof) != {"kind", "edge", "children"} or budget <= 0 or not isinstance(proof["children"], dict):
            raise InvalidSupportCertificate("malformed branch proof")
        edge = mask_from_variables(proof["edge"], width)
        if edge not in frontier or edge == 0:
            raise InvalidSupportCertificate("branch edge is not a remaining edge")
        expected = {str(v) for v in bits(edge)}
        if set(proof["children"]) != expected:
            raise InvalidSupportCertificate("branch children do not cover every possible chosen reset")
        nodes = 1
        for variable in bits(edge):
            nodes += _check_negative(_remove_hit(frontier, variable), budget - 1, proof["children"][str(variable)], width)
        return nodes
    raise InvalidSupportCertificate("unknown negative-proof kind")


def check_optimality_certificate(packet: Any, *, expected_frontier: Sequence[int] | None = None, expected_width: int | None = None) -> dict[str, int]:
    if not isinstance(packet, dict) or set(packet) != {
        "width", "frontier", "support", "optimum", "lower_bound_budget", "lower_bound", "metrics"
    }:
        raise InvalidSupportCertificate("unexpected certificate keys")
    width = packet["width"]
    if type(width) is not int or not 0 <= width <= 128:
        raise InvalidSupportCertificate("invalid width")
    if expected_width is not None and width != expected_width:
        raise InvalidSupportCertificate("certificate width differs from instance")
    frontier = _parse_frontier(packet["frontier"], width)
    if expected_frontier is not None and frontier != minimize(expected_frontier, width=width):
        raise InvalidSupportCertificate("certificate frontier differs from instance")
    try:
        support = mask_from_variables(packet["support"], width)
    except ValueError as exc:
        raise InvalidSupportCertificate(str(exc)) from exc
    optimum = packet["optimum"]
    if type(optimum) is not int or optimum != support.bit_count() or not hits(frontier, support):
        raise InvalidSupportCertificate("positive support is invalid")
    budget = packet["lower_bound_budget"]
    if type(budget) is not int or budget != optimum - 1:
        raise InvalidSupportCertificate("lower-bound budget does not establish optimality")
    if optimum == 0:
        if frontier or packet["lower_bound"] is not None:
            raise InvalidSupportCertificate("zero optimum requires an empty frontier and no lower proof")
        nodes = 0
    else:
        nodes = _check_negative(frontier, budget, packet["lower_bound"], width)
    if not isinstance(packet["metrics"], dict):
        raise InvalidSupportCertificate("metrics field must be an object")
    return {"width": width, "frontier_edges": len(frontier), "optimum": optimum, "checked_lower_nodes": nodes}


def support_program(support_mask: int) -> dict[str, Any]:
    return {"kind": "blind-reset", "order": variables_from_mask(support_mask)}


def normalize_program(program: Any, width: int) -> int:
    if not isinstance(program, dict) or set(program) != {"kind", "order"} or program["kind"] != "blind-reset":
        raise ValueError("program must be a blind-reset object")
    if not isinstance(program["order"], list):
        raise ValueError("program order must be a list")
    support = 0
    for variable in program["order"]:
        if type(variable) is not int or not 0 <= variable < width:
            raise ValueError("program reset outside width")
        support |= 1 << variable
    return support
