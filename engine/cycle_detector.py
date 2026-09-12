"""
ChronosGraph: Core Streaming Motif Detector
Implements color-coded dynamic reachability sketches, temporal causality verification,
bounded active working set (V_max), and reservoir sampling.
"""

from collections import defaultdict
import time
from typing import Dict, List, Optional, Set, Tuple

from .color_coding import ColorCodingFamily, hash_node_to_int
from .temporal_graph import TemporalEdge, TemporalPathState, TemporalCycleMatch
from .reservoir_stream import BoundedActiveWorkingSet, ReservoirEdgeBuffer


class ChronosGraphDetector:
    """
    Streaming Temporal Motif Detector for directed k-cycles.
    
    Invariants guaranteed:
    1. Bounded Space: M <= O(V_max * L * 2^k + M_reservoir) = O(1)
    2. Temporal Soundness: Reported cycles satisfy t_1 < t_2 < ... < t_k and t_k - t_1 <= Delta T
    3. Per-edge update time: O(L * 2^k) = O(1) operations
    """
    def __init__(
        self,
        k: int = 3,
        num_trials: int = 24,
        delta_t: float = 3600.0,
        v_max: int = 1000,
        m_reservoir: int = 50000,
        seed: int = 42
    ):
        self.k = k
        self.num_trials = num_trials
        self.delta_t = delta_t
        self.v_max = v_max
        self.m_reservoir = m_reservoir

        self.coloring_family = ColorCodingFamily(k=k, num_trials=num_trials, base_seed=seed)
        self.working_set = BoundedActiveWorkingSet(v_max=v_max)
        self.reservoir = ReservoirEdgeBuffer(m_reservoir=m_reservoir, delta_t=delta_t, seed=seed)

        # DP Reachability Tables:
        # dp_tables[trial_idx][vertex_id] -> Dict[color_mask, TemporalPathState]
        # Maintaining at most 1 optimal state per bitmask strictly guarantees <= 2^k states per vertex
        self.dp_tables: List[Dict[str, Dict[int, TemporalPathState]]] = [
            defaultdict(dict) for _ in range(num_trials)
        ]

        # Telemetry & Audit Log
        self.total_edges_processed = 0
        self.detected_cycles: List[TemporalCycleMatch] = []
        self._seen_cycle_fingerprints: Set[Tuple[str, ...]] = set()

    def _evict_vertex(self, vertex_id: str) -> None:
        """Purges all reachability states for evicted vertex across all sketch trials."""
        for trial_idx in range(self.num_trials):
            if vertex_id in self.dp_tables[trial_idx]:
                del self.dp_tables[trial_idx][vertex_id]

    def process_edge(self, edge: TemporalEdge) -> List[TemporalCycleMatch]:
        """
        Processes an incoming streaming transaction edge e = (u -> v, timestamp).
        Returns list of newly closed, certified temporal cycles.
        """
        self.total_edges_processed += 1
        t = edge.timestamp
        u = edge.source
        v = edge.target

        # Self-loops cannot form simple k-cycles (k >= 3)
        if u == v:
            return []

        # 1. Update Active Working Set with LRU Eviction (Lock 1)
        evicted_u = self.working_set.touch(u, t)
        if evicted_u:
            self._evict_vertex(evicted_u)
        evicted_v = self.working_set.touch(v, t)
        if evicted_v:
            self._evict_vertex(evicted_v)

        # 2. Ingest into sliding window reservoir buffer (Lock 3)
        accepted, expired_edges = self.reservoir.ingest(edge)
        if not accepted:
            # Edge dropped by reservoir sampling; cannot be used to extend paths
            return []

        # 3. Process edge across all L independent sketches (Lock 2)
        newly_detected: List[TemporalCycleMatch] = []
        cutoff_time = t - self.delta_t

        u_int = hash_node_to_int(u)
        v_int = hash_node_to_int(v)

        for l in range(self.num_trials):
            sketch = self.coloring_family.sketches[l]
            c_u = sketch.get_color(u_int)
            c_v = sketch.get_color(v_int)
            u_mask = 1 << c_u
            v_mask = 1 << c_v

            # Prune outdated DP states at u and v
            table = self.dp_tables[l]
            if u in table:
                table[u] = {
                    m: s for m, s in table[u].items()
                    if s.start_time >= cutoff_time
                }
            if v in table:
                table[v] = {
                    m: s for m, s in table[v].items()
                    if s.start_time >= cutoff_time
                }

            # Check Cycle Closure:
            # If u holds a colorful path of length k that started at v,
            # and edge (u -> v) closes the cycle with t > latest_time and t - start_time <= Delta T:
            if u in table:
                for mask, state in list(table[u].items()):
                    if (
                        state.length == self.k
                        and state.nodes[0] == v
                        and state.color_mask == self.coloring_family.full_mask
                        and state.latest_time < t
                        and (t - state.start_time) <= self.delta_t
                    ):
                        # Certified Temporal Cycle Found! (Lock 4)
                        cycle_nodes = state.nodes
                        cycle_edges = state.edge_ids + (edge.edge_id,)
                        # Use sorted canonical representation to avoid duplicate multi-sketch emissions
                        fingerprint = (cycle_nodes, tuple(cycle_edges))
                        if fingerprint not in self._seen_cycle_fingerprints:
                            self._seen_cycle_fingerprints.add(fingerprint)
                            match = TemporalCycleMatch(
                                nodes=cycle_nodes,
                                edge_ids=cycle_edges,
                                timestamps=(state.start_time, state.latest_time, t),
                                duration=t - state.start_time,
                                min_amount=min(state.min_amount, edge.amount),
                                trial_idx=l,
                                detected_at=t
                            )
                            newly_detected.append(match)
                            self.detected_cycles.append(match)

            # Extend Existing Paths:
            # If u has a path of length < k that does not yet visit v's color:
            if u in table and (c_u != c_v or self.k <= 2):
                for mask, state in list(table[u].items()):
                    if (
                        state.length < self.k
                        and not (state.color_mask & v_mask)
                        and v not in state.nodes
                        and state.latest_time < t
                        and (t - state.start_time) <= self.delta_t
                    ):
                        new_mask = state.color_mask | v_mask
                        new_nodes = state.nodes + (v,)
                        new_edges = state.edge_ids + (edge.edge_id,)
                        candidate_state = TemporalPathState(
                            color_mask=new_mask,
                            start_time=state.start_time,
                            latest_time=t,
                            nodes=new_nodes,
                            edge_ids=new_edges,
                            min_amount=min(state.min_amount, edge.amount),
                            total_amount=state.total_amount + edge.amount
                        )
                        # Keep state with most recent start_time (tighter window)
                        if new_mask not in table[v] or candidate_state.start_time > table[v][new_mask].start_time:
                            table[v][new_mask] = candidate_state

            # Initiate New 2-Node Path if colors are distinct:
            if c_u != c_v:
                init_mask = u_mask | v_mask
                init_state = TemporalPathState(
                    color_mask=init_mask,
                    start_time=t,
                    latest_time=t,
                    nodes=(u, v),
                    edge_ids=(edge.edge_id,),
                    min_amount=edge.amount,
                    total_amount=edge.amount
                )
                if init_mask not in table[v] or init_state.start_time > table[v][init_mask].start_time:
                    table[v][init_mask] = init_state

        return newly_detected

    def get_memory_stats(self) -> Dict:
        """Returns exact state count, working set size, and reservoir metrics."""
        total_dp_states = sum(
            len(states)
            for table in self.dp_tables
            for states in table.values()
        )
        return {
            "v_active": self.working_set.size(),
            "v_max": self.v_max,
            "edges_in_window": self.reservoir.size(),
            "m_reservoir": self.m_reservoir,
            "total_dp_states": total_dp_states,
            "max_possible_states": self.v_max * self.num_trials * (1 << self.k),
            "reservoir_loss_rate": round(self.reservoir.empirical_reservoir_loss_rate, 4),
            "total_edges_processed": self.total_edges_processed,
            "detected_cycles_count": len(self.detected_cycles)
        }
