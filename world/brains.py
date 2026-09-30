"""Survival brains: deep recursive settlement layouts with value outputs.

One brain per being. The six scalar action-value outputs settle jointly in
one query (the `Reinforcement` vector form), so action ranks vary with the
whole sensed situation without a separate solve per action. A two-coordinate
foresight output predicts the next tick's own energy change and the food under
the body; its later measured error drives the curiosity heuristic and its
witnessed targets keep shaping the shared representation.

Layouts are parameterized the way a genome varies a body: `width` sets the
perception population, `depth` counts recursive observer stages above it (the
last stage carries the outputs), `radius` sets the sensed window and
`history_steps` the temporal context. Raw senses reach every stage, so added
depth never hides information. The `composed` layout keeps identical
population sizes with ordinary state connections, and `flat` is a
direct-sensor control; both exist because a capability claim about
observation wiring needs matched comparisons, not because any depth advantage
is asserted here.
"""

from __future__ import annotations

from cadence import Cortex, History

from .population import ACTIONS
from .senses import RADIUS, SUMMARY_SIZE, scene_size

SIZES = {
    "small": (16, 2),
    "base": (24, 3),
    "wide": (36, 3),
}
FORESIGHT = 2
POLICY_MIN = len(ACTIONS) + FORESIGHT


def stage_widths(width, depth):
    """Perception plus `depth` observer stages, tapering to the policy."""
    policy = max(POLICY_MIN, round(width / 3))
    return [
        max(POLICY_MIN, round(width + (policy - width) * stage / depth))
        for stage in range(depth + 1)
    ]


def context_size(history_steps):
    return History(SUMMARY_SIZE, steps=history_steps).size


def make_history(history_steps):
    return History(SUMMARY_SIZE, steps=history_steps)


def make_brain(
    *,
    architecture="recursive",
    size="base",
    width=None,
    depth=None,
    radius=RADIUS,
    history_steps=4,
    seed=0,
    parameter_prior=0.4,
    settle_budget=4096,
    device="python",
):
    if architecture not in ("flat", "composed", "recursive"):
        raise ValueError("architecture must be flat, composed or recursive")
    if width is None or depth is None:
        width, depth = SIZES[size]
    widths = stage_widths(width, depth)
    layout = Cortex(
        seed=seed,
        parameter_prior=parameter_prior,
        settle_budget=settle_budget,
        device=device,
    )
    scene = layout.input("scene", shape=scene_size(radius))
    efference = layout.input("efference", shape=len(ACTIONS))
    context = layout.input("context", shape=context_size(history_steps))
    senses = (scene, efference, context)
    if architecture == "flat":
        policy = layout.column("policy", patches=widths[-1], inputs=senses)
    else:
        populations = [
            layout.column("perception", patches=widths[0], inputs=senses)
        ]
        for stage, patches in enumerate(widths[1:], start=1):
            name = "policy" if stage == depth else f"observer_{stage}"
            if architecture == "recursive":
                population = layout.observer(
                    name,
                    patches=patches,
                    inputs=senses,
                    observes=tuple(populations),
                )
            else:
                population = layout.column(
                    name, patches=patches, inputs=(*senses, *populations)
                )
            populations.append(population)
        policy = populations[-1]
    for index, name in enumerate(ACTIONS):
        layout.output(name, shape=(), reads=policy, indices=(index,))
    layout.output(
        "foresight",
        shape=FORESIGHT,
        reads=policy,
        indices=tuple(len(ACTIONS) + i for i in range(FORESIGHT)),
    )
    return layout.build()
