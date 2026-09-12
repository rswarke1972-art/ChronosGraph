# ChronosGraph: Bounded-Memory Streaming Temporal Motif Detection via Color-Coded Reachability Sketches

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests: 12/12 Passing](https://img.shields.io/badge/Tests-12%2F12%20Passing-brightgreen.svg)](tests/test_chronos_graph.py)
[![Interactive Demo: 60 FPS](https://img.shields.io/badge/Interactive%20Demo-60%20FPS%20Canvas-cyan.svg)](https://rswarke1972-art.github.io/ChronosGraph/)
[![IEEE Research Paper](https://img.shields.io/badge/Research%20Paper-IEEE%20Format-gold.svg)](paper/IEEE_ChronosGraph_Manuscript.md)
[![Patentability Review](https://img.shields.io/badge/Patentability-12%20Claims%20Drafted-rose.svg)](paper/patentability_and_prior_art_review.md)

> **ChronosGraph** is an online streaming temporal graph engine that achieves bounded-memory, sub-millisecond detection of directed cyclical motifs ($k$-cliques, temporal triangles) used to model financial-forensics patterns (such as smurfing rings, triangular trading cycles, and wash-trading structures) in high-velocity streams without maintaining an unbounded adjacency matrix.

---

## 1. The Core Scientific Dilemma

In high-velocity transaction streams (Visa, Ethereum, SWIFT), fraud syndicates route capital in closed temporal loops. However:
1. **Static Graph Algorithms (Neo4j, NetworkX, Tarjan's SCC)** ignore the chronological arrow of time ($t_1 < t_2 < \dots < t_k$), resulting in catastrophic false-alarm rates (**financial-pattern precision $< 4.4\%$** in our benchmarks).
2. **Exact Sliding-Window Temporal DFS** scales exponentially with vertex degree $O(V \cdot d^k)$, freezing stream processors when encountering exchange hot wallets ($d > 10^4$).
3. **Unbounded Streams** cause out-of-memory crashes if edges or historical paths are accumulated indefinitely.

---

## 2. The 7 Theoretical Invariants of ChronosGraph

ChronosGraph establishes 7 audited mathematical guarantees:

1. **Option A Bounded System:** Active vertex working set is strictly capped at $|V_{\text{active}}| \le V_{\max}$ with LRU temporal eviction, establishing certified total memory:
   $$\boxed{M_{\text{total}} \le O(V_{\max} \cdot L \cdot 2^k + M_{\text{reservoir}}) = O(1)}$$
   independent of stream volume $N \to \infty$.
2. **Unbiased $k$-Wise Independent Coloring:** Evaluated via hash polynomials over Mersenne prime field $\mathbb{F}_{2^{31}-1}$ with deterministic remainder re-mapping, mathematically validating exact:
   $$P(C \text{ is colorful}) = \frac{k!}{k^k}$$
3. **Union-Bound Miss Probability Bound:** Combines color-coding miss probability with reservoir edge loss:
   $$\boxed{\delta_{\text{miss}} \le \delta_{\text{color}} + \delta_{\text{reservoir}} = \left(1 - \frac{k!}{k^k}\right)^L + \delta_{\text{reservoir}}(M_{\text{reservoir}}, \Delta T, \lambda)}$$
4. **Deterministic Temporal Soundness:** Every DP reachability state carries temporal provenance $(t_{\text{start}}, t_{\text{latest}}, \text{nodes})$. Proven theorem: **ChronosGraph may miss a cycle under reservoir pressure, but it never reports a temporally invalid cycle** (100% temporal motif precision $P_{\text{motif}} = 1.0$).
5. **Scientific Framing vs. Static Baselines:** Formulated as answering different queries: topological existence in $G$ vs. strictly chronological progression within sliding window $\Delta T$.
6. **Decoupled Architecture:** Core engine detects directed temporal motifs $C_k$, which are downstream-classified by financial cyber-forensics rules (AML smurfing, DEX arbitrage, wash trading).
7. **The Pareto Frontier:** Directly maps hardware memory budget against empirical recall and per-edge latency.

---

## 3. Empirical Benchmarks

### Precision Metric Clarification: $P_{\text{motif}}$ vs. $P_{\text{financial}}$
- **Temporal Motif Precision ($P_{\text{motif}}$):** Fraction of reported cycles that are mathematically valid chronological cycles. Both Exact Temporal DFS and ChronosGraph achieve **100.0%**.
- **Financial-Pattern Precision ($P_{\text{financial}}$):** Fraction of reported cycles corresponding to pre-labeled synthetic fraud rings. Accidental temporal cycles forming by chance in background traffic naturally yield $P_{\text{financial}} \approx 71\%\text{--}83\%$. ChronosGraph matches Exact DFS identically, while Static Graph algorithms collapse to $0.1\%\text{--}4.4\%$.

### Experiment 1: The Memory-Recall-Latency Pareto Frontier ($k=3, \Delta T=300\text{s}$)

| $V_{\max}$ | $L$ | Recall (%) | Wilson 95% CI | Precision ($P_{\text{fin}}$) | $F_1$-Score | RAM (KB) | Throughput (tx/s) | $p_{50}$ Latency | $p_{99}$ Latency |
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

## 4. Quickstart & Verification

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

## 5. Live Interactive Simulation
Experience the 60 FPS Canvas simulation live at:  
👉 **[https://rswarke1972-art.github.io/ChronosGraph/](https://rswarke1972-art.github.io/ChronosGraph/)**

---

## 6. License & Author
- **Author:** Sahil Rajesh Warke
- **License:** MIT License
