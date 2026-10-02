# Rollback-frontier JSON formats

## Instance

```json
{
  "width": 5,
  "frontier": [[0, 1], [1, 2, 3], [3, 4]]
}
```

`width` is an integer in `[0,128]`.  Each edge lists distinct integer atom indices.  The list must already be a normalized inclusion antichain and may not contain the empty edge, because the all-old reference is required to satisfy the goal.

## Optimality certificate

The solver emits:

```json
{
  "width": 5,
  "frontier": [[0, 1], [3, 4], [1, 2, 3]],
  "support": [1, 3],
  "optimum": 2,
  "lower_bound_budget": 1,
  "lower_bound": {"kind": "..."},
  "metrics": {"decision_nodes": 0, "proof_nodes": 0, "forced_reductions": 0}
}
```

The exact edge order is canonical: increasing cardinality and then integer bit-mask order.  `metrics` is informational and is not trusted as proof.  The checker validates the support and recursively validates `lower_bound`.

Negative proof node shapes are:

```json
{"kind": "unconditional", "edge": []}
{"kind": "zero-budget", "edge": [0, 2]}
{"kind": "packing", "edges": [[0, 1], [2, 3]]}
{"kind": "branch", "edge": [0, 2], "children": {"0": {...}, "2": {...}}}
```

A branch child is interpreted after removing every frontier edge hit by the named selected atom and decrementing the budget.  All atoms of the branch edge must occur exactly once as child keys.

## Program

A blind reset program is:

```json
{"kind": "blind-reset", "order": [1, 3]}
```

Order and duplicate commands do not change the normalized support because resets are idempotent in the model.  The public solver emits one canonical increasing order.
