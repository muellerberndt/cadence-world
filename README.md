# cadence-world

**Current brain guidance.** Within a creature's life, the intended brain acquires reusable relationships
between senses, actions and outcomes, retains context and reads durable memory.
Witnessed prediction failures can admit local repair tied to the executed action.
Fresh founders remain an evolutionary control, not a reason to reset every
observation. Compare retained-state behavior, memory cuts and repair schedules.
The world's simulated metabolic price does not measure physical energy, and
its survival results do not establish low recurring compute.

For new integrated brains, follow the [world-model guide](https://github.com/muellerberndt/cadence/blob/main/docs/world-model.md) and use
`Brain.compose`: observer-like software patches with reciprocal connections,
bounded local state, ports, memory readback, records and witnessed repair, with
public evidence for
behavioral claims. Continuing state and durable acquired knowledge support the
same life. Deep System 1 is the foundation; System 2 is optional feedback inside
the same settlement. The implementations and measurements below keep their
own source identity.

[Website](https://floatingpragma.io/cadence/) · [Library](https://github.com/muellerberndt/cadence) · [Paper](https://philpapers.org/rec/MUECAP-2)

A conserved-mass world under a moving sun, now with dens, predators and
beings that carry **Cadence 0.50** brains. Every being owns a deep
recursive-settlement brain with six jointly settled action values, an
explicit bounded sensory history, a reward learner with replay, a foresight
predictor and a curiosity heuristic. Two Python lanes produce receipts:
**survival** (fixed bodies, matched controls) and **evolution** (mutating
senses and depth competing in one world). The earlier supervised **settling**
forager remains available. The browser ecosystem lives in
[cadence-demos](https://github.com/muellerberndt/cadence-demos) as Patch
World.

## Run the survival lane

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m world.survival --trace
.venv/bin/python -m world.evolution --trace
.venv/bin/python -m pytest tests -q
python3 -m http.server 8080
```

Open [the survival replay](http://localhost:8080/web/survival.html) and load
`runs/survival.json` or `runs/evolution.json`. The page replays the Python
run's recorded frames: food, dens, predators, each being's sensed window and
per-being outcomes. It executes no solver and invents no frames.

## The world

One quantity, mass, in integer units, conserved at every tick. A band of
sunlight crosses the torus and grows food where it passes; food decays and
soil diffuses. Fixed den cells exclude predators. Predators move on even
ticks, patrol until a being comes within sense range, then chase; adjacency
drains one energy unit per tick into the soil under the being. Eating moves a
unit of food into the body; metabolism prices existence, movement, every
sensed window cell and every brain patch, so wider senses and bigger brains
are a metabolic trade rather than a free win. Death ends the body; splits are
disabled so one brain owns one continuing life.

## The being

Senses: local food, threat and den channels in a window of genome-controlled
radius, own light, own energy, the last executed action, and a `History`
window over a twelve-value summary row. Motion — the predator's heading, the
light band's drift — exists only in how consecutive summary rows differ, so
temporal tactics require the supplied context. Inputs are standardized by
per-coordinate norms fitted on bootstrap rows only and saved beside every
checkpoint.

Brain: a perception population plus recursive observer stages, each reading
raw senses and observing every earlier population's states and prediction
errors; the final stage exposes six scalar action values and a two-value
foresight output in one joint settlement. `composed` keeps identical sizes
with ordinary state connections and `flat` is a direct-sensor control; both
exist for matched comparisons, and no depth advantage is claimed.

Life: a disclosed scripted teacher with the same sensory window supplies
bootstrap demonstrations (danger first, then the meal, then the approach,
then a committed search), rebalanced so rare actions keep their weight and
admitted through a small-batch warmup ramp. The live phase is the library's
`Reinforcement` helper: epsilon exploration, one-step value targets, bounded
replay of stored transitions. Reward is the being's own measured energy
change plus a bounded curiosity bonus from the foresight predictor's error
reduction. Refused solves wait explicitly and are counted; there is no hidden
reflex fallback and no route script.

Receipts compare the same frozen evaluation worlds before learning, after
learning, and under random, threat-blind reflex, scripted-teacher and
untrained-brain controls, then measure tactics directly: threat response,
den use under threat against den use when safe, and light-band tracking.
Differences on those matched worlds are the lane's only behavioral evidence.

## The evolution lane

`world.evolution` runs lineage competition. A genome sets window radius,
perception width, recursive depth, history steps, parameter prior, discount,
exploration and curiosity weight. Fresh genomes bootstrap from a cached
teacher corpus for their radius and history window, then every lineage lives
in one shared world and competes for the same conserved food under the same
predators. The fitter half persists with its trained brain and replay memory;
the other half's lineages end and mutated offspring are raised fresh. Weights
never copy across layouts: offspring inherit a body plan, not a parent's
memory. This lane is a competition demonstration with receipts, not a
controlled architecture comparison; matched claims stay in the survival lane.

`world.sweep` runs the survival lane across observation wiring, parameter
prior and history-window axes with one process per configuration and a
summary row per job.

## The settling lane

`world.settling` is the earlier supervised forager: a bootstrap teacher, six
settled motor preferences, live rollouts with untrained/random/reflex
controls, and [the settling replay](http://localhost:8080/web/settling.html).
It demonstrates supervised local foraging and recursive coupling; it does not
establish autonomous discovery or an advantage from additional depth. See
[the measured comparison](receipts/settling-0.48/README.md).

Optional `--device cpu`, `mps` or `cuda` on any lane uses Cadence's tensor
engine after installing `cadence-net[gpu]`. A GPU is not automatically faster
for these small brains.

## The Python world

`world/substrate.py` holds the light-driven soil and food physics;
`world/hazards.py` the dens and predators; `world/senses.py` the window,
summary and history encodings; `world/brains.py` the layouts;
`world/teacher.py` the scripted curriculum; `world/beings.py` the beings and
the shared tick; `world/survival.py`, `world/evolution.py` and
`world/sweep.py` the lanes; `world/population.py` the earlier stage-W0
controls. The tests check mass conservation through predators, dens and
deaths, den exclusion, teacher priorities, history and norms custody,
alignment evaluation purity, live-phase transition custody, learner
snapshot resume, frozen-parameter evaluation, refusal handling without
hidden fallbacks, genome bounds, and the settling lane's earlier
obligations.

## Forking

Everything is here. The physics live in `world/substrate.py` and
`world/hazards.py`; the prices in `world/beings.py`; the genome bounds at the
top of `world/evolution.py`.

## License

MIT.
