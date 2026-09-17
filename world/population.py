"""Creatures on the substrate: mass held, a window read, an action, a metabolic price, a split.

Stage W0 creatures carry no learning brain. Their policy is one of two controls the later stages
are measured against: ``random`` (a uniform action) and ``reflex`` (eat if the cell has food, else
step toward the most food in the window, ties by the draw). Each creature keeps a witnessed map:
what food it saw in each cell of its window and when. The known view of the world is built from
those maps alone (``known_view``), which is what the page draws by default.

Every rule is local and every unit of mass is accounted for: eating moves a unit from the cell's
food into the creature, metabolism moves a unit from the creature into the soil under it, a split
divides the parent's units, a death leaves nothing behind that was not already in the soil.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cadence.records import Mulberry32

from .substrate import Substrate

ACTIONS = ("north", "east", "south", "west", "eat", "wait")
DIRECTIONS = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}


@dataclass(frozen=True)
class PopulationConfig:
    initial: int = 200
    energy_at_birth: int = 8
    split_at: int = 16  # a creature with this much mass divides
    cost_base: float = 0.10  # per-tick probability of losing one unit
    cost_move: float = 0.05
    cost_read: float = 0.002  # per reading field (the window's cells)
    radius: int = 1  # window radius (a gene from W2 on; fixed here)
    policy: str = "reflex"  # or "random"
    max_creatures: int = 4000


@dataclass
class Creature:
    id: int
    x: int
    y: int
    energy: int
    hue: float
    lineage: int
    parent: int | None
    born: int
    age: int = 0
    last_action: int = 5
    outcome: str = "none"
    # the witnessed map: cell -> (food seen, tick seen)
    memory: dict[tuple[int, int], tuple[int, int]] = field(default_factory=dict)


class Population:
    def __init__(self, substrate: Substrate, config: PopulationConfig = PopulationConfig(), seed: int = 1) -> None:
        self.substrate = substrate
        self.config = config
        self.rng = Mulberry32(seed)
        self.next_id = 0
        self.creatures: list[Creature] = []
        self.births = 0
        self.deaths = 0
        w, h = substrate.config.width, substrate.config.height
        for _ in range(config.initial):
            x = int(self.rng.random() * w)
            y = int(self.rng.random() * h)
            hue = self.rng.random()
            self._spawn(x, y, config.energy_at_birth, hue, lineage=None, parent=None)

    # -- accounting

    @property
    def held(self) -> int:
        return sum(c.energy for c in self.creatures)

    @property
    def mass(self) -> int:
        """The whole world's mass: soil + food + what creatures hold. Constant over time."""
        return self.substrate.mass + self.held

    def occupied(self) -> np.ndarray:
        grid = np.full((self.substrate.config.height, self.substrate.config.width), -1, dtype=np.int64)
        for i, c in enumerate(self.creatures):
            grid[c.y, c.x] = i
        return grid

    # -- creatures

    def _spawn(self, x: int, y: int, energy: int, hue: float, lineage: int | None, parent: int | None) -> Creature:
        c = Creature(id=self.next_id, x=x, y=y, energy=energy, hue=hue, lineage=self.next_id if lineage is None else lineage, parent=parent, born=self.substrate.tick)
        self.next_id += 1
        self.creatures.append(c)
        return c

    def window(self, c: Creature) -> list[tuple[int, int, int]]:
        """(dx, dy, food) for each cell in the window, row by row."""
        w, h = self.substrate.config.width, self.substrate.config.height
        r = self.config.radius
        out = []
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                out.append((dx, dy, int(self.substrate.food[(c.y + dy) % h, (c.x + dx) % w])))
        return out

    def witness(self, c: Creature) -> None:
        w, h = self.substrate.config.width, self.substrate.config.height
        for dx, dy, food in self.window(c):
            c.memory[((c.x + dx) % w, (c.y + dy) % h)] = (food, self.substrate.tick)

    def policy(self, c: Creature, window: list[tuple[int, int, int]]) -> int:
        if self.config.policy == "random":
            return int(self.rng.random() * len(ACTIONS))
        here = next(f for dx, dy, f in window if dx == 0 and dy == 0)
        if here > 0:
            return ACTIONS.index("eat")
        best, best_food = None, 0
        draw = self.rng.random()
        for dx, dy, food in window:
            if (dx, dy) == (0, 0) or food <= best_food:
                continue
            best, best_food = (dx, dy), food
        if best is None:
            return int(draw * 4)
        dx, dy = best
        if abs(dx) >= abs(dy) and dx != 0:
            return ACTIONS.index("east" if dx > 0 else "west")
        return ACTIONS.index("south" if dy > 0 else "north")

    # -- one tick

    def step(self) -> None:
        s = self.substrate
        w, h = s.config.width, s.config.height
        cfg = self.config
        occupied = self.occupied()
        order = np.arange(len(self.creatures))
        draws = self.rng.batch(max(len(order) - 1, 0))
        for i in range(len(order) - 1, 0, -1):
            j = int(draws[len(order) - 1 - i] * (i + 1))
            order[i], order[j] = order[j], order[i]
        for k in order:
            c = self.creatures[k]
            c.age += 1
            window = self.window(c)
            self.witness(c)
            a = self.policy(c, window)
            c.last_action = a
            name = ACTIONS[a]
            moved = False
            c.outcome = "none"
            if name in DIRECTIONS:
                dx, dy = DIRECTIONS[name]
                nx, ny = (c.x + dx) % w, (c.y + dy) % h
                if occupied[ny, nx] < 0:
                    occupied[c.y, c.x] = -1
                    occupied[ny, nx] = k
                    c.x, c.y = nx, ny
                    moved = True
                    c.outcome = "moved"
                else:
                    c.outcome = "blocked"
            elif name == "eat":
                if s.food[c.y, c.x] > 0:
                    s.food[c.y, c.x] -= 1
                    c.energy += 1
                    c.outcome = "ate"
            # metabolism: one unit to the soil under the creature, with the price as the probability
            price = cfg.cost_base + cfg.cost_read * len(window) + (cfg.cost_move if moved else 0.0)
            if self.rng.random() < price:
                c.energy -= 1
                s.soil[c.y, c.x] += 1
        # deaths and splits after every creature has acted
        survivors = []
        for k, c in enumerate(self.creatures):
            if c.energy <= 0:
                self.deaths += 1
                continue
            survivors.append(c)
        self.creatures = survivors
        occupied = self.occupied()
        children = []
        for k, c in enumerate(self.creatures):
            if c.energy < cfg.split_at or len(self.creatures) + len(children) >= cfg.max_creatures:
                continue
            free = [(dx, dy) for (dx, dy) in DIRECTIONS.values() if occupied[(c.y + dy) % h, (c.x + dx) % w] < 0]
            if not free:
                continue
            dx, dy = free[int(self.rng.random() * len(free))]
            nx, ny = (c.x + dx) % w, (c.y + dy) % h
            share = c.energy // 2
            c.energy -= share
            hue = (c.hue + (self.rng.random() - 0.5) * 0.02) % 1.0
            child = Creature(id=self.next_id, x=nx, y=ny, energy=share, hue=hue, lineage=c.lineage, parent=c.id, born=s.tick)
            self.next_id += 1
            occupied[ny, nx] = len(self.creatures) + len(children)
            children.append(child)
            self.births += 1
        self.creatures.extend(children)


def known_view(pop: Population) -> dict[str, np.ndarray]:
    """The world as its living observers hold it.

    ``witnesses``: how many living creatures hold a record of the cell. ``held``: the mean food
    those records say, or -1 where none. ``spread``: the spread between the records' values
    (max minus min), which is where observers disagree with each other. ``stale``: the mean age
    of the records in ticks. ``error``: |held - actual food|, where the record disagrees with the
    substrate, -1 where none.
    """
    s = pop.substrate
    h, w = s.config.height, s.config.width
    count = np.zeros((h, w), dtype=np.int32)
    total = np.zeros((h, w), dtype=np.float64)
    lo = np.full((h, w), np.inf)
    hi = np.full((h, w), -np.inf)
    age = np.zeros((h, w), dtype=np.float64)
    for c in pop.creatures:
        for (x, y), (food, tick) in c.memory.items():
            count[y, x] += 1
            total[y, x] += food
            lo[y, x] = min(lo[y, x], food)
            hi[y, x] = max(hi[y, x], food)
            age[y, x] += s.tick - tick
    seen = count > 0
    held = np.where(seen, total / np.maximum(count, 1), -1.0)
    spread = np.where(seen, hi - lo, 0.0)
    stale = np.where(seen, age / np.maximum(count, 1), 0.0)
    error = np.where(seen, np.abs(held - s.food), -1.0)
    return {"witnesses": count, "held": held, "spread": spread, "stale": stale, "error": error}
