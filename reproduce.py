#!/usr/bin/env python3
"""Reproduce every retained deterministic result with one bounded worker.

Run from a clean extraction:
    python3 reproduce.py --output /tmp/rr-reproduction
The destination must be empty and outside the repository.  No download,
package installation, solver, network access, or private input is used.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADDRESS_LIMIT = 3_758_096_384  # 3.5 GiB
CPU_LIMIT = 120
WALL_LIMIT = 150
UNIT_TEST_METHODS = 54


def semantic_json(path: Path) -> object:
    value = json.loads(path.read_text())
    if isinstance(value, dict):
        value = dict(value)
        value.pop("measurements", None)
    return value


def run_step(arguments: list[str], *, out: Path, env: dict[str, str], index: int,
             steps: list[dict[str, object]]) -> None:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall = time.monotonic()
    print(f"[{index:02d}] " + " ".join(arguments), flush=True)
    log_path = out / f"command-{index:02d}.txt"
    with log_path.open("w") as log_stream:
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "src" / "limited_exec.py"),
             str(ADDRESS_LIMIT), str(CPU_LIMIT), *arguments],
            cwd=ROOT,
            env=env,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=WALL_LIMIT,
        )
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    steps.append({
        "command": ["python", *[arg.replace(str(out), "<OUTPUT>") for arg in arguments]],
        "returncode": result.returncode,
        "wall_seconds": time.monotonic() - wall,
        "child_cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
    })
    if result.returncode:
        print(f"[{index:02d}] failed ({steps[-1]['wall_seconds']:.3f}s)", flush=True)
        raise RuntimeError(f"command {index} failed; inspect command-{index:02d}.txt")
    print(f"[{index:02d}] ok ({steps[-1]['wall_seconds']:.3f}s)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--_resume", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = args.output.resolve()
    if out == ROOT or ROOT in out.parents:
        parser.error("use a destination outside the repository")
    state_path = out / ".reproduction-controller.json"
    if args._resume:
        if not state_path.is_file():
            parser.error("internal continuation state is missing")
        controller = json.loads(state_path.read_text())
        steps = controller["steps"]
        next_index = int(controller["next_index"])
        start = float(controller["start_monotonic"])
        begin_user = float(controller["begin_child_user"])
        begin_system = float(controller["begin_child_system"])
    else:
        if out.exists() and any(out.iterdir()):
            parser.error("the output directory must be empty")
        out.mkdir(parents=True, exist_ok=True)
        begin = resource.getrusage(resource.RUSAGE_CHILDREN)
        steps: list[dict[str, object]] = []
        next_index = 0
        start = time.monotonic()
        begin_user = begin.ru_utime
        begin_system = begin.ru_stime

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(ROOT / "src"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    tasks: list[list[str]] = [
        ["-m", "unittest", "discover", "-s", "tests", "-v"],
        ["src/pilot.py", "--output", str(out / "pilot.json")],
    ]
    tasks += [["src/campaign.py", "finite", "--chunk", str(chunk), "--output", str(out)]
              for chunk in range(8)]
    tasks += [
        ["src/campaign.py", "network", "--output", str(out)],
        ["src/campaign.py", "cores", "--output", str(out)],
        ["src/logged_rollback.py", "--output", str(out)],
        ["src/examples.py", "--output", str(out / "examples")],
        ["src/analyze.py", "--results", str(out), "--output", str(out / "summary.json")],
        ["src/frontier_examples.py", "--output", str(out / "frontiers")],
    ]
    tasks += [["src/frontier_campaign.py", "exhaustive", "--width", "5", "--chunk", str(chunk),
               "--chunks", "8", "--output", str(out)] for chunk in range(8)]
    tasks += [
        ["src/frontier_campaign.py", "boundary", "--output", str(out)],
        ["src/frontier_campaign.py", "benchmarks", "--output", str(out)],
        ["src/frontier_campaign.py", "summary", "--chunks", "8", "--output", str(out)],
    ]

    # Re-exec the controller after small batches.  Some hosted Python runtimes
    # can stall after many sequential process creations; exec preserves the
    # one-command interface and evidence while resetting interpreter state.
    for index in range(next_index, len(tasks)):
        run_step(tasks[index], out=out, env=env, index=index, steps=steps)
        if index == 0:
            text = (out / "command-00.txt").read_text()
            if not re.search(rf"Ran {UNIT_TEST_METHODS} tests\b", text):
                raise AssertionError("unexpected unit-test count")
        controller = {
            "next_index": index + 1,
            "steps": steps,
            "start_monotonic": start,
            "begin_child_user": begin_user,
            "begin_child_system": begin_system,
        }
        state_path.write_text(json.dumps(controller))
        if index + 1 < len(tasks) and (index + 1) % 8 == 0:
            os.execv(sys.executable, [sys.executable, "-B", str(Path(__file__).resolve()),
                                      "--output", str(out), "--_resume"])

    deterministic = [
        *[f"finite-{i}.csv" for i in range(8)],
        "network.csv", "fault-cases.json",
        *[f"core-{i}.json" for i in range(2, 9)],
        "logged-assignments.csv", "summary.json",
        *[f"frontier-exhaustive-5-chunk-{i:02d}-of-08.csv" for i in range(8)],
        "frontier-benchmarks.csv", "frontier-summary.json",
    ]
    compared: list[str] = []
    for name in deterministic:
        if (ROOT / "results" / name).read_bytes() != (out / name).read_bytes():
            raise AssertionError(f"deterministic scientific output differs: {name}")
        compared.append("results/" + name)

    for source_dir, generated_dir in ((ROOT / "inputs" / "examples", out / "examples"),
                                      (ROOT / "inputs" / "frontiers", out / "frontiers")):
        for reference in sorted(source_dir.glob("*")):
            if not reference.is_file():
                continue
            candidate = generated_dir / reference.name
            if reference.read_bytes() != candidate.read_bytes():
                raise AssertionError(f"generated evidence differs: {reference.name}")
            compared.append(str(reference.relative_to(ROOT)))

    measurements = [
        *sorted((ROOT / "results").glob("*measurement.json")),
        ROOT / "results" / "pilot.json",
    ]
    for reference in measurements:
        candidate = out / reference.name
        if semantic_json(reference) != semantic_json(candidate):
            raise AssertionError(f"non-timing measurement fields differ: {reference.name}")

    old_example = out / "examples"
    interfaces = [
        ["src/rr.py", "solve", "--input", str(old_example / "read-and-restore.problem.json"),
         "--output", str(out / "cli-positive.json")],
        ["src/rr.py", "check", "--input", str(old_example / "read-and-restore.problem.json"),
         "--certificate", str(out / "cli-positive.json")],
        ["src/rr.py", "execute", "--input", str(old_example / "read-and-restore.problem.json"),
         "--certificate", str(out / "cli-positive.json")],
        ["src/rr.py", "core", "--input", str(old_example / "minimal-not-minimum.problem.json"),
         "--output", str(out / "cli-core.json")],
        ["src/rr.py", "check-core", "--input", str(old_example / "minimal-not-minimum.problem.json"),
         "--certificate", str(out / "cli-core.json")],
    ]
    frontier_example = out / "frontiers" / "running.frontier.json"
    interfaces += [
        ["src/support_cli.py", "solve", "--input", str(frontier_example),
         "--output", str(out / "cli-frontier-certificate.json")],
        ["src/support_cli.py", "check", "--input", str(frontier_example),
         "--certificate", str(out / "cli-frontier-certificate.json")],
        ["src/support_cli.py", "simulate", "--input", str(frontier_example),
         "--certificate", str(out / "cli-frontier-certificate.json")],
    ]
    base_index = len(tasks)
    for offset, arguments in enumerate(interfaces):
        run_step(arguments, out=out, env=env, index=base_index + offset, steps=steps)
    if (out / "cli-frontier-certificate.json").read_bytes() != \
            (ROOT / "inputs" / "frontiers" / "running.certificate.json").read_bytes():
        raise AssertionError("frontier CLI did not reproduce the recorded certificate")

    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    own = resource.getrusage(resource.RUSAGE_SELF)
    total = usage.ru_utime + usage.ru_stime - begin_user - begin_system
    if total > 21_600:
        raise RuntimeError("science allocation exhausted; repair reserve must not be spent silently")
    frontier_summary = json.loads((out / "frontier-summary.json").read_text())
    old_summary = json.loads((out / "summary.json").read_text())
    logged_summary = json.loads((out / "logged-assignments-measurement.json").read_text())
    data = {
        "status": "all documented deterministic checks reproduced",
        "unit_test_methods": UNIT_TEST_METHODS,
        "frontier_antichains": frontier_summary["frontier_theorem"]["frontiers"],
        "frontier_support_checks": frontier_summary["frontier_theorem"]["support_checks"],
        "frontier_hidden_state_replays": frontier_summary["frontier_theorem"]["hidden_state_replays"],
        "goal_predicates": frontier_summary["monotonicity_boundary"]["predicates"],
        "benchmark_instances": frontier_summary["benchmarks"]["instances"],
        "legacy_exact_queries": old_summary["principal_exact_queries"],
        "legacy_logged_assignment_cases": logged_summary["safe_prefix_cases"],
        "byte_identical_scientific_files": len(compared),
        "compared_files": compared,
        "full_child_cpu_seconds": total,
        "controller_cpu_seconds_to_measurement": own.ru_utime + own.ru_stime,
        "wall_seconds": time.monotonic() - start,
        "peak_child_rss_kib": usage.ru_maxrss,
        "workers": 1,
        "child_address_space_limit_bytes": ADDRESS_LIMIT,
        "child_cpu_limit_seconds": CPU_LIMIT,
        "child_wall_limit_seconds": WALL_LIMIT,
        "steps": steps,
        "interpretation": "Execution evidence for finite instances; not a proof-assistant result, deployment benchmark, or independent review.",
    }
    (out / "reproduction.json").write_text(json.dumps(data, indent=2) + "\n")
    state_path.unlink(missing_ok=True)
    print(json.dumps({key: value for key, value in data.items() if key not in {"steps", "compared_files"}}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, AssertionError, subprocess.TimeoutExpired) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
