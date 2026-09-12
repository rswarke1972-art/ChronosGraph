"""
ChronosGraph: Color-Coding Engine
Implements k-wise independent polynomial hashing with certified rejection sampling
and bitmask algebra for streaming temporal motif reachability sketches.
"""

import hashlib
import random
import math
from typing import List, Set, Tuple

# Mersenne prime for polynomial hashing: 2^31 - 1
MERSENNE_PRIME_31 = 2147483647


def hash_node_to_int(node_id: str) -> int:
    """Deterministically maps arbitrary vertex identifiers (strings, addresses) to positive integer in [0, p-1]."""
    digest = hashlib.sha256(str(node_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big") % MERSENNE_PRIME_31


class ColorSketch:
    """
    A single coloring trial utilizing a k-wise independent polynomial hash function
    over GF(p) where p = 2^31 - 1 with true rejection sampling.
    
    Because p is prime and not divisible by k (e.g., p % 3 = 1, p % 4 = 3),
    evaluations falling in the boundary interval [p - (p % k), p - 1] are rejected
    and resampled. The accepted domain [0, p - (p % k) - 1] has cardinality exactly
    divisible by k, guaranteeing exactly (p - (p % k)) / k pre-images per color
    and certified exact uniform probability P(c) = 1/k.
    """
    def __init__(self, k: int, seed: int, prime: int = MERSENNE_PRIME_31):
        self.k = k
        self.prime = prime
        self.seed = seed
        self.unbiased_limit = prime - (prime % k)
        rng = random.Random(seed)
        # Generate k coefficients in [1, prime - 1]
        self.coefficients = [rng.randint(1, prime - 1) for _ in range(k)]

    def get_color(self, node_int: int) -> int:
        """
        Returns color c in {0, 1, ..., k - 1} with certified exact uniform probability 1/k
        via true rejection sampling on the boundary [p - (p % k), p - 1].
        """
        salt = 0
        while True:
            val = 0
            cur_power = 1
            x = (node_int + salt * 48271) % self.prime
            for coeff in self.coefficients:
                val = (val + coeff * cur_power) % self.prime
                cur_power = (cur_power * x) % self.prime

            # True rejection sampling:
            # Only accept if val < unbiased_limit.
            # Card([0, unbiased_limit - 1]) == unbiased_limit, which is an exact multiple of k.
            if val < self.unbiased_limit:
                return val % self.k

            # Rejection probability is (prime % k) / prime <= 3 / 2147483647 ~= 1.4e-9.
            # Upon rejection, re-evaluate with deterministic salt increment.
            salt += 1

    def get_color_mask(self, node_int: int) -> int:
        """Returns 1-hot bitmask (1 << color)."""
        color = self.get_color(node_int)
        return 1 << color


class ColorCodingFamily:
    """
    Maintains L independent k-wise independent coloring trials.
    Provides collective colorfulness tests and theoretical bounds.
    """
    def __init__(self, k: int, num_trials: int, base_seed: int = 42):
        self.k = k
        self.num_trials = num_trials
        self.base_seed = base_seed
        self.sketches = [
            ColorSketch(k=k, seed=base_seed + l * 7919)
            for l in range(num_trials)
        ]
        self.full_mask = (1 << k) - 1

    def theoretical_colorful_prob(self) -> float:
        """Exact probability that k distinct vertices receive distinct colors: k! / k^k."""
        return math.factorial(self.k) / (self.k ** self.k)

    def theoretical_coloring_miss_bound(self) -> float:
        """Union-bound upper bound on coloring miss probability: (1 - k!/k^k)^L."""
        p_col = self.theoretical_colorful_prob()
        return (1.0 - p_col) ** self.num_trials

    def is_colorful_in_trial(self, trial_idx: int, nodes: List[str]) -> bool:
        """Verifies if a list of nodes has k distinct colors in trial_idx."""
        sketch = self.sketches[trial_idx]
        mask = 0
        for node in nodes:
            node_int = hash_node_to_int(node)
            c_mask = sketch.get_color_mask(node_int)
            if mask & c_mask:
                return False
            mask |= c_mask
        return mask == self.full_mask
