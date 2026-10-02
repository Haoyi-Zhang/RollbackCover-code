#!/usr/bin/env python3
"""Apply process resource limits and replace this process with a Python command."""
from __future__ import annotations

import os
import resource
import sys


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: limited_exec.py ADDRESS_BYTES CPU_SECONDS SCRIPT_OR_OPTION ...", file=sys.stderr)
        return 2
    address_bytes = int(sys.argv[1])
    cpu_seconds = int(sys.argv[2])
    command = sys.argv[3:]
    resource.setrlimit(resource.RLIMIT_AS, (address_bytes, address_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    os.execv(sys.executable, [sys.executable, "-B", *command])
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
