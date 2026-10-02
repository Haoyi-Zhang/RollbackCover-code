# Source map and novelty boundary

Access date for the final internal pass: **2026-09-15** (America/Los_Angeles). External papers are cited or paraphrased; no external paper PDF is redistributed in this artifact. Exact URLs, license boundaries, and integration modes are in `../external_resources.csv`.

## Direct lineage and strongest technical comparisons

| Source | Passages/results used | Legitimate reuse | Boundary against this project |
|---|---|---|---|
| Jia and Walker, *Modal Proofs as Distributed Programs* (ESOP 2004) | Modal type/proof terms as distributed programs; safety framing; stated metatheoretic results and limitations of the available extended abstract | Historical proof-as-program motivation and terminology calibration | Does not define ambiguous batch commit, packet-trace relations, reset-to-old commands, rollback frontiers, or minimum ambiguity-robust support |
| Reitblatt et al., *Abstractions for Network Update* (SIGCOMM 2012) | Consistent network-update abstraction and per-packet consistency | Network-update semantics and safe-transition context | Assumes an update protocol; does not solve hidden partial commit after a lost acknowledgement by partial rollback |
| Anderson et al., *NetKAT: Semantic Foundations for Networks* (POPL 2014) | Packet-history semantics and algebraic network reasoning | Packet-language context and comparison | The delivered fragment is smaller and makes commit/reset uncertainty explicit; it is not a NetKAT implementation |
| McClurg et al., *Efficient Synthesis of Network Updates* (PLDI 2015) | Synthesis of careful/simple update sequences and its scoped soundness/completeness | Forward-update synthesis comparison | Does not characterize one reset support for every hidden committed subset |
| Wagemaker et al., *Concurrent NetKAT* (ESOP 2022) | Stateful/concurrent network-language context | Boundary discussion for concurrency and state | Recovery-time concurrency and stateful command interaction are excluded here |
| Xu et al., *Network Change Validation with Relational NetKAT* (POPL 2026) | Relational trace-image comparison for network changes | Closest current relational-network language comparison | Validates network changes under a richer language; does not establish the ambiguity-robust rollback theorem or reset minimization |
| Zhao et al., *Provenance Guided Rollback Suggestions* (TPLP 2025) | Provenance for a known input difference, fault localization, and optimized partial rollback suggestions | Strongest rollback/provenance adversary; prevents novelty claims for partial rollback and minimum repair | Their changed set is known. This project proves when one support chosen before the actual committed subset is known is correct for every compatible subset |
| Chatterjee et al., *Algorithms for ω-Regular Games with Imperfect Information* (LMCS 2007) | Knowledge-set construction, observation-based strategies, sure winning, and antichain context | Establishes that the retained bounded belief recurrence is prior art | The frontier theorem is a fragment-specific collapse that avoids general game solving; no general new imperfect-information algorithm is claimed |

## Algebra, provenance, relational properties, and recovery context

| Source | Role in the manuscript | Non-claim enforced by the source |
|---|---|---|
| Buneman, Khanna, and Tan (ICDT 2001) | Why/where provenance and minimal causes | Minimal-cause provenance is not new here |
| Green, Karvounarakis, and Tannen (PODS 2007) | Provenance semirings | Semiring provenance is established technique |
| Green and Tannen (PODS 2017) | Semiring-framework synthesis | The absorptive antichain representation is not presented as a new provenance framework |
| Garcia-Molina and Salem (SIGMOD 1987) | Compensation and long-running transactions | Reset-to-old commands are a much narrower compensation model |
| Xing et al., *Occam* (EuroSys 2024) | Operation-sensitive network recovery and cases needing operator involvement | Plain reverse order is not claimed to solve general network-management recovery |
| Clarkson and Schneider (JCS 2010) | Hyperproperty vocabulary | The paper does not introduce a new temporal hyperlogic |
| Finkbeiner, Rabe, and Sánchez (CAV 2015) | Hyperlogic model-checking context | The artifact is not a HyperLTL/HyperCTL* model checker |
| Foster et al. (ESOP 2016) and Smolka et al. (POPL 2017) | Probabilistic network semantics context | No probabilistic/expected-cost rollback theorem is claimed |
| Karp (1972) | Classical NP-completeness context | The hardness proof is an identity reduction locating the network fragment, not a new complexity result |

## What the paper claims as its delta

The paper does **not** claim novelty for hitting sets, antichains, provenance semirings, partial rollback, or knowledge-set search. Its technical delta is the following chain, all under an explicit finite reset model:

1. endpoint repair equals ambiguity-robust repair for every support exactly at downward closure of the relational good-state predicate;
2. minimal relational deviations therefore form a complete rollback frontier, and robust supports are exactly its transversals;
3. every finite frontier is realized by an owned acyclic packet-chain trace semantics;
4. the characterization yields a worst-case telemetry equality, a complete static availability witness, regression-free reset execution, and replayable lower-bound certificates;
5. complete finite enumerations attack both the favorable positive fragment and the nonmonotone boundary.

## Reading and redistribution boundary

- The artifact contains original source, owned generated inputs/results, and unmodified supplied publisher assets only.
- Scholarly PDFs were consulted through publisher, author, or archive copies and are not bundled.
- Website snippets and official policy pages are workflow evidence, not manuscript scholarship.
- A bibliography record is not treated as proof that a source establishes a theorem; the manuscript comparisons are tied to the substantive roles above.
- The TOPLAS calibration corpus recorded in `../../research-plan.md` is used for structure and exposition, not as technical evidence for the rollback claims.
