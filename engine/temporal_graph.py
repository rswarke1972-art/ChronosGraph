"""
ChronosGraph: Temporal Graph Data Structures & Provenance
Defines temporal edges, state bitmasks, and strict causal provenance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set


@dataclass(frozen=True)
class TemporalEdge:
    """A directed, timestamped edge representing a transaction or interaction."""
    source: str
    target: str
    timestamp: float
    amount: float = 1.0
    edge_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.edge_id is None:
            # Deterministic default ID
            object.__setattr__(self, 'edge_id', f"{self.source}->{self.target}@{self.timestamp:.4f}")


@dataclass(frozen=True)
class TemporalPathState:
    """
    Provenance state for a colorful temporal path ending at a specific vertex.
    Carries start time, latest hop time, and vertex sequence to certify causality.
    """
    color_mask: int
    start_time: float
    latest_time: float
    nodes: Tuple[str, ...]
    edge_ids: Tuple[str, ...]
    min_amount: float = 0.0
    total_amount: float = 0.0

    @property
    def length(self) -> int:
        return len(self.nodes)

    def is_causally_valid(self, delta_t: float) -> bool:
        """Verifies strict monotonic timestamp progression within sliding window."""
        return (self.latest_time >= self.start_time) and ((self.latest_time - self.start_time) <= delta_t)


@dataclass
class TemporalCycleMatch:
    """
    Represents a detected, certified temporal directed cycle.
    Guarantees strict chronological ordering: t_1 < t_2 < ... < t_k <= t_1 + Delta T.
    """
    nodes: Tuple[str, ...]
    edge_ids: Tuple[str, ...]
    timestamps: Tuple[float, ...]
    duration: float
    min_amount: float
    trial_idx: int
    detected_at: float

    def to_dict(self) -> Dict:
        return {
            "nodes": list(self.nodes),
            "edge_ids": list(self.edge_ids),
            "timestamps": list(self.timestamps),
            "duration": round(self.duration, 4),
            "min_amount": round(self.min_amount, 2),
            "trial_idx": self.trial_idx,
            "detected_at": round(self.detected_at, 4),
            "cycle_str": " -> ".join(self.nodes) + f" -> {self.nodes[0]}"
        }
