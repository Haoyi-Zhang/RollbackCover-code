Electronic evidence description

This standalone repository contains the implementation, mathematical proof
specification, deterministic owned inputs, replayable certificates, raw finite
results, tests, evidence ledgers, and reproduction command for the internal
research article Rollback Transversals for Ambiguous Programmable-Network
Updates.

Run from a clean extraction:
  python3 reproduce.py --output /tmp/rr-reproduction

The output directory must be empty and outside the repository.  Python's
standard library is the only software dependency.  The evidence is a finite
executable validation of a precisely stated fragment, not proof-assistant
mechanization, production-network testing, or independent review.
