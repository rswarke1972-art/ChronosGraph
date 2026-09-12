"""
Baseline 3: Degree & Volume Heuristic Filter
Flags addresses that exceed transaction degree or velocity thresholds.
Demonstrates high false-negative rates against micro-structuring and subtle AML rings.
"""

from collections import defaultdict
from typing import Dict, List, Set, Tuple
from engine.temporal_graph import TemporalEdge


class DegreeVolumeHeuristic:
    """
    Standard compliance rule heuristic: flags high-degree/high-volume hubs.
    """
    def __init__(self, degree_threshold: int = 15, volume_threshold: float = 25000.0):
        self.degree_threshold = degree_threshold
        self.volume_threshold = volume_threshold
        self.in_degree: Dict[str, int] = defaultdict(int)
        self.out_degree: Dict[str, int] = defaultdict(int)
        self.total_volume: Dict[str, float] = defaultdict(float)
        self.flagged_entities: Set[str] = set()

    def process_edge(self, edge: TemporalEdge) -> List[str]:
        new_flags = []
        self.out_degree[edge.source] += 1
        self.in_degree[edge.target] += 1
        self.total_volume[edge.source] += edge.amount
        self.total_volume[edge.target] += edge.amount

        for v in (edge.source, edge.target):
            deg = self.in_degree[v] + self.out_degree[v]
            vol = self.total_volume[v]
            if (deg >= self.degree_threshold or vol >= self.volume_threshold) and v not in self.flagged_entities:
                self.flagged_entities.add(v)
                new_flags.append(v)

        return new_flags
