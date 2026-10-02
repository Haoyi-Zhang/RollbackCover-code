"""Owned, acyclic two-forwarding-node toy network and one lost acknowledgement.

Configuration is two bits xy. For class 0, x=0 forwards A->D; x=1
forwards A->B, where y=1 delivers to D and y=0 drops. Class 1 always
follows A->E. Packet processing is atomic between control commands.
"""
from __future__ import annotations
from model import Model

ACTIONS = ('set-x-0', 'set-x-1', 'set-y-0', 'set-y-1', 'flip-x', 'flip-y', 'read-x', 'read-y')
WRITES = ACTIONS[:4]


def trace_set(config: int) -> frozenset[tuple]:
    x, y = config >> 1, config & 1
    path = ('A', 'D') if x == 0 else ('A', 'B', 'D' if y else 'DROP')
    return frozenset(((0, path), (1, ('A', 'E'))))


def normalized(config: int, relation: str) -> frozenset[tuple]:
    traces = trace_set(config)
    if relation == 'identity':
        return traces
    if relation == 'erase-relay':
        return frozenset((packet, tuple(node for node in path if node != 'B')) for packet, path in traces)
    raise ValueError('unknown relation')


def safe(config: int) -> bool:
    return all('DROP' not in path for _, path in trace_set(config))


def command(config: int, action: str) -> tuple[str, int]:
    x, y = config >> 1, config & 1
    if action == 'set-x-0':
        return ('ack', y)
    if action == 'set-x-1':
        return ('ack', 2 | y)
    if action == 'set-y-0':
        return ('ack', x << 1)
    if action == 'set-y-1':
        return ('ack', (x << 1) | 1)
    if action == 'flip-x':
        return ('ack', config ^ 2)
    if action == 'flip-y':
        return ('ack', config ^ 1)
    if action == 'read-x':
        return (str(x), config)
    if action == 'read-y':
        return (str(y), config)
    raise ValueError('unknown command')


def compile_network(reference: int, actions: tuple[str, ...], relation: str = 'identity') -> Model:
    if reference not in range(4) or not safe(reference):
        raise ValueError('reference must be a safe configuration')
    if any(a not in ACTIONS for a in actions):
        raise ValueError('unknown network action')
    worlds = tuple(f'ref={reference:02b};cfg={c:02b}' for c in range(4))
    safe_set = frozenset(c for c in range(4) if safe(c))
    goal = frozenset(c for c in safe_set if normalized(c, relation) == normalized(reference, relation))
    transitions = tuple(tuple((command(c, a),) for c in range(4)) for a in actions)
    return Model(worlds, actions, transitions, safe_set, goal)


def lost_acknowledgements(reference: int, schedule: tuple[str, ...]) -> list[dict]:
    """A fault aborts immediately; the failed command may or may not have applied.

    Position and preceding acknowledgements are known. No second fault occurs
    during recovery. Output includes every failed attempt, including stuttering
    writes; no-fault prefix safety is recorded separately.
    """
    config = reference
    result = []
    for position, action in enumerate(schedule):
        if action not in WRITES:
            raise ValueError('forward schedules contain only bit assignments')
        after = command(config, action)[1]
        result.append({'position': position, 'before': config, 'after': after,
                       'belief': sorted({config, after}), 'safe_fault_belief': safe(config) and safe(after)})
        config = after
    return result


def conflict_family(size: int) -> tuple[Model, frozenset[int]]:
    """Finite-system obstruction family, not claimed to be a restricted network.

    Action a_j is fatal exactly from hidden fault world j. It repairs every other
    fault world. Goal/bad are absorbing; bad is unsafe. Horizon one suffices.
    """
    if size < 2 or size > 64:
        raise ValueError('family size must be in [2,64]')
    goal, bad = size, size + 1
    rows = []
    for j in range(size):
        rows.append(tuple((('ack', bad if i == j else goal),) for i in range(size)) +
                    ((('ack', goal),), (('ack', bad),)))
    return Model(tuple([f'hidden-{i}' for i in range(size)] + ['repaired', 'bad']),
                 tuple(f'a-{j}' for j in range(size)), tuple(rows),
                 frozenset(range(size + 1)), frozenset({goal})), frozenset(range(size))


def hidden_reference_case() -> tuple[Model, frozenset[int]]:
    """Same current configuration but two unobserved saved references.

    This is a diagnostic variation. In the network suite the saved reference IS
    known, so its different values produce separate initial information sets.
    """
    refs=(0,3);actions=('set-x-0','set-x-1','read-x')
    worlds=tuple(f'ref={r:02b};cfg={c:02b}' for r in refs for c in range(4))
    rows=tuple(tuple(((command(c,a)[0],ri*4+command(c,a)[1]),)
                     for ri,r in enumerate(refs) for c in range(4)) for a in actions)
    return Model(worlds,actions,rows,
                 frozenset(ri*4+c for ri,r in enumerate(refs) for c in range(4) if safe(c)),
                 frozenset(ri*4+c for ri,r in enumerate(refs) for c in range(4) if safe(c) and trace_set(c)==trace_set(r))),frozenset({1,5})


def nonminimum_core_case() -> tuple[Model, frozenset[int]]:
    # Winning iff one member of {0,1} AND one member of {2,3,4} is absent.
    # The fixed deletion order removes 0 and 1, leaving a size-3 core, although
    # {0,1} is a size-2 core. All starting worlds are individually recoverable.
    pairs=tuple((i,j) for i in (0,1) for j in (2,3,4))
    goal,bad=5,6
    matrices=tuple(tuple((('ack',bad if w in pair else goal),) for w in range(5))+
                   ((('ack',goal),),(('ack',bad),)) for pair in pairs)
    return Model(tuple(f'w{i}' for i in range(5))+('goal','bad'),
                 tuple(f'avoid-{i}-{j}' for i,j in pairs),matrices,
                 frozenset(range(6)),frozenset({goal})),frozenset(range(5))
