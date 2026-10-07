"""Portable finite packing/export regressions; no private baseline imports."""
from __future__ import annotations

import copy
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import support
import support_cli
from model import read_json
from rr import write_new


def literal_frontiers(width):
    """Enumerate the literal Cartesian family domain, without frontier helpers."""
    atoms = tuple(range(width))
    edges = [frozenset(i for i in atoms if mask & (1 << i))
             for mask in range(1, 1 << width)]
    for flags in itertools.product((False, True), repeat=len(edges)):
        selected = [edge for edge, flag in zip(edges, flags) if flag]
        if any(a <= b or b <= a for a, b in itertools.combinations(selected, 2)):
            continue
        yield tuple(sorted((sum(1 << i for i in edge) for edge in selected),
                           key=lambda mask: (mask.bit_count(), mask)))


def priority_scan_reference(edges):
    """Independent set-based reference: repeatedly select the least remaining edge."""
    pending = list(edges)
    used = set()
    packed = []
    while pending:
        edge = min(pending, key=lambda mask: (mask.bit_count(), mask))
        pending.remove(edge)
        variables = {i for i in range(edge.bit_length()) if edge & (1 << i)}
        if used.isdisjoint(variables):
            packed.append(edge)
            used.update(variables)
    return tuple(packed)


def literal_optima(frontier, width):
    edges = [{i for i in range(width) if edge & (1 << i)} for edge in frontier]
    feasible = []
    for flags in itertools.product((False, True), repeat=width):
        chosen = {i for i, flag in enumerate(flags) if flag}
        if all(not chosen.isdisjoint(edge) for edge in edges):
            feasible.append(chosen)
    size = min(map(len, feasible))
    return size, {sum(1 << i for i in chosen) for chosen in feasible if len(chosen) == size}


FIXTURES = (
    ("empty", 0, (), [], (1, 0, 0)),
    ("triangle", 3, (3, 5, 6), [0, 1], (6, 3, 0)),
    ("running", 5, (3, 24, 14), [1, 3], (3, 1, 0)),
    ("singletons", 3, (1, 2, 4), [0, 1, 2], (1, 1, 3)),
    ("disjoint", 4, (3, 12), [0, 2], (3, 1, 0)),
)


class PackingExportRegression(unittest.TestCase):
    def test_canonical_packing_and_filtered_residuals(self):
        count = 0
        for frontier in literal_frontiers(4):
            count += 1
            for removed in range(16):
                residual = tuple(edge for edge in frontier if not edge & removed)
                expected = priority_scan_reference(residual)
                self.assertEqual(support._packing_canonical(residual), expected)
                self.assertEqual(support._packing(tuple(reversed(residual))), expected)
        self.assertEqual(count, 167)
        # The compatibility wrapper also retains unsorted/duplicate input behavior.
        edges = (12, 3, 6, 3, 0, 0)
        self.assertEqual(support._packing(edges), priority_scan_reference(edges))

    def test_solver_certificates_literal_oracle_and_named_counters(self):
        count = 0
        for frontier in literal_frontiers(4):
            count += 1
            size, optima = literal_optima(frontier, 4)
            packet = support.make_optimality_certificate(tuple(reversed(frontier)), 4)
            self.assertEqual(packet["optimum"], size)
            self.assertIn(sum(1 << i for i in packet["support"]), optima)
            checked = support.check_optimality_certificate(packet, expected_frontier=frontier, expected_width=4)
            self.assertEqual(checked["optimum"], size)
            for budget in range(6):
                chosen = support.find_support(tuple(reversed(frontier)), 4, budget)
                self.assertEqual(chosen is not None, size <= budget)
                if chosen is not None:
                    self.assertLessEqual(chosen.bit_count(), budget)
                    self.assertTrue(all(chosen & edge for edge in frontier))
        self.assertEqual(count, 167)
        for name, width, frontier, selected, counters in FIXTURES:
            with self.subTest(name=name):
                packet = support.make_optimality_certificate(frontier, width)
                self.assertEqual(packet["support"], selected)
                self.assertEqual(tuple(packet["metrics"][key] for key in
                                       ("decision_nodes", "proof_nodes", "forced_reductions")), counters)
                if name == "triangle":
                    self.assertEqual(packet["lower_bound"], {
                        "kind": "branch", "edge": [0, 1], "children": {
                            "0": {"kind": "packing", "edges": [[1, 2]]},
                            "1": {"kind": "packing", "edges": [[0, 2]]}}})
                    self.assertEqual(list(packet["lower_bound"]["children"]), ["0", "1"])
                elif name == "empty":
                    self.assertIsNone(packet["lower_bound"])
                    self.assertEqual(packet["lower_bound_budget"], -1)
                else:
                    self.assertEqual(packet["lower_bound"], {
                        "kind": "packing", "edges": [
                            [i for i in range(width) if edge & (1 << i)]
                            for edge in priority_scan_reference(frontier)]})

    def test_checker_independence_and_nonvacuous_mutations(self):
        frontier = (3, 5, 6)
        packet = support.make_optimality_certificate(frontier, 3)
        self.assertEqual(packet["lower_bound"]["kind"], "branch")
        with patch.object(support, "_packing", side_effect=AssertionError("producer called")), \
                patch.object(support, "_packing_canonical", side_effect=AssertionError("producer called")), \
                patch.object(support, "optimal_support", side_effect=AssertionError("search called")):
            self.assertEqual(support.check_optimality_certificate(packet)["optimum"], 2)
            mutations = []
            missing = copy.deepcopy(packet)
            del missing["lower_bound"]["children"]["0"]
            mutations.append(missing)
            extra = copy.deepcopy(packet)
            extra["lower_bound"]["children"]["2"] = extra["lower_bound"]["children"]["0"]
            mutations.append(extra)
            missed = copy.deepcopy(packet)
            missed["support"] = [0]
            missed["optimum"] = 1
            missed["lower_bound_budget"] = 0
            mutations.append(missed)
            for broken in mutations:
                with self.assertRaises(support.InvalidSupportCertificate):
                    support.check_optimality_certificate(broken)
        for budget in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                support.find_support(frontier, 3, budget)
        self.assertIsNone(support.find_support((0,), 3, 3))
        with self.assertRaises(ValueError):
            support.make_optimality_certificate((0,), 3)
        self.assertEqual(support.make_optimality_certificate((), 128)["optimum"], 0)

    def test_default_bytes_compact_roundtrips_and_strict_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, width, frontier, _, _ in FIXTURES:
                packet = support.make_optimality_certificate(frontier, width)
                default = root / (name + ".default.json")
                compact = root / (name + ".compact.json")
                write_new(default, packet)
                write_new(compact, packet, compact=True)
                self.assertEqual(default.read_bytes(), (json.dumps(packet, indent=2) + "\n").encode("utf-8"))
                self.assertEqual(compact.read_bytes(), (json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
                self.assertEqual(read_json(default), packet)
                self.assertEqual(read_json(compact), packet)
                self.assertEqual(support.check_optimality_certificate(read_json(default)),
                                 support.check_optimality_certificate(read_json(compact)))
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"width":3,"width":3}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                read_json(duplicate)

    def test_encoded_caps_refuse_before_creation_and_no_overwrite(self):
        value = {"z": "é", "a": [1, 2]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for compact in (False, True):
                text = (json.dumps(value, sort_keys=True, separators=(",", ":")) if compact
                        else json.dumps(value, indent=2)) + "\n"
                expected = text.encode("utf-8")
                for delta in (-1, 0, 1):
                    path = root / str(compact) / str(delta) / "data.json"
                    if delta < 0:
                        with self.assertRaises(ValueError):
                            write_new(path, value, max_bytes=len(expected) + delta, compact=compact)
                        self.assertFalse(path.parent.exists())
                    else:
                        write_new(path, value, max_bytes=len(expected) + delta, compact=compact)
                        self.assertEqual(path.read_bytes(), expected)
                        with self.assertRaises(FileExistsError):
                            write_new(path, value, compact=not compact)
                        self.assertEqual(path.read_bytes(), expected)
            # Exercise the actual default writer cap, not an increased release limit.
            oversized = root / "absent" / "oversized.json"
            for compact in (False, True):
                with self.assertRaises(ValueError):
                    write_new(oversized, "x" * (16 * 1024 * 1024), compact=compact)
                self.assertFalse(oversized.parent.exists())

    def test_public_cli_modes_and_literal_restored_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, width, frontier, _, _ in FIXTURES:
                instance = root / (name + ".input.json")
                write_new(instance, {"width": width, "frontier": [
                    [i for i in range(width) if edge & (1 << i)] for edge in frontier]})
                summaries = []
                for compact in (False, True):
                    certificate = root / (name + str(compact) + ".json")
                    argv = ["support_cli", "solve", "--input", str(instance), "--output", str(certificate)]
                    if compact:
                        argv.append("--compact")
                    output = io.StringIO()
                    with patch("sys.argv", argv), patch("sys.stdout", output):
                        self.assertEqual(support_cli.main(), 0)
                    packet = read_json(certificate)
                    with patch("sys.argv", ["support_cli", "check", "--input", str(instance),
                                            "--certificate", str(certificate)]), patch("sys.stdout", io.StringIO()):
                        self.assertEqual(support_cli.main(), 0)
                    simulation = io.StringIO()
                    with patch("sys.argv", ["support_cli", "simulate", "--input", str(instance),
                                            "--certificate", str(certificate)]), patch("sys.stdout", simulation):
                        self.assertEqual(support_cli.main(), 0)
                    actual = json.loads(simulation.getvalue())
                    chosen = set(packet["support"])
                    edges = [{i for i in range(width) if edge & (1 << i)} for edge in frontier]
                    expected = []
                    for mask in range(1 << width):
                        hidden = {i for i in range(width) if mask & (1 << i)}
                        final = hidden - chosen
                        expected.append({"hidden": mask, "final": sum(1 << i for i in final),
                                         "goal": not any(edge <= final for edge in edges),
                                         "deviations_before": [i for i, edge in enumerate(edges) if edge <= hidden],
                                         "deviations_after": [i for i, edge in enumerate(edges) if edge <= final]})
                    self.assertEqual(actual["states"], expected)
                    summaries.append(actual)
                self.assertEqual(summaries[0], summaries[1])


if __name__ == "__main__":
    unittest.main()

