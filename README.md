# ChronosGraph: Bounded-Memory Streaming Temporal Motif Detection via Color-Coded Reachability Sketches

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests: 12/12 Passing](https://img.shields.io/badge/Tests-12%2F12%20Passing-brightgreen.svg)](tests/test_chronos_graph.py)
[![Interactive Demo: 60 FPS](https://img.shields.io/badge/Interactive%20Demo-60%20FPS%20Canvas-cyan.svg)](https://rswarke1972-art.github.io/ChronosGraph/)
[![IEEE Research Paper](https://img.shields.io/badge/Research%20Paper-IEEE%20Format-gold.svg)](paper/IEEE_ChronosGraph_Manuscript.md)
[![Patentability Review](https://img.shields.io/badge/Patentability-12%20Claims%20Drafted-rose.svg)](paper/patentability_and_prior_art_review.md)

> **ChronosGraph** is an online streaming temporal graph engine that achieves bounded-memory, sub-millisecond detection of directed cyclical motifs ($k$-cliques, smurfing rings, triangular arbitrage loops, wash-trading rings) in high-velocity financial streams without maintaining an unbounded adjacency matrix.

---

## 1. The Core Scientific Dilemma

In high-velocity transaction networks (Visa, Ethereum, SWIFT), fraud syndicates route capital in closed temporal loops. However:
1. **Static Graph Algorithms (Neo4j, NetworkX, Tarjan's SCC)** ignore the chronological arrow of time ($t_1 < t_2 < \dots < t_k$), resulting in catastrophic false-alarm rates (**precision $< 4.4\%$** in our benchmarks).
2. **Exact Sliding-Window Temporal DFS** scales exponentially with vertex degree $O(V \cdot d^k)$, freezing stream processors when encountering exchange hot wallets ($d > 10^4$).
3. **Unbounded Streams** cause out-of-memory crashes if edges or historical paths are accumulated indefinitely.

---

## 2. The 7 Theoretical Invariants of ChronosGraph

ChronosGraph establishes 7 locked architectural and mathematical guarantees:

1. **Option A Bounded System:** Active vertex working set is strictly capped at $|V_{\text{active}}| \le V_{\max}$ with LRU temporal eviction, establishing certified total memory:
   $$\boxed{M_{\text{total}} \le O(V_{\max} \cdot L \cdot 2^k + M_{\text{reservoir}}) = O(1)}$$
   independent of stream volume $N \to \infty$.
2. **$k$-Wise Independent Coloring:** Replaces generic 2-universal hashing with a formal $k$-wise independent polynomial construction over $\mathbb{F}_p$ ($p = 2^{31} - 1$), mathematically validating:
   $$P(\text{colorful}) = \frac{k!}{k^k}$$
3. **Unified Miss Probability Bound:** Incorporates reservoir sampling loss into the miss rate:
   $$P(\text{miss}) \le \left(1 - \frac{k!}{k^k}\right)^L + \delta_{\text{reservoir}}(M_{\text{reservoir}}, \Delta T, \lambda)$$
4. **Temporal Soundness Invariant:** Every DP reachability state carries temporal provenance $(t_{\text{start}}, t_{\text{latest}}, \text{nodes})$. Proven theorem: **ChronosGraph may miss a cycle, but it never reports a temporally invalid cycle** (100% temporal precision).
5. **Scientific Framing vs. Static Baselines:** Articulates the difference as answering distinct queries: topological existence in $G$ vs. strictly chronological progression within sliding window $\Delta T$.
6. **Decoupled Architecture:** Core engine detects directed temporal motifs $C_k$, which are downstream-classified by financial cyber-forensics rules (AML smurfing, DEX arbitrage, wash trading).
7. **The Pareto Frontier:** Directly maps hardware memory budget against empirical recall and per-edge latency.

---

## 3. Empirical Benchmarks

### Experiment 1: The Memory-Recall-Latency Pareto Frontier
Tested on 4,114 streaming transactions with 40 embedded ground-truth temporal cycles ($k=3, \Delta T=300\text{s}$):

| $V_{\max}$ | $L$ | Recall (%) | Wilson 95% CI | Precision (%) | $F_1$-Score | RAM (KB) | Throughput (tx/s) | $p_{50}$ Latency | $p_{99}$ Latency |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **100** | 8 | 85.0% | [70.9% - 92.9%] | 100.0% | 0.919 | **73.1 KB** | **23,320 tx/s** | **36.2 $\mu$s** | 132.2 $\mu$s |
| **100** | 16 | 97.5% | [87.1% - 99.6%] | 100.0% | 0.987 | 122.0 KB | 12,445 tx/s | 69.7 $\mu$s | 193.1 $\mu$s |
| **100** | 24 | 100.0% | [91.2% - 100.0%] | 100.0% | **1.000** | 175.3 KB | 8,031 tx/s | 105.5 $\mu$s | 294.2 $\mu$s |
| **250** | 24 | 100.0% | [91.2% - 100.0%] | 97.6% | **0.988** | 545.6 KB | 7,014 tx/s | 125.0 $\mu$s | 373.2 $\mu$s |

### Experiment 2: Five Financial Cyber-Forensics Topologies

| Topology Scenario | Metric | Exact Temporal DFS | Static Graph Detector | Degree Heuristic | ChronosGraph (Fast, L=16) | ChronosGraph (Assurance, L=32) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Smurfing / Structuring ($k=4$)** | Recall / Prec / $F_1$ | 100% / 78.1% / 0.877 | 100% / 0.5% / 0.009 | 0% / 100% / 0.000 | 68.0% / 70.8% / 0.694 | **88.0% / 75.9% / 0.815** |
| **DEX Triangular Arbitrage ($k=3$)** | Recall / Prec / $F_1$ | 100% / 83.3% / 0.909 | 100% / 3.0% / 0.058 | 0% / 100% / 0.000 | **100% / 83.3% / 0.909** | **100% / 83.3% / 0.909** |
| **Token/NFT Wash Trading ($k=3$)** | Recall / Prec / $F_1$ | 100% / 73.5% / 0.847 | 100% / 4.4% / 0.084 | 0% / 100% / 0.000 | **100% / 73.5% / 0.847** | **100% / 73.5% / 0.847** |
| **Visa/SWIFT Burst Noise Stream** | Recall / Prec / $F_1$ | 100% / 12.1% / 0.216 | 100% / 0.1% / 0.001 | 0% / 100% / 0.000 | **95.0% / 15.2% / 0.262** | **100% / 14.0% / 0.246** |
| **Adversarial Tumbler Mixer** | Recall / Prec / $F_1$ | 100% / 71.4% / 0.833 | 100% / 3.5% / 0.067 | 0% / 100% / 0.000 | **100% / 71.4% / 0.833** | **100% / 71.4% / 0.833** |

---

## 4. Repository Structure

```
ChronosGraph/
├── engine/
│   ├── color_coding.py         # k-wise independent polynomial hashing & bitmask algebra
│   ├── reservoir_stream.py     # Bounded active vertex LRU + priority reservoir buffer
│   ├── temporal_graph.py       # Temporal edges, provenance, and active state tracking
│   └── cycle_detector.py       # Core ChronosGraph streaming motif detector
├── baselines/
│   ├── exact_temporal_dfs.py   # Ground truth sliding-window temporal DFS
│   ├── static_cycle_detector.py# Static graph cycle detector (topological only)
│   └── degree_heuristic.py     # Compliance degree & volume thresholding filter
├── benchmarks/
│   ├── pareto_frontier.py      # Core research experiment: Memory vs Recall vs Latency
│   └── benchmark_streaming_aml.py # 5 financial cyber-forensics topologies
├── tests/
│   └── test_chronos_graph.py   # 12 automated mathematical unit tests
├── dashboard/                  # 60 FPS HTML5 Canvas interactive simulation
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── paper/
│   ├── IEEE_ChronosGraph_Manuscript.md # Complete IEEE research paper
│   └── patentability_and_prior_art_review.md # 12 formal patent claims
├── index.html                  # GitHub Pages entry point
├── styles.css
└── app.js
```

---

## 5. Quickstart & Verification

### Run Automated Unit Tests (12/12 Passing)
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Run Pareto Frontier Benchmark
```bash
python -m benchmarks.pareto_frontier
```

### Run 5-Topology Financial Forensics Benchmark
```bash
python -m benchmarks.benchmark_streaming_aml
```

---

## 6. Live Interactive Simulation
Experience the 60 FPS Canvas simulation live at:  
👉 **[https://rswarke1972-art.github.io/ChronosGraph/](https://rswarke1972-art.github.io/ChronosGraph/)**

---

## 7. License & Author
- **Author:** Sahil Rajesh Warke
- **License:** MIT License
