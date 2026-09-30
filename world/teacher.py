"""A disclosed scripted survival teacher for the bootstrapping phase.

The teacher reads exactly the student's sensory window: local food, threat
and den channels, own energy and last action. It has no global map, no
predator internals and no route planner. Priorities follow the Doom lane's
working order — danger first, then the meal, then the approach, then a
committed serpentine search:

1. visible threat within two cells: flee (den cells preferred, never onto a
   predator), or hold still inside a den;
2. food underfoot with no adjacent threat: eat;
3. food in the window: move toward the heaviest sector;
4. otherwise: keep the current heading, with an occasional deterministic turn.

These coefficients are a hand-set curriculum and control, not measured
biology, and no selection over them is claimed. Bootstrapping targets are
asymmetric preferences in value units: the chosen action high, the rest
mildly negative, inside the solver's comfortable range.
"""

from __future__ import annotations

from .population import ACTIONS
from .senses import RADIUS, nearest_threat_offset, sectors, side

MOVES = ("north", "east", "south", "west")
MOVE_OFFSETS = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
CHOSEN_TARGET = 0.4
OTHER_TARGET = -0.15
FORESIGHT_SCALE = 0.6


def _cell(dx, dy, radius):
    return (dy + radius) * side(radius) + (dx + radius)


def teacher_action(food, threat, den, energy, last_action, rng, radius=RADIUS):
    """One action index from the student's own window channels."""
    tx, ty, present = nearest_threat_offset(threat, radius)
    here = _cell(0, 0, radius)
    threat_near = present and max(abs(tx), abs(ty)) * radius <= 2
    if threat_near:
        if den[here]:
            return ACTIONS.index("eat") if food[here] > 0 else ACTIONS.index("wait")
        scored = []
        for name in MOVES:
            dx, dy = MOVE_OFFSETS[name]
            cell = _cell(dx, dy, radius)
            if threat[cell] > 0:
                continue
            away = -(dx * tx + dy * ty)
            score = away + (1.5 if den[cell] else 0.0) + 0.2 * food[cell]
            scored.append((score, name))
        if scored:
            best = max(score for score, _ in scored)
            candidates = [name for score, name in scored if score >= best - 1e-9]
            choice = candidates[int(rng.random() * len(candidates))]
            return ACTIONS.index(choice)
        return ACTIONS.index("wait")
    if food[here] > 0:
        return ACTIONS.index("eat")
    named = sectors(radius)
    masses = {name: sum(food[i] for i in named[name]) for name in MOVES}
    heaviest = max(masses.values())
    if heaviest > 0:
        candidates = [n for n in MOVES if masses[n] >= heaviest - 1e-9]
        choice = candidates[int(rng.random() * len(candidates))]
        return ACTIONS.index(choice)
    if ACTIONS[last_action] in MOVES and rng.random() >= 0.15:
        return last_action
    return int(rng.random() * 4)


def preference_targets(action):
    """Asymmetric value-unit targets for the six action outputs."""
    return {
        name: CHOSEN_TARGET if index == action else OTHER_TARGET
        for index, name in enumerate(ACTIONS)
    }


def foresight_targets(energy_delta, food_here_after):
    """Witnessed next-tick body consequences in the solver's target range."""
    return (
        max(-1.0, min(1.0, energy_delta / 2.0)) * FORESIGHT_SCALE,
        (min(food_here_after, 8) / 8.0) * 2 * FORESIGHT_SCALE - FORESIGHT_SCALE,
    )


def rebalanced(rows, rng, dominant_keep=0.4):
    """Subsample the dominant action so rare actions keep their weight.

    The Doom corpus needed exactly this: forward-only frames drowned rare
    buttons. `rows` are (example, action) pairs; the most common action's
    rows are kept with the given probability, every other row survives.
    """
    counts = {}
    for _, action in rows:
        counts[action] = counts.get(action, 0) + 1
    if not counts:
        return []
    dominant = max(counts, key=counts.get)
    kept = []
    for example, action in rows:
        if action == dominant and rng.random() > dominant_keep:
            continue
        kept.append((example, action))
    return kept
