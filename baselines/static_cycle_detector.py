"""
Baseline 2: Static Graph Cycle Detector
Detects directed cycles in the accumulated graph ignoring timestamp ordering.
Demonstrates why static algorithms yield high nominal false-alarm rates for temporal queries.
"""

from collections import defaultdict
from typing import Dict, List, Set, Tuple
from engine.temporal_graph import TemporalEdge


class StaticCycleDetector:
    """
    Evaluates directed topological cycles without temporal causality constraints.
    """
    def __init__(self, k: int = 3):
        self.k = k
        self.adj: Dict[str, Set[str]] = defaultdict(set)
        self.detected_static_cycles: List[Tuple[str, ...]] = []
        self._seen_cycles: Set[Tuple[str, ...]] = set()

    def process_edge(self, edge: TemporalEdge) -> List[Tuple[str, ...]]:
        self.adj[edge.source].add(edge.target)
        new_cycles = []

        # Find paths of length k-1 from edge.target to edge.source
        def dfs(current: str, dest: str, path: List[str]):
            if len(path) == self.k:
                if current == dest:
                    cycle = tuple(path)
                    min_idx = cycle.index(min(cycle))
                    canonical = cycle[min_idx:] + cycle[:min_idx]
                    if canonical not in self._seen_cycles:
                        self._seen_cycles.add(canonical)
                        new_cycles.append(canonical)
                        self.detected_static_cycles.append(canonical)
                return

            for neighbor in self.adj[current]:
                if neighbor not in path or (neighbor == dest and len(path) == self.k - 1):
                    dfs(neighbor, dest, path + [neighbor])

        dfs(edge.target, edge.source, [edge.target])
        return new_cycles
