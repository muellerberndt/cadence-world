# cadence-world: shared observers constructing a world

Date: 2026-09-17. Status: W0 built in Python with tests; the page runs W0 to W3 in one file (evolving records brains, symbols, the three views, the live brain scan); section 10 holds the first measurement. Prompted by a Telegram reader's request for a
Conway-like, visual, aesthetic simulation of how shared observers construct reality, and by the
cadence-adaptation programme's result that wiring is evolved across generations while records are
learned within a life (`cadence-adaptation/fable/2026-09-17-evolved-development.md`).

## 1. The idea in one paragraph

A grid world with a cellular-automaton substrate that grows food. Creatures with records brains
live on it. Each creature sees a small window, eats, moves, emits a symbol, and splits when it has
stored enough energy. The child inherits a mutated genome: the wiring of its brain and its
development policy. It inherits none of the parent's records. Within its life the creature writes
records of what followed each reading it took, and acts by imagining the consequences of its
candidate actions in those records. There is no fitness function; energy and death select. The
picture the visitor watches is the union of the creatures' records: where no creature has ever
looked the world is dark, where one has looked it is faint, where many agree it is sharp, and where
their records disagree with each other or with the substrate it shimmers. The substrate can be
shown, but the default view is the world as its observers hold it.

That last choice is the whole point for the reader's question. Reality on the page is what the
population has witnessed and agrees on. A creature's private world (click on it) is its own records
and its imagined consequences, side by side with its brain scan.

## 2. What is already built and reused

| piece | where | reused as |
|---|---|---|
| Records cortex: sparse expansion, winner-take-all, delta-rule records, no replay | `cadence/src/cadence/records.py` | every creature's world head |
| Experience agent: `Moment`, imagined consequences over candidate actions, the witnessed stores (place, map, word), best-first search | `cadence-examples/agent/`, `cadence-examples/world/brain.py` | the creature, with the window in place of the cell |
| Genome, `develop`, `mutate`, `evolve` | `cadence/src/cadence/genome.py` | the inherited wiring |
| Genome with the development policy: masks, heads, gains, bank settings, allocation thresholds, probation, guard sensitivity, learning rates | lane F, `cadence-adaptation` | the full inherited object |
| World-change guard: protect the bank that fits the old world, twin bank for the new, mixture without feedback | `cadence-examples` branch `structural-allocation`, `agent/allocate.py` | the seasons test (section 6, W4) |
| Browser port of the agent, records head, stores, planner; brain scan | `cadence-examples/world/web/`, `cadence/src/cadence/brain_scan.js`, `atlas.py` | the page |
| Word store: word to referent co-occurrence in one life, joint attention | S02 `env.py` `set_word_rule`, `stores.js` `WordStore` | the ear |

The S02 world in `cadence-examples/world` is one agent on a 6 by 6 map with a curriculum. This
lane is many agents, no curriculum, an open world, and selection. It lives in its own folder at the
root of `oph-meta` beside `cadence-1942` and `cadence-artist`, since the public examples stay at
five (`cadence-docs-patterns-and-pages` rule). Runs and checkpoints live on the Cadence1 instance
per the large-data policy; the folder keeps sources, receipts and the page.

## 3. The rules, minimal form (v0)

Bernhard's direction (2026-09-17): a very simple world with physical rules that nevertheless allow
the evolution of very complex observers. So the rules are physics, and the complexity is on the
observer's side of the boundary. Four physical commitments:

1. **Conservation.** One quantity, mass, in integer units. Every unit is at every tick in exactly
   one place: soil, food, or a creature. Nothing is created or destroyed; the sun moves mass
   from soil into food, metabolism moves it from creatures back into soil.
2. **One external drive.** Light. It is the only thing that varies from outside, and it varies
   slowly and predictably: a band of light drifts across the torus with a period (the day), and its
   contrast breathes with a longer period (the season). Everything else follows from the rules.
3. **Locality.** Every rule touches a cell and its neighbours. Every sense is a window around the
   creature. Every signal reaches two cells.
4. **Computation costs mass.** A reading field, an expansion cell, a bank, a written record: each
   has a metabolic price. A bigger observer is possible and pays for itself or dies.

Everything a creature is told is in this section. Anything not listed here is learned within a life
or selected across lives.

**Substrate.** A torus of 64 by 64 cells (later 128). Each cell holds soil nutrient n and food f,
integer units of mass. Light l(x, t) in [0, 1] is a cosine band drifting along x with period P_day,
its amplitude modulated with period P_season. Each tick, per cell:

- growth: with probability g times l, one unit moves from soil to food (if n above 0);
- decay: with probability d, one unit moves from food to soil (if f above 0);
- diffusion: with probability delta, one unit of soil moves to a uniformly chosen neighbour.

With no creatures this reaches a steady state that follows the light around. A creature's
metabolic losses go into the soil of the cell it stands on, so where creatures gather the soil
enriches and, when the light returns, food follows. A creature that dies leaves what it holds in
the soil beneath it.

**Creature state.** Position, energy e (units of mass held), age, genome, brain, and the symbol it
emitted last tick.

**Senses (the reading).** Categorical fields, each with a missingness flag as in S02:

- the food level in the 3 by 3 window (nine fields, four classes each),
- creature presence in the eight neighbouring cells (eight fields, two classes),
- the symbol heard: the symbol emitted last tick by the nearest neighbour within two cells, or
  silence (K + 1 classes),
- own energy in four bins,
- own last action and its outcome (moved, blocked, ate, emitted, split, nothing),
- the displacement of the last action (dx, dy as in S02).

**Actions.** Move north, east, south, west; eat (takes one unit of food from the cell); emit symbol
k for k in 1..K (K is a gene, 0 to 8); wait. Split is not an action: when energy exceeds E_split
the creature divides, the child appears in a free neighbouring cell with half the energy and a
mutated genome, and the parent keeps the other half. This keeps reproduction out of the decision
and makes energy the only currency.

**Costs.** Per tick a creature loses one unit of mass to the soil under it with probability
c_0 + c_read times (reading fields) + c_cell times (expansion cells, in thousands) + c_bank times
(live banks) + c_write times (records written this tick) + c_move (if it moved) + c_emit (if it
emitted). Eating moves one unit from the cell's food into the creature. A creature at 0 dies. The
brain cost is what lane F subtracts from fitness as "the life's cost", here paid in the world's own
currency, so a bigger observer is selected against unless it pays for itself in food. The window
radius, the number of symbols and the expansion size are genes, so the observer's complexity is
open upward and the price is the only thing that holds it.

**Genome (inherited, mutated at split).** The lane F object, with a few world genes added:

- wiring: for each prediction head, the mask over sensory fields, the reading gains per field, the
  sparsity and size of the expansion, the fixed offsets;
- heads: food-in-window next tick, creature-in-window next tick, own energy next tick, reward;
- development policy: allocation thresholds, probation rule, guard sensitivity, learning rate,
  context state on or off;
- world genes: K (symbols), the search horizon (one or two steps), the exploration rate, a hue.

The child inherits no records, no stores, no bank contents. This is the animal's order from the
lane F note: wiring across generations, experience within a life.

**Decision.** Each tick a creature reads, imagines each legal action through its records (the S02
predict-batch over candidates), scores by the reward record plus the energy head, and acts with
exploration at the gene's rate. Then it witnesses the outcome and writes exactly the records the
reading touched. There is no global objective anywhere in the simulation.

That is the complete v0. It is about the size of the S02 world plus a population loop.

## 4. Why the interesting things can happen

**Foraging and maps.** The S02 receipts already show one life learning consequences, remembering
places and correcting them. On a torus with a food CA the same brain learns where food regrows and
which moves are blocked by neighbours. Frozen-born and random-walker controls die faster; this is
the first gate.

**Wiring selected by the world.** Lane F evolves the genome against an explicit fitness. Here the
fitness is implicit. A brain whose food head reads the whole window pays more per tick than one
that reads the four adjacent cells; whether the wider mask pays depends on the season's clustering.
The population's mask distribution is the readout, and it should move when the season changes.

**Signals with meaning.** Emit is nearly free and by itself does nothing. A symbol matters only
through a listener's ear field, which is one input field among others to the listener's food and
creature heads. A listener whose ear is wired into its food head, and a speaker whose emit is
conditioned on food in its window, both gain when they are kin, and splitting puts kin next to
each other. This is the standard route by which referential signalling arises in evolutionary
signalling simulations (Werner and Dyer 1991, Cangelosi and Parisi 1998, Floreano et al. 2007).
Two things in this design make it reachable here rather than hoped for: the ear is a witnessed
co-occurrence store the S02 agent already has, so word-to-referent grounding happens within one
life; and the speaker's emit is a learned action like any other, rewarded only through the energy
of the speaker, which is why kinship and not altruism has to carry it at first.

The measurements are declared before any run: mutual information between the emitted symbol and
the food in the speaker's window against a shuffled control; the listener's food-head prediction
gain with the ear field masked against unmasked; median lifetime of a deafened control population;
and a dialect map, the MI computed per lineage and per region.

**What is not promised.** Compositional language (symbol strings whose meaning is a function of
the parts) does not arise without a pressure to combine, and v0 has one referent axis (food). A
second axis (food kind by colour, or danger from a predator) is the natural W6 pressure, and the
outcome is measured, not assumed.

**Seasons and memory.** When the season returns, a creature whose guard sensitivity protected the
old-season bank instead of overwriting it answers correctly within about a hundred decisions
(the guard report reads 0.96 against 0.34 for a committed router at 320,000 decisions). Here the
guard's sensitivity is a gene. The prediction is that it sweeps when seasons alternate and drifts
when they do not. That is the world-change guard as an evolutionary fact rather than a
hand-set flag.

**Culture, optional.** A parent emits for T ticks after a split, in range of the child. Meanings
then pass through records rather than genes. With mutation switched off and culture on, the
dialect map should persist across generations; with culture off it should decay. This is the
cleanest visible separation of the two inheritances the programme runs on.

## 5. The picture

The page is what the reader asked for, so it is designed before the numbers.

**Three views of one world, a keystroke apart.**

1. *What is.* The substrate: food as a muted four-step ramp, creatures as glyphs coloured by lineage
   hue, sized by energy. This is the view every artificial-life sim has.
2. *What is known.* The default view. Each cell is drawn from the records the living creatures hold
   about it: the place stores and map stores, aggregated. Never witnessed: black. Witnessed by one:
   faint. Witnessed by many and consistent: full brightness. Disagreeing with the substrate or
   with each other: a slow shimmer between the held values. The world literally appears where
   observers have been and fades where their records go stale or where they die. A population
   crash darkens the map.
3. *What one believes.* Click a creature. The map is redrawn from that creature's records alone,
   its imagined consequences for each candidate action shown as ghost moves, and the whole brain
   in the standard brain scan beside it (`atlas.py`, `brain_scan.js`), banks lighting as they are
   read and written.

**Signals.** An emitted symbol is a ripple two cells wide in the symbol's colour. A dialect map
overlay tints regions by the dominant symbol-to-food mapping. A sidebar chart shows MI over time.

**Lineages.** A phylogeny in the sidebar grows as splits happen; hue is inherited with a small
drift so the map's colour field is the tree. Hover a lineage to see its mask distribution as a
small glyph: which fields its brains read.

**Time.** A speed slider, and a time-lapse mode that plays a recorded run at 50 to 500 ticks per
second with the shared-picture view. The recorded flagship run comes from the GPU box; the page can
also run a small live population (about fifty creatures, in the browser port) that the visitor can
prod: drop food, kill a lineage, silence a region, flip the season.

**An optional mode for the rabbit hole.** "The substrate is lazy": an unobserved cell does not tick.
Its food is resolved only when a creature's window covers it, and it is resolved consistent with the
records of the creatures observing it (the majority record, with the CA rule run forward for the
ticks it was unobserved only if that keeps it consistent). This is a toy and is labelled as one on
the page, but it is the OPH claim made playable: consistency between observers is what the world is
held to. It changes no gate.

## 6. Stages and gates

Each stage has a gate with a control, in the style of the adaptation lanes. Numbers only with
receipts.

| stage | build | gate | controls |
|---|---|---|---|
| W0 | substrate CA, random walkers, energy, death, split without mutation, the three views | the page renders both views at 64 by 64 with 200 walkers at 10 ticks per second in the browser; the known view differs from the substrate view by a measured fraction of cells | none |
| W1 | records brains with a fixed hand genome, learning within a life | median lifetime and population size at tick 20,000 above random walkers and above the identical brain frozen at birth | random, frozen-born |
| W2 | mutation of the genome at split | mean food-head prediction gain of newborns rises over generations; mask distribution differs between the two seasons' populations | mutation off; mutation of hue only |
| W3 | symbols and the ear | MI(symbol, food in speaker's window) above shuffled; ear-masked prediction gain lower than unmasked; deafened population shorter-lived | K forced to 0; ears masked; shuffled symbols |
| W4 | alternating seasons, guard sensitivity as a gene | the guard gene's population mean rises under alternation and not under one season; read-back of the old season on return above the committed-router control | fixed season; guard gene fixed at 0 |
| W5 | culture: post-split emitting | dialects persist across generations with mutation off and culture on; decay with culture off | culture off |
| W6 | a second referent axis (food kinds, or a predator) | measured, not promised: whether two-symbol sequences carry more MI than the best single symbol | one axis |

## 7. Cost and where it runs

The guard report's largest run writes 320,000 decisions in 409 seconds in Python, about 1.3 ms per
decision with allocation on. Two hundred creatures at 10 ticks per second is 2,000 decisions per
second, so a one-process Python life runs at roughly half real time. Two changes make it
comfortable: the records cortex batches across creatures whose expansions have the same dimension
(one sparse matrix product per tick for the whole population, masks applied per creature), and the
torch backend on the Cadence1 g5 for the flagship runs of thousands of creatures over millions of
ticks. The browser page runs the S02 port at fifty creatures for the live mode and plays recorded
runs for the rest. Runs, logs and checkpoints stay on the instance and are catalogued in
`DATA_CATALOGUE.md`.

## 8. Files (proposed)

```
cadence-world/
  DESIGN.md            this file
  world/               substrate.py (the CA), creature.py, population.py, genome.py (world genes on the lane F genome)
  brain/               the creature's agent: window reading, heads, search; imports cadence-examples/agent
  measure/             mi.py, dialects.py, lineages.py, known_view.py (the shared picture from records)
  run.py, verify.py    life runner and independent verifier, receipts per stage
  web/                 the page: substrate, known, believed views; ripples; phylogeny; brain scan; live mode
  receipts/            one folder per stage
```

## 9. Open decisions

- Window size: 3 by 3 (nine food fields) keeps the reading small and the expansion cheap; 5 by 5
  gives signalling something to be about that the listener cannot see. v0 takes 3 by 3 and lets W3
  decide whether the ear needs a larger speaker window to carry anything.
- Whether split is automatic (this design) or an action. Automatic keeps energy the only currency
  and one fewer thing to learn. An action lets a lineage evolve restraint. v0 automatic.
- Whether the world genes include the search horizon at all, or the horizon is fixed at one step.
  Two-step search is what made S02's requests reachable; v0 fixes one step and W2 reopens it.

## 10. First measurement: what the world selects (2026-09-17)

The page's simulation core, run headless in node for 6,000 ticks on two seeds
(`receipts/probe-2026-09-17/`, `probe.js` is the core of `web/index.html` with a logger). Every
tick conserves mass. The population settles near 1,000 creatures; the mean age at death is about
300 ticks.

**At the page's prices** (0.01 per 256 cells, 0.002 per active cell) the population drifts to
smaller brains: the mean expansion falls from 261 cells to 183 and 227, the 128-cell genome grows
from 7 per cent to 69 and 42 per cent, and the active count falls from 8 to 5. Lifetime at death
by brain size, median over both seeds: 128 cells 296, 256 cells 325 to 328, 512 cells 226 to 236,
1,024 cells 123 to 203.

**At a quarter of the price** (0.01 per 1,024 cells, 0.0005 per active cell) the mean rises to
327 and 359 cells and the 512- and 1,024-cell genomes hold 26 to 38 per cent of the population,
but the order of lifetimes is the same: 256 cells live longest (366 to 373), 1,024 shortest (218 to
234).

So the price is not the only thing holding brain size down. In this world a 3 by 3 window of food
and a few active cells is enough to forage, a life of 300 ticks is too short for a large code to be
revisited often enough to fill its records, and nothing in the substrate rewards predicting beyond
the window. The genes that do move are the cheap ones: the learning rate rises (0.2 to 0.29), the
exploration rises (0.1 to 0.18), and speech and ears drift to 20 to 50 per cent under no selection
that this measurement can see.

What follows from this for W2: the observer's complexity is selected by what the world makes
worth predicting. The next step is a substrate feature a small brain cannot handle and a larger one
can: food that grows only where the soil is rich, so that remembering where the soil is pays; a
poison food kind told apart only by a second window field; or a night in which nothing can be
seen and the last reading must carry the decision. Each is one rule, each keeps the physics, and
each is measured the same way, by the lifetime-by-brain-size table against the run before it.
