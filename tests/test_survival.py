"""Integration obligations for the survival and evolution lanes."""

import json

import pytest
from cadence import Brain, Reinforcement

from world.beings import Being, SurvivalWorld, WorldConfig
from world.brains import make_brain, make_history, stage_widths
from world.hazards import make_dens
from world.norms import Norms
from world.population import ACTIONS
from world.random import Mulberry32
from world.senses import RADIUS, cells, scene_size, sectors, summary_row
from world.survival import (
    build_examples,
    evaluate_alignment,
    harvest,
    learner_beings,
    make_learners,
    run_lives,
    scripted_being,
)
from world.teacher import preference_targets, rebalanced, teacher_action

SMALL = WorldConfig(width=10, height=10, dens=2, predators=1, warmup_ticks=10)


def small_brain(**overrides):
    options = dict(width=8, depth=1, history_steps=2, seed=1)
    options.update(overrides)
    return make_brain(**options)


def test_layouts_expose_actions_foresight_and_matched_controls():
    for architecture in ("flat", "composed", "recursive"):
        brain = make_brain(
            architecture=architecture, width=12, depth=2, history_steps=2, seed=2
        )
        info = brain.inspect()
        names = {o["name"] for o in info["outputs"]}
        assert names == set(ACTIONS) | {"foresight"}
        observers = [p for p in info["populations"] if p["role"] == "observer"]
        assert len(observers) == (2 if architecture == "recursive" else 0)
    assert stage_widths(24, 3)[0] == 24
    assert stage_widths(12, 4)[-1] >= 8


def test_mass_is_conserved_with_predators_dens_and_deaths():
    cast = [scripted_being(i, "random") for i in range(3)]
    world = SurvivalWorld(SMALL, cast, seed=5, learning=False)
    for _ in range(120):
        world.step()
    assert world.mass == world.initial_mass  # asserted every tick internally


def test_dens_shelter_and_predators_cannot_enter():
    dens = make_dens(10, 10, 2, seed=1)
    assert dens.sum() == 2
    cast = [scripted_being(0, "random")]
    world = SurvivalWorld(SMALL, cast, seed=5, learning=False)
    for _ in range(80):
        world.step()
        for p in world.predators:
            assert not world.dens[p.y, p.x]


def test_teacher_flees_eats_and_approaches():
    rng = Mulberry32(3)
    n = cells(RADIUS)
    empty = [0.0] * n
    center = n // 2
    # food underfoot, no threat: eat
    food = list(empty)
    food[center] = 0.5
    assert teacher_action(food, empty, empty, 8, 5, rng) == ACTIONS.index("eat")
    # adjacent threat east: never move east
    threat = list(empty)
    threat[center + 1] = 1.0
    for _ in range(12):
        action = teacher_action(food, threat, empty, 8, 5, rng)
        assert ACTIONS[action] != "east"
    # heavy food north, no threat: go north
    food = list(empty)
    for i in sectors(RADIUS)["north"]:
        food[i] = 0.9
    assert teacher_action(food, empty, empty, 8, 5, rng) == ACTIONS.index("north")


def test_summary_row_and_norms_roundtrip():
    n = cells(RADIUS)
    food, threat = [0.0] * n, [0.0] * n
    threat[0] = 1.0
    row = summary_row(food, threat, 0.5)
    assert row[8] == -1.0 and row[9] == -1.0 and row[10] == 1.0
    rows = [{"scene": (0.1, 0.9), "efference": (1.0, 0.0)} for _ in range(4)]
    norms = Norms.fit(rows, ("scene",))
    restored = Norms.load(norms.dump())
    assert restored.apply(rows[0]) == norms.apply(rows[0])
    assert rows[0]["efference"] == restored.apply(rows[0])["efference"]


def test_harvest_records_consequences_and_examples_balance():
    rows = harvest(
        episodes=1, ticks=20, beings=2, history_steps=2, seed=9, config=SMALL
    )
    assert rows and all(set(r["inputs"]) == {"scene", "efference", "context"} for r in rows)
    assert any(r["next"] is not None for r in rows)
    assert all(len(r["inputs"]["scene"]) == scene_size(RADIUS) for r in rows)
    kept = rebalanced([(r, r["action"]) for r in rows], Mulberry32(1), dominant_keep=0.0)
    actions = {a for _, a in kept}
    counts = {}
    for _, a in ((r, r["action"]) for r in rows):
        counts[a] = counts.get(a, 0) + 1
    assert max(counts, key=counts.get) not in actions


def test_bootstrap_improves_alignment_and_admits_nothing_in_evaluation():
    config = SMALL
    rows = harvest(
        episodes=2, ticks=30, beings=2, history_steps=2, seed=11, config=config
    )
    norms = Norms.fit([r["inputs"] for r in rows], ("scene", "efference", "context"))
    examples = build_examples(rows, norms)
    train, test = examples[:40], examples[40:60]
    brain = small_brain()
    before = evaluate_alignment(brain, test)
    for _ in range(2):
        for inputs, targets in train:
            assert brain.observe(inputs, targets)["accepted"]
    after = evaluate_alignment(brain, test)
    assert after["agreement"] > before["agreement"]
    restored = Brain.from_snapshot(brain.snapshot())
    assert restored.predict(test[0][0]) == brain.predict(test[0][0])


def test_live_learning_stores_transitions_and_learner_resumes():
    brain = small_brain()
    learners = make_learners([brain], discount=0.85, exploration=0.2, seed=4)
    norms = Norms(
        {
            "scene": (
                [0.0] * scene_size(RADIUS),
                [1.0] * scene_size(RADIUS),
            )
        }
    )
    cast = learner_beings(learners, 2, norms)
    assert cast[0].patches == brain.inspect()["patches"]
    result = run_lives(
        lambda: cast,
        config=SMALL,
        episodes=1,
        ticks=15,
        seeds=[21],
        learning=True,
    )
    stats = result["episodes"][0]["stats"][0]
    assert stats["ticks"] > 0
    assert stats["transitions"] > 0
    assert not learners[0].inspect()["pending"]  # boundary abandons cleanly
    saved = learners[0].snapshot()
    resumed = Reinforcement.from_snapshot(saved)
    assert resumed.snapshot() == saved


def test_frozen_lives_change_no_parameters():
    brain = small_brain()
    snapshot = brain.snapshot()
    learners = make_learners([Brain.from_snapshot(snapshot)], discount=0.85, exploration=0.0, seed=4)
    norms = Norms({})
    cast = learner_beings(learners, 2, norms)
    run_lives(
        lambda: cast,
        config=SMALL,
        episodes=1,
        ticks=10,
        seeds=[22],
        learning=False,
    )
    frozen = learners[0].brain
    assert (frozen.weights, frozen.biases) == (
        Brain.from_snapshot(snapshot).weights,
        Brain.from_snapshot(snapshot).biases,
    )


def test_refused_solves_wait_without_hidden_fallback():
    brain = small_brain()
    learners = make_learners([brain], discount=0.85, exploration=0.0, seed=4)
    cast = learner_beings(learners, 2, Norms({}))
    world = SurvivalWorld(SMALL, cast, seed=7, learning=False)
    being = cast[0]
    being.learner.act = lambda inputs, explore=True, budget=None: {
        "accepted": False,
        "action": None,
    }
    world.step()
    assert being.stats["refused"] == 1
    assert ACTIONS[being.last_action] == "wait"


def test_evolution_genomes_stay_in_bounds():
    from world.evolution import BOUNDS, Genome, founder_genomes

    rng = Mulberry32(5)
    genome = Genome()
    for step in range(200):
        genome = genome.mutate(rng, step)
        for gene, (low, high) in BOUNDS.items():
            assert low <= getattr(genome, gene) <= high
    founders = founder_genomes(6, rng)
    assert len({(g.radius, g.depth, g.history_steps) for g in founders}) > 1
