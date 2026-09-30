"""A current-Cadence forager in the conserved-mass world.

The bootstrap teacher supplies bounded local action preferences. During live
rollouts only qualified settled outputs select actions; there is no teacher or
reflex fallback. This is supervised acquisition of a small foraging policy,
not reward-only discovery, learned planning or a depth-advantage claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import random
import time
from collections import Counter
from pathlib import Path

from cadence import Brain, Cortex, __version__, bootstrap

from .population import ACTIONS, Population, PopulationConfig
from .substrate import Substrate, SubstrateConfig


def make_brain(*, architecture="recursive", width=4, depth=1, seed=0, device="python"):
    """Build exact-width populations with six settled motor preference outputs.

    Recursive observers read all preceding populations' current states and
    errors. Ordinary composition has the same population counts but reads
    states only. Flat control has six directly connected output patches.
    Sensors reach each stage, so increasing depth never hides raw information.
    """
    if architecture not in ("flat", "composed", "recursive"):
        raise ValueError("architecture must be flat, composed or recursive")
    if type(width) is not int or width < 1 or type(depth) is not int or depth < 1:
        raise ValueError("width and depth must be positive integers")
    layout = Cortex(seed=seed, parameter_prior=1.0, device=device)
    senses = layout.input("food", shape=9)
    if architecture == "flat":
        motor = layout.column("motor", patches=6, inputs=senses)
    else:
        populations = [layout.column("perception", patches=width, inputs=senses)]
        for level in range(depth):
            size = 6 if level == depth - 1 else width
            if architecture == "recursive":
                motor = layout.observer(
                    f"observer_{level}",
                    patches=size,
                    inputs=senses,
                    observes=tuple(populations),
                )
            else:
                motor = layout.column(
                    f"processing_{level}",
                    patches=size,
                    inputs=(senses, *populations),
                )
            populations.append(motor)
    layout.output("action", shape=6, reads=motor)
    return layout.build()


def encode_food(counts):
    """Nine row-major local cell counts in fixed units: eight food units = 1."""
    if len(counts) != 9 or any(not 0 <= value <= 8 for value in counts):
        raise ValueError("Provide nine food counts between zero and eight")
    return {"food": tuple(float(value) / 8 for value in counts)}


def teaching_preferences(inputs):
    """A disclosed local teacher, called only to construct bootstrap/check data.

    Move toward adjacent food, favor eating at the current cell, and penalize
    waiting. These are bounded scores, not probabilities or measured rewards.
    The policy and its coefficients are a hand-set curriculum/control. No
    evolutionary selection of these coefficients is claimed.
    """
    food = inputs["food"]
    here = food[4]
    # Broad directional fields also include diagonal food in the local retina.
    sectors = ((0, 1, 2), (2, 5, 8), (6, 7, 8), (0, 3, 6))
    scores = [
        math.tanh(1.2 * sum(food[i] for i in sector) - here) for sector in sectors
    ]
    scores.extend((math.tanh(4 * here - 0.2), -0.4))
    return {"action": tuple(scores)}


def examples(count, seed):
    """Independent synthetic local sensory scenes, including sparse scenes.

    Teaching scenes are explicitly generated, not harvested live experiences.
    Separate seeds reserve development and final-test scenes before fitting.
    """
    rng = random.Random(seed)
    pairs = []
    for index in range(count):
        maximum = 2 if index % 3 else 8
        counts = [
            rng.randrange(maximum + 1) if rng.random() < 0.45 else 0 for _ in range(9)
        ]
        inputs = encode_food(counts)
        pairs.append((inputs, teaching_preferences(inputs)))
    return pairs


def evaluate(brain, pairs):
    """Pure, unclamped held-out queries; ties accept any teacher-maximal action."""
    before = brain.snapshot()
    correct = qualified = 0
    error = 0.0
    work = Counter()
    for inputs, targets in pairs:
        result = brain.settle(inputs)
        work.update(result["work"])
        if not result["qualified"]:
            continue
        qualified += 1
        scores = result["outputs"]["action"]
        desired = targets["action"]
        chosen = max(range(6), key=scores.__getitem__)
        correct += desired[chosen] >= max(desired) - 1e-12
        error = max(error, max(abs(a - b) for a, b in zip(scores, desired)))
    assert brain.snapshot() == before, "Evaluation must not admit experience"
    return {
        "examples": len(pairs),
        "qualified": qualified,
        "correct": correct,
        "action_agreement": correct / len(pairs),
        "max_error": error if qualified == len(pairs) else None,
        "work": dict(work),
    }


class SettlingPopulation(Population):
    """One body driven by one continuing brain, with existing world physics."""

    def __init__(self, substrate, brain, *, seed=0):
        super().__init__(
            substrate,
            PopulationConfig(
                initial=1,
                energy_at_birth=16,
                split_at=1000000,
                max_creatures=1,
                cost_base=0.06,
                cost_move=0.02,
                radius=1,
            ),
            seed=seed,
        )
        self.brain = brain
        self.refused = 0
        self.solves = 0
        self.work = Counter()
        self.last_solve = None

    def policy(self, creature, window):
        result = self.brain.step(encode_food([food for _, _, food in window]))
        self.last_solve = result
        self.solves += 1
        self.work.update(result["work"])
        if not result["qualified"]:
            self.refused += 1
            # Explicit safe refusal: no hidden reflex or forced food-seeking.
            return ACTIONS.index("wait")
        return max(range(6), key=result["outputs"]["action"].__getitem__)


def live(brain, *, seed, ticks=96, trace=False, control=None):
    """A teacher-free continuation; optional controls share the physical setup.

    Population splits are disabled to keep each brain's event stream explicit.
    Food, soil and body mass remain conserved; CPU time is measured separately
    and is not converted into a fictional metabolic cost in this lane.
    """
    substrate = Substrate(SubstrateConfig(width=12, height=12, day=120), seed=seed)
    for _ in range(60):
        substrate.step()
    if control is None:
        population = SettlingPopulation(substrate, brain, seed=seed + 1000)
    else:
        population = Population(
            substrate,
            PopulationConfig(
                initial=1,
                energy_at_birth=16,
                split_at=1000000,
                max_creatures=1,
                cost_base=0.06,
                cost_move=0.02,
                radius=1,
                policy=control,
            ),
            seed=seed + 1000,
        )
    before_relations = None if brain is None else (brain.weights, brain.biases)
    initial_mass = population.mass
    outcomes = Counter()
    frames = []
    started = time.perf_counter()
    for _ in range(ticks):
        if not population.creatures:
            break
        substrate.step()
        population.step()
        assert population.mass == initial_mass, "Mass conservation failed"
        for creature in population.creatures:
            outcomes[creature.outcome] += 1
        if trace:
            solve = getattr(population, "last_solve", None)
            frames.append(
                {
                    "tick": substrate.tick,
                    "food": substrate.food.tolist(),
                    "creatures": [
                        {
                            "x": c.x,
                            "y": c.y,
                            "energy": c.energy,
                            "action": ACTIONS[c.last_action],
                            "outcome": c.outcome,
                        }
                        for c in population.creatures
                    ],
                    "state": list(brain.state) if brain is not None else [],
                    "stationarity": solve["stationarity"] if solve else None,
                    "qualified": solve["qualified"] if solve else None,
                    "sweeps": solve["sweeps"] if solve else None,
                }
            )
    if brain is not None:
        assert (brain.weights, brain.biases) == before_relations
    return {
        "seed": seed,
        "ticks_requested": ticks,
        "ticks_completed": substrate.tick - 60,
        "alive": len(population.creatures),
        "body_mass": population.held,
        "initial_total_mass": initial_mass,
        "final_total_mass": population.mass,
        "outcomes": dict(outcomes),
        "solves": getattr(population, "solves", 0),
        "refused": getattr(population, "refused", 0),
        "work": dict(getattr(population, "work", {})),
        "seconds": time.perf_counter() - started,
        "frames": frames,
    }


def run(
    *,
    architecture="recursive",
    seed=0,
    width=4,
    depth=1,
    epochs=20,
    samples=96,
    ticks=96,
    device="python",
    trace=False,
):
    """Run one bounded bootstrap, final test, continuation and baseline suite."""
    started = time.perf_counter()
    brain = make_brain(
        architecture=architecture, width=width, depth=depth, seed=seed, device=device
    )
    training = examples(samples, 100)
    development = examples(24, 200)
    heldout = examples(48, 300)
    baseline = evaluate(brain, heldout)
    preparation = bootstrap(
        brain, training, checks=development, max_error=0.12, epochs=epochs, seed=seed
    )
    learned = evaluate(brain, heldout)
    saved = brain.snapshot()
    restored = Brain.from_snapshot(saved)
    assert restored.predict(heldout[0][0]) == brain.predict(heldout[0][0])
    # A final-test outcome never changes the predeclared curriculum or config.
    environment_seed = 400 + seed
    rollout = live(brain, seed=environment_seed, ticks=ticks, trace=trace)
    controls = {
        kind: live(None, seed=environment_seed, ticks=ticks, control=kind)
        for kind in ("random", "reflex")
    }
    untrained = live(
        make_brain(
            architecture=architecture,
            width=width,
            depth=depth,
            seed=seed,
            device=device,
        ),
        seed=environment_seed,
        ticks=ticks,
    )
    return {
        "schema": "cadence-world-settling-v1",
        "cadence_version": __version__,
        "distribution_metadata_version": importlib.metadata.version("cadence-net"),
        "architecture": architecture,
        "seed": seed,
        "layout": brain.inspect(),
        "config": {
            "width": width,
            "depth": depth,
            "epochs": epochs,
            "samples": samples,
            "ticks": ticks,
            "device": device,
            "parameter_prior": 1.0,
        },
        "teacher": "explicit local sensory action-preference demonstrations; no live teacher",
        "baseline": baseline,
        "bootstrap": preparation,
        "heldout": learned,
        "checkpoint": saved,
        "checkpoint_sha256": hashlib.sha256(saved.encode()).hexdigest(),
        "checkpoint_roundtrip": True,
        "live": rollout,
        "controls": controls,
        "untrained_live": untrained,
        "seconds": time.perf_counter() - started,
        "source_sha256": {
            str(path.relative_to(Path(__file__).parent.parent)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--architecture", choices=("flat", "composed", "recursive"), default="recursive"
    )
    for name, default in (
        ("seed", 0),
        ("width", 4),
        ("depth", 1),
        ("epochs", 20),
        ("samples", 96),
        ("ticks", 96),
    ):
        parser.add_argument(f"--{name}", type=int, default=default)
    parser.add_argument("--device", default="python")
    parser.add_argument(
        "--trace", action="store_true", help="Include small viewer replay frames"
    )
    parser.add_argument("--output", type=Path, default=Path("runs/settling.json"))
    args = parser.parse_args()
    if args.samples < 1 or args.ticks < 1 or args.epochs < 0 or args.seed < 0:
        parser.error("samples/ticks must be positive; epochs/seed must be nonnegative")
    options = vars(args).copy()
    output = options.pop("output")
    result = run(**options)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "receipt": str(output),
                "architecture": args.architecture,
                "bootstrap_passed": result["bootstrap"]["passed"],
                "heldout": result["heldout"],
                "outcomes": result["live"]["outcomes"],
                "refused": result["live"]["refused"],
                "seconds": result["seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
