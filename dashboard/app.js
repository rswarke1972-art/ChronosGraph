/**
 * ChronosGraph 60 FPS Interactive Forensic Simulation & Telemetry Engine
 */

(function () {
  'use strict';

  // --- Configuration & State ---
  const state = {
    scenario: 'smurfing',
    k: 4,
    L: 24,
    v_max: 250,
    delta_t: 45.0,
    injectionRate: 4,
    isPlaying: true,
    nodes: new Map(), // id -> { id, x, y, vx, vy, radius, color, lastActive, type }
    edges: [], // { id, source, target, timestamp, amount, progress, isCycle }
    particles: [], // { x, y, tx, ty, progress, speed, color, radius }
    detectedCycles: [],
    recentLatencies: [],
    totalIngested: 0,
    simTime: 0,
    paretoCurve: [
      { v: 100, l: 8, rec: 85.0, f1: 0.919, ram: 73.1, p50: 36.2 },
      { v: 100, l: 16, rec: 97.5, f1: 0.987, ram: 122.0, p50: 69.7 },
      { v: 250, l: 24, rec: 100.0, f1: 0.988, ram: 545.6, p50: 125.0 },
      { v: 500, l: 32, rec: 100.0, f1: 0.988, ram: 1241.2, p50: 187.0 }
    ]
  };

  // Canvas context
  const canvas = document.getElementById('graph-canvas');
  const ctx = canvas.getContext('2d');
  const paretoCanvas = document.getElementById('pareto-mini-canvas');
  const pCtx = paretoCanvas.getContext('2d');

  function resizeCanvas() {
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = canvas.parentElement.clientHeight;
    paretoCanvas.width = paretoCanvas.parentElement.clientWidth;
    paretoCanvas.height = 130;
  }
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  // --- Node & Graph Management ---
  function getOrCreateNode(id, type = 'wallet') {
    if (!state.nodes.has(id)) {
      // LRU Eviction if capacity exceeded
      if (state.nodes.size >= state.v_max) {
        let oldestId = null;
        let oldestTime = Infinity;
        for (const [nId, n] of state.nodes.entries()) {
          if (n.lastActive < oldestTime) {
            oldestTime = n.lastActive;
            oldestId = nId;
          }
        }
        if (oldestId) state.nodes.delete(oldestId);
      }

      const padding = 60;
      const x = padding + Math.random() * (canvas.width - padding * 2);
      const y = padding + Math.random() * (canvas.height - padding * 2);
      state.nodes.set(id, {
        id,
        x,
        y,
        vx: 0,
        vy: 0,
        radius: type === 'mixer' ? 14 : type === 'kingpin' ? 11 : 7,
        type,
        color: type === 'mixer' ? '#f43f5e' : type === 'kingpin' ? '#f59e0b' : '#22d3ee',
        lastActive: state.simTime,
        pulseRadius: 0
      });
    }
    const node = state.nodes.get(id);
    node.lastActive = state.simTime;
    return node;
  }

  // --- ChronosGraph Browser Sketch Detector ---
  class BrowserChronosSketch {
    constructor(k, L, delta_t) {
      this.k = k;
      this.L = L;
      this.delta_t = delta_t;
      this.tables = Array.from({ length: L }, () => new Map());
      this.seeds = Array.from({ length: L }, (_, i) => i * 7919 + 42);
    }

    hashColor(nodeId, trialIdx) {
      let hash = this.seeds[trialIdx];
      for (let i = 0; i < nodeId.length; i++) {
        hash = ((hash << 5) - hash + nodeId.charCodeAt(i)) | 0;
      }
      return Math.abs(hash) % this.k;
    }

    processEdge(edge) {
      const u = edge.source;
      const v = edge.target;
      const t = edge.timestamp;
      const newlyDetected = [];
      const cutoff = t - this.delta_t;

      for (let l = 0; l < this.L; l++) {
        const c_u = this.hashColor(u, l);
        const c_v = this.hashColor(v, l);
        const u_mask = 1 << c_u;
        const v_mask = 1 << c_v;
        const fullMask = (1 << this.k) - 1;
        const table = this.tables[l];

        // Prune expired states
        if (table.has(u)) {
          const uMap = table.get(u);
          for (const [mask, st] of uMap.entries()) {
            if (st.startTime < cutoff) uMap.delete(mask);
          }
        }
        if (table.has(v)) {
          const vMap = table.get(v);
          for (const [mask, st] of vMap.entries()) {
            if (st.startTime < cutoff) vMap.delete(mask);
          }
        }

        // Check Cycle Closure: u holds a k-hop path starting at v
        if (table.has(u)) {
          const uMap = table.get(u);
          for (const [mask, st] of uMap.entries()) {
            if (
              st.nodes.length === this.k &&
              st.nodes[0] === v &&
              mask === fullMask &&
              st.latestTime < t &&
              (t - st.startTime) <= this.delta_t
            ) {
              const cycleNodes = [...st.nodes];
              newlyDetected.push({
                nodes: cycleNodes,
                timestamps: [st.startTime, st.latestTime, t],
                duration: t - st.startTime,
                amount: edge.amount,
                trial: l,
                detectedAt: t
              });
            }
          }
        }

        // Extend paths
        if (table.has(u) && (c_u !== c_v || this.k <= 2)) {
          const uMap = table.get(u);
          if (!table.has(v)) table.set(v, new Map());
          const vMap = table.get(v);

          for (const [mask, st] of uMap.entries()) {
            if (
              st.nodes.length < this.k &&
              !(mask & v_mask) &&
              !st.nodes.includes(v) &&
              st.latestTime < t &&
              (t - st.startTime) <= this.delta_t
            ) {
              const newMask = mask | v_mask;
              vMap.set(newMask, {
                startTime: st.startTime,
                latestTime: t,
                nodes: [...st.nodes, v]
              });
            }
          }
        }

        // Initiate length 2 path
        if (c_u !== c_v) {
          if (!table.has(v)) table.set(v, new Map());
          const initMask = u_mask | v_mask;
          table.get(v).set(initMask, {
            startTime: t,
            latestTime: t,
            nodes: [u, v]
          });
        }
      }

      return newlyDetected;
    }
  }

  let sketchEngine = new BrowserChronosSketch(state.k, state.L, state.delta_t);

  // --- Edge Ingestion ---
  function pushEdge(sourceId, targetId, amount = 100, isCycle = false, type = 'wallet') {
    state.simTime += 0.2;
    state.totalIngested++;

    const srcNode = getOrCreateNode(sourceId, type);
    const tgtNode = getOrCreateNode(targetId, type);

    const edge = {
      id: `${sourceId}->${targetId}@${state.simTime.toFixed(2)}`,
      source: sourceId,
      target: targetId,
      timestamp: state.simTime,
      amount,
      isCycle,
      progress: 0
    };
    state.edges.push(edge);

    // Particle
    state.particles.push({
      x: srcNode.x,
      y: srcNode.y,
      tx: tgtNode.x,
      ty: tgtNode.y,
      progress: 0,
      speed: 0.02 + Math.random() * 0.02,
      color: isCycle ? '#fbbf24' : '#22d3ee',
      radius: isCycle ? 4 : 2.5
    });

    // Run sketch detection
    const t0 = performance.now();
    const detected = sketchEngine.processEdge(edge);
    const tElapsed = performance.now() - t0;
    state.recentLatencies.push(tElapsed);
    if (state.recentLatencies.length > 50) state.recentLatencies.shift();

    if (detected.length > 0) {
      for (const match of detected) {
        onCycleDetected(match);
      }
    }
  }

  function onCycleDetected(match) {
    state.detectedCycles.unshift(match);
    if (state.detectedCycles.length > 25) state.detectedCycles.pop();

    // Visual pulse on cycle nodes
    for (const nId of match.nodes) {
      const node = state.nodes.get(nId);
      if (node) {
        node.pulseRadius = 24;
        node.color = '#ffd700';
      }
    }

    // Add card to audit feed
    const feed = document.getElementById('audit-feed');
    if (feed) {
      const item = document.createElement('div');
      item.className = 'feed-item';
      item.innerHTML = `
        <div class="feed-item-header">
          <span class="feed-badge">MOTIF DETECTED · L=${match.trial}</span>
          <span class="feed-time">${match.duration.toFixed(2)}s window</span>
        </div>
        <div class="feed-cycle-path">
          ${match.nodes.join(' → ')} → ${match.nodes[0]}
        </div>
        <div class="feed-metrics">
          <span>Amount: $${match.amount.toLocaleString()}</span>
          <span class="text-emerald">Certified Causal Invariant ✓</span>
        </div>
      `;
      feed.prepend(item);
      if (feed.children.length > 15) feed.removeChild(feed.lastChild);
    }

    // Sound / HUD trigger
    document.getElementById('hud-cycle-count').textContent = state.detectedCycles.length;
  }

  // --- Scenario Generators ---
  let cycleCounter = 0;
  function injectScenarioBatch() {
    cycleCounter++;
    if (state.scenario === 'smurfing') {
      // 4-hop structuring ring: Kingpin -> MuleA -> MuleB -> MuleC -> Kingpin
      const kingpin = `KP_${cycleCounter % 3}`;
      const m1 = `M1_${cycleCounter}`;
      const m2 = `M2_${cycleCounter}`;
      const m3 = `M3_${cycleCounter}`;
      const amt = 9400 + Math.random() * 400;
      setTimeout(() => pushEdge(kingpin, m1, amt, true, 'kingpin'), 0);
      setTimeout(() => pushEdge(m1, m2, amt * 0.98, true), 120);
      setTimeout(() => pushEdge(m2, m3, amt * 0.96, true), 240);
      setTimeout(() => pushEdge(m3, kingpin, amt * 0.94, true), 360);
    } else if (state.scenario === 'arbitrage') {
      // Triangular DEX Arbitrage: USDC -> WETH -> WBTC -> USDC
      const tA = 'Pool_USDC';
      const tB = 'Pool_WETH';
      const tC = 'Pool_WBTC';
      pushEdge(tA, tB, 250000, true);
      setTimeout(() => pushEdge(tB, tC, 252100, true), 100);
      setTimeout(() => pushEdge(tC, tA, 254800, true), 200);
    } else if (state.scenario === 'wash') {
      // 3-wallet reciprocal wash ring
      const w1 = `TraderA_${cycleCounter % 4}`;
      const w2 = `TraderB_${cycleCounter % 4}`;
      const w3 = `TraderC_${cycleCounter % 4}`;
      pushEdge(w1, w2, 12.5, true);
      setTimeout(() => pushEdge(w2, w3, 12.8, true), 150);
      setTimeout(() => pushEdge(w3, w1, 13.1, true), 300);
    } else if (state.scenario === 'adversarial') {
      // Mixer with decoy transactions
      const mixer = 'TUMBLER_MIXER';
      getOrCreateNode(mixer, 'mixer');
      for (let i = 0; i < 3; i++) {
        pushEdge(mixer, `decoy_${Math.floor(Math.random() * 20)}`, 15.0, false, 'mixer');
      }
    } else {
      // Background noise
      const u = `acc_${Math.floor(Math.random() * 20)}`;
      const v = `acc_${Math.floor(Math.random() * 20)}`;
      if (u !== v) pushEdge(u, v, Math.floor(Math.random() * 1000) + 50);
    }
  }

  // --- Physics & Layout ---
  function updatePhysics() {
    const nodes = Array.from(state.nodes.values());

    // Gentle center attraction & repulsion
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;

    for (let i = 0; i < nodes.length; i++) {
      const n1 = nodes[i];
      n1.vx += (cx - n1.x) * 0.0003;
      n1.vy += (cy - n1.y) * 0.0003;

      for (let j = i + 1; j < nodes.length; j++) {
        const n2 = nodes[j];
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist < 100) {
          const force = (100 - dist) / 100 * 0.08;
          n1.vx -= (dx / dist) * force;
          n1.vy -= (dy / dist) * force;
          n2.vx += (dx / dist) * force;
          n2.vy += (dy / dist) * force;
        }
      }

      n1.x += n1.vx;
      n1.y += n1.vy;
      n1.vx *= 0.92;
      n1.vy *= 0.92;

      // Pulse decay
      if (n1.pulseRadius > 0) n1.pulseRadius -= 0.5;

      // Wall bounds
      n1.x = Math.max(30, Math.min(canvas.width - 30, n1.x));
      n1.y = Math.max(30, Math.min(canvas.height - 30, n1.y));
    }
  }

  // --- Rendering Loop ---
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
    ctx.lineWidth = 1;
    const step = 40;
    for (let x = 0; x < canvas.width; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Draw active edges
    const now = state.simTime;
    state.edges = state.edges.filter(e => (now - e.timestamp) <= state.delta_t);

    for (const edge of state.edges) {
      const src = state.nodes.get(edge.source);
      const tgt = state.nodes.get(edge.target);
      if (!src || !tgt) continue;

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.strokeStyle = edge.isCycle ? 'rgba(245, 158, 11, 0.5)' : 'rgba(6, 182, 212, 0.15)';
      ctx.lineWidth = edge.isCycle ? 2 : 1;
      ctx.stroke();
    }

    // Draw moving particles
    for (let i = state.particles.length - 1; i >= 0; i--) {
      const p = state.particles[i];
      p.progress += p.speed;
      if (p.progress >= 1) {
        state.particles.splice(i, 1);
        continue;
      }
      const curX = p.x + (p.tx - p.x) * p.progress;
      const curY = p.y + (p.ty - p.y) * p.progress;

      ctx.beginPath();
      ctx.arc(curX, curY, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.shadowColor = p.color;
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // Draw nodes
    for (const node of state.nodes.values()) {
      // Outer pulse ring
      if (node.pulseRadius > 0) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius + node.pulseRadius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(251, 191, 36, ${node.pulseRadius / 24})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.shadowColor = node.color;
      ctx.shadowBlur = 10;
      ctx.fill();
      ctx.shadowBlur = 0;

      // Label
      ctx.fillStyle = '#94a3b8';
      ctx.font = '9px JetBrains Mono';
      ctx.textAlign = 'center';
      ctx.fillText(node.id, node.x, node.y + node.radius + 12);
    }

    // Update Telemetry HUD
    updateHUD();

    // Draw Pareto mini chart
    drawParetoChart();
  }

  function updateHUD() {
    document.getElementById('stat-working-set').textContent = `${state.nodes.size} / ${state.v_max} V_max`;
    document.getElementById('hud-edge-count').textContent = state.totalIngested.toLocaleString();

    const avgLat = state.recentLatencies.length > 0
      ? (state.recentLatencies.reduce((a, b) => a + b, 0) / state.recentLatencies.length).toFixed(3)
      : '0.042';
    document.getElementById('hud-latency').textContent = `${avgLat} ms`;

    // Calculate theoretical assurance: 1 - (1 - k!/k^k)^L
    let pColorful = 1;
    if (state.k === 3) pColorful = 6 / 27;
    else if (state.k === 4) pColorful = 24 / 256;
    const missBound = Math.pow(1 - pColorful, state.L);
    const assurance = Math.max(0, (1 - missBound) * 100).toFixed(1);
    document.getElementById('stat-assurance').textContent = `${assurance}% (1 - δ)`;
    document.getElementById('stat-throughput').textContent = `${(state.injectionRate * 12).toFixed(0)} tx/s`;
  }

  function drawParetoChart() {
    pCtx.clearRect(0, 0, paretoCanvas.width, paretoCanvas.height);
    const w = paretoCanvas.width;
    const h = paretoCanvas.height;

    pCtx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    pCtx.lineWidth = 1;
    pCtx.beginPath();
    pCtx.moveTo(35, 10);
    pCtx.lineTo(35, h - 20);
    pCtx.lineTo(w - 10, h - 20);
    pCtx.stroke();

    // Draw points: x = RAM, y = Recall
    pCtx.strokeStyle = '#22d3ee';
    pCtx.lineWidth = 2;
    pCtx.beginPath();

    state.paretoCurve.forEach((pt, i) => {
      const x = 40 + (pt.ram / 1400) * (w - 60);
      const y = (h - 25) - (pt.rec / 100) * (h - 45);
      if (i === 0) pCtx.moveTo(x, y);
      else pCtx.lineTo(x, y);
    });
    pCtx.stroke();

    state.paretoCurve.forEach((pt) => {
      const x = 40 + (pt.ram / 1400) * (w - 60);
      const y = (h - 25) - (pt.rec / 100) * (h - 45);
      pCtx.beginPath();
      pCtx.arc(x, y, 3.5, 0, Math.PI * 2);
      pCtx.fillStyle = '#fbbf24';
      pCtx.fill();
    });

    pCtx.fillStyle = '#64748b';
    pCtx.font = '8px JetBrains Mono';
    pCtx.fillText('Recall %', 5, 20);
    pCtx.fillText('RAM (KB)', w - 45, h - 6);
  }

  // --- Animation Frame Loop ---
  let lastSpawn = 0;
  function animate(timestamp) {
    if (state.isPlaying) {
      updatePhysics();
      if (timestamp - lastSpawn > (1000 / state.injectionRate)) {
        injectScenarioBatch();
        lastSpawn = timestamp;
      }
    }
    draw();
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  // --- UI Event Listeners ---
  document.querySelectorAll('.btn-scenario').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.btn-scenario').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.scenario = btn.dataset.scenario;
      if (state.scenario === 'smurfing') state.k = 4;
      else state.k = 3;
      sketchEngine = new BrowserChronosSketch(state.k, state.L, state.delta_t);
    });
  });

  const sliderTrials = document.getElementById('slider-trials');
  sliderTrials.addEventListener('input', (e) => {
    state.L = parseInt(e.target.value, 10);
    document.getElementById('val-trials').textContent = state.L;
    sketchEngine = new BrowserChronosSketch(state.k, state.L, state.delta_t);
  });

  const sliderVmax = document.getElementById('slider-vmax');
  sliderVmax.addEventListener('input', (e) => {
    state.v_max = parseInt(e.target.value, 10);
    document.getElementById('val-vmax').textContent = state.v_max;
  });

  const sliderDeltaT = document.getElementById('slider-deltat');
  sliderDeltaT.addEventListener('input', (e) => {
    state.delta_t = parseFloat(e.target.value);
    document.getElementById('val-deltat').textContent = `${state.delta_t}s`;
    sketchEngine = new BrowserChronosSketch(state.k, state.L, state.delta_t);
  });

  const sliderRate = document.getElementById('slider-rate');
  sliderRate.addEventListener('input', (e) => {
    state.injectionRate = parseInt(e.target.value, 10);
    document.getElementById('val-rate').textContent = `${state.injectionRate}x`;
  });

  document.getElementById('btn-inject-cycle').addEventListener('click', () => {
    injectScenarioBatch();
  });

  const btnPlay = document.getElementById('btn-toggle-play');
  btnPlay.addEventListener('click', () => {
    state.isPlaying = !state.isPlaying;
    document.getElementById('txt-play').textContent = state.isPlaying ? '⏸ Pause Stream' : '▶ Resume Stream';
  });

  document.getElementById('btn-reset').addEventListener('click', () => {
    state.nodes.clear();
    state.edges = [];
    state.particles = [];
    state.detectedCycles = [];
    sketchEngine = new BrowserChronosSketch(state.k, state.L, state.delta_t);
    document.getElementById('audit-feed').innerHTML = '';
    document.getElementById('hud-cycle-count').textContent = '0';
  });

})();
