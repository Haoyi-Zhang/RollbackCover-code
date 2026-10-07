#!/usr/bin/env python3
"""Offline interface for rollback-frontier support certificates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from frontier import minimize
from forwarding import ChainNetwork
from model import read_json
from rr import write_new
from support import (
    InvalidSupportCertificate,
    check_optimality_certificate,
    make_optimality_certificate,
    mask_from_variables,
)


def read_instance(path: Path) -> tuple[int, tuple[int, ...]]:
    obj = read_json(path)
    if not isinstance(obj, dict) or set(obj) != {"width", "frontier"}:
        raise ValueError("instance requires exactly width and frontier")
    width = obj["width"]
    if type(width) is not int or not 0 <= width <= 128:
        raise ValueError("width must be an integer in [0,128]")
    if not isinstance(obj["frontier"], list):
        raise ValueError("frontier must be an array")
    edges = []
    for values in obj["frontier"]:
        if not isinstance(values, list):
            raise ValueError("each frontier edge must be an array")
        edges.append(mask_from_variables(values, width))
    frontier = minimize(edges, width=width)
    if 0 in frontier:
        raise ValueError("the all-old reference may not deviate")
    if len(frontier) != len(edges):
        raise ValueError("instance frontier must already be an inclusion antichain")
    return width, frontier


def simulate(width: int, frontier: tuple[int, ...], packet: dict[str, Any]) -> dict[str, Any]:
    checked = check_optimality_certificate(packet, expected_frontier=frontier, expected_width=width)
    support = mask_from_variables(packet["support"], width)
    network = ChainNetwork.from_hypergraph(width, frontier)
    records = []
    for hidden in range(1 << width):
        final = hidden & ~support
        records.append({
            "hidden": hidden,
            "final": final,
            "goal": network.operational_goal(final),
            "deviations_before": sorted(network.deviation_classes(hidden)),
            "deviations_after": sorted(network.deviation_classes(final)),
        })
    if not all(record["goal"] for record in records):
        raise ValueError("certificate does not restore the full ambiguity cube")
    return {"checked": checked, "support": packet["support"], "states": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    solve = sub.add_parser("solve")
    solve.add_argument("--input", type=Path, required=True)
    solve.add_argument("--output", type=Path, required=True)
    solve.add_argument("--compact", action="store_true", help="write compact sorted-key JSON under the unchanged size cap")
    for name in ("check", "simulate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--input", type=Path, required=True)
        cmd.add_argument("--certificate", type=Path, required=True)
    args = parser.parse_args()
    try:
        width, frontier = read_instance(args.input)
        if args.command == "solve":
            packet = make_optimality_certificate(frontier, width)
            check_optimality_certificate(packet, expected_frontier=frontier, expected_width=width)
            write_new(args.output, packet, compact=args.compact)
            print(json.dumps({"optimum": packet["optimum"], "support": packet["support"], "output": str(args.output)}))
        else:
            packet = read_json(args.certificate)
            if args.command == "check":
                print(json.dumps(check_optimality_certificate(packet, expected_frontier=frontier, expected_width=width)))
            else:
                print(json.dumps(simulate(width, frontier, packet), indent=2))
        return 0
    except (ValueError, InvalidSupportCertificate, KeyError, TypeError, OSError, RecursionError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
