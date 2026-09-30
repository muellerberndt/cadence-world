"""The survival lane: bootstrapped, then reward-driven, beings under threat.

One bounded pipeline per configuration:

1. harvest a corpus from disclosed scripted-teacher lives in real worlds;
2. fit input norms on training rows only and rebalance the dominant action;
3. bootstrap each being's brain with a small-batch warmup ramp, then batched
   replay with unclamped readiness checks;
4. measure teacher-alignment on reserved rows, then frozen pre-learning lives;
5. run the live phase: `Reinforcement` feedback and replay per turn, foresight
   witnesses every fourth transition, curiosity-weighted reward;
6. re-run the same frozen evaluation worlds after learning, beside random,
   threat-blind reflex, scripted-teacher and untrained-brain controls;
7. write one receipt with checkpoints, norms, stats and behavior probes.

The probes measure tactics, not intentions: threat response, den use under
threat, and light-band tracking. A difference between the post-learning brain
and its bootstrapped-frozen twin on matched worlds is the only evidence this
lane offers that the live phase changed behavior; no depth advantage or
autonomous-discovery claim is made beyond those measured comparisons.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from cadence import Brain, LearningProgress, Reinforcement, __version__, bootstrap

from .beings import Being, SurvivalWorld, WorldConfig
from .brains import make_brain, make_history
from .norms import Norms
from .population import ACTIONS
from .random import Mulberry32
from .senses import RADIUS
from .teacher import foresight_targets, preference_targets, rebalanced

VALUE_SCALE = 0.6
REWARD_SCALE = 1.0
REPLAY_CAPACITY = 512
REPLAY_BATCH = 8
WARMUP_RAMP = (4, 8)


def scripted_being(index, kind, history_steps=None, radius=None):
    history = make_history(history_steps) if history_steps else None
    return Being(
        id=index,
        x=0,
        y=0,
        energy=0,
        kind=kind,
        history=history,
        radius=RADIUS if radius is None else radius,
    )


def revive(being):
    being.alive = True
    being.died = None
    being.mark = None
    being.prev_inputs = None
    being.prev_foresight = None
    being.prev_key = "empty"
    being.last_action = ACTIONS.index("wait")
    being.outcome = "none"
    if being.learner is not None and being.learner.inspect()["pending"]:
        being.learner.reset()


def harvest(*, episodes, ticks, beings, history_steps, seed, config, radius=None):
    """Teacher lives in real worlds, recorded as raw rows with consequences."""
    rows = []
    for episode in range(episodes):
        cast = [
            scripted_being(i, "teacher", history_steps, radius)
            for i in range(beings)
        ]
        world = SurvivalWorld(config, cast, seed=seed + episode, learning=False)
        raw = {}

        def record(being, inputs, action):
            entry = {
                "inputs": inputs,
                "action": action,
                "energy": being.energy,
                "next": None,
            }
            previous = raw.get(being.id)
            if previous is not None:
                previous["next"] = (
                    being.energy - previous["energy"],
                    int(world.substrate.food[being.y, being.x]),
                )
            raw[being.id] = entry
            rows.append(entry)

        world.recorder = record
        for _ in range(ticks):
            if not world.alive:
                break
            world.step()
    return rows


def build_examples(rows, norms):
    """Normalized bootstrap pairs: value preferences plus witnessed foresight."""
    examples = []
    for row in rows:
        targets = dict(preference_targets(row["action"]))
        if row["next"] is not None:
            targets["foresight"] = foresight_targets(*row["next"])
        examples.append((norms.apply(row["inputs"]), targets))
    return examples


def evaluate_alignment(brain, examples):
    """Pure ranked agreement with the recorded teacher choice; no admissions."""
    before = brain.snapshot()
    agree = qualified = 0
    recall = {name: [0, 0] for name in ACTIONS}
    work = Counter()
    for inputs, targets in examples:
        recorded = max(range(len(ACTIONS)), key=lambda i: targets[ACTIONS[i]])
        recall[ACTIONS[recorded]][1] += 1
        result = brain.settle(inputs)
        work.update(result["work"])
        if not result["qualified"]:
            continue
        qualified += 1
        chosen = max(
            range(len(ACTIONS)),
            key=lambda i: result["outputs"][ACTIONS[i]][0],
        )
        if chosen == recorded:
            agree += 1
            recall[ACTIONS[recorded]][0] += 1
    assert brain.snapshot() == before, "Evaluation must not admit experience"
    return {
        "examples": len(examples),
        "qualified": qualified,
        "agreement": agree / len(examples) if examples else None,
        "recall_by_action": {
            name: (hit / total if total else None) for name, (hit, total) in recall.items()
        },
        "work": dict(work),
    }


def make_learners(brains, *, discount, exploration, seed):
    return [
        Reinforcement(
            brain,
            actions=len(ACTIONS),
            action_input=None,
            value_output=ACTIONS,
            discount=discount,
            exploration=exploration,
            reward_scale=REWARD_SCALE,
            value_scale=VALUE_SCALE,
            capacity=REPLAY_CAPACITY,
            batch_size=REPLAY_BATCH,
            seed=seed + index,
        )
        for index, brain in enumerate(brains)
    ]


def learner_beings(learners, history_steps, norms, radius=None):
    return [
        Being(
            id=index,
            x=0,
            y=0,
            energy=0,
            kind="learner",
            learner=learner,
            history=make_history(history_steps),
            curiosity=LearningProgress(rate=0.1),
            norms=norms,
            radius=RADIUS if radius is None else radius,
            patches=learner.brain.inspect()["patches"],
        )
        for index, learner in enumerate(learners)
    ]


class Probes:
    """Online tactic measurements over one set of lives."""

    def __init__(self, world):
        self.world = world
        self.previous = {}
        self.totals = Counter()
        self.sums = {
            "flee": 0.0,
            "den_threat": 0,
            "den_safe": 0,
            "light_here": 0.0,
            "light_world": 0.0,
        }

    def tick(self):
        world = self.world
        light = world.substrate.light()
        for being in world.alive:
            distance = min(
                (
                    world.pack._distance(p.x, p.y, being.x, being.y)
                    for p in world.pack.predators
                ),
                default=None,
            )
            previous = self.previous.get(being.id)
            if previous is not None and previous <= 3 and distance is not None:
                self.totals["threat_events"] += 1
                self.sums["flee"] += distance - previous
            self.previous[being.id] = distance
            in_den = bool(world.dens[being.y, being.x])
            if distance is not None and distance <= 4:
                self.totals["threat_ticks"] += 1
                self.sums["den_threat"] += in_den
            else:
                self.totals["safe_ticks"] += 1
                self.sums["den_safe"] += in_den
            self.sums["light_here"] += float(light[being.y, being.x])
            self.sums["light_world"] += float(light.mean())
            self.totals["ticks"] += 1

    def report(self):
        t = self.totals
        return {
            "threat_response": (
                self.sums["flee"] / t["threat_events"] if t["threat_events"] else None
            ),
            "den_rate_under_threat": (
                self.sums["den_threat"] / t["threat_ticks"] if t["threat_ticks"] else None
            ),
            "den_rate_when_safe": (
                self.sums["den_safe"] / t["safe_ticks"] if t["safe_ticks"] else None
            ),
            "light_tracking": (
                (self.sums["light_here"] - self.sums["light_world"]) / t["ticks"]
                if t["ticks"]
                else None
            ),
            "counts": dict(t),
        }


def run_lives(
    cast_factory,
    *,
    config,
    episodes,
    ticks,
    seeds,
    learning,
    trace=False,
):
    """Run episodes over matched world seeds; return stats, probes and frames."""
    outcomes = []
    frames = []
    dens = None
    probe_totals = []
    cast = cast_factory()
    for episode in range(episodes):
        for being in cast:
            revive(being)
        world = SurvivalWorld(
            config, cast, seed=seeds[episode % len(seeds)], learning=learning
        )
        probes = Probes(world)
        before = {b.id: Counter(b.stats) for b in cast}
        for _ in range(ticks):
            if not world.alive:
                break
            world.step(trace=trace and episode == 0)
            probes.tick()
        for being in cast:
            revive(being)  # abandon any pending action at the boundary
        episode_stats = {
            b.id: {
                key: b.stats[key] - before[b.id][key]
                for key in set(b.stats) | set(before[b.id])
            }
            for b in cast
        }
        outcomes.append(
            {
                "seed": seeds[episode % len(seeds)],
                "stats": episode_stats,
                "ticks_survived": {
                    b.id: episode_stats[b.id].get("ticks", 0) for b in cast
                },
                "solver_work": dict(world.work),
            }
        )
        probe_totals.append(probes.report())
        if trace and episode == 0:
            frames = world.frames
            dens = world.dens.tolist()
    mean_survival = sum(
        sum(o["ticks_survived"].values()) / max(len(o["ticks_survived"]), 1)
        for o in outcomes
    ) / max(len(outcomes), 1)
    mean_ate = sum(
        sum(s.get("ate", 0) for s in o["stats"].values()) / max(len(o["stats"]), 1)
        for o in outcomes
    ) / max(len(outcomes), 1)
    return {
        "episodes": outcomes,
        "mean_survival_ticks": mean_survival,
        "mean_food_eaten": mean_ate,
        "probes": probe_totals,
        "frames": frames,
        "dens": dens,
    }


def run(
    *,
    architecture="recursive",
    size="base",
    history_steps=4,
    seed=0,
    parameter_prior=0.4,
    discount=0.85,
    exploration=0.15,
    device="python",
    beings=4,
    harvest_episodes=6,
    ticks=240,
    epochs=4,
    batch_size=16,
    learn_episodes=12,
    eval_episodes=4,
    trace=False,
):
    started = time.perf_counter()
    config = WorldConfig()
    brain_options = dict(
        architecture=architecture,
        size=size,
        history_steps=history_steps,
        parameter_prior=parameter_prior,
        device=device,
    )

    training_rows = harvest(
        episodes=harvest_episodes,
        ticks=ticks,
        beings=3,
        history_steps=history_steps,
        seed=1000 + seed,
        config=config,
    )
    check_rows = harvest(
        episodes=2,
        ticks=ticks,
        beings=3,
        history_steps=history_steps,
        seed=2000 + seed,
        config=config,
    )
    test_rows = harvest(
        episodes=2,
        ticks=ticks,
        beings=3,
        history_steps=history_steps,
        seed=3000 + seed,
        config=config,
    )
    balance_rng = Mulberry32(seed ^ 0x0BADF00D)
    kept = rebalanced(
        [(row, row["action"]) for row in training_rows], balance_rng
    )
    training_rows = [row for row, _ in kept]
    norms = Norms.fit(
        [row["inputs"] for row in training_rows],
        ("scene", "efference", "context"),
    )
    training = build_examples(training_rows, norms)[:1200]
    checks = build_examples(check_rows, norms)[:200]
    final_test = build_examples(test_rows, norms)[:240]

    brains = [
        make_brain(seed=seed * 100 + index, **brain_options)
        for index in range(beings)
    ]
    corpus_actions = Counter(row["action"] for row in training_rows)
    reports = []
    warmups = []
    for index, brain in enumerate(brains):
        cursor = 0
        accepted = []
        for ramp in WARMUP_RAMP:
            batch = training[cursor : cursor + ramp]
            if batch:
                accepted.append(bool(brain.observe_batch(batch)["accepted"]))
            cursor += ramp
        warmups.append(accepted)
        reports.append(
            bootstrap(
                brain,
                training[cursor:],
                checks=checks,
                max_error=0.35,
                epochs=epochs,
                seed=seed + index,
                batch_size=batch_size,
            )
        )
    alignment = [evaluate_alignment(brain, final_test) for brain in brains]
    bootstrapped = [brain.snapshot() for brain in brains]

    eval_seeds = [9000 + seed * 10 + i for i in range(eval_episodes)]
    learn_seeds = [5000 + seed * 100 + i for i in range(learn_episodes)]

    def frozen_cast(snapshots):
        def factory():
            learners = make_learners(
                [Brain.from_snapshot(s) for s in snapshots],
                discount=discount,
                exploration=exploration,
                seed=7000 + seed,
            )
            return learner_beings(learners, history_steps, norms)

        return factory

    before_learning = run_lives(
        frozen_cast(bootstrapped),
        config=config,
        episodes=eval_episodes,
        ticks=ticks,
        seeds=eval_seeds,
        learning=False,
    )

    learners = make_learners(
        brains, discount=discount, exploration=exploration, seed=4000 + seed
    )
    cast = learner_beings(learners, history_steps, norms)
    learning_phase = run_lives(
        lambda: cast,
        config=config,
        episodes=learn_episodes,
        ticks=ticks,
        seeds=learn_seeds,
        learning=True,
    )
    life_snapshots = [learner.snapshot() for learner in learners]
    trained = [learner.brain.snapshot() for learner in learners]

    after_learning = run_lives(
        frozen_cast(trained),
        config=config,
        episodes=eval_episodes,
        ticks=ticks,
        seeds=eval_seeds,
        learning=False,
        trace=trace,
    )

    controls = {}
    for kind in ("random", "reflex", "teacher"):
        controls[kind] = run_lives(
            lambda kind=kind: [
                scripted_being(i, kind, history_steps if kind == "teacher" else None)
                for i in range(beings)
            ],
            config=config,
            episodes=eval_episodes,
            ticks=ticks,
            seeds=eval_seeds,
            learning=False,
        )
    controls["untrained"] = run_lives(
        frozen_cast(
            [
                make_brain(seed=seed * 100 + index, **brain_options).snapshot()
                for index in range(beings)
            ]
        ),
        config=config,
        episodes=eval_episodes,
        ticks=ticks,
        seeds=eval_seeds,
        learning=False,
    )

    receipt = {
        "schema": "cadence-world-survival-v1",
        "cadence_version": __version__,
        "config": {
            **brain_options,
            "seed": seed,
            "discount": discount,
            "exploration": exploration,
            "value_scale": VALUE_SCALE,
            "reward_scale": REWARD_SCALE,
            "replay_capacity": REPLAY_CAPACITY,
            "replay_batch": REPLAY_BATCH,
            "warmup_ramp": WARMUP_RAMP,
            "batch_size": batch_size,
            "epochs": epochs,
            "beings": beings,
            "ticks": ticks,
            "learn_episodes": learn_episodes,
            "eval_episodes": eval_episodes,
            "world": config.__dict__,
        },
        "layout": brains[0].inspect(),
        "corpus": {
            "training_rows": len(training),
            "checks": len(checks),
            "final_test": len(final_test),
            "actions": {ACTIONS[a]: n for a, n in sorted(corpus_actions.items())},
        },
        "warmup_accepted": warmups,
        "bootstrap": reports,
        "alignment": alignment,
        "before_learning": before_learning,
        "learning_phase": {
            k: v for k, v in learning_phase.items() if k != "frames"
        },
        "after_learning": after_learning,
        "controls": controls,
        "checkpoints": {
            "bootstrapped_first": bootstrapped[0],
            "life_first": life_snapshots[0],
        },
        "checkpoint_sha256": [
            hashlib.sha256(s.encode()).hexdigest() for s in life_snapshots
        ],
        "norms": norms.dump(),
        "seconds": time.perf_counter() - started,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
    }
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--architecture", choices=("flat", "composed", "recursive"), default="recursive"
    )
    parser.add_argument("--size", choices=("small", "base", "wide"), default="base")
    for name, default in (
        ("history-steps", 4),
        ("seed", 0),
        ("beings", 4),
        ("harvest-episodes", 6),
        ("ticks", 240),
        ("epochs", 4),
        ("batch-size", 16),
        ("learn-episodes", 12),
        ("eval-episodes", 4),
    ):
        parser.add_argument(f"--{name}", type=int, default=default)
    for name, default in (
        ("parameter-prior", 0.4),
        ("discount", 0.85),
        ("exploration", 0.15),
    ):
        parser.add_argument(f"--{name}", type=float, default=default)
    parser.add_argument("--device", default="python")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("runs/survival.json"))
    args = parser.parse_args()
    options = {k.replace("-", "_"): v for k, v in vars(args).items()}
    output = options.pop("output")
    receipt = run(**options)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "receipt": str(output),
                "alignment": [a["agreement"] for a in receipt["alignment"]],
                "before": receipt["before_learning"]["mean_survival_ticks"],
                "after": receipt["after_learning"]["mean_survival_ticks"],
                "teacher": receipt["controls"]["teacher"]["mean_survival_ticks"],
                "reflex": receipt["controls"]["reflex"]["mean_survival_ticks"],
                "seconds": receipt["seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
