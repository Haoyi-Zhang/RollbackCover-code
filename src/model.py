"""Finite labelled recovery systems. No networking or external dependencies."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import json
from pathlib import Path


@dataclass(frozen=True)
class Model:
    worlds: tuple[str, ...]
    actions: tuple[str, ...]
    # Indexed by action, then source world. A pair is (observation, target index).
    edges: tuple[tuple[tuple[tuple[str, int], ...], ...], ...]
    safe: frozenset[int]
    goal: frozenset[int]

    def __post_init__(self) -> None:
        n = len(self.worlds)
        if not 1 <= n <= 256 or len(set(self.worlds)) != n or not all(isinstance(s, str) for s in self.worlds):
            raise ValueError('worlds must be distinct strings and nonempty')
        if len(self.actions) > 64 or len(set(self.actions)) != len(self.actions) or not all(isinstance(a, str) for a in self.actions):
            raise ValueError('actions must be distinct strings')
        if len(self.edges) != len(self.actions):
            raise ValueError('one transition matrix per action is required')
        if any(type(x) is not int for x in self.goal | self.safe) or not self.goal <= self.safe <= frozenset(range(n)):
            raise ValueError('goal must be a subset of safe, and safe of worlds')
        for matrix in self.edges:
            if len(matrix) != n:
                raise ValueError('one transition row per world is required')
            for row in matrix:
                if len(set(row)) != len(row):
                    raise ValueError('duplicate outcomes are not accepted')
                for observation, target in row:
                    if not isinstance(observation, str) or type(target) is not int or not 0 <= target < n:
                        raise ValueError('malformed outcome')

    def belief(self, values: list[int] | tuple[int, ...] | frozenset[int], *, allow_empty: bool = False) -> frozenset[int]:
        if not isinstance(values, (list, tuple, frozenset)):
            raise ValueError('belief must be a list, tuple, or frozenset')
        if any(type(x) is not int or x < 0 or x >= len(self.worlds) for x in values):
            raise ValueError('invalid world index')
        if len(set(values)) != len(values):
            raise ValueError('belief contains duplicate world indices')
        b = frozenset(values)
        if not b and not allow_empty:
            raise ValueError('the initial belief cannot be empty')
        return b

    def to_dict(self) -> dict[str, Any]:
        return {'worlds': list(self.worlds), 'actions': list(self.actions),
                'edges': [[[list(e) for e in row] for row in matrix] for matrix in self.edges],
                'safe': sorted(self.safe), 'goal': sorted(self.goal)}

    @classmethod
    def from_dict(cls, obj: dict[str, Any]) -> Model:
        if not isinstance(obj, dict) or set(obj) != {'worlds', 'actions', 'edges', 'safe', 'goal'}:
            raise ValueError('unexpected or missing model keys')
        for key in ['worlds', 'actions', 'edges', 'safe', 'goal']:
            if not isinstance(obj[key], list):
                raise ValueError(f'{key} must be a JSON array')
        for key in ['worlds', 'actions']:
            if not all(isinstance(x, str) for x in obj[key]):
                raise ValueError(f'{key} must contain strings')
        for key in ['safe', 'goal']:
            if any(type(x) is not int for x in obj[key]) or len(set(obj[key])) != len(obj[key]):
                raise ValueError(f'{key} must contain distinct integers')
        matrices = []
        for matrix in obj['edges']:
            if not isinstance(matrix, list):
                raise ValueError('each transition matrix must be an array')
            converted = []
            for row in matrix:
                if not isinstance(row, list):
                    raise ValueError('each transition row must be an array')
                outcomes = []
                for entry in row:
                    if not isinstance(entry, list) or len(entry) != 2:
                        raise ValueError('each outcome must be an observation-target array')
                    if not isinstance(entry[0], str) or type(entry[1]) is not int:
                        raise ValueError('outcomes require a string observation and integer target')
                    outcomes.append((entry[0], entry[1]))
                converted.append(tuple(outcomes))
            matrices.append(tuple(converted))
        return cls(tuple(obj['worlds']), tuple(obj['actions']), tuple(matrices),
                   frozenset(obj['safe']), frozenset(obj['goal']))



def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f'duplicate JSON key: {k}')
        result[k] = v
    return result


def read_json(path: Path) -> Any:
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('input exceeds the documented 16 MiB limit')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=no_duplicate_keys)


def horizon(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 32:
        raise ValueError('horizon must be an integer in [0,32]')
    return value
