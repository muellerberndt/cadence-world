"""Integration obligations for the current-Cadence world lane."""

import numpy as np
import pytest
from cadence import Brain

from world.settling import (
    SettlingPopulation,
    encode_food,
    evaluate,
    examples,
    live,
    make_brain,
    teaching_preferences,
)
from world.substrate import Substrate, SubstrateConfig


@pytest.mark.parametrize("architecture", ["flat", "composed", "recursive"])
def test_layout_information_and_joint_qualification(architecture):
    brain = make_brain(architecture=architecture, width=3, depth=2)
    info = brain.inspect()
    assert info["patches"] == (6 if architecture == "flat" else 12)
    assert info["outputs"][0]["sensor_coverage_by_coordinate"] == (9,) * 6
    assert info["output_connected_patches"] == info["patches"]
    observers = [p for p in info["populations"] if p["role"] == "observer"]
    assert len(observers) == (2 if architecture == "recursive" else 0)
    if observers:
        assert observers[-1]["observes"] == ["perception", "observer_0"]
    result = brain.settle(encode_food([0, 1, 0, 0, 2, 0, 0, 0, 0]))
    assert result["qualified"]
    assert len(result["state"]) == info["patches"]


def test_observer_and_observed_populations_have_reciprocal_influence():
    brain = make_brain(width=2)
    senses = encode_food([0, 1, 2, 0, 3, 0, 0, 0, 0])
    free = brain.settle(senses)
    raised = brain.settle(senses, interventions={"perception": [0.6, -0.6]})
    feedback = brain.settle(senses, targets={"action": [0.6] * 6})
    assert free["qualified"] and raised["qualified"] and feedback["qualified"]
    assert (
        max(
            abs(a - b)
            for a, b in zip(free["outputs"]["action"], raised["outputs"]["action"])
        )
        > 1e-5
    )
    assert (
        max(abs(a - b) for a, b in zip(free["state"][:2], feedback["state"][:2])) > 1e-5
    )
    assert brain.inspect()["admissions"] == 0


def test_refusal_waits_without_reading_partial_outputs_or_learning():
    brain = make_brain()
    population = SettlingPopulation(
        Substrate(SubstrateConfig(width=4, height=4)), brain
    )
    population.brain.step = lambda inputs: {
        "qualified": False,
        "work": {},
        "outputs": {"action": [100, 0, 0, 0, 0, 0]},
    }
    before = brain.snapshot()
    choice = population.policy(population.creatures[0], [(0, 0, 1)] * 9)
    assert choice == 5 and population.refused == 1
    assert brain.snapshot() == before


def test_live_uses_no_teacher_and_preserves_relations_and_mass(monkeypatch):
    from world import settling

    brain = make_brain()
    before = brain.snapshot()
    monkeypatch.setattr(
        settling, "teaching_preferences", lambda *_: pytest.fail("Live teacher called")
    )
    a = live(brain, seed=42, ticks=20, trace=True)
    b = live(Brain.from_snapshot(before), seed=42, ticks=20, trace=True)
    assert a["frames"] == b["frames"]
    assert a["initial_total_mass"] == a["final_total_mass"]
    assert a["solves"] == 20 and a["refused"] == 0
    assert brain.inspect()["admissions"] == 0


def test_short_bootstrap_improves_unclamped_heldout_predictions():
    brain = make_brain(width=2)
    checks = examples(16, 901)
    before = evaluate(brain, checks)
    data = examples(32, 902)
    for _ in range(3):
        for inputs, targets in data:
            result = brain.observe(inputs, targets)
            assert result["accepted"]
    after = evaluate(brain, checks)
    assert after["max_error"] < before["max_error"] * 0.6
    assert after["correct"] > before["correct"]
    restored = Brain.from_snapshot(brain.snapshot())
    assert restored.predict(checks[0][0]) == brain.predict(checks[0][0])


def test_sensory_units_and_teacher_keep_action_contract_explicit():
    assert encode_food([0] * 8 + [8])["food"][-1] == 1
    with pytest.raises(ValueError):
        encode_food([9] * 9)
    food = [0] * 9
    food[4] = 4
    targets = teaching_preferences(encode_food(food))["action"]
    assert np.argmax(targets) == 4  # eat at current cell
