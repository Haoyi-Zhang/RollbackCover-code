"""Deterministic experiments for relational rollback frontiers."""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

from forwarding import ChainNetwork, frontier_deviates, trace_deviates
from frontier import all_intervals, enumerate_antichains, hits, minimize, statistics
from update_language import compile_frontier, denote, evaluate
from robustness import bad_frontier, downward_closed, endpoint_correct, endpoint_robust_equivalent, robust_correct
from support import (
    SearchMetrics,
    brute_force_support,
    check_optimality_certificate,
    greedy_support,
    interval_support,
    make_optimality_certificate,
    optimal_support,
)


def _measurement(start_wall: float, start_cpu: float) -> dict[str, float]:
    return {"wall_seconds": time.monotonic() - start_wall, "cpu_seconds": time.process_time() - start_cpu}


def exhaustive(width: int, out: Path, chunk: int = 0, chunks: int = 1) -> dict:
    start_wall, start_cpu = time.monotonic(), time.process_time()
    frontiers = support_checks = hidden_replays = interval_frontiers = 0
    optimum_hist: dict[str, int] = {}
    max_edges = max_certificate_bytes = 0
    rows = []
    if type(chunks) is not int or chunks <= 0 or type(chunk) is not int or not 0 <= chunk < chunks:
        raise ValueError("invalid exhaustive chunk selection")
    for index, frontier in enumerate(enumerate_antichains(width, exclude_empty_cause=True)):
        if index % chunks != chunk:
            continue
        # enumerate_antichains includes the empty frontier and excludes {empty set}.
        network = ChainNetwork.from_hypergraph(width, frontier)
        expression = compile_frontier(frontier)
        if denote(expression, width) != frontier:
            raise AssertionError("compositional antichain denotation differs from frontier")
        if network.symbolic_frontier() != network.enumerate_frontier():
            raise AssertionError("symbolic and trace-enumerated frontiers differ")
        for hidden in range(1 << width):
            trace_value = trace_deviates(network, hidden)
            if trace_value != frontier_deviates(network, hidden) or trace_value != evaluate(expression, hidden, width):
                raise AssertionError("trace/language/provenance deviation mismatch")
        brute = brute_force_support(frontier, width)
        packet = make_optimality_certificate(frontier, width)
        checked = check_optimality_certificate(packet, expected_frontier=frontier, expected_width=width)
        exact = sum(1 << v for v in packet["support"])
        if exact.bit_count() != brute.bit_count() or checked["optimum"] != brute.bit_count():
            raise AssertionError("exact support differs from brute force")
        if all_intervals(frontier):
            interval_frontiers += 1
            if interval_support(frontier, width).bit_count() != brute.bit_count():
                raise AssertionError("interval greedy is not optimal")
        for support in range(1 << width):
            semantic = network.endpoint_correct_by_cube(support)
            theorem = hits(frontier, support)
            if semantic != theorem or semantic != network.endpoint_correct(support):
                raise AssertionError("rollback transversal theorem falsified")
            support_checks += 1
            hidden_replays += 1 << width
            # Every reset order is regression-free; one canonical order suffices
            # here because the proof covers permutations and unit tests mutate it.
            if theorem and not network.regression_free((1 << width) - 1, [v for v in range(width) if support & (1 << v)]):
                raise AssertionError("canonical rollback order introduced a new deviation")
        stats = statistics(frontier, width)
        encoded = len((json.dumps(packet, sort_keys=True) + "\n").encode())
        max_certificate_bytes = max(max_certificate_bytes, encoded)
        max_edges = max(max_edges, stats.edges)
        optimum_hist[str(brute.bit_count())] = optimum_hist.get(str(brute.bit_count()), 0) + 1
        rows.append([index, stats.edges, stats.maximum_edge_width, int(all_intervals(frontier)), brute.bit_count(), encoded])
        frontiers += 1
    suffix = "" if chunks == 1 else f"-chunk-{chunk:02d}-of-{chunks:02d}"
    with (out / f"frontier-exhaustive-{width}{suffix}.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frontier_index", "edges", "max_edge_width", "interval", "optimum", "certificate_bytes"])
        writer.writerows(rows)
    result = {
        "suite": "all-proper-antichains",
        "update_atoms": width,
        "chunk": chunk,
        "chunks": chunks,
        "frontiers": frontiers,
        "support_checks": support_checks,
        "hidden_state_replays": hidden_replays,
        "interval_frontiers": interval_frontiers,
        "maximum_frontier_edges": max_edges,
        "maximum_certificate_bytes": max_certificate_bytes,
        "optimum_histogram": optimum_hist,
        "mismatches": 0,
        "measurements": _measurement(start_wall, start_cpu),
    }
    (out / f"frontier-exhaustive-{width}{suffix}-measurement.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def predicate_boundary(width: int, out: Path) -> dict:
    """Exhaust every finite goal predicate with a good all-old reference.

    This is an exact negative control for the monotonicity assumption: endpoint
    repair collapses to ambiguity-robust repair for every reset support exactly
    for downward-closed good predicates.
    """
    if type(width) is not int or not 0 <= width <= 4:
        raise ValueError("predicate boundary campaign supports width in [0,4]")
    start_wall, start_cpu = time.monotonic(), time.process_time()
    states = 1 << width
    predicates = downward = nonmonotone = support_checks = transversal_checks = 0
    first_counterexample = None
    # Bit zero is fixed to one: the all-old reference is required to satisfy the goal.
    for tail in range(1 << (states - 1)):
        table = 1 | (tail << 1)
        closure = downward_closed(table, width)
        collapse = endpoint_robust_equivalent(table, width)
        if closure != collapse:
            raise AssertionError("downward closure characterization falsified")
        predicates += 1
        support_checks += states
        if closure:
            downward += 1
            frontier = bad_frontier(table, width)
            for support in range(states):
                semantic = robust_correct(table, width, support)
                theorem = hits(frontier, support)
                if semantic != theorem or semantic != endpoint_correct(table, width, support):
                    raise AssertionError("frontier transversal characterization falsified")
                transversal_checks += 1
        else:
            nonmonotone += 1
            if first_counterexample is None:
                for support in range(states):
                    if endpoint_correct(table, width, support) and not robust_correct(table, width, support):
                        full = states - 1
                        endpoint = full & ~support
                        bad = next(hidden & ~support for hidden in range(states)
                                   if not ((table >> (hidden & ~support)) & 1))
                        first_counterexample = {
                            "good_endpoint": endpoint,
                            "bad_reachable_subset": bad,
                            "support": support,
                        }
                        break
    result = {
        "suite": "all-goal-predicates-with-good-reference",
        "update_atoms": width,
        "predicates": predicates,
        "downward_closed_predicates": downward,
        "nonmonotone_predicates": nonmonotone,
        "endpoint_robust_support_checks": support_checks,
        "transversal_support_checks": transversal_checks,
        "first_nonmonotone_counterexample": first_counterexample,
        "mismatches": 0,
        "measurements": _measurement(start_wall, start_cpu),
    }
    (out / f"frontier-boundary-{width}-measurement.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def _structured_instances() -> Iterable[tuple[str, int, tuple[int, ...], int]]:
    # family, width, frontier, seed.  Seed -1 marks a closed-form construction.
    for width in (8, 12, 16, 20, 24):
        shared = tuple((1 << 0) | (1 << i) | (1 << ((i % (width - 1)) + 1)) for i in range(1, width))
        yield "shared", width, minimize(shared, width=width), -1
    for width in (6, 9, 12, 15, 18, 21, 24):
        disjoint = tuple(sum(1 << (start + j) for j in range(3)) for start in range(0, width, 3))
        yield "disjoint", width, minimize(disjoint, width=width), -1
    for width in (16, 24, 32, 48, 64):
        intervals = []
        for left in range(0, width, 3):
            right = min(width - 1, left + 2 + (left // 3) % 5)
            intervals.append(((1 << (right - left + 1)) - 1) << left)
        for right in range(5, width, 7):
            left = max(0, right - 5)
            intervals.append(((1 << (right - left + 1)) - 1) << left)
        yield "interval", width, minimize(intervals, width=width), -1
    for width in (8, 10, 12, 14):
        complete3 = tuple(sum(1 << v for v in choice) for choice in __import__("itertools").combinations(range(width), 3))
        yield "complete-3", width, minimize(complete3, width=width), -1
    for width in (12, 16, 20, 24):
        for seed in range(20):
            rng = random.Random(10_000 * width + seed)
            edges = set()
            while len(edges) < 2 * width:
                size = 2 + rng.randrange(4)
                values = rng.sample(range(width), min(size, width))
                edges.add(sum(1 << value for value in values))
            yield "random", width, minimize(edges, width=width), seed


def benchmarks(out: Path) -> dict:
    start_wall, start_cpu = time.monotonic(), time.process_time()
    rows = []
    solved = greedy_optimal = interval_instances = 0
    max_nodes = max_proof_nodes = max_certificate_bytes = 0
    solver_wall_seconds = 0.0
    for family, width, frontier, seed in _structured_instances():
        metrics = SearchMetrics()
        wall = time.monotonic()
        exact = optimal_support(frontier, width, metrics=metrics)
        elapsed = time.monotonic() - wall
        solver_wall_seconds += elapsed
        greedy = greedy_support(frontier, width)
        packet = make_optimality_certificate(frontier, width)
        checked = check_optimality_certificate(packet, expected_frontier=frontier, expected_width=width)
        interval = interval_support(frontier, width) if all_intervals(frontier) else None
        if interval is not None and interval.bit_count() != exact.bit_count():
            raise AssertionError("interval solver disagrees with exact solver")
        network = ChainNetwork.from_hypergraph(width, frontier)
        if not network.endpoint_correct(exact) or not hits(frontier, exact):
            raise AssertionError("reported support is not rollback-correct")
        if width <= 14 and brute_force_support(frontier, width).bit_count() != exact.bit_count():
            raise AssertionError("benchmark exact solver disagrees with brute force")
        proof_nodes = packet["metrics"]["proof_nodes"]
        cert_bytes = len((json.dumps(packet, sort_keys=True) + "\n").encode())
        rows.append({
            "family": family,
            "seed": seed,
            "updates": width,
            "frontier_edges": len(frontier),
            "maximum_edge_width": max((e.bit_count() for e in frontier), default=0),
            "full_log": width,
            "greedy": greedy.bit_count(),
            "optimum": exact.bit_count(),
            "interval": "" if interval is None else interval.bit_count(),
            "decision_nodes": metrics.decision_nodes,
            "forced_reductions": metrics.reductions,
            "proof_nodes": proof_nodes,
            "certificate_bytes": cert_bytes,
        })
        solved += 1
        greedy_optimal += greedy.bit_count() == exact.bit_count()
        interval_instances += interval is not None
        max_nodes = max(max_nodes, metrics.decision_nodes)
        max_proof_nodes = max(max_proof_nodes, proof_nodes)
        max_certificate_bytes = max(max_certificate_bytes, cert_bytes)
    path = out / "frontier-benchmarks.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    result = {
        "suite": "deterministic-rollback-frontiers",
        "instances": solved,
        "families": sorted({row["family"] for row in rows}),
        "greedy_optimal_instances": greedy_optimal,
        "interval_instances": interval_instances,
        "maximum_decision_nodes": max_nodes,
        "maximum_proof_nodes": max_proof_nodes,
        "maximum_certificate_bytes": max_certificate_bytes,
        "mismatches": 0,
        "measurements": {**_measurement(start_wall, start_cpu), "solver_wall_seconds": solver_wall_seconds},
    }
    (out / "frontier-benchmarks-measurement.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def _checked_exhaustive_chunks(out: Path, chunks: int) -> list[dict]:
    """Bind reported exhaustive counts to the complete, disjoint row domain."""
    if type(chunks) is not int or not 1 <= chunks <= 7580:
        raise ValueError("invalid width-five chunk count")
    measurements = []
    for chunk in range(chunks):
        path = out / f"frontier-exhaustive-5-chunk-{chunk:02d}-of-{chunks:02d}-measurement.json"
        data = json.loads(path.read_text())
        if (data.get("suite"), data.get("update_atoms"), data.get("chunk"), data.get("chunks")) != (
                "all-proper-antichains", 5, chunk, chunks):
            raise ValueError("exhaustive chunk identity differs from its assigned domain")
        csv_path = out / f"frontier-exhaustive-5-chunk-{chunk:02d}-of-{chunks:02d}.csv"
        with csv_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        indices = [int(row["frontier_index"]) for row in rows]
        if indices != list(range(chunk, 7580, chunks)):
            raise ValueError("exhaustive indices are missing, duplicated, or assigned to the wrong chunk")
        expected = {
            "frontiers": len(rows),
            "support_checks": 32 * len(rows),
            "hidden_state_replays": 1024 * len(rows),
            "interval_frontiers": sum(int(row["interval"]) for row in rows),
            "maximum_frontier_edges": max(int(row["edges"]) for row in rows),
            "maximum_certificate_bytes": max(int(row["certificate_bytes"]) for row in rows),
            "optimum_histogram": dict(Counter(row["optimum"] for row in rows)),
            "mismatches": 0,
        }
        if any(data.get(key) != value for key, value in expected.items()):
            raise ValueError("exhaustive measurement disagrees with its scientific rows")
        measurements.append(data)
    return measurements


def summarize(out: Path, chunks: int = 8) -> dict:
    measurements = _checked_exhaustive_chunks(out, chunks)
    exhaustive_data = {
        "frontiers": sum(x["frontiers"] for x in measurements),
        "support_checks": sum(x["support_checks"] for x in measurements),
        "hidden_state_replays": sum(x["hidden_state_replays"] for x in measurements),
        "interval_frontiers": sum(x["interval_frontiers"] for x in measurements),
        "maximum_frontier_edges": max(x["maximum_frontier_edges"] for x in measurements),
        "maximum_certificate_bytes": max(x["maximum_certificate_bytes"] for x in measurements),
        "mismatches": sum(x["mismatches"] for x in measurements),
    }
    benchmark_data = json.loads((out / "frontier-benchmarks-measurement.json").read_text())
    boundary_data = json.loads((out / "frontier-boundary-4-measurement.json").read_text())
    with (out / "frontier-benchmarks.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != benchmark_data["instances"]:
        raise ValueError("benchmark CSV is incomplete")
    by_family: dict[str, dict[str, float | int]] = {}
    for row in rows:
        family = row["family"]
        target = by_family.setdefault(family, {"instances": 0, "updates": 0, "full_log": 0, "greedy": 0, "optimum": 0})
        target["instances"] += 1
        for key in ("updates", "full_log", "greedy", "optimum"):
            target[key] += int(row[key])
    for target in by_family.values():
        target["full_log_saved_fraction"] = 0.0 if not target["full_log"] else 1 - target["optimum"] / target["full_log"]
        target["greedy_excess_fraction"] = 0.0 if not target["optimum"] else (target["greedy"] - target["optimum"]) / target["optimum"]
    summary = {
        "frontier_theorem": {
            "frontiers": exhaustive_data["frontiers"],
            "support_checks": exhaustive_data["support_checks"],
            "hidden_state_replays": exhaustive_data["hidden_state_replays"],
            "interval_frontiers": exhaustive_data["interval_frontiers"],
            "maximum_frontier_edges": exhaustive_data["maximum_frontier_edges"],
            "maximum_certificate_bytes": exhaustive_data["maximum_certificate_bytes"],
            "mismatches": exhaustive_data["mismatches"],
        },
        "monotonicity_boundary": {
            "predicates": boundary_data["predicates"],
            "downward_closed_predicates": boundary_data["downward_closed_predicates"],
            "nonmonotone_predicates": boundary_data["nonmonotone_predicates"],
            "endpoint_robust_support_checks": boundary_data["endpoint_robust_support_checks"],
            "transversal_support_checks": boundary_data["transversal_support_checks"],
            "mismatches": boundary_data["mismatches"],
        },
        "benchmarks": {
            "instances": benchmark_data["instances"],
            "greedy_optimal_instances": benchmark_data["greedy_optimal_instances"],
            "by_family": by_family,
            "maximum_decision_nodes": benchmark_data["maximum_decision_nodes"],
            "maximum_proof_nodes": benchmark_data["maximum_proof_nodes"],
            "maximum_certificate_bytes": benchmark_data["maximum_certificate_bytes"],
        },
        "scope": "Owned deterministic chain networks; exact finite validation of the stated fragment, not production-network performance.",
    }
    (out / "frontier-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=["exhaustive", "boundary", "benchmarks", "summary", "all"])
    parser.add_argument("--width", type=int, default=5)
    parser.add_argument("--chunk", type=int, default=0)
    parser.add_argument("--chunks", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    if args.suite in ("exhaustive", "all"):
        print(json.dumps(exhaustive(args.width, args.output, args.chunk, args.chunks)))
    if args.suite in ("boundary", "all"):
        print(json.dumps(predicate_boundary(4, args.output)))
    if args.suite in ("benchmarks", "all"):
        print(json.dumps(benchmarks(args.output)))
    if args.suite in ("summary", "all"):
        print(json.dumps(summarize(args.output, args.chunks)))


if __name__ == "__main__":
    main()
