"""Dens and predators: the pressure that makes survival tactics worth having.

Both are physics, not learners. A den is a fixed cell predators cannot enter.
A predator is a hazard body that patrols, chases the nearest visible being and
drains energy on adjacency; drained units land in the soil under the being, so
world mass stays conserved. Predators move on even ticks only, which makes
fleeing, kiting and shelter use physically possible rather than hopeless.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .random import Mulberry32

SENSE = 5  # Chebyshev chase radius
BITE = 1  # units drained per adjacent tick
STEPS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def make_dens(width, height, count, seed):
    """A fixed boolean den grid, cells spread apart deterministically."""
    rng = Mulberry32(seed ^ 0x9E3779B9)
    dens = np.zeros((height, width), dtype=bool)
    placed = []
    attempts = 0
    while len(placed) < count and attempts < 1000:
        attempts += 1
        x = int(rng.random() * width)
        y = int(rng.random() * height)
        if all(
            max(abs(x - px), abs(y - py)) >= 5 for px, py in placed
        ):
            placed.append((x, y))
            dens[y, x] = True
    return dens


@dataclass
class Predator:
    x: int
    y: int
    heading: int = 0  # index into STEPS


class Pack:
    """All predators of one world, moved by one deterministic rule."""

    def __init__(self, substrate, dens, count, seed):
        self.substrate = substrate
        self.dens = dens
        self.rng = Mulberry32(seed ^ 0x5DEECE66)
        w, h = substrate.config.width, substrate.config.height
        self.predators = []
        while len(self.predators) < count:
            x = int(self.rng.random() * w)
            y = int(self.rng.random() * h)
            if not dens[y, x] and all(
                (p.x, p.y) != (x, y) for p in self.predators
            ):
                self.predators.append(Predator(x, y))

    def _distance(self, ax, ay, bx, by):
        w, h = self.substrate.config.width, self.substrate.config.height
        dx = min(abs(ax - bx), w - abs(ax - bx))
        dy = min(abs(ay - by), h - abs(ay - by))
        return max(dx, dy)

    def _toward(self, predator, x, y):
        """The step index that most reduces torus distance to (x, y)."""
        best, best_distance = None, None
        for index, (dx, dy) in enumerate(STEPS):
            w, h = self.substrate.config.width, self.substrate.config.height
            nx, ny = (predator.x + dx) % w, (predator.y + dy) % h
            if self.dens[ny, nx]:
                continue
            distance = self._distance(nx, ny, x, y)
            if best_distance is None or distance < best_distance:
                best, best_distance = index, distance
        return best

    def step(self, beings):
        """Move every predator (even ticks only) and drain adjacent beings.

        Returns {being id: units drained}. Draining moves each unit from the
        being into the soil under it.
        """
        w, h = self.substrate.config.width, self.substrate.config.height
        if self.substrate.tick % 2 == 0:
            occupied = {(p.x, p.y) for p in self.predators}
            for predator in self.predators:
                alive = [b for b in beings if b.alive]
                target = None
                if alive:
                    target = min(
                        alive,
                        key=lambda b: self._distance(predator.x, predator.y, b.x, b.y),
                    )
                    if (
                        self._distance(predator.x, predator.y, target.x, target.y)
                        > SENSE
                    ):
                        target = None
                if target is not None:
                    choice = self._toward(predator, target.x, target.y)
                else:
                    if self.rng.random() < 0.3:
                        predator.heading = int(self.rng.random() * 4)
                    choice = predator.heading
                if choice is None:
                    continue
                dx, dy = STEPS[choice]
                nx, ny = (predator.x + dx) % w, (predator.y + dy) % h
                if self.dens[ny, nx] or (nx, ny) in occupied:
                    predator.heading = int(self.rng.random() * 4)
                    continue
                occupied.discard((predator.x, predator.y))
                occupied.add((nx, ny))
                predator.x, predator.y = nx, ny
                predator.heading = choice
        drained = {}
        for being in beings:
            if not being.alive or self.dens[being.y, being.x]:
                continue
            adjacent = any(
                self._distance(p.x, p.y, being.x, being.y) <= 1
                for p in self.predators
            )
            if adjacent:
                bite = min(BITE, being.energy)
                if bite:
                    being.energy -= bite
                    self.substrate.soil[being.y, being.x] += bite
                    drained[being.id] = drained.get(being.id, 0) + bite
        return drained
