"""Lineage competition over brain bodies: senses, depth and constants evolve.

Each individual carries a genome: window radius, perception width, recursive
observer depth, history steps, parameter prior, discount, exploration and
curiosity weight. A fresh genome is bootstrapped from the cached teacher
corpus for its radius and history window, then lives in one shared world
where every lineage competes for the same conserved food under the same
predators. Wider senses and bigger brains pay their declared metabolic price
every tick, so growth is a trade, not a free win.

Selection is by measured fitness: survival ticks plus eaten food, averaged
over the generation's episodes. The fitter half persists with its trained
brain and continuing replay memory; the other half's lineages end, and
mutated offspring of the survivors are bootstrapped fresh. Weights never copy
across layouts — an offspring inherits a body plan, not its parent's memory.

This lane is a competition demonstration with receipts, not a controlled
architecture comparison: fitness differences confound the genome, its random
wiring, its bootstrap and its shared-world history. Matched claims belong to
the survival lane's fixed controls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from cadence import LearningProgress, Reinforcement, __version__, bootstrap

from .beings import Being, WorldConfig
from .brains import make_brain, make_history
from .norms import Norms
from .population import ACTIONS
from .random import Mulberry32
from .survival import (
    REPLAY_BATCH,
    REPLAY_CAPACITY,
    REWARD_SCALE,
    VALUE_SCALE,
    WARMUP_RAMP,
    build_examples,
    harvest,
    run_lives,
)
from .teacher import rebalanced

BOUNDS = {
    "radius": (1, 3),
    "width": (12, 48),
    "depth": (1, 4),
    "history_steps": (1, 6),
    "parameter_prior": (0.05, 1.0),
    "discount": (0.75, 0.95),
    "exploration": (0.05, 0.3),
    "curiosity_weight": (0.0, 0.3),
}
MUTATION_RATE = 0.35


@dataclass(frozen=True)
class Genome:
    radius: int = 2
    width: int = 20
    depth: int = 2
    history_steps: int = 3
    parameter_prior: float = 0.4
    discount: float = 0.85
    exploration: float = 0.15
    curiosity_weight: float = 0.15
    brain_seed: int = 0

    def mutate(self, rng, brain_seed):
        changes = {"brain_seed": brain_seed}
        for gene, (low, high) in BOUNDS.items():
            if rng.random() >= MUTATION_RATE:
                continue
            value = getattr(self, gene)
            if isinstance(low, int):
                value += 1 if rng.random() < 0.5 else -1
                # widths move in visible steps, not single patches
                if gene == "width":
                    value = getattr(self, gene) + (4 if rng.random() < 0.5 else -4)
            else:
                value *= 0.7 + 0.6 * rng.random()
            changes[gene] = max(low, min(high, value))
        return replace(self, **changes)


def founder_genomes(count, rng):
    """A varied first generation: every sense and depth band is represented."""
    founders = []
    for index in range(count):
        founders.append(
            Genome(
                radius=1 + index % 3,
                width=12 + 4 * (index % 4),
                depth=1 + index % 3,
                history_steps=(1, 3, 4, 6)[index % 4],
                brain_seed=index,
            ).mutate(rng, index)
        )
    return founders


@dataclass
class Individual:
    id: int
    genome: Genome
    parent: int
    born: int
    learner: object = None
    norms: object = None
    fitness: float = None
    bootstrap_reason: str = None


class Nursery:
    """Cached teacher corpora and bootstrapping for new genomes."""

    def __init__(self, config, *, ticks, seed, device):
        self.config = config
        self.ticks = ticks
        self.seed = seed
        self.device = device
        self.cache = {}

    def corpus(self, radius, history_steps):
        key = (radius, history_steps)
        if key not in self.cache:
            rows = harvest(
                episodes=4,
                ticks=self.ticks,
                beings=3,
                history_steps=history_steps,
                seed=1000 + self.seed + 31 * radius + history_steps,
                config=self.config,
                radius=radius,
            )
            check_rows = harvest(
                episodes=1,
                ticks=self.ticks,
                beings=3,
                history_steps=history_steps,
                seed=2000 + self.seed + 31 * radius + history_steps,
                config=self.config,
                radius=radius,
            )
            rng = Mulberry32(self.seed ^ (radius * 131 + history_steps))
            rows = [row for row, _ in rebalanced([(r, r["action"]) for r in rows], rng)]
            norms = Norms.fit(
                [row["inputs"] for row in rows], ("scene", "efference", "context")
            )
            self.cache[key] = (
                build_examples(rows, norms)[:800],
                build_examples(check_rows, norms)[:160],
                norms,
            )
        return self.cache[key]

    def raise_individual(self, individual):
        genome = individual.genome
        training, checks, norms = self.corpus(genome.radius, genome.history_steps)
        brain = make_brain(
            width=genome.width,
            depth=genome.depth,
            radius=genome.radius,
            history_steps=genome.history_steps,
            parameter_prior=genome.parameter_prior,
            seed=genome.brain_seed,
            device=self.device,
        )
        cursor = 0
        for ramp in WARMUP_RAMP:
            if training[cursor : cursor + ramp]:
                brain.observe_batch(training[cursor : cursor + ramp])
            cursor += ramp
        report = bootstrap(
            brain,
            training[cursor:],
            checks=checks,
            max_error=0.35,
            epochs=2,
            seed=self.seed + individual.id,
            batch_size=16,
        )
        individual.learner = Reinforcement(
            brain,
            actions=len(ACTIONS),
            action_input=None,
            value_output=ACTIONS,
            discount=genome.discount,
            exploration=genome.exploration,
            reward_scale=REWARD_SCALE,
            value_scale=VALUE_SCALE,
            capacity=REPLAY_CAPACITY,
            batch_size=REPLAY_BATCH,
            seed=self.seed + individual.id,
        )
        individual.norms = norms
        individual.bootstrap_reason = report["reason"]
        return individual


def competition_beings(individuals):
    return [
        Being(
            id=slot,
            x=0,
            y=0,
            energy=0,
            kind="learner",
            learner=individual.learner,
            history=make_history(individual.genome.history_steps),
            curiosity=LearningProgress(rate=0.1),
            norms=individual.norms,
            radius=individual.genome.radius,
            patches=individual.learner.brain.inspect()["patches"],
            curiosity_weight=individual.genome.curiosity_weight,
        )
        for slot, individual in enumerate(individuals)
    ]


def evolve(
    *,
    generations=6,
    population=8,
    ticks=240,
    episodes=2,
    seed=0,
    device="python",
    trace=False,
):
    started = time.perf_counter()
    config = WorldConfig(width=32, height=32, dens=5, predators=3)
    rng = Mulberry32(seed ^ 0xE01)
    nursery = Nursery(config, ticks=ticks, seed=seed, device=device)
    next_id = population
    individuals = [
        nursery.raise_individual(
            Individual(id=index, genome=genome, parent=-1, born=0)
        )
        for index, genome in enumerate(founder_genomes(population, rng))
    ]
    history = []
    frames = []
    dens = None
    for generation in range(generations):
        cast = competition_beings(individuals)
        lives = run_lives(
            lambda: cast,
            config=config,
            episodes=episodes,
            ticks=ticks,
            seeds=[6000 + seed * 100 + generation * 10 + e for e in range(episodes)],
            learning=True,
            trace=trace and generation == generations - 1,
        )
        for slot, individual in enumerate(individuals):
            survival = sum(
                o["ticks_survived"][slot] for o in lives["episodes"]
            ) / len(lives["episodes"])
            ate = sum(
                o["stats"][slot].get("ate", 0) for o in lives["episodes"]
            ) / len(lives["episodes"])
            individual.fitness = survival + 0.5 * ate
        ranked = sorted(individuals, key=lambda i: i.fitness, reverse=True)
        survivors = ranked[: population // 2]
        history.append(
            {
                "generation": generation,
                "individuals": [
                    {
                        "id": i.id,
                        "parent": i.parent,
                        "born": i.born,
                        "genome": asdict(i.genome),
                        "patches": i.learner.brain.inspect()["patches"],
                        "fitness": i.fitness,
                        "bootstrap_reason": i.bootstrap_reason,
                        "survived": i in survivors,
                    }
                    for i in ranked
                ],
                "probes": lives["probes"],
                "mean_survival_ticks": lives["mean_survival_ticks"],
                "mean_food_eaten": lives["mean_food_eaten"],
            }
        )
        if trace and generation == generations - 1:
            frames = lives["frames"]
            dens = lives["dens"]
        if generation == generations - 1:
            individuals = ranked
            break
        offspring = []
        for index in range(population - len(survivors)):
            parent = survivors[index % len(survivors)]
            child = Individual(
                id=next_id,
                genome=parent.genome.mutate(rng, next_id),
                parent=parent.id,
                born=generation + 1,
            )
            next_id += 1
            offspring.append(nursery.raise_individual(child))
        individuals = survivors + offspring
    best = individuals[0]
    return {
        "schema": "cadence-world-evolution-v1",
        "cadence_version": __version__,
        "config": {
            "generations": generations,
            "population": population,
            "ticks": ticks,
            "episodes": episodes,
            "seed": seed,
            "device": device,
            "world": config.__dict__,
            "bounds": {k: list(v) for k, v in BOUNDS.items()},
            "mutation_rate": MUTATION_RATE,
            "fitness": "mean survival ticks + 0.5 * mean food eaten",
        },
        "generations": history,
        "best": {
            "id": best.id,
            "genome": asdict(best.genome),
            "fitness": best.fitness,
            "learner_checkpoint": best.learner.snapshot(),
            "norms": best.norms.dump(),
        },
        "frames": frames,
        "dens": dens,
        "seconds": time.perf_counter() - started,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in (
        ("generations", 6),
        ("population", 8),
        ("ticks", 240),
        ("episodes", 2),
        ("seed", 0),
    ):
        parser.add_argument(f"--{name}", type=int, default=default)
    parser.add_argument("--device", default="python")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("runs/evolution.json"))
    args = parser.parse_args()
    options = vars(args).copy()
    output = options.pop("output")
    receipt = evolve(**options)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "receipt": str(output),
                "best_genome": receipt["best"]["genome"],
                "best_fitness": receipt["best"]["fitness"],
                "final_mean_survival": receipt["generations"][-1][
                    "mean_survival_ticks"
                ],
                "seconds": receipt["seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
