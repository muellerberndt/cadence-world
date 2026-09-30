"""Per-coordinate input standardization, fitted on bootstrap rows only.

The Doom lane measured this as its largest single admission speedup: raw
sensor rows are ill-conditioned for the joint solve. Each coordinate is
centred on its training mean, divided by its training standard deviation
(floored at 1e-3), clipped to three deviations and scaled by 0.2, so almost
every value lands inside +-0.6. The fitted constants are part of the
creature's identity: they are saved beside every checkpoint and applied
identically during bootstrapping, live rollouts and evaluation.
"""

from __future__ import annotations

import json

CLIP = 3.0
SCALE = 0.2
FLOOR = 1e-3


class Norms:
    def __init__(self, table):
        self.table = {
            name: (tuple(map(float, mean)), tuple(map(float, std)))
            for name, (mean, std) in table.items()
        }

    @classmethod
    def fit(cls, rows, names):
        """Fit means and deviations for the named input vectors of `rows`."""
        if not rows:
            raise ValueError("Norms need at least one training row")
        table = {}
        for name in names:
            columns = list(zip(*(row[name] for row in rows)))
            means = [sum(column) / len(column) for column in columns]
            stds = [
                max(
                    FLOOR,
                    (sum((v - m) ** 2 for v in column) / len(column)) ** 0.5,
                )
                for column, m in zip(columns, means)
            ]
            table[name] = (means, stds)
        return cls(table)

    def apply(self, inputs):
        """Standardize the named vectors; other inputs pass through unchanged."""
        out = dict(inputs)
        for name, (mean, std) in self.table.items():
            out[name] = tuple(
                max(-CLIP, min(CLIP, (v - m) / s)) * SCALE
                for v, m, s in zip(inputs[name], mean, std)
            )
        return out

    def dump(self):
        return json.dumps(
            {
                "clip": CLIP,
                "scale": SCALE,
                "floor": FLOOR,
                "table": {n: [list(m), list(s)] for n, (m, s) in self.table.items()},
            }
        )

    @classmethod
    def load(cls, text):
        data = json.loads(text)
        if data["clip"] != CLIP or data["scale"] != SCALE or data["floor"] != FLOOR:
            raise ValueError("Norms constants do not match this implementation")
        return cls({n: (m, s) for n, (m, s) in data["table"].items()})
