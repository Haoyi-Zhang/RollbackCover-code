"""Terminal relational recovery and safety throughout execution are distinct."""
import unittest

from checker import check
from model import Model
from support import optimal_support
from synthesis import Solver, is_winning


class RecoverySafetyBoundaryTests(unittest.TestCase):
    def test_terminal_recovery_does_not_establish_initial_safety(self):
        # Worlds encode the empty committed set and the singleton atom.
        initial = frozenset({0, 1})
        support = optimal_support((1,), 1)
        self.assertEqual(support, 1)
        self.assertTrue(all(hidden & ~support == 0 for hidden in initial))
        edges = (((("same", 0),), (("same", 0),)),)
        strict = Model(("empty", "atom"), ("reset",), edges,
                       frozenset({0}), frozenset({0}))
        result = Solver(strict).solve(initial, 1)
        self.assertEqual(result["kind"], "lose-unsafe")
        self.assertEqual(check(strict, initial, 1, result), "lose")
        terminal_only = Model(("empty", "atom"), ("reset",), edges,
                              initial, frozenset({0}))
        recovered = Solver(terminal_only).solve(initial, 1)
        self.assertTrue(is_winning(recovered))
        self.assertEqual(check(terminal_only, initial, 1, recovered), "win")


if __name__ == "__main__":
    unittest.main()
