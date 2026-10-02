"""Acyclic packet-chain networks for relational rollback frontiers.

Each packet class is associated with one minimal critical set of update atoms.
A packet continues through a test node while that atom has the new value.  The
first old atom exits to the allowed egress; if every atom in the critical set
is new, the packet reaches DROP.  Projection erases internal test nodes while
retaining packet class and the ALLOW/DROP outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from frontier import Frontier, bits, deviates, minimize

ALLOW = "ALLOW"
DROP = "DROP"


@dataclass(frozen=True)
class PacketTrace:
    packet_class: int
    hops: tuple[str, ...]

    @property
    def outcome(self) -> str:
        return self.hops[-1]

    def projected(self) -> tuple[int, str, str]:
        return (self.packet_class, self.hops[0], self.outcome)


@dataclass(frozen=True)
class ChainNetwork:
    update_count: int
    critical_sets: Frontier

    def __post_init__(self) -> None:
        if type(self.update_count) is not int or not 0 <= self.update_count <= 128:
            raise ValueError("update_count must be in [0,128]")
        normalized = minimize(self.critical_sets, width=self.update_count)
        if normalized != self.critical_sets:
            raise ValueError("critical_sets must be a normalized antichain")
        if 0 in normalized:
            raise ValueError("the all-old reference may not deviate")

    @classmethod
    def from_hypergraph(cls, update_count: int, edges: Iterable[int]) -> "ChainNetwork":
        frontier = minimize(edges, width=update_count)
        if 0 in frontier:
            raise ValueError("empty critical sets are incompatible with a valid reference")
        return cls(update_count, frontier)

    def trace(self, packet_class: int, commit_mask: int) -> PacketTrace:
        if type(packet_class) is not int or not 0 <= packet_class < len(self.critical_sets):
            raise ValueError("unknown packet class")
        if type(commit_mask) is not int or commit_mask < 0 or commit_mask >= (1 << self.update_count):
            raise ValueError("commit mask outside network width")
        edge = self.critical_sets[packet_class]
        hops = [f"I{packet_class}"]
        for variable in bits(edge):
            hops.append(f"Q{packet_class}_{variable}")
            if not (commit_mask & (1 << variable)):
                hops.append(ALLOW)
                return PacketTrace(packet_class, tuple(hops))
        hops.append(DROP)
        return PacketTrace(packet_class, tuple(hops))

    def traces(self, commit_mask: int) -> tuple[PacketTrace, ...]:
        return tuple(self.trace(packet, commit_mask) for packet in range(len(self.critical_sets)))

    def projected_language(self, commit_mask: int) -> frozenset[tuple[int, str, str]]:
        return frozenset(trace.projected() for trace in self.traces(commit_mask))

    def reference_language(self) -> frozenset[tuple[int, str, str]]:
        return self.projected_language(0)

    def goal(self, commit_mask: int) -> bool:
        return self.projected_language(commit_mask) == self.reference_language()

    def deviation_classes(self, commit_mask: int) -> frozenset[int]:
        return frozenset(i for i, trace in enumerate(self.traces(commit_mask)) if trace.outcome == DROP)

    def enumerate_frontier(self) -> Frontier:
        bad = [mask for mask in range(1 << self.update_count) if not self.goal(mask)]
        return minimize(bad, width=self.update_count)

    def symbolic_frontier(self) -> Frontier:
        # Each packet chain contributes the product of its positive update guards;
        # packet-language union contributes antichain addition.  The resulting
        # minimal monomials are precisely the declared critical sets.
        return self.critical_sets

    def endpoint_correct(self, support_mask: int) -> bool:
        if type(support_mask) is not int or support_mask < 0 or support_mask >= (1 << self.update_count):
            raise ValueError("support mask outside network width")
        keep = ((1 << self.update_count) - 1) & ~support_mask
        # The deviation predicate is monotone, so the maximal remaining commit
        # state suffices; tests also replay the full cube independently.
        return self.goal(keep)

    def operational_goal(self, commit_mask: int) -> bool:
        """Evaluate packet chains without calling the frontier algebra.

        This loop follows each chain guard-by-guard and is used as the
        independent fast operational oracle in the exhaustive campaign.
        """
        if type(commit_mask) is not int or not 0 <= commit_mask < (1 << self.update_count):
            raise ValueError("commit mask outside network width")
        for edge in self.critical_sets:
            dropped = True
            for variable in bits(edge):
                if not (commit_mask & (1 << variable)):
                    dropped = False
                    break
            if dropped:
                return False
        return True

    def endpoint_correct_by_cube(self, support_mask: int) -> bool:
        return all(self.operational_goal(hidden & ~support_mask) for hidden in range(1 << self.update_count))

    def regression_free(self, hidden_mask: int, reset_order: Sequence[int]) -> bool:
        if type(hidden_mask) is not int or not 0 <= hidden_mask < (1 << self.update_count):
            raise ValueError("hidden mask outside network width")
        current = hidden_mask
        previous = self.deviation_classes(current)
        seen = set()
        for variable in reset_order:
            if type(variable) is not int or not 0 <= variable < self.update_count:
                raise ValueError("reset variable outside network width")
            if variable in seen:
                # Repeated idempotent resets are allowed but do no additional work.
                pass
            seen.add(variable)
            current &= ~(1 << variable)
            next_deviations = self.deviation_classes(current)
            if not next_deviations <= previous:
                return False
            previous = next_deviations
        return True


def trace_deviates(network: ChainNetwork, commit_mask: int) -> bool:
    return not network.goal(commit_mask)


def frontier_deviates(network: ChainNetwork, commit_mask: int) -> bool:
    return deviates(network.symbolic_frontier(), commit_mask)
