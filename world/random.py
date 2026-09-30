"""The world's deterministic RNG, independent of the neural library.

Matches ``Mulberry`` in ``sim/core.js``. Simulation randomness is an environment
concern; it must not depend on a removed Cadence records implementation.
"""

import numpy as np


class Mulberry32:
    """Unsigned 32-bit Mulberry generator with sequential batch semantics."""

    def __init__(self, seed: int = 0) -> None:
        self.state = int(seed) & 0xFFFFFFFF

    def random(self) -> float:
        self.state = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        value = self.state
        value = ((value ^ (value >> 15)) * (value | 1)) & 0xFFFFFFFF
        value ^= (value + ((value ^ (value >> 7)) * (value | 61))) & 0xFFFFFFFF
        return ((value ^ (value >> 14)) & 0xFFFFFFFF) / 4294967296

    def batch(self, count: int) -> np.ndarray:
        """Draw in exactly the same order as repeated ``random`` calls."""
        return np.fromiter((self.random() for _ in range(count)), float, count)
