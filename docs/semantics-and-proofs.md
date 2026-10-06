# Semantics and proof obligations

This document is the standalone mathematical specification checked by the repository.  It uses the same notation as the paper but does not depend on the paper directory.

## 1. Ambiguous batches and reset supports

Let `U = {0,...,n-1}` be finite update atoms.  The all-old reference is the empty committed set.  After a batch acknowledgement is lost, the hidden state is any `H ⊆ U`; atom `i` is in `H` exactly when its new rule committed.  A blind rollback support `R ⊆ U` issues the idempotent reset-to-old command for every atom in `R`, in any order, and maps `H` to

`rho_R(H) = H \ R`.

A good-state predicate `G ⊆ 2^U` contains the reference `∅`.  A support is:

- **endpoint-correct** when `U \ R ∈ G`, i.e. it repairs the known all-new state;
- **ambiguity-robust** when `H \ R ∈ G` for every `H ⊆ U`.

The implementation represents an arbitrary predicate as a finite truth table in `robustness.py`.

## 2. Exact endpoint-collapse boundary

**Theorem 1 (robustification).** If `G` is downward closed, then for every support `R`, endpoint correctness is equivalent to ambiguity robustness.

*Proof.* Robustness implies endpoint correctness by choosing `H=U`.  Conversely, assume `U\R ∈ G`.  For every `H⊆U`, `H\R ⊆ U\R`; downward closure gives `H\R ∈ G`.  ∎

**Theorem 2 (necessity).** Endpoint correctness and ambiguity robustness agree for every support if and only if `G` is downward closed.

*Proof.* The forward direction is Theorem 1.  For the converse, suppose `G` is not downward closed.  There are `B⊂A` with `A∈G` and `B∉G`.  Choose `R=U\A`.  Its all-new endpoint is `U\R=A`, so it is endpoint-correct.  The hidden state `H=B` is unchanged because `B⊆A` and hence disjoint from `R`; it remains bad, so the support is not robust.  ∎

`predicate_boundary` exhausts all predicates with a good reference through width four.  It decides the universal support predicate with short-circuit evaluation, records the first concrete separating witness, and separately checks the frontier characterization below for every downward-closed predicate.

## 3. Rollback frontiers and transversals

When `G` is downward closed, the bad set `D=2^U\G` is upward closed.  Its **rollback frontier** is the antichain

`F = min(D)`,

the inclusion-minimal bad committed sets.  An edge `E∈F` is a minimal relational-deviation cause.  A support `R` is a **transversal** when `R∩E` is nonempty for every `E∈F`.

**Theorem 3 (rollback-transversal theorem).** For a downward-closed goal, a support is ambiguity-robust exactly when it hits every rollback-frontier edge.

*Proof.* By Theorem 1, robustness is equivalent to `U\R∈G`.  The endpoint is bad exactly when it contains a minimal bad set `E∈F`, which is equivalent to `E∩R=∅`.  Negating gives the transversal condition.  ∎

This theorem immediately yields four corollaries.

1. A minimum-command blind rollback is a minimum-cardinality transversal.
2. Resetting every updated atom is safe but is minimal only when the frontier forces it.
3. If only atoms in an availability set `A` can be reset, recovery exists exactly when `A` hits every frontier edge; an edge disjoint from `A` is a complete unrecoverability witness.
4. Every reset order is regression-free for the positive deviation language: reset operations only remove committed atoms, so no upward-closed deviation can become newly active.

The full-cube blind-support characterization itself needs less than downward
closure. For any finite good predicate with a good reference, let `F=min(2^U\G)`.
Then `R` is ambiguity-robust iff it hits every member of `F`: a missed bad
minimal set `E` survives on hidden state `H=E`; conversely, every bad repaired
state contains a minimal bad set disjoint from `R`. Without monotonicity,
`up(F)` is generally larger than the actual bad predicate. It still describes
which retained atom sets contain a bad hidden subset, but does not justify
endpoint-only checking, state-specific repair, or regression freedom. The
exact boundary in Theorem 2 concerns endpoint collapse, not the existence of a
hypergraph description of robust blind supports.

## 4. Perfect observation cannot improve worst-case reset count

Let `tau(F)` be the minimum transversal size.  Suppose a controller can observe the exact hidden set before choosing resets.  For a particular `H`, it may choose a minimum transversal of the residual active causes.  Nevertheless:

**Theorem 4 (worst-case telemetry lower bound).** The worst-case number of resets used by any correct perfectly informed recovery policy is at least `tau(F)`, and a fixed blind minimum transversal achieves exactly `tau(F)` for every hidden state.

*Proof.* The ambiguity cube includes `H=U`.  Any correct execution from that state must delete at least one atom from every `E∈F`, so its reset set is a transversal and has size at least `tau(F)`.  Conversely, Theorem 3 says that any fixed minimum transversal is correct for every hidden state and uses `tau(F)` resets.  Any nonnegative observation cost only strengthens the lower bound on total commands.  ∎

The code exhausts this equality over every proper antichain on four atoms by independently minimizing the state-specific repair for each hidden set.

## 5. Packet-chain relational semantics

For every nonempty frontier edge `E`, `forwarding.py` constructs one packet class and an acyclic chain of positive tests, one for each update atom in `E`.  The packet exits at `ALLOW` when it encounters an old atom; it reaches `DROP` exactly when every atom in `E` is new.  Projection keeps the packet-class identifier, ingress, and outcome while erasing internal test nodes.  The relational goal is equality between the set of projected traces in the current state and in the all-old reference.

Therefore packet class `E` deviates exactly when `E⊆H`. The union over packet classes is bad exactly when one frontier edge is contained in `H`. Every finite antichain without the empty cause, including the empty frontier, is realized by this construction, so the identity reduction from Hitting Set with nonempty edges produces owned packet-chain instances without importing an external benchmark.

**Theorem 5 (frontier realization).** The symbolic antichain denotation, direct operational packet traces, and exhaustive enumeration of minimal bad commit sets all equal the declared frontier.

*Proof.* A single chain is a conjunction of its positive update tests, hence its unique minimal monomial is `E`.  Packet-language union is disjunction, whose minimal satisfying monomials are the absorption-minimized union of all `E`.  Because the input is already an antichain, absorption changes nothing.  Directly, the chain drops iff every test in `E` succeeds.  Thus both semantics produce exactly the upward closure of the input antichain, whose minimal elements are the antichain itself.  ∎

## 6. Compositional antichain provenance

`update_language.py` contains four constructors: `Allow`, `Drop`, `New(i,p)`, and finite `Choice`.  Its denotation is in the finite absorptive semiring of Sperner families:

- zero is the empty antichain (no deviation);
- one is `{∅}` (unconditional deviation);
- addition is union followed by absorption;
- multiplication is pairwise set union followed by absorption;
- variable `i` is `{{i}}`.

`Allow` denotes zero, `Drop` denotes one, `New(i,p)` multiplies by variable `i`, and `Choice` adds branch denotations.  Structural induction proves that a hidden commit set operationally produces a deviation exactly when it contains one denoted monomial.  The implementation tests identity, commutativity, idempotence, absorption, and distributivity exhaustively on all antichains through width three, and checks the structural interpretation for every antichain through width four.

The semiring/provenance machinery is established algebraic technique; the research claim is the ambiguity-robust rollback consequence and its exact monotonicity boundary, not invention of antichain provenance.

## 7. Optimization, complexity, and tractable structure

The decision problem asks whether a frontier has a transversal of size at most `k`.

**Theorem 6.** Deciding whether a robust rollback support of size at most `k` exists is NP-complete, even for the packet-chain fragment. Cardinality optimization is NP-hard.

*Proof.* Membership in NP follows by checking intersection with every edge. For hardness, use Hitting Set with nonempty edges, already NP-hard on two-element edges by Vertex Cover, and normalize its family by absorption. Map `(U,F,k)` to the packet-chain network of Section 5. By Theorem 3, its robust rollback supports of size at most `k` are exactly the hitting sets of the original instance. The construction is polynomial and the all-old reference is good. ∎

`support.py` includes:

- a deterministic coverage greedy baseline;
- brute force for small oracle instances;
- an exact budgeted branch algorithm that chooses a surviving edge and branches on each atom in it, with singleton forcing, memoization, and a disjoint-edge packing bound;
- iterative deepening from a packing lower bound to the greedy upper bound;
- an interval-frontier algorithm that repeatedly selects the right endpoint of the earliest-ending unhit interval.

If every edge has size at most `d`, the basic search tree has at most `d^k` leaves before polynomial reductions and memoization.  No stronger scalability claim is made.

**Theorem 7 (interval optimum).** For frontiers whose edges are intervals in one common atom order, selecting the right endpoint of the earliest-ending unhit interval yields a minimum transversal.

*Proof.* Let the earliest-ending interval be `[l,r]`.  Every transversal contains some `x∈[l,r]`.  Replacing `x` by `r` cannot lose coverage of an interval that was hit by `x` and remains relevant: such an interval ends no earlier than `r`, and because it contains `x≤r`, it also contains `r` whenever its left endpoint is at most `x`; otherwise it was not hit by `x`.  Hence some optimum contains `r`.  Remove all intervals hit by `r` and apply induction.  ∎

## 8. Optimality certificates

A certificate has a normalized frontier, a positive support, its size, and, for positive optimum, a proof that no support of size one less exists. The checker verifies the positive hits directly. At optimum zero, it requires an empty frontier and support, `lower_bound_budget=-1`, and `lower_bound=null`; nonnegative cardinality establishes the lower bound without a recursive proof. Its negative proof rules for nonnegative budgets are:

- `unconditional`: the empty edge survives, so no support can remove the deviation;
- `zero-budget`: a nonempty edge survives when no reset remains;
- `packing`: more than `k` pairwise-disjoint surviving edges require more than `k` atoms;
- `branch`: choose a nonempty surviving edge `E`; every hitting set must choose some `v∈E`, and every child proves that the residual frontier after choosing `v` has no support within the remaining budget.

Induction on the proof tree establishes soundness.  Conversely, branching on an arbitrary surviving edge and recursing on every atom constructs a finite proof whenever no budget-feasible transversal exists; zero-budget leaves terminate the recursion.  Packing leaves only shorten the proof.  Therefore the proof system is complete for finite frontiers.  The checker recomputes residual frontiers and validates exact child coverage.  Frontier mutation controls forge a support and delete a child from a triangle-frontier branch node; finite-game tests cover their separate model obligations.

## 9. Exhaustive campaign interpretation

The width-five campaign enumerates all 7,580 antichains that do not contain the empty cause.  For each, it compares:

1. declared frontier versus direct trace-enumerated minimal bad sets;
2. compositional language denotation versus operational evaluation on every hidden state;
3. exact support and certificate versus brute force;
4. the transversal theorem versus full ambiguity-cube replay for every support;
5. interval greedy versus brute force whenever all edges are intervals.

The 101 deterministic structured instances exercise shared causes, disjoint causes, intervals, complete 3-uniform frontiers, and fixed-seed random antichains.  They test exact optimization and certificate checking, not production representativeness.  The largest retained size metric is about 14.4 MB for single-line sorted-key JSON. The public indented writer uses a different serialization and cannot emit that proof within its 16 MiB cap.

The older finite-game code and results are preserved because they provide a useful negative control: per-world recoverability does not imply one observation-based program.  They are not evidence that the frontier algorithm is novel or general beyond the positive fragment.
