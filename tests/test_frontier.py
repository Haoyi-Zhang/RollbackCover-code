from __future__ import annotations

import copy
import json
import unittest

from forwarding import ChainNetwork
from frontier import (
    all_intervals,
    deviates,
    enumerate_antichains,
    hits,
    minimize,
    one,
    plus,
    times,
    variable,
    zero,
)
from support import (
    InvalidSupportCertificate,
    brute_force_support,
    check_optimality_certificate,
    greedy_support,
    interval_support,
    make_optimality_certificate,
    normalize_program,
    optimal_support,
    support_program,
)


class FrontierTests(unittest.TestCase):
    def test_minimize_absorbs_supersets(self):
        self.assertEqual(minimize([0b001, 0b011, 0b101, 0b001], width=3), (0b001,))

    def test_semiring_laws_small(self):
        families = list(enumerate_antichains(3))
        for a in families:
            self.assertEqual(plus(a, zero(), width=3), a)
            self.assertEqual(times(a, one(), width=3), a)
            self.assertEqual(times(a, zero(), width=3), zero())
            self.assertEqual(plus(a, a, width=3), a)
            self.assertEqual(times(a, a, width=3), a)
        for a in families:
            for b in families:
                self.assertEqual(plus(a, b, width=3), plus(b, a, width=3))
                self.assertEqual(times(a, b, width=3), times(b, a, width=3))
                for c in families:
                    self.assertEqual(times(a, plus(b, c, width=3), width=3),
                                     plus(times(a, b, width=3), times(a, c, width=3), width=3))

    def test_chain_trace_frontier(self):
        frontier = minimize([0b011, 0b110], width=3)
        network = ChainNetwork.from_hypergraph(3, frontier)
        self.assertEqual(network.enumerate_frontier(), frontier)
        for hidden in range(8):
            self.assertEqual(not network.goal(hidden), deviates(frontier, hidden))

    def test_transversal_equivalence(self):
        frontier = minimize([0b011, 0b110], width=3)
        network = ChainNetwork.from_hypergraph(3, frontier)
        for support in range(8):
            self.assertEqual(hits(frontier, support), network.endpoint_correct_by_cube(support))

    def test_regression_free_every_permutation(self):
        frontier = minimize([0b011, 0b110, 0b101], width=3)
        network = ChainNetwork.from_hypergraph(3, frontier)
        import itertools
        for hidden in range(8):
            for order in itertools.permutations(range(3)):
                self.assertTrue(network.regression_free(hidden, order))

    def test_exact_support_and_certificate(self):
        frontier = minimize([0b0011, 0b0110, 0b1100], width=4)
        exact = optimal_support(frontier, 4)
        self.assertEqual(exact.bit_count(), brute_force_support(frontier, 4).bit_count())
        packet = make_optimality_certificate(frontier, 4)
        result = check_optimality_certificate(packet, expected_frontier=frontier, expected_width=4)
        self.assertEqual(result['optimum'], exact.bit_count())

    def test_certificate_rejects_missing_hit(self):
        frontier = minimize([0b0011, 0b1100], width=4)
        packet = make_optimality_certificate(frontier, 4)
        packet['support'] = [0]
        packet['optimum'] = 1
        packet['lower_bound_budget'] = 0
        with self.assertRaises(InvalidSupportCertificate):
            check_optimality_certificate(packet, expected_frontier=frontier, expected_width=4)

    def test_certificate_rejects_deleted_branch(self):
        frontier = minimize([0b0011, 0b0110, 0b1100], width=4)
        packet = make_optimality_certificate(frontier, 4)
        proof = packet['lower_bound']
        if proof['kind'] == 'branch':
            proof['children'].pop(next(iter(proof['children'])))
            with self.assertRaises(InvalidSupportCertificate):
                check_optimality_certificate(packet, expected_frontier=frontier, expected_width=4)

    def test_interval_greedy(self):
        frontier = minimize([0b000111, 0b011100, 0b110000], width=6)
        self.assertTrue(all_intervals(frontier))
        self.assertEqual(interval_support(frontier, 6).bit_count(), brute_force_support(frontier, 6).bit_count())

    def test_general_greedy_can_be_suboptimal(self):
        # Deterministically search a small counterexample instead of relying on
        # a hand-transcribed folklore instance.
        found = False
        for frontier in enumerate_antichains(5, exclude_empty_cause=True):
            if greedy_support(frontier, 5).bit_count() > brute_force_support(frontier, 5).bit_count():
                found = True
                break
        self.assertTrue(found)

    def test_program_normalization(self):
        program = {'kind': 'blind-reset', 'order': [3, 1, 3, 1]}
        self.assertEqual(normalize_program(program, 4), 0b1010)
        self.assertEqual(normalize_program(support_program(0b1010), 4), 0b1010)

    def test_reference_bad_rejected(self):
        with self.assertRaises(ValueError):
            ChainNetwork.from_hypergraph(2, [0])

    def test_antichain_count_width_five(self):
        values = list(enumerate_antichains(5, exclude_empty_cause=True))
        self.assertEqual(len(values), 7580)
        self.assertEqual(len(set(values)), 7580)


class UpdateLanguageTests(unittest.TestCase):
    def test_compositional_denotation_matches_operation(self):
        from update_language import compile_frontier, denote, evaluate
        for frontier in enumerate_antichains(4, exclude_empty_cause=True):
            expr = compile_frontier(frontier)
            self.assertEqual(denote(expr, 4), frontier)
            for hidden in range(16):
                self.assertEqual(evaluate(expr, hidden, 4), deviates(frontier, hidden))

class RobustnessBoundaryTests(unittest.TestCase):
    def test_downward_closure_exactly_characterizes_endpoint_collapse(self):
        from robustness import downward_closed, endpoint_robust_equivalent
        width = 3
        # Hold the all-old reference good; enumerate every remaining predicate.
        predicates = 0
        downward = 0
        for tail in range(1 << ((1 << width) - 1)):
            table = 1 | (tail << 1)
            self.assertEqual(downward_closed(table, width), endpoint_robust_equivalent(table, width))
            predicates += 1
            downward += downward_closed(table, width)
        self.assertEqual(predicates, 128)
        self.assertEqual(downward, 19)

    def test_nonmonotone_endpoint_has_concrete_failure_witness(self):
        from robustness import boundary_witness, endpoint_correct, robust_correct, table_from_good
        width = 3
        table = table_from_good([0, 0b111], width)
        endpoint, subset, support = boundary_witness(table, width)
        self.assertEqual(endpoint, 0b111)
        self.assertNotEqual(subset, endpoint)
        self.assertTrue(endpoint_correct(table, width, support))
        self.assertFalse(robust_correct(table, width, support))

    def test_perfect_observation_does_not_improve_worst_case(self):
        from robustness import perfect_observation_worst_case
        for frontier in enumerate_antichains(4, exclude_empty_cause=True):
            self.assertEqual(perfect_observation_worst_case(frontier, 4),
                             brute_force_support(frontier, 4).bit_count())

    def test_unavailable_reset_has_disjoint_frontier_witness(self):
        from robustness import available_recovery
        frontier = minimize([0b0011, 0b1100], width=4)
        ok, witness = available_recovery(frontier, 0b0010, 4)
        self.assertFalse(ok)
        self.assertEqual(witness, 0b1100)
        ok, witness = available_recovery(frontier, 0b0110, 4)
        self.assertTrue(ok)
        self.assertIsNone(witness)


if __name__ == '__main__':
    unittest.main()
