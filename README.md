# cadence-world

A conserved-mass world under a moving sun, observed by creatures whose brains are inherited as
wiring and learned as records within one life. The page draws the world from what the living
observers have seen.

The rules are physics: one quantity, mass, in integer units, conserved at every tick; one external
drive, a band of sunlight crossing a torus; every rule local; every computation paid in mass. What
is on the observer's side of the boundary is open: the genome carries the window radius, the number
of expansion cells, how many fire, the fan-in, the learning rate, the horizon, the exploration, the
number of symbols the creature can utter and whether it hears, and a split mutates it. The brain is
a records cortex in the sense of the [cadence](https://github.com/muellerberndt/cadence) library:
a fixed sparse expansion of the reading, winner-take-all, one record per active cell and action,
one write per witnessed outcome into exactly the cells the reading touched, no replay, no global
objective. Energy and death select.

`DESIGN.md` states the idea, the rules, why signalling and memory can arise, the picture, the
stages and their gates, and what is not promised.

## The simulation core

`sim/core.js` holds the whole simulation with no DOM: the substrate, the rules as flags, the
genome (a list of cortices, each a mask over the reading's field groups with its own cells and
records; the window radius, the horizon, the symbols, the split threshold, the learning genes),
the brain and the population. `sim/probe.js` runs one world headless in node and prints the
population statistics, the lifetime-at-death tables by brain size, cortex count and horizon, the
mask census and the symbol statistics; `sim/summarize.py` tabulates a folder of such runs.

```bash
node sim/probe.js '{"ripen":true,"rock":true,"bite":true}' 8000 1 > runs/rrb_s1.jsonl
python3 sim/summarize.py runs
```

## The page

`web/index.html` is built by `python3 web/build.py` from `web/page.html` with `sim/core.js` inlined, so the page and the probe run the same code. It is the whole simulation in one file: the substrate, the population, the brains,
a three.js view with an orbiting camera, the three views (what is, what is known, what one
believes), a live brain scan of the selected creature, the lineages, and the population's brain
size and speech over time. Open it in a browser; it loads three.js and two typefaces from a CDN
and nothing else.

The rules of the next world are checkboxes. Keys: `1` `2` `3` switch the view, space pauses. Drag to orbit, wheel to zoom, shift-drag to pan,
click a creature to open its brain, "Follow it" to keep the camera on it.

## The Python world

`world/` holds the same substrate and the stage W0 population (reflex and random walkers, no
learning) with the known view built from the creatures' records, and `tests/` its obligations:
the light is a drifting band, mass is conserved through growth, decay, diffusion, eating,
metabolism, splits and deaths, a seed replays exactly, reflex walkers outlive random ones, the
known view is built from records only. The random numbers are one Mulberry32 stream in the same
draw order as the page, so the page can be checked against it cell by cell (a parity harness is
the next step; the learning brain of the page is not yet ported to Python).

```bash
python -m venv .venv && .venv/bin/pip install cadence-net numpy pytest
.venv/bin/python -m pytest tests -q
```

## Forking

Everything is here. The rules live in one place in each implementation (`world/substrate.py`,
`world/population.py`; the `Substrate`, `Brain`, `Population` classes at the top of the page's
script). The genome table `GENE` at the top of the page is where the observer's degrees of freedom
are declared; the price of each is in `POP`.

## License

MIT.
