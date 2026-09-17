"""The substrate: soil and food on a torus, driven by a drifting band of light.

Mass is integer and conserved. Each cell holds ``soil`` and ``food``. Per tick and per cell,
with the light ``l`` in [0, 1]:

- growth: with probability ``grow * l`` one unit moves from soil to food;
- decay: with probability ``decay`` one unit moves from food to soil;
- diffusion: with probability ``diffuse`` one unit of soil moves to one of the four neighbours.

Every draw comes from one Mulberry32 stream in a fixed order, so a seed replays a world exactly
and the browser port (``web/world.js``) can be checked against it cell by cell.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cadence.records import Mulberry32


@dataclass(frozen=True)
class SubstrateConfig:
    width: int = 64
    height: int = 64
    soil: int = 6  # initial soil per cell; the world's whole mass at tick 0 is width * height * soil
    grow: float = 0.08  # growth probability at full light
    decay: float = 0.01  # food to soil
    diffuse: float = 0.05  # soil to a neighbour
    day: int = 600  # ticks for the light band to cross the torus once
    season: int = 6000  # ticks for the band's contrast to breathe once
    contrast_min: float = 0.25  # the band's contrast at the season's low
    food_cap: int = 8  # food a cell can hold


class Substrate:
    def __init__(self, config: SubstrateConfig = SubstrateConfig(), seed: int = 0) -> None:
        self.config = config
        self.rng = Mulberry32(seed)
        self.tick = 0
        self.soil = np.full((config.height, config.width), config.soil, dtype=np.int32)
        self.food = np.zeros((config.height, config.width), dtype=np.int32)

    # -- light

    def light(self, tick: int | None = None) -> np.ndarray:
        """Light per cell in [0, 1]: a cosine band along x, drifting one width per day, with a
        contrast that breathes over the season."""
        c = self.config
        t = self.tick if tick is None else tick
        x = np.arange(c.width, dtype=np.float64)
        phase = 2.0 * np.pi * (x / c.width - t / c.day)
        contrast = c.contrast_min + (1.0 - c.contrast_min) * 0.5 * (1.0 - np.cos(2.0 * np.pi * t / c.season))
        row = 0.5 + 0.5 * contrast * np.cos(phase)
        return np.broadcast_to(row, (c.height, c.width)).copy()

    # -- one tick

    def step(self) -> None:
        c = self.config
        n = c.width * c.height
        light = self.light()
        # growth
        u = self.rng.batch(n).reshape(c.height, c.width)
        moves = (u < c.grow * light) & (self.soil > 0) & (self.food < c.food_cap)
        self.soil -= moves
        self.food += moves
        # decay
        u = self.rng.batch(n).reshape(c.height, c.width)
        moves = (u < c.decay) & (self.food > 0)
        self.food -= moves
        self.soil += moves
        # diffusion: a unit leaves a cell for a neighbour chosen by a second draw
        u = self.rng.batch(n).reshape(c.height, c.width)
        d = self.rng.batch(n).reshape(c.height, c.width)
        leaving = (u < c.diffuse) & (self.soil > 0)
        direction = np.minimum((d * 4).astype(np.int32), 3)
        self.soil -= leaving
        for k, (dy, dx) in enumerate(((-1, 0), (0, 1), (1, 0), (0, -1))):
            gain = np.roll(leaving & (direction == k), shift=(dy, dx), axis=(0, 1))
            self.soil += gain
        self.tick += 1

    # -- accounting

    @property
    def mass(self) -> int:
        return int(self.soil.sum() + self.food.sum())

    def state(self) -> dict:
        return {"tick": self.tick, "rng": self.rng.state, "soil": self.soil.tolist(), "food": self.food.tolist()}
