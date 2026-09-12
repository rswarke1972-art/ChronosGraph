"""
Streaming Financial Cyber-Forensics Benchmark (5 Realistic Topologies)
Compares ChronosGraph against Exact Temporal DFS, Static Graph Detector, and Degree Heuristics.
"""

import json
import math
import random
import time
from typing import Dict, List, Tuple

from engine.temporal_graph import TemporalEdge
from engine.cycle_detector import ChronosGraphDetector
from baselines.exact_temporal_dfs import ExactTemporalDFS
from baselines.static_cycle_detector import StaticCycleDetector
from baselines.degree_heuristic import DegreeVolumeHeuristic


def run_5_topology_benchmark() -> Dict:
    print("=" * 85)
    print("CHRONOSGRAPH: 5-TOPOLOGY STREAMING FINANCIAL CYBER-FORENSICS BENCHMARK")
    print("=" * 85)

    rng = random.Random(777)
    topologies = [
        ("Smurfing / Structuring Rings (k=4 AML)", 4, 3600.0, 25, 2500),
        ("Triangular DEX Arbitrage (k=3 Flash Bots)", 3, 15.0, 30, 3000),
        ("Token/NFT Wash Trading (k=3 Syndicates)", 3, 300.0, 25, 2500),
        ("Visa/SWIFT Burst Volume Stress Stream", 3, 60.0, 40, 15000),
        ("Adversarial Camouflage & Tumbler Hubs", 3, 600.0, 20, 3000)
    ]

    all_benchmarks = {}

    for name, k, delta_t, num_fraud, bg_edges in topologies:
        print(f"\nEvaluating: {name} (k={k}, DeltaT={delta_t}s, FraudRings={num_fraud}, BgEdges={bg_edges})")
        print("-" * 85)

        # Generate stream
        edges: List[TemporalEdge] = []
        ground_truth: List[Tuple[str, ...]] = []
        cur_t = 0.0

        # Create high degree mixing hubs in adversarial topology
        tumbler_hub = "TUMBLER_MIXER_01"

        spacing = max(1, bg_edges // num_fraud)
        fraud_idx = 0

        for i in range(bg_edges):
            cur_t += rng.uniform(0.005, 0.05)
            # Background
            if "Adversarial" in name and i % 5 == 0:
                # Decoy traffic through tumbler
                edges.append(TemporalEdge(tumbler_hub, f"decoy_{i}", timestamp=cur_t, amount=rng.uniform(10.0, 50.0)))
            else:
                u = f"user_{rng.randint(1, 200)}"
                v = f"user_{rng.randint(1, 200)}"
                if u != v:
                    edges.append(TemporalEdge(u, v, timestamp=cur_t, amount=rng.uniform(50.0, 1200.0)))

            # Inject fraud ring
            if i % spacing == 0 and fraud_idx < num_fraud:
                ring_nodes = [f"fraud_{name[:3]}_{fraud_idx}_{step}" for step in range(k)]
                t_start = cur_t
                step_dt = (delta_t * 0.4) / k
                for step in range(k):
                    s = ring_nodes[step]
                    t_target = ring_nodes[(step + 1) % k]
                    t_e = t_start + (step + 1) * step_dt
                    # structuring: amounts around 9500 to dodge 10000 limit
                    edges.append(TemporalEdge(s, t_target, timestamp=t_e, amount=rng.uniform(9200.0, 9800.0)))
                cur_t = t_start + k * step_dt
                ground_truth.append(tuple(ring_nodes))
                fraud_idx += 1

        edges.sort(key=lambda e: e.timestamp)
        gt_set = set(ground_truth)
        total_gt = len(gt_set)

        # Instantiate systems
        systems = {
            "ChronosGraph (Fast, L=16)": ChronosGraphDetector(k=k, num_trials=16, delta_t=delta_t, v_max=1000),
            "ChronosGraph (Assurance, L=32)": ChronosGraphDetector(k=k, num_trials=32, delta_t=delta_t, v_max=1000),
            "Exact Temporal DFS (Ground Truth)": ExactTemporalDFS(k=k, delta_t=delta_t),
            "Static Graph Cycle Detector": StaticCycleDetector(k=k),
            "Degree / Volume Heuristic": DegreeVolumeHeuristic(degree_threshold=10, volume_threshold=20000.0)
        }

        topo_results = {}

        for sys_name, sys_obj in systems.items():
            t0 = time.perf_counter()
            if isinstance(sys_obj, ChronosGraphDetector) or isinstance(sys_obj, ExactTemporalDFS):
                for e in edges:
                    sys_obj.process_edge(e)
                detected = [tuple(m.nodes) for m in sys_obj.detected_cycles]
            elif isinstance(sys_obj, StaticCycleDetector):
                for e in edges:
                    sys_obj.process_edge(e)
                detected = sys_obj.detected_static_cycles
            elif isinstance(sys_obj, DegreeVolumeHeuristic):
                for e in edges:
                    sys_obj.process_edge(e)
                # Map flagged entities to detected cycles if all k nodes flagged
                flagged = sys_obj.flagged_entities
                detected = [c for c in ground_truth if all(n in flagged for n in c)]

            elapsed = time.perf_counter() - t0
            throughput = len(edges) / elapsed if elapsed > 0 else 0.0

            tp = sum(1 for c in detected if c in gt_set)
            fp = max(0, len(detected) - tp)
            fn = max(0, total_gt - tp)

            recall = tp / total_gt if total_gt > 0 else 0.0
            precision = tp / len(detected) if len(detected) > 0 else 1.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

            print(
                f"  {sys_name:35s} | Recall={recall*100:5.1f}% | "
                f"Precision={precision*100:5.1f}% | F1={f1:.3f} | "
                f"Tput={throughput:7.1f} tx/s | Elapsed={elapsed:6.3f}s"
            )

            topo_results[sys_name] = {
                "recall": round(recall, 4),
                "precision": round(precision, 4),
                "f1": round(f1, 4),
                "throughput_tx_s": round(throughput, 1),
                "elapsed_sec": round(elapsed, 4)
            }

        all_benchmarks[name] = topo_results

    print("\n" + "=" * 85)
    return all_benchmarks


if __name__ == "__main__":
    benchmark_data = run_5_topology_benchmark()
    with open("benchmarks/streaming_aml_benchmark_results.json", "w") as f:
        json.dump(benchmark_data, f, indent=2)
    print("Saved 5-topology benchmark results to benchmarks/streaming_aml_benchmark_results.json")
