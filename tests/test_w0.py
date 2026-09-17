import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from world.population import ACTIONS, Population, PopulationConfig, known_view  # noqa: E402
from world.substrate import Substrate, SubstrateConfig  # noqa: E402

SMALL = SubstrateConfig(width=24, height=16, day=120, season=1200)


def test_light_is_a_drifting_band_in_unit_interval():
    s = Substrate(SMALL, seed=0)
    l0 = s.light(0)
    assert l0.shape == (16, 24) and l0.min() >= 0.0 and l0.max() <= 1.0
    # one day later the band's peak is back where it was; a quarter day later it has moved a quarter width
    peak = lambda t: int(np.argmax(s.light(t)[0]))
    assert peak(SMALL.day) == peak(0)
    assert peak(SMALL.day // 4) == (peak(0) + 6) % SMALL.width
    # the contrast breathes with the season: flat at its low, full at its high
    assert np.ptp(s.light(0)[0]) < np.ptp(s.light(SMALL.season // 2)[0])


def test_substrate_conserves_mass_and_replays_from_seed():
    a = Substrate(SMALL, seed=3)
    b = Substrate(SMALL, seed=3)
    m0 = a.mass
    for _ in range(300):
        a.step()
        b.step()
    assert a.mass == m0
    assert np.array_equal(a.soil, b.soil) and np.array_equal(a.food, b.food)
    assert a.food.sum() > 0  # the sun made food


def test_population_conserves_mass_through_eating_metabolism_splits_and_deaths():
    for policy in ("random", "reflex"):
        s = Substrate(SMALL, seed=5)
        p = Population(s, PopulationConfig(initial=60, policy=policy), seed=7)
        m0 = p.mass
        for _ in range(400):
            s.step()
            p.step()
            assert p.mass == m0
        assert p.deaths > 0 or p.births > 0


def test_reflex_outlives_random_walkers():
    def alive(policy, seed):
        s = Substrate(SMALL, seed=seed)
        p = Population(s, PopulationConfig(initial=60, policy=policy), seed=seed + 100)
        for _ in range(600):
            s.step()
            p.step()
        return len(p.creatures)

    reflex = [alive("reflex", k) for k in range(3)]
    random = [alive("random", k) for k in range(3)]
    assert sum(reflex) > sum(random)


def test_known_view_is_built_from_records_only():
    s = Substrate(SMALL, seed=1)
    p = Population(s, PopulationConfig(initial=10, policy="random"), seed=2)
    for _ in range(50):
        s.step()
        p.step()
    view = known_view(p)
    seen = view["witnesses"] > 0
    assert 0 < seen.sum() < seen.size  # some of the world has been witnessed, not all
    assert (view["held"][~seen] == -1).all()
    # the records go stale: where a cell was seen long ago and changed since, the record is wrong
    assert view["error"][seen].max() > 0 or view["stale"][seen].max() > 0


def test_actions_are_the_declared_six():
    assert ACTIONS == ("north", "east", "south", "west", "eat", "wait")
