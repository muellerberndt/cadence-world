# Current-core local foraging comparison

These receipts were produced by `world.settling.run` using Cadence 0.48.0.
Each receipt binds the example's Python sources and the core implementation,
and includes the pre-live checkpoint. Runtime and installed distribution
versions are recorded separately: the editable environment's package metadata
was stale, while the imported runtime and bound source hashes were 0.48.0.
The browser ecosystem's older results
are separate evidence.

The fixed curriculum is 96 generated local scenes, 24 development scenes and
48 held-out scenes, from separate fixed RNG seeds. Model seeds are 0, 1 and 2.
Bootstrap replays examples until the maximum recall and development error is
at most 0.12, with an allowance of 20 epochs. Thus the models have equal
information and stopping rules, **not equal realized work**. The simple flat
control has six patches; composed and recursive models each have ten, with
different connection counts because observers also read prediction errors.

| Model | Held-out correct, each seed | Presentations, seeds 0 / 1 / 2 | Food eaten in 96 ticks, seeds 0 / 1 / 2 |
| --- | --- | --- | --- |
| Flat | 48/48, 48/48, 48/48 | 672 / 576 / 576 | 55 / 60 / 53 |
| Composed | 48/48, 48/48, 48/48 | 480 / 480 / 384 | 60 / 61 / 46 |
| Recursive | 48/48, 48/48, 48/48 | 576 / 576 / 672 | 59 / 59 / 59 |

Untrained recursive models ate 7 / 39 / 0 times. Uniform random controllers
ate 13 / 18 / 10 times. The explicit reflex controller ate 74 / 78 / 78 times.
The same world seed and physical setup are used within each comparison; actions
naturally change subsequent food distributions and sensory histories. Every
trained model passed readiness; every live solve qualified; all world mass
checks passed. No live teaching or parameter updates occurred. These are three
short lives, not a survival benchmark or an uncertainty estimate for a broad
population of worlds.

Recursive runs took approximately 7–10 seconds for the full bounded suite on
this local machine under concurrent work, composed runs 3–4 seconds and flat
runs approximately 0.5–1.5 seconds. The JSON retains exact timing and solver work. These
timings are not isolated hardware benchmarks. This simple task does not show
a recursive depth advantage: all models acquired the teaching relation, and
the hand-coded reflex still collected more food.

Reproduce the full nine-run comparison:

```bash
for seed in 0 1 2; do
  for model in flat composed recursive; do
    .venv/bin/python -m world.settling --architecture "$model" --seed "$seed" \
      --trace --output "runs/${model}-seed${seed}.json"
  done
done
```

The included `recursive-seed0.json` contains replay frames for
`web/settling.html`; the other receipts omit frames to stay small. `summary.json`
is a convenience projection of those nine receipts. Integration tests cover
bidirectional observer influence, safe refused actions, teacher-free live
control, exact checkpoint continuation, seeded replay, learned improvement,
world mass conservation and JavaScript/Python RNG parity. They do not prove
general reasoning, learned memory or natural selection of the chosen layout.
