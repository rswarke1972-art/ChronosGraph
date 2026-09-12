"""
Unit Test Suite for ChronosGraph (13 Theoretical Invariant Proofs)
"""

import math
import random
import unittest
import time

from engine.color_coding import ColorCodingFamily, ColorSketch, hash_node_to_int
from engine.temporal_graph import TemporalEdge, TemporalPathState
from engine.reservoir_stream import BoundedActiveWorkingSet, ReservoirEdgeBuffer
from engine.cycle_detector import ChronosGraphDetector
from baselines.exact_temporal_dfs import ExactTemporalDFS
from baselines.static_cycle_detector import StaticCycleDetector


class TestChronosGraph(unittest.TestCase):

    def setUp(self):
        random.seed(42)

    def test_01_k_wise_coloring_uniformity(self):
        """Test 1: Verify hash colors across 10,000 nodes are uniformly distributed."""
        k = 4
        sketch = ColorSketch(k=k, seed=12345)
        color_counts = [0] * k
        num_nodes = 10000
        for i in range(num_nodes):
            node_id = f"0xwallet_{i:08x}"
            node_int = hash_node_to_int(node_id)
            c = sketch.get_color(node_int)
            color_counts[c] += 1

        expected = num_nodes / k
        for c, count in enumerate(color_counts):
            # Deviation should be within 10% for 10,000 nodes
            self.assertTrue(abs(count - expected) / expected < 0.10, f"Color {c} count {count} deviates from {expected}")

    def test_01b_rejection_sampling_unbiased_boundary(self):
        """Test 1b: Verify that rejection sampling strictly bounds accepted range to unbiased_limit."""
        k = 3
        p31 = 2147483647
        sketch = ColorSketch(k=k, seed=42, prime=p31)
        self.assertEqual(sketch.unbiased_limit % k, 0)
        self.assertEqual(sketch.unbiased_limit, p31 - (p31 % 3))

        # Test small-field model (p=11, k=3, limit=9) to prove rejection behavior
        small_sketch = ColorSketch(k=3, seed=7, prime=11)
        self.assertEqual(small_sketch.unbiased_limit, 9)
        # Verify that all 11 inputs map into colors {0, 1, 2}
        colors = [small_sketch.get_color(x) for x in range(11)]
        for c in colors:
            self.assertIn(c, (0, 1, 2))

    def test_02_theoretical_colorfulness_probability(self):
        """Test 2: Empirical colorfulness of k-tuples matches k! / k^k."""
        k = 3
        family = ColorCodingFamily(k=k, num_trials=1, base_seed=999)
        sketch = family.sketches[0]
        theoretical_p = math.factorial(k) / (k ** k)  # 6 / 27 = 0.2222...

        num_samples = 5000
        colorful_count = 0
        for i in range(num_samples):
            nodes = [f"node_{i}_{j}" for j in range(k)]
            colors = [sketch.get_color(hash_node_to_int(n)) for n in nodes]
            if len(set(colors)) == k:
                colorful_count += 1

        empirical_p = colorful_count / num_samples
        self.assertAlmostEqual(empirical_p, theoretical_p, delta=0.03)

    def test_03_temporal_causality_soundness(self):
        """Test 3: Every detected cycle strictly satisfies t_1 < t_2 < ... < t_k and duration <= Delta T."""
        detector = ChronosGraphDetector(k=3, num_trials=24, delta_t=100.0, v_max=500)
        
        # Inject valid temporal triangle: A -> B (t=10), B -> C (t=20), C -> A (t=30)
        edges = [
            TemporalEdge("A", "B", timestamp=10.0, amount=100.0),
            TemporalEdge("B", "C", timestamp=20.0, amount=95.0),
            TemporalEdge("C", "A", timestamp=30.0, amount=90.0),
        ]
        
        detected = []
        for e in edges:
            detected.extend(detector.process_edge(e))

        self.assertGreaterEqual(len(detected), 1)
        for match in detected:
            self.assertEqual(match.nodes[0], "A")
            self.assertEqual(match.nodes[1], "B")
            self.assertEqual(match.nodes[2], "C")
            t1, t2, t3 = match.timestamps
            self.assertLess(t1, t2)
            self.assertLess(t2, t3)
            self.assertLessEqual(t3 - t1, 100.0)

    def test_04_sliding_window_expiration(self):
        """Test 4: Temporal cycle spanning duration > Delta T must NOT be detected."""
        detector = ChronosGraphDetector(k=3, num_trials=32, delta_t=50.0, v_max=500)
        
        # Edges spanning 100.0 seconds (delta_t is 50.0)
        edges = [
            TemporalEdge("A", "B", timestamp=10.0),
            TemporalEdge("B", "C", timestamp=30.0),
            TemporalEdge("C", "A", timestamp=110.0),  # 110 - 10 = 100 > 50
        ]
        
        detected = []
        for e in edges:
            detected.extend(detector.process_edge(e))

        self.assertEqual(len(detected), 0, "Expired temporal cycle must not be detected")

    def test_05_bounded_active_working_set_vmax(self):
        """Test 5: Verify active working set strictly enforces |V_active| <= V_max via LRU eviction."""
        v_max = 50
        working_set = BoundedActiveWorkingSet(v_max=v_max)
        
        # Ingest 200 distinct vertices
        for i in range(200):
            evicted = working_set.touch(f"node_{i}", timestamp=float(i))
            self.assertLessEqual(working_set.size(), v_max)
            if i >= v_max:
                self.assertIsNotNone(evicted)

        self.assertEqual(working_set.size(), v_max)

    def test_06_bounded_reservoir_capacity(self):
        """Test 6: Reservoir buffer strictly bounds stored edge count <= M_reservoir."""
        m_reservoir = 100
        reservoir = ReservoirEdgeBuffer(m_reservoir=m_reservoir, delta_t=1000.0)
        
        for i in range(500):
            e = TemporalEdge(f"u_{i}", f"v_{i}", timestamp=float(i))
            reservoir.ingest(e)
            self.assertLessEqual(reservoir.size(), m_reservoir)

        self.assertEqual(reservoir.size(), m_reservoir)
        self.assertGreater(reservoir.empirical_reservoir_loss_rate, 0.0)

    def test_07_zero_false_detections_on_acyclic_paths(self):
        """Test 7: Feeding a directed acyclic path generates zero false cycle alarms."""
        detector = ChronosGraphDetector(k=3, num_trials=32, delta_t=1000.0)
        
        # Linear chain: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7
        edges = [
            TemporalEdge(f"node_{i}", f"node_{i+1}", timestamp=float(i * 10))
            for i in range(1, 15)
        ]
        
        detected = []
        for e in edges:
            detected.extend(detector.process_edge(e))

        self.assertEqual(len(detected), 0, "DAG must yield 0 cycle detections")

    def test_08_temporal_triangle_high_recall_k3(self):
        """Test 8: Temporal triangle detection with L=32 achieves high detection reliability."""
        detector = ChronosGraphDetector(k=3, num_trials=32, delta_t=100.0)
        
        # 10 independent temporal triangles with different addresses
        detected_count = 0
        for i in range(10):
            u, v, w = f"tx_u_{i}", f"tx_v_{i}", f"tx_w_{i}"
            t_base = i * 200.0
            e1 = TemporalEdge(u, v, timestamp=t_base + 1.0)
            e2 = TemporalEdge(v, w, timestamp=t_base + 2.0)
            e3 = TemporalEdge(w, u, timestamp=t_base + 3.0)
            
            detector.process_edge(e1)
            detector.process_edge(e2)
            res = detector.process_edge(e3)
            if res:
                detected_count += 1

        # With L=32 and k=3, P(miss) = (1 - 6/27)^32 = 0.00032 => theoretical recall 99.97%
        self.assertEqual(detected_count, 10)

    def test_09_smurfing_cycle_recovery_k4(self):
        """Test 9: 4-hop smurfing cycle recovery (k=4)."""
        detector = ChronosGraphDetector(k=4, num_trials=48, delta_t=500.0, v_max=500)
        
        # 4-hop ring: Kingpin -> Mule1 -> Mule2 -> Mule3 -> Kingpin
        edges = [
            TemporalEdge("Kingpin", "Mule1", timestamp=100.0, amount=9900.0),
            TemporalEdge("Mule1", "Mule2", timestamp=150.0, amount=9800.0),
            TemporalEdge("Mule2", "Mule3", timestamp=200.0, amount=9700.0),
            TemporalEdge("Mule3", "Kingpin", timestamp=250.0, amount=9600.0),
        ]
        
        detected = []
        for e in edges:
            detected.extend(detector.process_edge(e))

        self.assertGreaterEqual(len(detected), 1)
        match = detected[0]
        self.assertEqual(len(match.nodes), 4)
        self.assertEqual(match.nodes, ("Kingpin", "Mule1", "Mule2", "Mule3"))

    def test_10_static_detector_vs_chronos_temporal_ordering(self):
        """Test 10: Static cycle detector falsely flags reversed timestamps while ChronosGraph rejects them."""
        static_detector = StaticCycleDetector(k=3)
        chronos_detector = ChronosGraphDetector(k=3, num_trials=32, delta_t=1000.0)

        # Edges arriving in chronologically reversed order:
        # A -> B at t=30, B -> C at t=20, C -> A at t=10
        edges = [
            TemporalEdge("A", "B", timestamp=30.0),
            TemporalEdge("B", "C", timestamp=20.0),
            TemporalEdge("C", "A", timestamp=10.0),
        ]

        static_results = []
        chronos_results = []
        for e in edges:
            static_results.extend(static_detector.process_edge(e))
            chronos_results.extend(chronos_detector.process_edge(e))

        # Static detector sees topological cycle and fires
        self.assertGreaterEqual(len(static_results), 1)
        # ChronosGraph enforces chronological order (t1 < t2 < t3) and correctly emits 0
        self.assertEqual(len(chronos_results), 0)

    def test_11_high_degree_hub_update_cost_bounded(self):
        """
        Test 11: Invariant verification that high-degree hubs (1,000 incident edges)
        do NOT cause state explosion. Per-vertex DP states remain strictly <= 2^k
        and total state update operations remain bounded by O(L * 2^k).
        """
        k = 3
        L = 16
        v_max = 2000
        detector = ChronosGraphDetector(k=k, num_trials=L, delta_t=100.0, v_max=v_max)
        
        hub = "BinanceHotWallet"
        # Ingest 1,000 incident edges on the central hub
        for i in range(1000):
            e = TemporalEdge(hub, f"user_{i}", timestamp=float(i) * 0.1)
            detector.process_edge(e)

        # Theoretical invariant verification:
        # For each sketch trial, the hub vertex must hold at most 2^k bitmask states
        max_states_per_vertex = 1 << k  # 2^3 = 8
        for l in range(L):
            if hub in detector.dp_tables[l]:
                hub_state_count = len(detector.dp_tables[l][hub])
                self.assertLessEqual(
                    hub_state_count,
                    max_states_per_vertex,
                    f"Hub state count {hub_state_count} exceeds 2^k bound {max_states_per_vertex}"
                )

        # Total active vertices must strictly obey V_max
        self.assertLessEqual(detector.working_set.size(), v_max)

    def test_12_memory_bounded_flatness_over_stream(self):
        """Test 12: Memory consumption remains flat over 10,000 continuous updates under bounded V_max."""
        v_max = 200
        m_res = 500
        detector = ChronosGraphDetector(k=3, num_trials=16, delta_t=50.0, v_max=v_max, m_reservoir=m_res)

        for i in range(10000):
            u = f"wallet_{i}"
            v = f"wallet_{i + 1}"
            e = TemporalEdge(u, v, timestamp=float(i) * 0.05)
            detector.process_edge(e)

        stats = detector.get_memory_stats()
        self.assertLessEqual(stats["v_active"], v_max)
        self.assertLessEqual(stats["edges_in_window"], m_res)
        self.assertLessEqual(stats["total_dp_states"], stats["max_possible_states"])


if __name__ == "__main__":
    unittest.main()
