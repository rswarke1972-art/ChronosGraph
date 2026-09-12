"""
Baseline 1: Exact Sliding-Window Temporal DFS
Performs exhaustive temporal path search within Delta T window.
Guarantees 100% recall and precision, but exhibits O(V * d^k) worst-case complexity.
"""

from collections import deque, defaultdict
from typing import Dict, List, Set, Tuple
from engine.temporal_graph import TemporalEdge, TemporalCycleMatch


class ExactTemporalDFS:
    """
    Exhaustive ground truth temporal cycle detector.
    Searches sliding window adjacency lists for valid temporal k-cycles.
    """
    def __init__(self, k: int = 3, delta_t: float = 3600.0):
        self.k = k
        self.delta_t = delta_t
        self.adj: Dict[str, List[TemporalEdge]] = defaultdict(list)
        self.edge_window: deque[TemporalEdge] = deque()
        self.detected_cycles: List[TemporalCycleMatch] = []
        self._seen_cycle_fingerprints: Set[Tuple[str, ...]] = set()

    def process_edge(self, edge: TemporalEdge) -> List[TemporalCycleMatch]:
        t = edge.timestamp
        cutoff = t - self.delta_t

        # Evict expired edges from window
        while self.edge_window and self.edge_window[0].timestamp < cutoff:
            old_edge = self.edge_window.popleft()
            if old_edge in self.adj[old_edge.source]:
                self.adj[old_edge.source].remove(old_edge)

        self.edge_window.append(edge)
        self.adj[edge.source].append(edge)

        # Check if incoming edge closes any temporal k-cycle ending at edge.source and starting at edge.target
        newly_detected: List[TemporalCycleMatch] = []
        target = edge.target
        source = edge.source

        # Recursive DFS from target towards source
        def dfs(current: str, path: List[str], edge_path: List[TemporalEdge], current_time: float):
            if len(path) == self.k:
                if current == source and edge.timestamp > current_time and (edge.timestamp - edge_path[0].timestamp) <= self.delta_t:
                    cycle_nodes = tuple(path)
                    cycle_edges = tuple(e.edge_id for e in edge_path) + (edge.edge_id,)
                    fingerprint = (cycle_nodes, cycle_edges)
                    if fingerprint not in self._seen_cycle_fingerprints:
                        self._seen_cycle_fingerprints.add(fingerprint)
                        all_timestamps = tuple(e.timestamp for e in edge_path) + (edge.timestamp,)
                        match = TemporalCycleMatch(
                            nodes=cycle_nodes,
                            edge_ids=cycle_edges,
                            timestamps=all_timestamps,
                            duration=edge.timestamp - edge_path[0].timestamp,
                            min_amount=min(e.amount for e in edge_path + [edge]),
                            trial_idx=-1,
                            detected_at=edge.timestamp
                        )
                        newly_detected.append(match)
                        self.detected_cycles.append(match)
                return

            for next_edge in self.adj[current]:
                if next_edge.timestamp > current_time and (next_edge.timestamp - edge_path[0].timestamp) <= self.delta_t:
                    if next_edge.target not in path:
                        dfs(next_edge.target, path + [next_edge.target], edge_path + [next_edge], next_edge.timestamp)

        # Look for temporal paths starting at target
        for first_edge in self.adj[target]:
            if (edge.timestamp - first_edge.timestamp) <= self.delta_t and first_edge.timestamp < edge.timestamp:
                dfs(first_edge.target, [target, first_edge.target], [first_edge], first_edge.timestamp)

        return newly_detected
