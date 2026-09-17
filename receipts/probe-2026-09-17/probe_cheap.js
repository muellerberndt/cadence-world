'use strict';
// ---------- Mulberry32, the generator the Python world uses ----------
function Mulberry(seed) { this.s = seed >>> 0; }
Mulberry.prototype.random = function () {
  let a = (this.s = (this.s + 0x6D2B79F5) >>> 0);
  let t = Math.imul(a ^ (a >>> 15), a | 1) >>> 0;
  t = (t ^ (t + Math.imul(t ^ (t >>> 7), t | 61))) >>> 0;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

// ---------- the substrate ----------
const CFG = { w: 96, h: 96, soil: 6, grow: 0.08, decay: 0.01, diffuse: 0.05, day: 900, season: 9000, contrastMin: 0.25, foodCap: 8 };
const POP = { initial: 300, birth: 12, splitAt: 24, max: 1500, base: 0.08, move: 0.05, emit: 0.02, read: 0.0004, cell: 0.01 / 1024, write: 0.0005 };
const N = CFG.w * CFG.h;
const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]];
const BASE_ACTIONS = ['north', 'east', 'south', 'west', 'eat', 'wait'];
const OUTCOMES = ['none', 'moved', 'blocked', 'ate', 'spoke'];

class Substrate {
  constructor(seed) {
    this.rng = new Mulberry(seed); this.tick = 0;
    this.soil = new Int32Array(N).fill(CFG.soil); this.food = new Int32Array(N);
    this.lightRow = new Float64Array(CFG.w); this.contrast = 0; this.eclipse = 0; this.peak = 0;
  }
  light() {
    const t = this.tick;
    let c = CFG.contrastMin + (1 - CFG.contrastMin) * 0.5 * (1 - Math.cos(2 * Math.PI * t / CFG.season));
    if (this.eclipse > 0) { c *= 0.15; this.eclipse--; }
    this.contrast = c; this.peak = ((t / CFG.day) % 1) * CFG.w;
    for (let x = 0; x < CFG.w; x++) this.lightRow[x] = 0.5 + 0.5 * c * Math.cos(2 * Math.PI * (x / CFG.w - t / CFG.day));
  }
  step() {
    this.light();
    const { soil, food, rng } = this;
    for (let i = 0; i < N; i++) { const u = rng.random(); if (u < CFG.grow * this.lightRow[i % CFG.w] && soil[i] > 0 && food[i] < CFG.foodCap) { soil[i]--; food[i]++; } }
    for (let i = 0; i < N; i++) { const u = rng.random(); if (u < CFG.decay && food[i] > 0) { food[i]--; soil[i]++; } }
    const leaving = new Uint8Array(N), dir = new Uint8Array(N);
    for (let i = 0; i < N; i++) { const u = rng.random(); leaving[i] = (u < CFG.diffuse && soil[i] > 0) ? 1 : 0; }
    for (let i = 0; i < N; i++) { const d = rng.random(); dir[i] = Math.min((d * 4) | 0, 3); }
    for (let i = 0; i < N; i++) if (leaving[i]) {
      soil[i]--; const x = i % CFG.w, y = (i / CFG.w) | 0; const [dx, dy] = DIRS[dir[i]];
      soil[((y + dy + CFG.h) % CFG.h) * CFG.w + (x + dx + CFG.w) % CFG.w]++;
    }
    this.tick++;
  }
  get mass() { let m = 0; for (let i = 0; i < N; i++) m += this.soil[i] + this.food[i]; return m; }
}

// ---------- the genome: what is inherited ----------
const GENE = {
  radius: [1, 2], cells: [128, 256, 512, 1024], active: [4, 8, 16, 32], fanin: [4, 6, 8, 12],
  eps: [0.02, 0.05, 0.1, 0.2], lr: [0.05, 0.1, 0.2, 0.4], gamma: [0, 0.3, 0.6, 0.9], symbols: [0, 1, 2, 4], ear: [0, 1],
};
function firstGenome(rng) {
  return { radius: 0, cells: 1, active: 1, fanin: 2, eps: 2, lr: 2, gamma: 2, symbols: 0, ear: 0, wiring: (rng.random() * 4294967296) >>> 0, hue: rng.random() };
}
function mutate(g, rng) {
  const c = Object.assign({}, g);
  for (const k of Object.keys(GENE)) if (rng.random() < 0.12) { const n = GENE[k].length; c[k] = Math.max(0, Math.min(n - 1, c[k] + (rng.random() < 0.5 ? -1 : 1))); }
  if (rng.random() < 0.05) c.wiring = (rng.random() * 4294967296) >>> 0;
  c.hue = (((g.hue + (rng.random() - 0.5) * 0.02) % 1) + 1) % 1;
  return c;
}
const G = (g, k) => GENE[k][g[k]];

// ---------- the brain: a records cortex developed from the genome ----------
class Brain {
  constructor(g) {
    this.g = g;
    const r = G(g, 'radius'); this.r = r; this.nWin = (2 * r + 1) ** 2;
    this.K = G(g, 'symbols'); this.ear = G(g, 'ear'); this.A = 6 + this.K;
    this.foodOff = 0; this.occOff = this.nWin * 9; this.energyOff = this.occOff + this.nWin; this.outcomeOff = this.energyOff + 4; this.lightOff = this.outcomeOff + 5;
    this.earOff = this.lightOff + 3; this.D = this.earOff + (this.ear ? this.K + 1 : 0);
    this.M = G(g, 'cells'); this.k = Math.min(G(g, 'active'), this.M >> 3); this.fanin = G(g, 'fanin');
    // development: the fixed sparse expansion, the same for the same wiring seed and layout
    const dev = new Mulberry(g.wiring ^ (this.D * 2654435761));
    this.idx = new Int32Array(this.M * this.fanin); this.w = new Int8Array(this.M * this.fanin);
    for (let i = 0; i < this.idx.length; i++) { this.idx[i] = (dev.random() * this.D) | 0; this.w[i] = dev.random() < 0.7 ? 1 : -1; }
    this.records = new Float32Array(this.M * this.A);
    this.x = new Uint8Array(this.D); this.act = new Int32Array(this.M); this.active = new Int32Array(this.k);
    this.q = new Float32Array(this.A); this.prevActive = null; this.prevAction = -1; this.lastDelta = 0;
    this.eps = G(g, 'eps'); this.lr = G(g, 'lr'); this.gamma = G(g, 'gamma');
  }
  read(pop, c) { // the reading: binary units
    const x = this.x; x.fill(0); const s = pop.sub, r = this.r; let q = 0;
    for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++, q++) {
      const i = ((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w;
      x[this.foodOff + q * 9 + Math.min(s.food[i], 8)] = 1;
      if (pop.occ[i] >= 0 && pop.occ[i] !== c.slot) x[this.occOff + q] = 1;
    }
    x[this.energyOff + Math.min(3, (c.energy * 4 / POP.splitAt) | 0)] = 1;
    x[this.outcomeOff + c.outcome] = 1;
    const l = s.lightRow[c.x]; x[this.lightOff + (l < 0.4 ? 0 : l < 0.6 ? 1 : 2)] = 1;
    if (this.ear) x[this.earOff + Math.min(c.heard, this.K)] = 1;
  }
  code() { // the fixed expansion, winner-take-all: the k most driven cells, ties to the lower index
    const { M, fanin, idx, w, x, act } = this;
    for (let m = 0; m < M; m++) { let a = 0; const b = m * fanin; for (let j = 0; j < fanin; j++) a += w[b + j] * x[idx[b + j]]; act[m] = a; }
    // counting sort over the integer range [-fanin, fanin]
    const counts = new Int32Array(2 * fanin + 1); for (let m = 0; m < M; m++) counts[act[m] + fanin]++;
    let need = this.k, threshold = fanin, over = 0;
    for (let v = 2 * fanin; v >= 0; v--) { if (counts[v] >= need) { threshold = v - fanin; over = need; break; } need -= counts[v]; threshold = v - fanin - 1; }
    let n = 0, atT = 0;
    for (let m = 0; m < M && n < this.k; m++) { if (act[m] > threshold) this.active[n++] = m; else if (act[m] === threshold && atT < over) { this.active[n++] = m; atT++; } }
    while (n < this.k) this.active[n++] = 0;
  }
  predict() { const q = this.q; q.fill(0); for (let j = 0; j < this.k; j++) { const b = this.active[j] * this.A; for (let a = 0; a < this.A; a++) q[a] += this.records[b + a]; } for (let a = 0; a < this.A; a++) q[a] /= this.k; }
  learn(reward) { // one write into exactly the cells the previous reading touched
    if (!this.prevActive) return;
    let best = -Infinity; for (let a = 0; a < this.A; a++) if (this.q[a] > best) best = this.q[a];
    const target = reward + this.gamma * best, a = this.prevAction; let delta = 0;
    for (let j = 0; j < this.k; j++) { const i = this.prevActive[j] * this.A + a; const d = target - this.records[i]; this.records[i] += this.lr * d; delta += d; }
    this.lastDelta = delta / this.k;
  }
  choose(rng) {
    const u = rng.random(); let a;
    if (u < this.eps) a = (rng.random() * this.A) | 0;
    else { let best = -Infinity; a = 0; for (let i = 0; i < this.A; i++) if (this.q[i] > best) { best = this.q[i]; a = i; } }
    this.prevActive = this.active.slice(); this.prevAction = a; return a;
  }
  get price() { return POP.read * this.D + POP.cell * this.M + POP.write * this.k; }
}

// ---------- the population, with the known view kept incrementally ----------
class Population {
  constructor(sub, seed) {
    this.sub = sub; this.rng = new Mulberry(seed); this.nextId = 0; this.creatures = []; this.births = 0; this.deaths = 0;
    this.count = new Int32Array(N); this.sum = new Float64Array(N); this.sumsq = new Float64Array(N); this.sumTick = new Float64Array(N);
    this.occ = new Int32Array(N).fill(-1); this.spoken = [];
    for (let k = 0; k < POP.initial; k++) {
      const x = (this.rng.random() * CFG.w) | 0, y = (this.rng.random() * CFG.h) | 0;
      if (this.occ[y * CFG.w + x] >= 0) continue;
      this.spawn(x, y, POP.birth, firstGenome(this.rng), null, null);
    }
  }
  spawn(x, y, energy, g, lineage, parent) {
    const id = this.nextId++;
    const c = { id, x, y, energy, g, brain: new Brain(g), lineage: lineage === null ? id : lineage, parent, born: this.sub.tick, age: 0, last: 5, outcome: 0, heard: 0, symbol: 0, symbolPrev: 0, mem: new Map(), slot: -1 };
    this.creatures.push(c); return c;
  }
  get held() { let m = 0; for (const c of this.creatures) m += c.energy; return m; }
  get mass() { return this.sub.mass + this.held; }
  record(c, i, food) {
    const old = c.mem.get(i);
    if (old !== undefined) { const f = old & 15, t = old >>> 4; this.count[i]--; this.sum[i] -= f; this.sumsq[i] -= f * f; this.sumTick[i] -= t; }
    c.mem.set(i, food | (this.sub.tick << 4));
    this.count[i]++; this.sum[i] += food; this.sumsq[i] += food * food; this.sumTick[i] += this.sub.tick;
  }
  forget(c) { for (const [i, v] of c.mem) { const f = v & 15, t = v >>> 4; this.count[i]--; this.sum[i] -= f; this.sumsq[i] -= f * f; this.sumTick[i] -= t; } c.mem.clear(); }
  reindex() { this.occ.fill(-1); this.creatures.forEach((c, k) => { c.slot = k; this.occ[c.y * CFG.w + c.x] = k; }); }
  hear(c) { // the nearest speaker within two cells, last tick
    for (let d = 1; d <= 2; d++) for (let dy = -d; dy <= d; dy++) for (let dx = -d; dx <= d; dx++) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) !== d) continue;
      const k = this.occ[((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w];
      if (k >= 0 && this.creatures[k].symbolPrev > 0) return this.creatures[k].symbolPrev;
    }
    return 0;
  }
  step() {
    const s = this.sub, cs = this.creatures, n = cs.length; this.reindex(); this.spoken.length = 0;
    for (const c of cs) { c.symbolPrev = c.symbol; c.symbol = 0; }
    const order = new Int32Array(n); for (let i = 0; i < n; i++) order[i] = i;
    const draws = new Float64Array(Math.max(n - 1, 0)); for (let i = 0; i < draws.length; i++) draws[i] = this.rng.random();
    for (let i = n - 1; i > 0; i--) { const j = (draws[n - 1 - i] * (i + 1)) | 0; const t = order[i]; order[i] = order[j]; order[j] = t; }
    for (let q = 0; q < n; q++) {
      const k = order[q], c = cs[k], b = c.brain; c.age++;
      const r = b.r;
      for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) { const i = ((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w; this.record(c, i, s.food[i]); }
      c.heard = b.ear ? this.hear(c) : 0;
      b.read(this, c); b.code(); b.predict(); b.learn(c.reward || 0);
      const a = b.choose(this.rng); c.last = a; c.outcome = 0; let moved = false; const before = c.energy;
      if (a < 4) {
        const [dx, dy] = DIRS[a]; const nx = (c.x + dx + CFG.w) % CFG.w, ny = (c.y + dy + CFG.h) % CFG.h, ni = ny * CFG.w + nx;
        if (this.occ[ni] < 0) { this.occ[c.y * CFG.w + c.x] = -1; this.occ[ni] = k; c.x = nx; c.y = ny; moved = true; c.outcome = 1; } else c.outcome = 2;
      } else if (a === 4) { const i = c.y * CFG.w + c.x; if (s.food[i] > 0) { s.food[i]--; c.energy++; c.outcome = 3; } }
      else if (a >= 6) { c.symbol = a - 5; c.outcome = 4; this.spoken.push(c); }
      const price = POP.base + b.price + (moved ? POP.move : 0) + (a >= 6 ? POP.emit : 0);
      if (this.rng.random() < price) { c.energy--; s.soil[c.y * CFG.w + c.x]++; }
      c.reward = c.energy - before;
    }
    const survivors = [];
    for (const c of cs) { if (c.energy <= 0) { this.deaths++; this.forget(c); c.dead = true; continue; } survivors.push(c); }
    this.creatures = survivors; this.reindex();
    const children = [];
    for (const c of this.creatures) {
      if (c.energy < POP.splitAt || this.creatures.length + children.length >= POP.max) continue;
      const free = DIRS.filter(([dx, dy]) => this.occ[((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w] < 0);
      if (!free.length) continue;
      const [dx, dy] = free[(this.rng.random() * free.length) | 0];
      const nx = (c.x + dx + CFG.w) % CFG.w, ny = (c.y + dy + CFG.h) % CFG.h;
      const share = c.energy >> 1; c.energy -= share;
      const g = mutate(c.g, this.rng);
      const child = { id: this.nextId++, x: nx, y: ny, energy: share, g, brain: new Brain(g), lineage: c.lineage, parent: c.id, born: s.tick, age: 0, last: 5, outcome: 0, heard: 0, symbol: 0, symbolPrev: 0, mem: new Map(), slot: -1 };
      this.occ[ny * CFG.w + nx] = 1; children.push(child); this.births++;
    }
    this.creatures.push(...children); this.reindex();
  }
}


const T = +process.argv[2] || 6000, seed = +process.argv[3] || 1;
const sub = new Substrate(seed), pop = new Population(sub, seed + 100); const m0 = pop.mass;
const deadBy = {}; // lifetime by brain-cells bucket
const origForget = pop.forget.bind(pop);
pop.forget = c => { const k = c.brain.M; (deadBy[k] = deadBy[k] || []).push(c.age); origForget(c); };
const t0 = Date.now();
for (let t = 1; t <= T; t++) {
  sub.step(); pop.step();
  if (t % 500 === 0 || t === T) {
    const cs = pop.creatures, n = Math.max(cs.length, 1); const mean = f => (cs.reduce((a, c) => a + f(c), 0) / n);
    const hist = {}; for (const c of cs) hist[c.brain.M] = (hist[c.brain.M] || 0) + 1;
    console.log(JSON.stringify({ t, alive: cs.length, births: pop.births, deaths: pop.deaths, mass_ok: pop.mass === m0,
      cells: +mean(c => c.brain.M).toFixed(0), radius: +mean(c => c.brain.r).toFixed(2), active: +mean(c => c.brain.k).toFixed(1), fanin: +mean(c => c.brain.fanin).toFixed(1),
      lr: +mean(c => c.brain.lr).toFixed(3), gamma: +mean(c => c.brain.gamma).toFixed(2), eps: +mean(c => c.brain.eps).toFixed(3), speak: +mean(c => c.brain.K > 0).toFixed(2), ear: +mean(c => c.brain.ear).toFixed(2),
      age: +mean(c => c.age).toFixed(0), hist, s: ((Date.now() - t0) / 1000) | 0 }));
  }
}
const life = {}; for (const k of Object.keys(deadBy)) { const a = deadBy[k]; a.sort((x, y) => x - y); life[k] = { n: a.length, median: a[a.length >> 1], mean: +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(0) }; }
console.log('lifetime at death by brain cells', JSON.stringify(life));
