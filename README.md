# Relational rollback programmable

This standalone repository accompanies **Rollback Transversals for Ambiguous Programmable-Network Updates**.  It implements and checks the paper's finite positive update fragment, relational rollback-frontier semantics, minimum reset-support solver, replayable optimality certificates, exact monotonicity-boundary experiment, and retained imperfect-information baseline.  It is research code for a bounded mathematical model, not a production controller or a device-management package.

## Main result represented by the code

A failed acknowledgement for a batch of `n` update atoms leaves an unknown committed subset `H`.  A reset support `R` replaces `H` by `H \ R`.  In the positive packet-chain fragment, projected trace deviations are upward closed and are represented by their inclusion-minimal causes, the **rollback frontier** `F`.

The checker validates the following finite certificate statement: `R` restores the relational goal for every hidden `H` exactly when `R` intersects every edge in `F`.  Thus a smallest robust blind rollback is a minimum transversal of `F`.  Downward closure is the exact condition under which checking only the known all-new endpoint is sound for every support.  The code also checks that perfect state observation cannot reduce the worst-case number of reset commands, because the all-new hidden state already requires a minimum transversal.

The mathematical proofs are in `docs/semantics-and-proofs.md` and in the paper.  Python executions are finite checks of those claims, not a proof-assistant mechanization.

## Reproduce from a clean extraction

Requirements are Linux/POSIX and Python 3.10 or later, using only the standard library.  No installation, network connection, private input, GPU, model service, or external solver is needed.  Use an empty destination outside the repository:

```sh
python3 reproduce.py --output /tmp/rr-reproduction
```

The POSIX runner uses one child at a time, a 3.5 GiB address-space ceiling, and bounded CPU/wall time per child. It performs 54 unit tests; regenerates all four example certificates; exhausts all 7,580 proper antichains on five update atoms in eight chunks; checks all 242,560 candidate supports over a nominal 7,761,920 support--state domain, with universal replay stopping at the first failure; exhausts all 32,768 goal predicates on four atoms whose all-old reference is good; solves and certifies 101 deterministic structured instances; replays the older finite-game and logged-assignment baselines; and compares deterministic scientific files byte for byte. Timing fields are deliberately excluded from byte equality. The aggregate verifies each chunk's identity and complete assigned index sequence, and recomputes its counts from CSV rows.

`results/reproduction.json` is the retained historical 49-test run, including that host's CPU and memory observations; it is not a measurement of the current 54-test suite. The additional tests cover nonmonotone minimal-bad-set robustness and rejection of duplicated or inconsistent exhaustive evidence.

For an arbitrary finite goal, minimal bad sets still characterize robust blind supports over the full ambiguity cube. Without downward closure, their upward closure is not the exact bad-state predicate, and endpoint-only checking, state-specific active-cause repair, and regression freedom do not follow.

Expected exact frontier results are:

| Check | Expected result |
|---|---:|
| Proper antichains on 5 atoms | 7,580 |
| Candidate reset supports | 242,560 |
| Nominal support--state pairs (not executed replay count) | 7,761,920 |
| Goal predicates on 4 atoms | 32,768 |
| Downward-closed predicates | 167 |
| Nonmonotone predicates | 32,601 |
| Deterministic benchmark instances | 101 |
| Mismatches | 0 |

These counts describe finite decision domains. The hidden-state total and the boundary's 524,288 support total are Cartesian domain sizes; their short-circuit predicates do not execute every inner comparison.  The structured benchmarks are not production traffic or performance evidence.

The campaign measures certificate size as sorted-key, single-line JSON plus a newline. The public writer emits indented JSON and enforces a 16 MiB output cap. For the largest width-14 complete-three-uniform proof, indentation alone exceeds that cap; in-memory acceptance is not successful public-file replay.

## Solve and check a rollback frontier

An instance is a JSON object with `width` and a normalized antichain `frontier`; every edge is a list of update indices.  Four examples and their expected certificates are in `inputs/frontiers/`.

```sh
python3 src/support_cli.py solve \
  --input inputs/frontiers/running.frontier.json \
  --output /tmp/running.certificate.json

python3 src/support_cli.py check \
  --input inputs/frontiers/running.frontier.json \
  --certificate /tmp/running.certificate.json

python3 src/support_cli.py simulate \
  --input inputs/frontiers/running.frontier.json \
  --certificate /tmp/running.certificate.json
```

The certificate contains a positive hitting support and a recursively checkable proof that no smaller support exists.  Negative leaves use an unconditional cause, a zero-budget surviving edge, or a packing of more pairwise-disjoint causes than the budget.  Branch nodes cover every possible reset selected from one surviving cause.  The checker recomputes each residual frontier and does not call the optimization routine.

## Repository map

- `src/frontier.py`: absorptive antichain operations and exhaustive antichain generation.
- `src/update_language.py`: positive acyclic deviation language and compositional denotation.
- `src/forwarding.py`: owned packet-chain trace semantics and projected relational goal.
- `src/robustness.py`: truth-table boundary checks, perfect-observation comparison, and availability witnesses.
- `src/support.py`: exact/greedy/interval transversals, program normalization, certificate generation and checking.
- `src/frontier_campaign.py`: exhaustive and structured experiments.
- `src/support_cli.py`: public solve/check/simulate interface.
- `tests/test_frontier.py`: algebraic, semantic, boundary, solver, checker, and mutation tests.
- `src/model.py`, `src/synthesis.py`, `src/checker.py`, and related files: retained bounded imperfect-information baseline used as a negative control and scope comparison.
- `results/`: deterministic raw outputs and separately marked timing measurements.
- `claim_evidence_ledger.csv`: claim-to-proof/check/result mapping.
- `external_resources.csv`: source, license, acquisition, and integration ledger.

## Boundaries

The positive fragment has finite update atoms, one ambiguous batch acknowledgement, idempotent reset-to-old commands, no recovery-time failure, no concurrency, and a projected trace-equality goal whose bad states are upward closed.  The exact monotonicity experiment shows why the endpoint reduction must not be applied outside that boundary.  The packet-chain construction realizes arbitrary finite antichain frontiers but does not claim that every production network update has this form.  Minimum support is NP-complete in general; the included branch solver is for bounded research instances, not a scalability claim.

The retained older baseline evaluates bounded observation-based controllers in arbitrary finite transition systems.  It is intentionally not presented as the paper's new algorithm: belief-state game search is established prior art.  Its 55,221 exact queries and logged reverse-update cases remain as falsification evidence and a comparison boundary.
