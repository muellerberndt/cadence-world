"""Sensory encoding for survival beings.

A being reads a local window of the world, its own body, its last executed
action, and an explicit bounded history of a compact summary row. All channels
are fixed physical units scaled into the solver's comfortable range; there is
no camera, learned feature bank or hidden global map. The history is the
library's `History` buffer: external context the brain must learn to use, not
learned recurrent memory.

The window radius is a body trait, not a constant: evolved lineages may carry
wider senses and pay the per-cell read price for them. Radius 2 is the fixed
lane's default.
"""

from __future__ import annotations

from functools import lru_cache

from .population import ACTIONS

RADIUS = 2
SUMMARY_SIZE = 12


def side(radius):
    return 2 * radius + 1


def cells(radius):
    return side(radius) ** 2


def scene_size(radius):
    return 3 * cells(radius) + 2  # food, threat, den channels + light + energy


@lru_cache(maxsize=None)
def sectors(radius):
    """Row-major window sectors: cells strictly north, east, south, west of
    the centre (diagonals shared between their two adjacent sectors)."""
    s = side(radius)
    return {
        "north": tuple(i for i in range(cells(radius)) if i // s < radius),
        "east": tuple(i for i in range(cells(radius)) if i % s > radius),
        "south": tuple(i for i in range(cells(radius)) if i // s > radius),
        "west": tuple(i for i in range(cells(radius)) if i % s < radius),
    }


def window_channels(world, being, radius=RADIUS):
    """Three flat row-major window channels around the being: food, threat,
    den. Food is in eighths of the cell cap; threat and den are occupancies."""
    w, h = world.substrate.config.width, world.substrate.config.height
    food, threat, den = [], [], []
    predators = {(p.x, p.y) for p in world.predators}
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            x, y = (being.x + dx) % w, (being.y + dy) % h
            food.append(float(world.substrate.food[y, x]) / 8.0)
            threat.append(1.0 if (x, y) in predators else 0.0)
            den.append(1.0 if world.dens[y, x] else 0.0)
    return food, threat, den


def nearest_threat_offset(threat, radius=RADIUS):
    """(dx, dy, present) of the nearest visible predator in window units."""
    s = side(radius)
    best = None
    for index, value in enumerate(threat):
        if value <= 0:
            continue
        dx, dy = index % s - radius, index // s - radius
        if best is None or abs(dx) + abs(dy) < abs(best[0]) + abs(best[1]):
            best = (dx, dy)
    if best is None:
        return 0.0, 0.0, 0.0
    return best[0] / radius, best[1] / radius, 1.0


def summary_row(food, threat, light, radius=RADIUS):
    """The compact per-tick summary retained by the `History` window.

    Four sector food masses, four sector threat indicators, the nearest-threat
    offset and presence, and the local light. Everything a being needs to
    notice motion (the predator's heading, the light band's drift) is only in
    how consecutive rows differ, which is exactly what the history exposes.
    """
    named = sectors(radius)
    row = [
        min(1.0, 2.0 * sum(food[i] for i in named[name]) / len(named[name]))
        for name in ("north", "east", "south", "west")
    ]
    row += [
        1.0 if any(threat[i] > 0 for i in named[name]) else 0.0
        for name in ("north", "east", "south", "west")
    ]
    row += list(nearest_threat_offset(threat, radius))
    row.append(light)
    assert len(row) == SUMMARY_SIZE
    return row


def observe(world, being, radius=RADIUS):
    """Raw sensor mapping for one being, before normalization and history.

    Returns (inputs-without-context, summary_row). The caller pushes the
    summary into the being's own `History` and attaches the encoding.
    """
    food, threat, den = window_channels(world, being, radius)
    light = float(world.substrate.light()[being.y, being.x])
    energy = min(1.0, being.energy / 16.0)
    efference = [0.0] * len(ACTIONS)
    efference[being.last_action] = 1.0
    scene = food + threat + den + [light, energy]
    return (
        {"scene": scene, "efference": efference},
        summary_row(food, threat, light, radius),
    )
