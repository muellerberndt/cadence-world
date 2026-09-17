/* cadence-world core: the substrate, the genome, the brain, the population. No DOM.
   Used by web/index.html (inlined) and by sim/probe.js (node). */
(function (root, factory) { if (typeof module === 'object' && module.exports) module.exports = factory(); else root.CW = factory(); })(typeof self !== 'undefined' ? self : this, function () {
'use strict';

// ---------- Mulberry32, the generator the Python world uses ----------
function Mulberry(seed) { this.s = seed >>> 0; }
Mulberry.prototype.random = function () {
  let a = (this.s = (this.s + 0x6D2B79F5) >>> 0);
  let t = Math.imul(a ^ (a >>> 15), a | 1) >>> 0;
  t = (t ^ (t + Math.imul(t ^ (t >>> 7), t | 61))) >>> 0;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

// ---------- the rules: each a flag, each one physical rule ----------
const RULES = { ripen: false, rock: false, night: false, kinds: false, bite: false, carry: false, digest: false };
const CFG = { w: 96, h: 96, soil: 6, grow: 0.08, decay: 0.01, diffuse: 0.05, day: 900, season: 9000, contrastMin: 0.25, foodCap: 8, ripenTicks: 30, rockFraction: 0.12, nightBelow: 0.35, warmup: 400, digestTicks: 6 };
const POP = { initial: 300, birth: 12, max: 1500, base: 0.08, move: 0.05, emit: 0.02, bite: 0.10, read: 0.0004, imagine: 0.1, cell: 0.01 / 256, write: 0.002 };
const N = CFG.w * CFG.h;
const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]];
const OUTCOMES = ['none', 'moved', 'blocked', 'ate', 'spoke', 'bit', 'spoiled', 'bitten'];
const GROUP_NAMES = ['food', 'occ', 'energy', 'out', 'light', 'green', 'rock', 'kind', 'lastkind', 'kin', 'dark', 'carried', 'heard', 'inner'];
const INNER_WIDTH = 16, MAX_CORTICES = 4; // the inner group: each cortex's code of the previous tick, folded onto 32 units
const WINDOW_WIDTH = { food: 9, occ: 1, green: 4, rock: 1, kind: 1, kin: 1 }; // per-cell width of the window groups

function actionsFor(rules, K) {
  const a = ['north', 'east', 'south', 'west', 'eat', 'wait'];
  if (rules.bite) a.push('bite');
  if (rules.carry) a.push('dig', 'drop');
  for (let k = 1; k <= K; k++) a.push('say ' + k);
  return a;
}

// blobs on the torus for rock and for the two kinds of ground
function blobs(rng, fraction, count, maxLen) {
  const out = new Uint8Array(N); let filled = 0; const target = fraction * N;
  for (let b = 0; b < count && filled < target; b++) {
    let x = (rng.random() * CFG.w) | 0, y = (rng.random() * CFG.h) | 0;
    const len = 6 + (rng.random() * (maxLen || 40)) | 0;
    for (let s = 0; s < len; s++) {
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const i = ((y + dy + CFG.h) % CFG.h) * CFG.w + (x + dx + CFG.w) % CFG.w; if (!out[i]) { out[i] = 1; filled++; } }
      const [dx, dy] = DIRS[(rng.random() * 4) | 0]; x = (x + dx + CFG.w) % CFG.w; y = (y + dy + CFG.h) % CFG.h;
    }
  }
  return out;
}

// ---------- the substrate ----------
class Substrate {
  constructor(seed, rules) {
    this.rules = Object.assign({}, RULES, rules || {}); this.rng = new Mulberry(seed); this.tick = 0;
    this.rock = this.rules.rock ? blobs(this.rng, CFG.rockFraction, 200) : new Uint8Array(N);
    this.kind = this.rules.kinds ? blobs(this.rng, 0.5, 1500, 10) : new Uint8Array(N); // the two kinds of ground in small patches
    this.soil = new Int32Array(N); for (let i = 0; i < N; i++) this.soil[i] = this.rock[i] ? 0 : CFG.soil;
    this.food = new Int32Array(N); this.green = new Int32Array(N);
    this.lightRow = new Float64Array(CFG.w); this.contrast = 0; this.eclipse = 0; this.peak = 0;
    for (let t = 0; t < CFG.warmup; t++) this.step(); // the sun was there before life: a grown world at tick 0
    this.tick = 0;
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
    const { soil, food, green, rng, rock } = this, ripen = this.rules.ripen;
    // growth: fertility scales with the soil, up to four units
    for (let i = 0; i < N; i++) {
      const u = rng.random();
      if (rock[i] || soil[i] <= 0 || food[i] + green[i] >= CFG.foodCap) continue;
      if (u < CFG.grow * this.lightRow[i % CFG.w] * Math.min(soil[i], 4) / 4) { soil[i]--; if (ripen) green[i]++; else food[i]++; }
    }
    if (ripen) for (let i = 0; i < N; i++) { const u = rng.random(); if (green[i] > 0 && u < 2 * this.lightRow[i % CFG.w] / CFG.ripenTicks) { green[i]--; food[i]++; } }
    for (let i = 0; i < N; i++) { const u = rng.random(); if (u < CFG.decay && food[i] > 0) { food[i]--; soil[i]++; } }
    const leaving = new Uint8Array(N), dir = new Uint8Array(N);
    for (let i = 0; i < N; i++) { const u = rng.random(); leaving[i] = (u < CFG.diffuse && soil[i] > 0) ? 1 : 0; }
    for (let i = 0; i < N; i++) { const d = rng.random(); dir[i] = Math.min((d * 4) | 0, 3); }
    for (let i = 0; i < N; i++) if (leaving[i]) {
      const x = i % CFG.w, y = (i / CFG.w) | 0; const [dx, dy] = DIRS[dir[i]];
      const j = ((y + dy + CFG.h) % CFG.h) * CFG.w + (x + dx + CFG.w) % CFG.w;
      if (rock[j]) continue; soil[i]--; soil[j]++;
    }
    this.tick++;
  }
  dark(i) { return this.rules.night && this.lightRow[i % CFG.w] < CFG.nightBelow; }
  get mass() { let m = 0; for (let i = 0; i < N; i++) m += this.soil[i] + this.food[i] + this.green[i]; return m; }
}

// ---------- the genome: what is inherited ----------
const GENE = { radius: [1, 2], horizon: [0, 1, 2], symbols: [0, 1, 2, 4], splitAt: [24, 32, 48, 64], eps: [0.02, 0.05, 0.1, 0.2], lr: [0.05, 0.1, 0.2, 0.4], gamma: [0, 0.3, 0.6, 0.9] };
const CORTEX = { cells: [64, 128, 256, 512, 1024], active: [4, 8, 16, 32], fanin: [4, 6, 8, 12] };
const G = (g, k) => GENE[k][g[k]];
const bit = name => 1 << GROUP_NAMES.indexOf(name);
const FIRST_MASK = bit('food') | bit('occ') | bit('energy') | bit('out') | bit('light');

function firstGenome(rng, available) { // the founders read everything the world offers through one cortex; evolution prunes and splits it
  const inner = GROUP_NAMES.indexOf('inner');
  const mask = available ? available.filter(gi => gi !== inner).reduce((m, gi) => m | (1 << gi), 0) : FIRST_MASK;
  return { radius: 0, horizon: 0, symbols: 0, splitAt: 0, eps: 2, lr: 2, gamma: 2, hue: rng.random(),
    cortices: [{ mask, cells: 2, active: 1, fanin: 2, wiring: (rng.random() * 4294967296) >>> 0 }] };
}
function stepGene(v, n, rng) { return Math.max(0, Math.min(n - 1, v + (rng.random() < 0.5 ? -1 : 1))); }
function mutate(g, rng, groupsAvailable) {
  const c = Object.assign({}, g); c.cortices = g.cortices.map(x => Object.assign({}, x));
  for (const k of Object.keys(GENE)) if (rng.random() < 0.12) c[k] = stepGene(c[k], GENE[k].length, rng);
  for (const x of c.cortices) {
    for (const k of Object.keys(CORTEX)) if (rng.random() < 0.08) x[k] = stepGene(x[k], CORTEX[k].length, rng);
    if (rng.random() < 0.10) { const b = 1 << (groupsAvailable[(rng.random() * groupsAvailable.length) | 0]); const m = x.mask ^ b; if (m) x.mask = m; }
    if (rng.random() < 0.03) x.wiring = (rng.random() * 4294967296) >>> 0;
  }
  if (rng.random() < 0.06 && c.cortices.length < MAX_CORTICES) { // a new cortex: a copy of one, one bit changed, its own wiring
    const src = c.cortices[(rng.random() * c.cortices.length) | 0]; const x = Object.assign({}, src);
    const b = 1 << (groupsAvailable[(rng.random() * groupsAvailable.length) | 0]); if (x.mask ^ b) x.mask ^= b;
    x.wiring = (rng.random() * 4294967296) >>> 0; c.cortices.push(x);
  }
  if (rng.random() < 0.06 && c.cortices.length > 1) c.cortices.splice((rng.random() * c.cortices.length) | 0, 1);
  if (rng.random() < 0.06 && c.cortices.length < MAX_CORTICES) { // a split: one cortex becomes two halves at the same total cost, the groups partitioned between them
    const i = (rng.random() * c.cortices.length) | 0, x = c.cortices[i];
    const bits = []; for (let b = 0; b < GROUP_NAMES.length; b++) if (x.mask & (1 << b)) bits.push(b);
    if (x.cells >= 1 && bits.length >= 2) {
      let ma = 0, mb = 0; for (const b of bits) { if (rng.random() < 0.5) ma |= 1 << b; else mb |= 1 << b; }
      if (!ma) { ma = 1 << bits[0]; mb &= ~ma; } if (!mb) { mb = 1 << bits[bits.length - 1]; ma &= ~mb; }
      const half = Object.assign({}, x, { cells: x.cells - 1, active: Math.max(0, x.active - 1) });
      c.cortices.splice(i, 1, Object.assign({}, half, { mask: ma }), Object.assign({}, half, { mask: mb, wiring: (rng.random() * 4294967296) >>> 0 }));
    }
  }
  c.hue = (((g.hue + (rng.random() - 0.5) * 0.02) % 1) + 1) % 1;
  return c;
}

// ---------- the reading's layout for a rule set ----------
function layoutFor(rules, r, K) {
  const nWin = (2 * r + 1) ** 2; const groups = []; let off = 0;
  const add = (name, size) => { groups.push({ name, off, size }); off += size; };
  add('food', nWin * 9); add('occ', nWin); add('energy', 4); add('out', OUTCOMES.length); add('light', 3);
  if (rules.ripen) add('green', nWin * 4);
  if (rules.rock) add('rock', nWin);
  if (rules.kinds) { add('kind', nWin); add('lastkind', 3); }
  if (rules.bite) add('kin', nWin);
  if (rules.night) add('dark', 1);
  if (rules.carry) add('carried', 1);
  add('heard', K + 1);
  add('inner', INNER_WIDTH * MAX_CORTICES);
  const byName = {}; for (const g of groups) byName[g.name] = g;
  return { groups, byName, D: off, nWin, r, available: groups.map(g => GROUP_NAMES.indexOf(g.name)) };
}

// ---------- the brain: cortices developed from the genome, records learned in the life ----------
class Brain {
  constructor(g, rules) {
    this.g = g; this.rules = rules; this.r = G(g, 'radius'); this.K = G(g, 'symbols'); this.horizon = G(g, 'horizon');
    this.actions = actionsFor(rules, this.K); this.A = this.actions.length;
    this.L = layoutFor(rules, this.r, this.K); this.D = this.L.D; this.nWin = this.L.nWin;
    this.x = new Uint8Array(this.D); this.q = new Float32Array(this.A); this.lastDelta = 0; this.imagined = 0;
    this.eps = G(g, 'eps'); this.gamma = G(g, 'gamma'); this.lr = G(g, 'lr') / Math.sqrt(g.cortices.length);
    this.cortices = g.cortices.map(cx => {
      const units = []; for (const grp of this.L.groups) if (cx.mask & bit(grp.name)) for (let u = 0; u < grp.size; u++) units.push(grp.off + u);
      const M = CORTEX.cells[cx.cells], k = Math.min(CORTEX.active[cx.active], M >> 3), fanin = CORTEX.fanin[cx.fanin];
      const dev = new Mulberry(cx.wiring ^ (units.length * 2654435761));
      const idx = new Int32Array(M * fanin), w = new Int8Array(M * fanin);
      for (let i = 0; i < idx.length; i++) { idx[i] = units.length ? units[(dev.random() * units.length) | 0] : 0; w[i] = dev.random() < 0.7 ? 1 : -1; }
      return { mask: cx.mask, units: units.length, M, k, fanin, idx, w, records: new Float32Array(M * this.A), act: new Int32Array(M), active: new Int32Array(k), prevActive: null };
    });
    this.readUnits = this.cortices.reduce((s, c) => s + c.units, 0);
    this.cellsTotal = this.cortices.reduce((s, c) => s + c.M, 0);
    this.activeTotal = this.cortices.reduce((s, c) => s + c.k, 0);
    this.hears = this.cortices.some(c => c.mask & bit('heard'));
    this.readsInner = this.cortices.some(c => c.mask & bit('inner'));
    this.halves = this.cortices.length >= 2 && this.readsInner; // two interacting cortices: one reads another's code
    this.inner = new Uint8Array(INNER_WIDTH * MAX_CORTICES);
    this.prevQ = null; this.prevAction = -1;
  }
  read(pop, c) {
    const x = this.x; x.fill(0); const s = pop.sub, r = this.r, L = this.L, B = L.byName; let q = 0;
    for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++, q++) {
      const i = ((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w;
      if (B.rock) x[B.rock.off + q] = s.rock[i];
      if (B.kind) x[B.kind.off + q] = s.kind[i];
      if (s.dark(i)) continue; // nothing else is seen in the dark
      x[B.food.off + q * 9 + Math.min(s.food[i], 8)] = 1;
      if (B.green) x[B.green.off + q * 4 + Math.min(s.green[i], 3)] = 1;
      const k = pop.occ[i];
      if (k >= 0 && k !== c.slot) { x[B.occ.off + q] = 1; if (B.kin && pop.creatures[k].lineage === c.lineage) x[B.kin.off + q] = 1; }
    }
    x[B.energy.off + Math.min(3, (c.energy * 4 / G(this.g, 'splitAt')) | 0)] = 1;
    x[B.out.off + c.outcome] = 1;
    const l = s.lightRow[c.x]; x[B.light.off + (l < 0.4 ? 0 : l < 0.6 ? 1 : 2)] = 1;
    if (B.lastkind) x[B.lastkind.off + c.lastKind] = 1;
    if (B.dark) x[B.dark.off] = s.dark(c.y * CFG.w + c.x) ? 1 : 0;
    if (B.carried) x[B.carried.off] = c.carried;
    x[B.heard.off + Math.min(c.heard, this.K)] = 1;
    x.set(this.inner, B.inner.off);
  }
  codeOne(cx, x) {
    const { M, fanin, idx, w, act } = cx;
    for (let m = 0; m < M; m++) { let a = 0; const b = m * fanin; for (let j = 0; j < fanin; j++) a += w[b + j] * x[idx[b + j]]; act[m] = a; }
    const counts = new Int32Array(2 * fanin + 1); for (let m = 0; m < M; m++) counts[act[m] + fanin]++;
    let need = cx.k, threshold = fanin, over = 0;
    for (let v = 2 * fanin; v >= 0; v--) { if (counts[v] >= need) { threshold = v - fanin; over = need; break; } need -= counts[v]; threshold = v - fanin - 1; }
    let n = 0, atT = 0;
    for (let m = 0; m < M && n < cx.k; m++) { if (act[m] > threshold) cx.active[n++] = m; else if (act[m] === threshold && atT < over) { cx.active[n++] = m; atT++; } }
    while (n < cx.k) cx.active[n++] = 0;
  }
  readOut(x, q) { // q[a] = the sum over cortices of the mean record of the cells the reading touches
    q.fill(0);
    for (const cx of this.cortices) { this.codeOne(cx, x); for (let j = 0; j < cx.k; j++) { const b = cx.active[j] * this.A; for (let a = 0; a < this.A; a++) q[a] += cx.records[b + a] / cx.k; } }
  }
  imagine(x, a) { // the reading after a move, as far as the window can tell; null if the move is blocked
    const L = this.L, B = L.byName, r = this.r, wn = 2 * r + 1, [dx, dy] = DIRS[a];
    const centre = (r + dy) * wn + (r + dx);
    if ((B.rock && x[B.rock.off + centre]) || x[B.occ.off + centre]) return null;
    const y = new Uint8Array(x);
    for (const grp of L.groups) {
      const wdt = WINDOW_WIDTH[grp.name]; if (!wdt) continue;
      for (let cy = 0; cy < wn; cy++) for (let cx = 0; cx < wn; cx++) {
        const sx = cx + dx, sy = cy + dy, dst = grp.off + (cy * wn + cx) * wdt;
        if (sx < 0 || sy < 0 || sx >= wn || sy >= wn) { for (let u = 0; u < wdt; u++) y[dst + u] = 0; continue; }
        const src = grp.off + (sy * wn + sx) * wdt; for (let u = 0; u < wdt; u++) y[dst + u] = x[src + u];
      }
    }
    for (let u = 0; u < B.out.size; u++) y[B.out.off + u] = 0; y[B.out.off + 1] = 1;
    return y;
  }
  lookahead(x, depth) { // the best value reachable from a reading within depth moves
    const q = new Float32Array(this.A); this.readOut(x, q); this.imagined++;
    let best = -Infinity; for (let a = 0; a < this.A; a++) if (q[a] > best) best = q[a];
    if (depth <= 1) return best;
    for (let a = 0; a < 4; a++) { const y = this.imagine(x, a); if (!y) continue; const v = this.gamma * this.lookahead(y, depth - 1); if (v > best) best = v; }
    return best;
  }
  decide(rng) { // the action-value read, then the horizon's search over imagined moves
    this.imagined = 0;
    const saved = this.cortices.map(cx => cx.active.slice()); // the real reading's code stays for learning
    const score = this.q.slice();
    if (this.horizon > 0) for (let a = 0; a < 4; a++) { const y = this.imagine(this.x, a); if (!y) continue; score[a] = 0.5 * this.q[a] + 0.5 * this.gamma * this.lookahead(y, this.horizon); }
    this.cortices.forEach((cx, i) => cx.active.set(saved[i]));
    const u = rng.random(); let a;
    if (u < this.eps) a = (rng.random() * this.A) | 0;
    else { let best = -Infinity; a = 0; for (let i = 0; i < this.A; i++) if (score[i] > best) { best = score[i]; a = i; } }
    for (const cx of this.cortices) cx.prevActive = cx.active.slice();
    this.inner.fill(0); this.cortices.forEach((cx, ci) => { for (let j = 0; j < cx.k; j++) this.inner[ci * INNER_WIDTH + cx.active[j] % INNER_WIDTH] = 1; });
    this.prevQ = this.q.slice(); this.prevAction = a; this.score = score; return a;
  }
  learn(reward) { // one write into exactly the cells the previous reading touched, by the shared error
    if (!this.prevQ) return;
    let best = -Infinity; for (let a = 0; a < this.A; a++) if (this.q[a] > best) best = this.q[a];
    const a = this.prevAction, err = reward + this.gamma * best - this.prevQ[a]; this.lastDelta = err;
    for (const cx of this.cortices) for (let j = 0; j < cx.k; j++) cx.records[cx.prevActive[j] * this.A + a] += this.lr * err;
  }
  get price() { return POP.read * this.readUnits + POP.cell * this.cellsTotal + POP.write * this.activeTotal; }
}

// ---------- the population, with the known view kept incrementally ----------
class Population {
  constructor(sub, seed) {
    this.sub = sub; this.rules = sub.rules; this.rng = new Mulberry(seed); this.nextId = 0; this.creatures = []; this.births = 0; this.deaths = 0;
    this.count = new Int32Array(N); this.sum = new Float64Array(N); this.sumsq = new Float64Array(N); this.sumTick = new Float64Array(N);
    this.occ = new Int32Array(N).fill(-1); this.spoken = []; this.bitten = []; this.events = []; this.bites = 0; this.available = layoutFor(this.rules, 1, 0).available; this.onDeath = null;
    this.founder = () => firstGenome(this.rng, this.available);
    for (let k = 0; k < POP.initial; k++) {
      const x = (this.rng.random() * CFG.w) | 0, y = (this.rng.random() * CFG.h) | 0, i = y * CFG.w + x;
      if (this.occ[i] >= 0 || sub.rock[i]) continue;
      this.spawn(x, y, POP.birth, this.founder(), null, null); this.occ[i] = 1;
    }
    this.reindex();
  }
  make(x, y, energy, g, lineage, parent) {
    const id = this.nextId++;
    return { id, x, y, energy, g, brain: new Brain(g, this.rules), lineage: lineage === null ? id : lineage, parent, born: this.sub.tick, age: 0, last: 5, outcome: 0, heard: 0, symbol: 0, symbolPrev: 0, lastKind: 2, carried: 0, gut: [], reward: 0, mem: new Map(), slot: -1, px: x, py: y, face: 2, eats: 0, bites: 0, bitten: 0 };
  }
  spawn(x, y, energy, g, lineage, parent) { const c = this.make(x, y, energy, g, lineage, parent); this.creatures.push(c); return c; }
  get held() { let m = 0; for (const c of this.creatures) m += c.energy + c.carried + c.gut.length; return m; }
  get mass() { return this.sub.mass + this.held; }
  record(c, i, food) {
    const old = c.mem.get(i);
    if (old !== undefined) { const f = old & 15, t = old >>> 4; this.count[i]--; this.sum[i] -= f; this.sumsq[i] -= f * f; this.sumTick[i] -= t; }
    c.mem.set(i, food | (this.sub.tick << 4));
    this.count[i]++; this.sum[i] += food; this.sumsq[i] += food * food; this.sumTick[i] += this.sub.tick;
  }
  forget(c) { for (const [i, v] of c.mem) { const f = v & 15, t = v >>> 4; this.count[i]--; this.sum[i] -= f; this.sumsq[i] -= f * f; this.sumTick[i] -= t; } c.mem.clear(); }
  reindex() { this.occ.fill(-1); this.creatures.forEach((c, k) => { c.slot = k; this.occ[c.y * CFG.w + c.x] = k; }); }
  hear(c) {
    for (let d = 1; d <= 2; d++) for (let dy = -d; dy <= d; dy++) for (let dx = -d; dx <= d; dx++) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) !== d) continue;
      const k = this.occ[((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w];
      if (k >= 0 && this.creatures[k].symbolPrev > 0) return this.creatures[k].symbolPrev;
    }
    return 0;
  }
  step() {
    const s = this.sub, cs = this.creatures, n = cs.length, R = this.rules; this.reindex(); this.spoken.length = 0; this.bitten.length = 0; this.events.length = 0;
    for (const c of cs) { c.symbolPrev = c.symbol; c.symbol = 0; c.px = c.x; c.py = c.y; }
    const order = new Int32Array(n); for (let i = 0; i < n; i++) order[i] = i;
    const draws = new Float64Array(Math.max(n - 1, 0)); for (let i = 0; i < draws.length; i++) draws[i] = this.rng.random();
    for (let i = n - 1; i > 0; i--) { const j = (draws[n - 1 - i] * (i + 1)) | 0; const t = order[i]; order[i] = order[j]; order[j] = t; }
    for (let qq = 0; qq < n; qq++) {
      const k = order[qq], c = cs[k], b = c.brain; c.age++;
      const r = b.r;
      for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) { const i = ((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w; if (!s.dark(i)) this.record(c, i, s.food[i]); }
      c.heard = b.hears ? this.hear(c) : 0;
      b.read(this, c); b.readOut(b.x, b.q); b.learn(c.reward);
      const a = b.decide(this.rng), name = b.actions[a]; c.last = a; const before = c.energy; let moved = false, extra = 0;
      while (c.gut.length && c.gut[0] <= s.tick) { c.gut.shift(); c.energy++; } // digestion: a unit eaten digestTicks ago becomes energy now
      const here = c.y * CFG.w + c.x;
      if (a < 4) {
        const [dx, dy] = DIRS[a]; const nx = (c.x + dx + CFG.w) % CFG.w, ny = (c.y + dy + CFG.h) % CFG.h, ni = ny * CFG.w + nx;
        c.face = a;
        if (this.occ[ni] < 0 && !s.rock[ni]) { this.occ[here] = -1; this.occ[ni] = k; c.x = nx; c.y = ny; moved = true; c.outcome = 1; } else c.outcome = 2;
      } else if (name === 'eat') {
        if (s.food[here] > 0) {
          s.food[here]--;
          if (R.kinds && c.lastKind === s.kind[here] && this.rng.random() < 0.5) { s.food[here]++; c.outcome = 6; } /* the same kind again digests half the time; the unit stays otherwise */ else { if (R.digest) c.gut.push(s.tick + CFG.digestTicks); else c.energy++; c.lastKind = s.kind[here]; c.outcome = 3; c.eats++; this.events.push({ kind: 'eat', c }); }
          if (c.outcome === 6) this.events.push({ kind: 'spoiled', c });
        } else if (s.green[here] > 0) { s.green[here]--; s.soil[here]++; c.outcome = 6; this.events.push({ kind: 'unripe', c }); } else c.outcome = 0;
      } else if (name === 'wait') c.outcome = 0;
      else if (name === 'bite') {
        c.outcome = 0; extra = POP.bite;
        for (const [dx, dy] of DIRS) { const j = this.occ[((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w]; if (j < 0) continue; const v = cs[j]; const take = Math.min(3, v.energy); v.energy -= take; c.energy += take; v.outcome = 7; c.outcome = 5; this.bites++; c.bites++; v.bitten++; c.face = DIRS.findIndex(d => d[0] === dx && d[1] === dy); this.bitten.push(v); this.events.push({ kind: 'bite', c, v, take }); break; }
      } else if (name === 'dig') { if (c.carried === 0 && s.soil[here] > 0) { s.soil[here]--; c.carried = 1; c.outcome = 3; this.events.push({ kind: 'dig', c }); } else c.outcome = 0; }
      else if (name === 'drop') { if (c.carried) { s.soil[here]++; c.carried = 0; c.outcome = 3; this.events.push({ kind: 'drop', c }); } else c.outcome = 0; }
      else { c.symbol = a - b.actions.indexOf('say 1') + 1; c.outcome = 4; this.spoken.push(c); this.events.push({ kind: 'speak', c, symbol: c.symbol }); }
      const price = POP.base + b.price + POP.read * POP.imagine * b.readUnits * b.imagined + (moved ? POP.move : 0) + (c.outcome === 4 ? POP.emit : 0) + extra;
      if (this.rng.random() < price) { c.energy--; s.soil[c.y * CFG.w + c.x]++; }
      c.reward = c.energy - before;
    }
    const survivors = [];
    for (const c of cs) { if (c.energy <= 0) { this.deaths++; s.soil[c.y * CFG.w + c.x] += c.carried + c.energy + c.gut.length; c.carried = 0; c.energy = 0; c.gut.length = 0; this.forget(c); c.dead = true; c.diedAt = s.tick; this.events.push({ kind: 'die', c }); if (this.onDeath) this.onDeath(c); continue; } survivors.push(c); }
    this.creatures = survivors; this.reindex();
    const children = [];
    for (const c of this.creatures) {
      const splitAt = G(c.g, 'splitAt');
      if (c.energy < splitAt || this.creatures.length + children.length >= POP.max) continue;
      const free = DIRS.filter(([dx, dy]) => { const j = ((c.y + dy + CFG.h) % CFG.h) * CFG.w + (c.x + dx + CFG.w) % CFG.w; return this.occ[j] < 0 && !s.rock[j]; });
      if (!free.length) continue;
      const [dx, dy] = free[(this.rng.random() * free.length) | 0];
      const nx = (c.x + dx + CFG.w) % CFG.w, ny = (c.y + dy + CFG.h) % CFG.h;
      const share = c.energy >> 1; c.energy -= share;
      const child = this.make(nx, ny, share, mutate(c.g, this.rng, this.available), c.lineage, c.id);
      this.occ[ny * CFG.w + nx] = 1; children.push(child); this.births++; this.events.push({ kind: 'birth', c: child, parent: c });
    }
    this.creatures.push(...children); this.reindex();
  }
}

function mutualInformation(counts) { // counts: array of rows (symbol) of arrays (state)
  let n = 0; const rs = counts.map(r => r.reduce((a, b) => a + b, 0)); const cols = counts[0].length; const cs = new Array(cols).fill(0);
  for (const r of counts) r.forEach((v, j) => { cs[j] += v; n += v; });
  if (!n) return 0; let mi = 0;
  counts.forEach((r, i) => r.forEach((v, j) => { if (v > 0) mi += v / n * Math.log2((v / n) / ((rs[i] / n) * (cs[j] / n))); }));
  return mi;
}

return { Mulberry, INNER_WIDTH, MAX_CORTICES, RULES, CFG, POP, N, DIRS, OUTCOMES, GROUP_NAMES, GENE, CORTEX, G, bit, Substrate, Brain, Population, actionsFor, layoutFor, mutate, firstGenome, mutualInformation };
});
