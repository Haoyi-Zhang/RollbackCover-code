#!/usr/bin/env python3
"""Generate deterministic rollback-frontier example instances and certificates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rr import write_new
from support import check_optimality_certificate, make_optimality_certificate, mask_from_variables
from frontier import minimize


EXAMPLES = {
    "running": {
        "width": 5,
        "frontier": [[0, 1], [1, 2, 3], [3, 4]],
        "description": "Three packet classes share update atoms; the optimum resets updates 1 and 3.",
    },
    "shared": {
        "width": 8,
        "frontier": [[0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 6], [0, 6, 7]],
        "description": "Every minimal deviation contains update 0, so one reset is optimal.",
    },
    "disjoint": {
        "width": 9,
        "frontier": [[0, 1, 2], [3, 4, 5], [6, 7, 8]],
        "description": "Three disjoint causes require three resets; the disjoint packing is a lower-bound certificate.",
    },
    "interval": {
        "width": 10,
        "frontier": [[0, 1, 2], [2, 3, 4], [4, 5, 6], [6, 7, 8, 9]],
        "description": "Ordered interval causes admit the right-endpoint greedy optimum.",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    index = []
    for name, spec in EXAMPLES.items():
        instance = {"width": spec["width"], "frontier": spec["frontier"]}
        edges = tuple(mask_from_variables(edge, spec["width"]) for edge in spec["frontier"])
        frontier = minimize(edges, width=spec["width"])
        if len(frontier) != len(edges):
            raise AssertionError(f"{name} is not a normalized antichain")
        packet = make_optimality_certificate(frontier, spec["width"])
        check = check_optimality_certificate(packet, expected_frontier=frontier, expected_width=spec["width"])
        write_new(args.output / f"{name}.frontier.json", instance)
        write_new(args.output / f"{name}.certificate.json", packet)
        index.append({"name": name, "description": spec["description"], "optimum": check["optimum"],
                      "instance": f"{name}.frontier.json", "certificate": f"{name}.certificate.json"})
    (args.output / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"examples": len(index), "names": [item["name"] for item in index]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
