"""Beings with continuing reward-driven brains in the conserved-mass world.

Each being owns one `Reinforcement` learner (six jointly settled action
values), one `History` window, one `LearningProgress` curiosity tracker and
the shared fitted norms. Per turn it delivers the previous action's actual
consequence as feedback, replays one sampled batch, then acts. Reward is the
being's own measured energy change plus a bounded curiosity bonus from the
foresight predictor's error; nothing scripts a route or a preferred cell.
Death is a terminal transition. Refused solves wait explicitly and are
counted; there is no hidden reflex fallback.

Mass stays conserved: eating moves food into the body, metabolism and
predator bites move body units into the soil, and the accounting is asserted
every tick.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .hazards import Pack, make_dens
from .population import ACTIONS, DIRECTIONS
from .random import Mulberry32
from .senses import RADIUS, cells, observe, side, window_channels
from .substrate import Substrate, SubstrateConfig
from .teacher import foresight_targets, teacher_action

CURIOSITY_WEIGHT = 0.15
FORESIGHT_EVERY = 4
REPLAY_EVERY = 2
DEATH_REWARD = -1.0


@dataclass(frozen=True)
class WorldConfig:
    width: int = 24
    height: int = 24
    day: int = 240
    dens: int = 4
    predators: int = 2
    energy_at_birth: int = 12
    cost_base: float = 0.05
    cost_read: float = 0.001  # per sensed window cell, the price of wide senses
    cost_patch: float = 0.0002  # per brain patch, the price of a big brain
    cost_move: float = 0.02
    warmup_ticks: int = 60


@dataclass
class Being:
    id: int
    x: int
    y: int
    energy: int
    kind: str = "learner"  # or "random", "reflex", "teacher"
    learner: object = None
    history: object = None
    curiosity: object = None
    norms: object = None
    radius: int = RADIUS
    patches: int = 0
    curiosity_weight: float = CURIOSITY_WEIGHT
    alive: bool = True
    last_action: int = ACTIONS.index("wait")
    outcome: str = "none"
    born: int = 0
    died: int = None
    mark: int = None  # energy at the pending action's decision moment
    prev_inputs: dict = None
    prev_foresight: tuple = None
    prev_key: str = "empty"
    stats: Counter = field(default_factory=Counter)


def context_key(threat, food):
    if any(v > 0 for v in threat):
        return "threat"
    if any(v > 0 for v in food):
        return "food"
    return "empty"


class SurvivalWorld:
    """One substrate, its dens and predators, and a mixed population."""

    def __init__(self, config, beings, *, seed, learning=True):
        self.config = config
        self.learning = learning
        self.substrate = Substrate(
            SubstrateConfig(width=config.width, height=config.height, day=config.day),
            seed=seed,
        )
        for _ in range(config.warmup_ticks):
            self.substrate.step()
        self.dens = make_dens(config.width, config.height, config.dens, seed)
        self.pack = Pack(self.substrate, self.dens, config.predators, seed)
        self.rng = Mulberry32(seed ^ 0xA511E9B3)
        self.beings = beings
        taken = {(p.x, p.y) for p in self.pack.predators}
        for being in self.beings:
            while True:
                x = int(self.rng.random() * config.width)
                y = int(self.rng.random() * config.height)
                if (x, y) not in taken:
                    taken.add((x, y))
                    being.x, being.y = x, y
                    break
            being.energy = config.energy_at_birth
            being.born = self.substrate.tick
            if being.history is not None:
                being.history.reset()
        self.initial_mass = self.mass
        self.work = Counter()
        self.frames = []
        self.recorder = None  # optional (being, inputs, action) harvest hook

    @property
    def predators(self):
        return self.pack.predators

    @property
    def mass(self):
        return self.substrate.mass + sum(b.energy for b in self.beings if b.alive)

    @property
    def alive(self):
        return [b for b in self.beings if b.alive]

    # -- one being's turn

    def _sense(self, being):
        raw, summary = observe(self, being, being.radius)
        if being.history is not None:
            raw = dict(raw)
            raw["context"] = being.history.push(summary)
        return being.norms.apply(raw) if being.norms is not None else raw

    def _feedback(self, being, inputs):
        """Deliver the pending action's measured consequence, then replay."""
        learner = being.learner
        if learner is None or not learner.inspect()["pending"]:
            return
        delta = being.energy - being.mark
        extrinsic = max(-1.0, min(1.0, delta / 2.0))
        bonus = 0.0
        if being.prev_foresight is not None and being.curiosity is not None:
            actual = foresight_targets(
                delta, int(self.substrate.food[being.y, being.x])
            )
            error = sum(
                abs(a - b) for a, b in zip(being.prev_foresight, actual)
            ) / len(actual)
            bonus = being.curiosity.update(being.prev_key, error)
        weight = being.curiosity_weight
        reward = max(
            -1.0,
            min(1.0, (1 - weight) * extrinsic + weight * bonus),
        )
        result = learner.feedback(reward, inputs, learn=self.learning)
        being.stats["transitions"] += 1
        if self.learning:
            if being.stats["transitions"] % REPLAY_EVERY == 0:
                replayed = learner.replay()
                if not replayed.get("accepted"):
                    being.stats["replay_refused"] += 1
            if (
                being.prev_inputs is not None
                and being.stats["transitions"] % FORESIGHT_EVERY == 0
            ):
                taught = learner.brain.observe(
                    being.prev_inputs,
                    {
                        "foresight": foresight_targets(
                            delta, int(self.substrate.food[being.y, being.x])
                        )
                    },
                )
                if not taught["accepted"]:
                    being.stats["foresight_refused"] += 1

    def _decide(self, being, inputs):
        """One action index, from the learner or a scripted control."""
        if being.learner is not None:
            decision = being.learner.act(inputs, explore=self.learning)
            being.stats["solves"] += 1
            if not decision["accepted"]:
                being.stats["refused"] += 1
                being.prev_foresight = None
                return ACTIONS.index("wait"), False
            settlement = decision["settlement"]
            self.work.update(settlement.get("work", {}))
            being.prev_foresight = settlement["outputs"].get("foresight")
            return decision["action"], True
        food, threat, den = window_channels(self, being, being.radius)
        if being.kind == "random":
            return int(self.rng.random() * len(ACTIONS)), False
        if being.kind == "teacher":
            return (
                teacher_action(
                    food,
                    threat,
                    den,
                    being.energy,
                    being.last_action,
                    self.rng,
                    radius=being.radius,
                ),
                False,
            )
        # threat-blind reflex: eat here, else step toward the most food
        here = cells(being.radius) // 2
        if food[here] > 0:
            return ACTIONS.index("eat"), False
        best, best_food = None, 0.0
        for index, value in enumerate(food):
            if index == here or value <= best_food:
                continue
            best, best_food = index, value
        if best is None:
            return int(self.rng.random() * 4), False
        s, r = side(being.radius), being.radius
        dx, dy = best % s - r, best // s - r
        if abs(dx) >= abs(dy) and dx != 0:
            return ACTIONS.index("east" if dx > 0 else "west"), False
        return ACTIONS.index("south" if dy > 0 else "north"), False

    def _execute(self, being, action, occupied):
        w, h = self.config.width, self.config.height
        name = ACTIONS[action]
        being.last_action = action
        being.outcome = "none"
        moved = False
        if name in DIRECTIONS:
            dx, dy = DIRECTIONS[name]
            nx, ny = (being.x + dx) % w, (being.y + dy) % h
            if occupied.get((nx, ny)) is None:
                del occupied[(being.x, being.y)]
                occupied[(nx, ny)] = being.id
                being.x, being.y = nx, ny
                moved = True
                being.outcome = "moved"
            else:
                being.outcome = "blocked"
        elif name == "eat":
            if self.substrate.food[being.y, being.x] > 0:
                self.substrate.food[being.y, being.x] -= 1
                being.energy += 1
                being.outcome = "ate"
                being.stats["ate"] += 1
        price = (
            self.config.cost_base
            + self.config.cost_read * cells(being.radius)
            + self.config.cost_patch * being.patches
            + (self.config.cost_move if moved else 0.0)
        )
        if self.rng.random() < price and being.energy > 0:
            being.energy -= 1
            self.substrate.soil[being.y, being.x] += 1

    # -- one world tick

    def step(self, trace=False):
        self.substrate.step()
        order = list(range(len(self.beings)))
        for i in range(len(order) - 1, 0, -1):
            j = int(self.rng.random() * (i + 1))
            order[i], order[j] = order[j], order[i]
        occupied = {(b.x, b.y): b.id for b in self.alive}
        for index in order:
            being = self.beings[index]
            if not being.alive:
                continue
            inputs = self._sense(being)
            self._feedback(being, inputs)
            being.mark = being.energy
            action, pending = self._decide(being, inputs)
            being.prev_inputs = inputs if pending else None
            if being.learner is not None and not pending:
                # a scripted or refused turn owns no learner transition
                if being.learner.inspect()["pending"]:
                    being.learner.reset()
            food, threat, _ = window_channels(self, being, being.radius)
            being.prev_key = context_key(threat, food)
            if self.recorder is not None:
                self.recorder(being, inputs, action)
            self._execute(being, action, occupied)
            being.stats["ticks"] += 1
        drained = self.pack.step(self.alive)
        for being in self.alive:
            being.stats["drained"] += drained.get(being.id, 0)
        for being in self.alive:
            if being.energy <= 0:
                being.alive = False
                being.died = self.substrate.tick
                being.outcome = "died"
                if (
                    being.learner is not None
                    and being.learner.inspect()["pending"]
                ):
                    if self.learning:
                        being.learner.feedback(
                            DEATH_REWARD, None, terminal=True, learn=True
                        )
                    else:
                        being.learner.reset()
                if being.history is not None:
                    being.history.reset()
        assert self.mass == self.initial_mass, "Mass conservation failed"
        if trace:
            self.frames.append(
                {
                    "tick": self.substrate.tick,
                    "food": self.substrate.food.tolist(),
                    "beings": [
                        {
                            "id": b.id,
                            "x": b.x,
                            "y": b.y,
                            "energy": b.energy,
                            "alive": b.alive,
                            "action": ACTIONS[b.last_action],
                            "outcome": b.outcome,
                            "kind": b.kind,
                            "radius": b.radius,
                        }
                        for b in self.beings
                    ],
                    "predators": [
                        {"x": p.x, "y": p.y} for p in self.pack.predators
                    ],
                }
            )
