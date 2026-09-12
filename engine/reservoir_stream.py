"""
ChronosGraph: Bounded Active Working Set & Priority Reservoir Stream
Enforces Lock 1 (strictly bounded active vertex working set V_max)
and Lock 3 (reservoir sampling with edge loss tracking).
"""

from collections import deque, OrderedDict
import heapq
import random
from typing import Dict, List, Optional, Set, Tuple
from .temporal_graph import TemporalEdge


class BoundedActiveWorkingSet:
    """
    Maintains active vertices bounded by V_max.
    Uses an LRU OrderedDict mapping vertex_id -> latest_active_timestamp.
    When |V_active| > V_max, evicts the least-recently active vertex.
    """
    def __init__(self, v_max: int):
        self.v_max = v_max
        self._active_vertices: OrderedDict[str, float] = OrderedDict()
        self.eviction_count = 0

    def touch(self, vertex_id: str, timestamp: float) -> Optional[str]:
        """
        Updates vertex activity. If capacity exceeded, evicts LRU vertex and returns its ID.
        """
        if vertex_id in self._active_vertices:
            self._active_vertices.move_to_end(vertex_id)
            self._active_vertices[vertex_id] = max(self._active_vertices[vertex_id], timestamp)
            return None

        # Insert new vertex
        self._active_vertices[vertex_id] = timestamp
        if len(self._active_vertices) > self.v_max:
            evicted_vertex, _ = self._active_vertices.popitem(last=False)
            self.eviction_count += 1
            return evicted_vertex
        return None

    def remove(self, vertex_id: str) -> None:
        """Explicitly evicts a vertex."""
        self._active_vertices.pop(vertex_id, None)

    def contains(self, vertex_id: str) -> bool:
        return vertex_id in self._active_vertices

    def size(self) -> int:
        return len(self._active_vertices)

    def prune_expired(self, cutoff_time: float) -> List[str]:
        """Evicts all vertices whose latest activity is prior to cutoff_time."""
        evicted = []
        for v, last_t in list(self._active_vertices.items()):
            if last_t < cutoff_time:
                evicted.append(v)
                del self._active_vertices[v]
                self.eviction_count += 1
            else:
                break
        return evicted


class ReservoirEdgeBuffer:
    """
    Sliding window buffer combined with randomized priority reservoir sampling.
    Guarantees buffer capacity <= M_reservoir edges.
    Tracks edge eviction and reservoir loss for Lock 3 miss-rate analysis.
    """
    def __init__(self, m_reservoir: int, delta_t: float, seed: int = 42):
        self.m_reservoir = m_reservoir
        self.delta_t = delta_t
        self.rng = random.Random(seed)
        self.window_queue: deque[TemporalEdge] = deque()
        self.total_ingested = 0
        self.expired_evictions = 0
        self.reservoir_drops = 0

    def ingest(self, edge: TemporalEdge) -> Tuple[bool, List[TemporalEdge]]:
        """
        Ingests a new edge. Evicts edges older than edge.timestamp - delta_t.
        If capacity > m_reservoir, randomly evicts an edge using reservoir priority.
        Returns: (accepted: bool, expired_edges: List[TemporalEdge])
        """
        self.total_ingested += 1
        cutoff = edge.timestamp - self.delta_t
        expired = []

        # Monotonic time eviction
        while self.window_queue and self.window_queue[0].timestamp < cutoff:
            expired.append(self.window_queue.popleft())
            self.expired_evictions += 1

        # Check reservoir capacity
        if len(self.window_queue) < self.m_reservoir:
            self.window_queue.append(edge)
            return True, expired
        else:
            # Reservoir replacement: sample index uniformly
            # Acceptance probability = m_reservoir / (len(window_queue) + 1)
            j = self.rng.randint(0, len(self.window_queue))
            if j < self.m_reservoir:
                # Replace edge at index j
                self.window_queue[j] = edge
                self.reservoir_drops += 1
                return True, expired
            else:
                self.reservoir_drops += 1
                return False, expired

    @property
    def empirical_reservoir_loss_rate(self) -> float:
        """Fraction of incoming edges dropped due to reservoir capacity."""
        if self.total_ingested == 0:
            return 0.0
        return self.reservoir_drops / self.total_ingested

    def size(self) -> int:
        return len(self.window_queue)
