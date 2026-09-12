"""
Core Research Experiment: Memory-Recall-Latency Pareto Frontier
Sweeps memory capacity (V_max) and sketch count (L) to characterize
the trade-off between hardware budget, detection recall, and per-edge latency.
"""

import json
import math
import random
import time
from typing import Dict, List, Tuple

from engine.temporal_graph import TemporalEdge
from engine.cycle_detector import ChronosGraphDetector
from baselines.exact_temporal_dfs import ExactTemporalDFS


def wilson_score_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Computes Wilson 95% confidence interval for binomial proportion."""
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + (z ** 2) / total
    center = (p + (z ** 2) / (2 * total)) / denom
    spread = (z / denom) * math.sqrt((p * (1.0 - p) / total) + (z ** 2) / (4 * (total ** 2)))
    return max(0.0, center - spread), min(1.0, center + spread)


def generate_stream_with_ground_truth(
    num_cycles: int = 50,
    background_edges: int = 5000,
    k: int = 3,
    delta_t: float = 300.0,
    seed: int = 42
) -> Tuple[List[TemporalEdge], List[Tuple[str, ...]]]:
    """Generates a realistic temporal edge stream with embedded ground truth cycles."""
    rng = random.Random(seed)
    edges: List[TemporalEdge] = []
    ground_truth_cycles: List[Tuple[str, ...]] = []

    cur_time = 0.0

    # Interleave cycles within background noise
    cycle_spacing = max(1, background_edges // num_cycles)
    cycle_idx = 0

    for i in range(background_edges):
        cur_time += rng.uniform(0.01, 0.1)
        # Background transaction between random accounts
        u = f"acc_{rng.randint(1, 300)}"
        v = f"acc_{rng.randint(1, 300)}"
        if u != v:
            edges.append(TemporalEdge(u, v, timestamp=cur_time, amount=rng.uniform(10.0, 500.0)))

        # Inject ground truth cycle
        if i % cycle_spacing == 0 and cycle_idx < num_cycles:
            nodes = [f"fraud_{cycle_idx}_{j}" for j in range(k)]
            t_cycle_start = cur_time
            dt_step = (delta_t * 0.5) / k
            for step in range(k):
                src = nodes[step]
                tgt = nodes[(step + 1) % k]
                t_edge = t_cycle_start + (step + 1) * dt_step
                edges.append(TemporalEdge(src, tgt, timestamp=t_edge, amount=rng.uniform(1000.0, 5000.0)))
            cur_time = t_cycle_start + k * dt_step
            ground_truth_cycles.append(tuple(nodes))
            cycle_idx += 1

    # Sort stream strictly by timestamp
    edges.sort(key=lambda e: e.timestamp)
    return edges, ground_truth_cycles


def run_pareto_sweep() -> Dict:
    """Sweeps V_max and L across multiple levels."""
    print("=" * 80)
    print("CHRONOSGRAPH: MEMORY-RECALL-LATENCY PARETO FRONTIER EXPERIMENT")
    print("=" * 80)

    edges, ground_truth = generate_stream_with_ground_truth(num_cycles=40, background_edges=4000, k=3)
    gt_set = set(ground_truth)
    total_gt = len(gt_set)
    print(f"Stream configuration: {len(edges)} total transactions, {total_gt} ground truth temporal cycles.")
    print("-" * 80)

    v_max_grid = [100, 250, 500, 1000]
    l_grid = [8, 16, 24, 32]

    results = []

    for v_max in v_max_grid:
        for l in l_grid:
            detector = ChronosGraphDetector(k=3, num_trials=l, delta_t=300.0, v_max=v_max, m_reservoir=10000)
            latencies_us = []

            t_start = time.perf_counter()
            for e in edges:
                t0 = time.perf_counter()
                detector.process_edge(e)
                latencies_us.append((time.perf_counter() - t0) * 1e6)
            total_duration = time.perf_counter() - t_start

            throughput = len(edges) / total_duration
            latencies_us.sort()
            p50 = latencies_us[int(len(latencies_us) * 0.50)]
            p95 = latencies_us[int(len(latencies_us) * 0.95)]
            p99 = latencies_us[int(len(latencies_us) * 0.99)]

            # Evaluate matches against ground truth
            detected_nodes = [tuple(m.nodes) for m in detector.detected_cycles]
            true_positives = sum(1 for c in detected_nodes if c in gt_set)
            false_positives = max(0, len(detected_nodes) - true_positives)
            recall = true_positives / total_gt if total_gt > 0 else 0.0
            precision = true_positives / len(detected_nodes) if len(detected_nodes) > 0 else 1.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

            ci_low, ci_high = wilson_score_interval(true_positives, total_gt)
            mem_stats = detector.get_memory_stats()
            estimated_ram_kb = (mem_stats["total_dp_states"] * 128 + mem_stats["edges_in_window"] * 96) / 1024.0

            row = {
                "v_max": v_max,
                "L": l,
                "recall": round(recall, 4),
                "recall_ci": [round(ci_low, 4), round(ci_high, 4)],
                "precision": round(precision, 4),
                "f1": round(f1, 4),
                "throughput_eps": round(throughput, 1),
                "p50_us": round(p50, 2),
                "p95_us": round(p95, 2),
                "p99_us": round(p99, 2),
                "ram_kb": round(estimated_ram_kb, 1),
                "dp_states": mem_stats["total_dp_states"],
                "reservoir_loss": mem_stats["reservoir_loss_rate"]
            }
            results.append(row)
            print(
                f"V_max={v_max:4d} | L={l:2d} | Rec={recall*100:5.1f}% [{ci_low*100:4.1f}-{ci_high*100:4.1f}%] | "
                f"Prec={precision*100:5.1f}% | F1={f1:.3f} | RAM={estimated_ram_kb:6.1f}KB | "
                f"Tput={throughput:7.1f} tx/s | p50={p50:5.1f}us | p99={p99:6.1f}us"
            )

    print("=" * 80)
    return {"pareto_results": results}


if __name__ == "__main__":
    sweep_data = run_pareto_sweep()
    with open("benchmarks/pareto_frontier_results.json", "w") as f:
        json.dump(sweep_data, f, indent=2)
    print("Saved Pareto frontier results to benchmarks/pareto_frontier_results.json")
