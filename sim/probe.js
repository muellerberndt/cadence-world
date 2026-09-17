// node sim/probe.js '{"ripen":true,"rock":true}' 8000 1 > out.jsonl
// One world under one rule set for T ticks; a line of population statistics every 500 ticks, and at
// the end the lifetime-at-death tables by brain size, by cortex count and by horizon, the mask
// census, and the symbol statistics over the last quarter of the run.
const CW = require('./core.js');
const rules = JSON.parse(process.argv[2] || '{}'), T = +process.argv[3] || 8000, seed = +process.argv[4] || 1;
const sub = new CW.Substrate(seed, rules), pop = new CW.Population(sub, seed + 100); const m0 = pop.mass;
const lifeByCells = {}, lifeByCortices = {}, lifeByHorizon = {}, lifeByRadius = {}, lifeByHalves = {};
const push = (t, k, v) => (t[k] = t[k] || []).push(v);
pop.onDeath = c => { push(lifeByCells, c.brain.cellsTotal, c.age); push(lifeByCortices, c.brain.cortices.length, c.age); push(lifeByHorizon, c.brain.horizon, c.age); push(lifeByRadius, c.brain.r, c.age); push(lifeByHalves, c.brain.halves ? 'halves' : c.brain.readsInner ? 'recurrent' : 'plain', c.age); };
// symbol statistics over the last quarter: joint counts of (symbol uttered, food here > 0), (symbol, a neighbour present), (symbol, kin adjacent)
const K = 5, joint = { food: Array.from({ length: K }, () => [0, 0]), neighbour: Array.from({ length: K }, () => [0, 0]), kin: Array.from({ length: K }, () => [0, 0]) };
let heardReward = [0, 0], deafReward = [0, 0];
const t0 = Date.now();
const mean = (cs, f) => cs.length ? cs.reduce((a, c) => a + f(c), 0) / cs.length : 0;
for (let t = 1; t <= T; t++) {
  sub.step(); pop.step();
  if (t > 0.75 * T) {
    for (const c of pop.creatures) {
      if (c.brain.K > 0) {
        const here = c.y * CW.CFG.w + c.x, foodHere = sub.food[here] > 0 ? 1 : 0; let nb = 0, kin = 0;
        for (const [dx, dy] of CW.DIRS) { const j = pop.occ[((c.y + dy + CW.CFG.h) % CW.CFG.h) * CW.CFG.w + (c.x + dx + CW.CFG.w) % CW.CFG.w]; if (j >= 0) { nb = 1; if (pop.creatures[j].lineage === c.lineage) kin = 1; } }
        const s = Math.min(c.symbol, K - 1); joint.food[s][foodHere]++; joint.neighbour[s][nb]++; joint.kin[s][kin]++;
      }
      if (c.brain.hears) { heardReward[0] += c.reward; heardReward[1]++; } else { deafReward[0] += c.reward; deafReward[1]++; }
    }
  }
  if (t % 500 === 0 || t === T) {
    const cs = pop.creatures; const census = {};
    for (const c of cs) for (const cx of c.brain.cortices) for (const name of CW.GROUP_NAMES) if (cx.mask & CW.bit(name)) census[name] = (census[name] || 0) + 1;
    for (const k of Object.keys(census)) census[k] = +(census[k] / Math.max(cs.length, 1)).toFixed(2);
    const hist = (f) => { const h = {}; for (const c of cs) { const v = f(c); h[v] = (h[v] || 0) + 1; } return h; };
    console.log(JSON.stringify({ t, alive: cs.length, births: pop.births, deaths: pop.deaths, bites: pop.bites, mass_ok: pop.mass === m0, age: +mean(cs, c => c.age).toFixed(0),
      cells: +mean(cs, c => c.brain.cellsTotal).toFixed(0), cortices: +mean(cs, c => c.brain.cortices.length).toFixed(2), readUnits: +mean(cs, c => c.brain.readUnits).toFixed(0),
      radius: +mean(cs, c => c.brain.r).toFixed(2), horizon: +mean(cs, c => c.brain.horizon).toFixed(2), splitAt: +mean(cs, c => CW.G(c.g, 'splitAt')).toFixed(0),
      lr: +mean(cs, c => CW.G(c.g, 'lr')).toFixed(3), gamma: +mean(cs, c => c.brain.gamma).toFixed(2), eps: +mean(cs, c => c.brain.eps).toFixed(3),
      inner: +mean(cs, c => c.brain.readsInner).toFixed(2), halves: +mean(cs, c => c.brain.halves).toFixed(2), speak: +mean(cs, c => c.brain.K > 0).toFixed(2), symbolsMean: +mean(cs, c => c.brain.K).toFixed(2), hears: +mean(cs, c => c.brain.hears).toFixed(2),
      corticesHist: hist(c => c.brain.cortices.length), horizonHist: hist(c => c.brain.horizon), census, s: ((Date.now() - t0) / 1000) | 0 }));
  }
}
const table = t => { const out = {}; for (const k of Object.keys(t)) { const a = t[k]; a.sort((x, y) => x - y); out[k] = { n: a.length, median: a[a.length >> 1], mean: +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(0) }; } return out; };
const shuffled = counts => { // the mutual information after the symbols are permuted: the chance level at this sample size
  const rng = new CW.Mulberry(7); const pairs = []; counts.forEach((r, i) => r.forEach((v, j) => { for (let q = 0; q < v; q++) pairs.push([i, j]); }));
  const sy = pairs.map(p => p[0]); for (let i = sy.length - 1; i > 0; i--) { const j = (rng.random() * (i + 1)) | 0; const t = sy[i]; sy[i] = sy[j]; sy[j] = t; }
  const c2 = counts.map(r => r.map(() => 0)); pairs.forEach((p, i) => { c2[sy[i]][p[1]]++; }); return CW.mutualInformation(c2);
};
const symbols = {}; for (const k of Object.keys(joint)) { const n = joint[k].flat().reduce((a, b) => a + b, 0); symbols[k] = { n, mi: +CW.mutualInformation(joint[k]).toFixed(4), chance: +shuffled(joint[k]).toFixed(4) }; }
console.log(JSON.stringify({ final: true, rules, seed, T, lifeByCells: table(lifeByCells), lifeByCortices: table(lifeByCortices), lifeByHorizon: table(lifeByHorizon), lifeByRadius: table(lifeByRadius), lifeByHalves: table(lifeByHalves), symbols,
  rewardPerTick: { hears: heardReward[1] ? +(heardReward[0] / heardReward[1]).toFixed(4) : null, deaf: deafReward[1] ? +(deafReward[0] / deafReward[1]).toFixed(4) : null } }));
