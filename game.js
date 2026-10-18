(() => {
'use strict';
// ---------- Setup ----------
const T = 48, COLS = 13, VR = 14, W = T * COLS, H = T * VR, NEED = 10, TETHER = 5;
const cv = document.getElementById('game'); cv.width = W; cv.height = H;
const ctx = cv.getContext('2d');
const ANIMALS = [
  { id: 'tiger', name: 'Tiger', body: '#f0922b', belly: '#ffe2b8', snd: 'roar', say: 'ROAR!' },
  { id: 'cat', name: 'House Cat', body: '#9aa0a6', belly: '#ffffff', snd: 'meow', say: 'MEOW!' },
  { id: 'lion', name: 'Lion', body: '#e8c25a', belly: '#fff0c0', snd: 'roar2', say: 'RAAWR!' },
  { id: 'dog', name: 'Dog', body: '#b0713f', belly: '#f1d3b0', snd: 'bark', say: 'WOOF!' },
  { id: 'frog', name: 'Frog', body: '#5cc24e', belly: '#d8f5b8', snd: 'ribbit', say: 'RIBBIT!' }
];
const PCOL = ['#3d8bff', '#ff4d6d'];
const POWERS = { up: 'Speed Up', down: 'Double Jump', left: 'Extra Life' };
const DIRS = { up: [0, 1], down: [0, -1], left: [-1, 0], right: [1, 0] };
const KEYS = { KeyW: [0, 'up'], KeyS: [0, 'down'], KeyA: [0, 'left'], KeyD: [0, 'right'],
  ArrowUp: [1, 'up'], ArrowDown: [1, 'down'], ArrowLeft: [1, 'left'], ArrowRight: [1, 'right'] };

let state = 'select', sel = [0, 1], ready = [false, false], g = null, bottom = 0, clock = 0;

// ---------- Audio (synthesized) ----------
let ac = null;
function audio() {
  if (!ac) { try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) {} }
  if (ac && ac.state === 'suspended') ac.resume();
  return ac;
}
function tone(type, f0, f1, dur, vol, delay = 0, lp = 0) {
  const a = audio(); if (!a) return;
  const t = a.currentTime + delay, o = a.createOscillator(), gn = a.createGain();
  o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur);
  gn.gain.setValueAtTime(0.0001, t); gn.gain.exponentialRampToValueAtTime(vol, t + 0.03);
  gn.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  if (lp) { const f = a.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = lp; o.connect(f); f.connect(gn); } else o.connect(gn);
  gn.connect(a.destination); o.start(t); o.stop(t + dur + 0.05);
}
const SND = {
  meow: () => { tone('triangle', 500, 900, .18, .25); tone('triangle', 900, 450, .35, .25, .17); },
  roar: () => { tone('sawtooth', 140, 60, .9, .35, 0, 500); tone('sawtooth', 100, 45, .9, .3, .02, 400); },
  roar2: () => { tone('sawtooth', 200, 80, .8, .3, 0, 700); tone('square', 150, 70, .8, .15, .03, 500); },
  bark: () => { tone('square', 420, 200, .12, .2, 0, 1500); tone('square', 420, 200, .12, .2, .2, 1500); },
  ribbit: () => { tone('square', 160, 320, .1, .2, 0, 900); tone('square', 180, 360, .12, .2, .14, 900); },
  hop: () => tone('sine', 300, 520, .08, .1),
  coin: () => { tone('square', 880, 880, .06, .1); tone('square', 1320, 1320, .1, .1, .06); },
  power: () => [523, 659, 784, 1047].forEach((f, i) => tone('triangle', f, f, .12, .2, i * .1)),
  nope: () => tone('sawtooth', 200, 100, .4, .2, 0, 600),
  gate: () => tone('triangle', 200, 420, .3, .2)
};

// ---------- World generation ----------
const rnd = (a, b) => a + Math.random() * (b - a);
const ri = (a, b) => Math.floor(rnd(a, b + 1));
const mk = (type, o) => Object.assign({ type, trees: new Set(), coins: new Set() }, o);
function lane(kind, dir, speed, lenR, gapR) {
  const items = []; let x = rnd(-4, 0), total = 0;
  while (x < COLS + 4) { const len = rnd(...lenR), gap = rnd(...gapR); items.push({ x, len, c: ri(0, 5) }); x += len + gap; total += len + gap; }
  return { dir, speed, items, period: Math.max(total, COLS + 8) };
}
function push(row) { g.rows.push(row); return g.rows.length - 1; }
function scatter(row, nT, nC, free) {
  // build a set of forbidden columns:
  const forbidden = new Set();
  if (Array.isArray(free)) for (const c of free) forbidden.add(c);
  // never place trees on gate columns or plate columns (they must remain clear for players)
  if (row.gate && Array.isArray(row.gate.cols)) for (const c of row.gate.cols) forbidden.add(c);
  if (Array.isArray(row.plates)) for (const c of row.plates) forbidden.add(c);

  for (let i = 0; i < nT; i++) {
    const c = ri(0, COLS - 1);
    if (!forbidden.has(c)) row.trees.add(c);
  }
  for (let i = 0; i < nC; i++) {
    const c = ri(0, COLS - 1);
    if (!row.trees.has(c)) row.coins.add(c);
  }
}
function addGrass() { const r = mk('grass'); scatter(r, ri(2, 4), Math.random() < .5 ? 1 : 0); push(r); }
function genSection() {
  g.sec++;
  if (g.sec % 4 === 0) {
    const c0 = ri(1, 7), cols = [c0 + 1, c0 + 3], span = [c0, c0 + 4];
    const plate1 = mk('grass', { plates: cols }); const pi1 = push(plate1);
    const gate1 = { cols, plateRow: pi1, openUntil: 0 }; plate1.gate = gate1; g.gates.push(gate1);
    push(mk('fence', { gate: gate1 }));
    for (let i = 0; i < 4; i++) { const b = mk('bridge', { span }); scatter(b, 0, 0); if (Math.random() < .6) b.coins.add(ri(c0, c0 + 4)); push(b); }
    const last = mk('bridge', { span, plates: cols }); const pi2 = push(last);
    const gate2 = { cols, plateRow: pi2, openUntil: 0 }; last.gate = gate2; g.gates.push(gate2);
    push(mk('fence', { gate: gate2 })); addGrass(); return;
  }
  const k = Math.random();
  if (k < .3) { addGrass(); if (Math.random() < .5) addGrass(); }
  else if (k < .65) {
    const n = ri(2, 4); let d = Math.random() < .5 ? 1 : -1;
    for (let i = 0; i < n; i++, d = -d) push(mk('road', { lane: lane('car', d, rnd(1.6, 4), [1.3, 2.2], [2.5, 6]) }));
    addGrass();
  } else {
    const n = ri(2, 3); let d = Math.random() < .5 ? 1 : -1;
    for (let i = 0; i < n; i++, d = -d) push(mk('water', { lane: lane('log', d, rnd(1, 2.2), [2, 4], [1.2, 2.6]) }));
    addGrass();
  }
}
function genMore() { while (g.rows.length < g.maxRow + 26) genSection(); }

// ---------- Game flow ----------
function startGame() {
  g = { rows: [], gates: [], sec: 0, coins: 0, lives: 3, maxRow: 0, cam: 3, time: 0, state: 'play',
    power: { up: 0, down: 0 }, bubbles: [], msg: '', msgT: 0, votes: [null, null], phase: '', vt: 0, shownGate: false,
    players: [0, 1].map(i => ({ i, kind: ANIMALS[sel[i]], x: 5.5 + i * 2, row: 0, fx: 0, frow: 0, hopT: 1, hopping: false,
      queue: null, invuln: 0, safe: { x: 5.5 + i * 2, row: 0 } })) };
  for (let i = 0; i < 3; i++) push(mk('grass'));
  genMore(); state = 'play';
  say('Reach the far side together!');
}
function say(m) { g.msg = m; g.msgT = 3; }
function toSelect() { state = 'select'; ready = [false, false]; }

function handleKey(pi, dir) {
  if (state === 'select') {
    if (dir === 'left' || dir === 'right') { ready[pi] = false; sel[pi] = (sel[pi] + (dir === 'left' ? -1 : 1) + ANIMALS.length) % ANIMALS.length; }
    else if (dir === 'up') ready[pi] = sel[0] !== sel[1];
    else ready[pi] = false;
    if (ready[0] && ready[1] && sel[0] !== sel[1]) startGame();
  } else if (state === 'play') {
    if (g.state === 'play') { g.players[pi].queue = dir; tryMove(g.players[pi]); }
    else if (g.state === 'vote' && g.phase === 'choose' && POWERS[dir] && g.votes[pi] === null) {
      g.votes[pi] = dir; SND.hop();
      if (g.votes[0] && g.votes[1]) { g.phase = 'reveal'; g.vt = 2; }
    }
  }
}
addEventListener('keydown', e => {
  audio();
  if (KEYS[e.code] || e.code === 'Space' || e.code === 'Enter') e.preventDefault();
  if (e.repeat) return;
  if ((e.code === 'Enter' || e.code === 'Space') && state === 'over') return toSelect();
  const k = KEYS[e.code]; if (k) handleKey(k[0], k[1]);
});

// ---------- Movement & collisions ----------
const colOf = x => Math.floor(x);
function blocked(row, x) {
  const c = colOf(x);
  if (row.trees.has(c)) return true;
  if (row.type === 'fence') return !(row.gate.cols.includes(c) && g.time < row.gate.openUntil);
  return false;
}
function canEnter(p, nx, nr, dy, steps, other) {
  if (nr < 0 || nr < Math.floor(g.cam - 5)) return false;
  if (nx < 0.5 || nx > COLS - 0.5) return false;
  if (dy > 0 && nr - other.row > TETHER) { say('Wait for your partner!'); return false; }
  const row = g.rows[nr]; if (!row) return false;
  if (steps === 2 && dy !== 0 && g.rows[p.row + dy].type === 'fence') return false;
  return !blocked(row, nx);
}
function tryMove(p) {
  if (p.hopping || !p.queue || g.state !== 'play') return;
  const [dx, dy] = DIRS[p.queue]; p.queue = null;
  const other = g.players[1 - p.i];
  for (let s = g.power.down > 0 ? 2 : 1; s >= 1; s--) {
    const nr = p.row + dy * s; let nx = p.x + dx * s;
    const row = g.rows[nr]; if (row && row.type !== 'water') nx = colOf(nx) + .5;
    if (canEnter(p, nx, nr, dy, s, other)) {
      p.fx = p.x; p.frow = p.row; p.x = nx; p.row = nr; p.hopping = true; p.hopT = 0; SND.hop(); return;
    }
  }
}
const effRow = p => p.hopping && p.hopT < .5 ? p.frow : p.row;
const effX = p => p.hopping && p.hopT < .5 ? p.fx : p.x;
function hit(p) {
  if (p.invuln > 0 || g.state !== 'play') return;
  SND[p.kind.snd](); g.lives--;
  g.bubbles.push({ x: p.x, row: p.row, text: p.kind.say, t: 1.3 });
  p.invuln = 2; p.hopping = false; p.hopT = 1; p.queue = null; p.x = p.safe.x; p.row = p.safe.row;
  if (g.lives <= 0) { state = 'over'; }
}
function land(p) {
  p.hopping = false;
  const row = g.rows[p.row], c = colOf(p.x);
  if (row.coins.has(c)) { row.coins.delete(c); SND.coin(); if (++g.coins >= NEED) { g.state = 'vote'; g.phase = 'choose'; g.votes = [null, null]; } }
  if (p.row > g.maxRow) { g.maxRow = p.row; genMore(); }
  if ((row.type === 'grass') || (row.type === 'bridge' && c >= row.span[0] && c <= row.span[1])) p.safe = { x: colOf(p.x) + .5, row: p.row };
  if (row.type === 'bridge' && (c < row.span[0] || c > row.span[1])) hit(p);
  if (!g.shownGate && row.type === 'grass' && g.gates.some(q => q.plateRow - p.row < 6 && q.plateRow >= p.row)) { g.shownGate = true; say('Gate ahead: stand on a plate each to open it!'); }
}
function resolveVote() {
  const [a, b] = g.votes;
  if (a === b) { SND.power(); if (a === 'left') g.lives++; else g.power[a] = 20; say(POWERS[a] + ' activated!'); }
  else { SND.nope(); say('Different picks - no power-up!'); }
  g.coins = 0; g.state = 'play';
}

function update(dt) {
  if (state !== 'play') return;
  if (g.state === 'vote') { if (g.phase === 'reveal' && (g.vt -= dt) <= 0) resolveVote(); return; }
  g.time += dt; if (g.msgT > 0) g.msgT -= dt;
  g.power.up = Math.max(0, g.power.up - dt); g.power.down = Math.max(0, g.power.down - dt);
  const lo = g.cam - 8, hi = g.cam + 24;
  g.rows.forEach((row, r) => {
    if (!row.lane || r < lo || r > hi) return;
    const L = row.lane;
    L.items.forEach(it => { it.x += L.dir * L.speed * dt;
      if (L.dir > 0 && it.x > COLS + 4) it.x -= L.period; if (L.dir < 0 && it.x + it.len < -4) it.x += L.period; });
  });
  // gate plates
  g.gates.forEach(q => {
    const on = g.players.filter(p => !p.hopping && p.row === q.plateRow && q.cols.includes(colOf(p.x))).map(p => colOf(p.x));
    if (on.length === 2 && on[0] !== on[1]) { if (g.time >= q.openUntil) SND.gate(); q.openUntil = g.time + 5; }
  });
  const dur = g.power.up > 0 ? .08 : .14;
  g.players.forEach(p => {
    p.invuln = Math.max(0, p.invuln - dt);
    if (p.hopping) { p.hopT += dt / dur; if (p.hopT >= 1) { p.hopT = 1; land(p); if (state !== 'play') return; } }
    const row = g.rows[effRow(p)], px = effX(p);
    if (row.type === 'road') row.lane.items.forEach(c => { if (px + .3 > c.x + .05 && px - .3 < c.x + c.len - .05) hit(p); });
    if (!p.hopping && row.type === 'water') {
      const log = row.lane.items.find(l => p.x >= l.x && p.x <= l.x + l.len);
      if (log) p.x += row.lane.dir * row.lane.speed * dt; else hit(p);
      if (p.x < 0 || p.x > COLS) hit(p);
    }
    if (!p.hopping) tryMove(p);
  });
  if (state !== 'play') return;
  const target = (g.players[0].row + g.players[1].row) / 2;
  g.cam += (target - g.cam) * Math.min(1, dt * 5);
  g.bubbles.forEach(b => b.t -= dt); g.bubbles = g.bubbles.filter(b => b.t > 0);
}

// ---------- Drawing ----------
const rowY = r => H - (r - bottom + 1) * T;
function rrect(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, h, r) : ctx.rect(x, y, w, h); }
function text(s, x, y, size, col = '#fff', align = 'center', stroke = true) {
  ctx.font = `bold ${size}px system-ui, sans-serif`; ctx.textAlign = align; ctx.textBaseline = 'middle';
  if (stroke) { ctx.lineWidth = size / 5; ctx.strokeStyle = 'rgba(0,0,0,.65)'; ctx.strokeText(s, x, y); }
  ctx.fillStyle = col; ctx.fillText(s, x, y);
}
function drawTree(c, y) {
  ctx.fillStyle = '#7a4a22'; ctx.fillRect(c * T + 20, y + 28, 8, 16);
  ctx.fillStyle = '#2f8f3a'; ctx.beginPath(); ctx.arc(c * T + 24, y + 22, 17, 0, 7); ctx.fill();
  ctx.fillStyle = '#3fae4a'; ctx.beginPath(); ctx.arc(c * T + 19, y + 17, 8, 0, 7); ctx.fill();
}
function drawRow(row, r) {
  const y = rowY(r);
  if (row.type === 'road') { ctx.fillStyle = '#4b4f58'; ctx.fillRect(0, y, W, T);
    ctx.fillStyle = '#e7e2c0'; if (g.rows[r + 1] && g.rows[r + 1].type === 'road') for (let x = 0; x < W; x += 40) ctx.fillRect(x + 6, y - 2, 24, 4); }
  else if (row.type === 'water' || row.type === 'bridge') {
    ctx.fillStyle = '#3aa5e6'; ctx.fillRect(0, y, W, T); ctx.fillStyle = 'rgba(255,255,255,.25)';
    for (let i = 0; i < 6; i++) ctx.fillRect(((i * 107 + r * 31 + clock * 12) % (W + 20)) - 10, y + 12 + (i % 3) * 10, 18, 3);
    if (row.type === 'bridge') { const x0 = row.span[0] * T, w = (row.span[1] - row.span[0] + 1) * T;
      ctx.fillStyle = '#b9824a'; ctx.fillRect(x0, y, w, T); ctx.fillStyle = '#8a5a2b';
      for (let x = x0; x < x0 + w; x += 16) ctx.fillRect(x, y, 2, T); ctx.fillRect(x0, y, w, 4); ctx.fillRect(x0, y + T - 4, w, 4); }
  } else { ctx.fillStyle = r % 2 ? '#7ccf5a' : '#72c450'; ctx.fillRect(0, y, W, T); }
  if (row.plates) row.plates.forEach(c => { const q = row.gate, on = g.time < q.openUntil;
    ctx.fillStyle = on ? '#58e07a' : '#ffd24a'; ctx.beginPath(); ctx.arc(c * T + 24, y + 24, 17, 0, 7); ctx.fill();
    ctx.strokeStyle = '#7a5a10'; ctx.lineWidth = 3; ctx.stroke(); });
  if (row.type === 'fence') { const q = row.gate, open = g.time < q.openUntil;
    for (let c = 0; c < COLS; c++) {
      if (q.cols.includes(c)) { ctx.fillStyle = '#5a3a1a'; ctx.fillRect(c * T, y + 6, 6, 36); ctx.fillRect(c * T + 42, y + 6, 6, 36);
        if (!open) { ctx.fillStyle = '#c0392b'; ctx.fillRect(c * T + 6, y + 12, 36, 6); ctx.fillRect(c * T + 6, y + 28, 36, 6); } }
      else { ctx.fillStyle = '#a5732f'; ctx.fillRect(c * T, y + 14, T, 6); ctx.fillRect(c * T, y + 30, T, 6);
        ctx.fillStyle = '#7a4a22'; ctx.fillRect(c * T + 4, y + 6, 8, 36); ctx.fillRect(c * T + 36, y + 6, 8, 36); } } }
  row.trees.forEach(c => drawTree(c, y));
  row.coins.forEach(c => { const b = Math.sin(clock * 5 + c) * 3;
    ctx.fillStyle = '#ffcf33'; ctx.beginPath(); ctx.ellipse(c * T + 24, y + 24 + b, 9, 11, 0, 0, 7); ctx.fill();
    ctx.strokeStyle = '#b8860b'; ctx.lineWidth = 2; ctx.stroke(); });
  if (row.lane) row.lane.items.forEach(it => { const x = it.x * T, w = it.len * T;
    if (row.type === 'road') { ctx.fillStyle = ['#e74c3c', '#f1c40f', '#9b59b6', '#ecf0f1', '#1abc9c', '#e67e22'][it.c];
      rrect(x, y + 8, w, 32, 7); ctx.fill(); ctx.fillStyle = 'rgba(30,40,60,.75)';
      const wx = row.lane.dir > 0 ? x + w * .55 : x + w * .1; ctx.fillRect(wx, y + 12, w * .35, 24); }
    else { ctx.fillStyle = '#8d5a2b'; rrect(x, y + 8, w, 32, 14); ctx.fill(); ctx.fillStyle = '#a8713a'; rrect(x + 4, y + 12, w - 8, 8, 4); ctx.fill(); } });
}
function drawAnimal(k, tag) {
  const o = (x, y, rx, ry, col) => { ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, 7); ctx.fill(); };
  const tri = (a, b, c, col) => { ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.lineTo(...c); ctx.fill(); };
  const dark = '#2b2018';
  if (k.id === 'lion') o(0, -8, 20, 20, '#a8661f');
  if (k.id === 'dog') { o(-15, -9, 6, 11, '#6b3f1c'); o(15, -9, 6, 11, '#6b3f1c'); }
  rrect(-15, -4, 30, 22, 8); ctx.fillStyle = k.body; ctx.fill();
  o(0, 10, 9, 7, k.belly); o(-10, 17, 6, 3.5, k.body); o(10, 17, 6, 3.5, k.body);
  o(0, -9, 14, 13, k.body);
  if (k.id === 'tiger' || k.id === 'cat') { for (const s of [-1, 1]) tri([s * 13, -15], [s * 11, -30], [s * 3, -21], k.body); }
  if (k.id === 'tiger') { ctx.fillStyle = dark; for (const x of [-4, 0, 4]) ctx.fillRect(x - 1, -21, 2, 6);
    ctx.fillRect(-15, 2, 7, 3); ctx.fillRect(8, 2, 7, 3); ctx.fillRect(-15, 9, 7, 3); ctx.fillRect(8, 9, 7, 3); o(0, -3, 7, 5, k.belly); }
  if (k.id === 'cat') { ctx.strokeStyle = '#555'; ctx.lineWidth = 1; ctx.beginPath();
    for (const s of [-1, 1]) { ctx.moveTo(s * 5, -4); ctx.lineTo(s * 17, -6); ctx.moveTo(s * 5, -3); ctx.lineTo(s * 17, -1); } ctx.stroke(); o(0, -3, 6, 4.5, k.belly); }
  if (k.id === 'lion') { o(-12, -20, 5, 5, k.body); o(12, -20, 5, 5, k.body); o(0, -9, 12, 11, k.body); o(0, -3, 6, 5, k.belly); }
  if (k.id === 'dog') o(0, -3, 7, 5, k.belly);
  if (k.id === 'frog') { o(-8, -21, 6, 6, k.body); o(8, -21, 6, 6, k.body); o(-8, -21, 3.5, 3.5, '#fff'); o(8, -21, 3.5, 3.5, '#fff');
    o(-8, -21, 1.8, 1.8, dark); o(8, -21, 1.8, 1.8, dark); ctx.strokeStyle = dark; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(0, -6, 8, .2, Math.PI - .2); ctx.stroke(); }
  else { o(-5, -10, 3.6, 3.6, '#fff'); o(5, -10, 3.6, 3.6, '#fff'); o(-5, -10, 1.8, 1.8, dark); o(5, -10, 1.8, 1.8, dark); o(0, -6, 2.6, 2, '#d96a7a'); }
  if (tag) { tri([-6, -35], [6, -35], [0, -29], tag); }
}
function drawPlayer(p) {
  if (p.invuln > 0 && Math.floor(clock * 12) % 2) return;
  const t = p.hopT, vx = p.fx + (p.x - p.fx) * t, vr = p.frow + (p.row - p.frow) * t;
  const lift = p.hopping ? Math.sin(Math.PI * t) * T * .45 : Math.sin(clock * 4 + p.i) * 1.2;
  const sx = p.hopping ? vx * T : p.x * T, sy = rowY(p.hopping ? vr : p.row) + T / 2 - lift;
  ctx.save(); ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.beginPath(); ctx.ellipse(sx, rowY(p.hopping ? vr : p.row) + 40, 14 - lift / 6, 5, 0, 0, 7); ctx.fill();
  ctx.translate(sx, sy); ctx.scale(.85, .85); drawAnimal(p.kind, PCOL[p.i]); ctx.restore();
}
function hud() {
  ctx.fillStyle = 'rgba(0,0,0,.45)'; ctx.fillRect(0, 0, W, 34);
  text('♥'.repeat(Math.min(g.lives, 8)) + (g.lives > 8 ? '+' : ''), 10, 17, 18, '#ff6b81', 'left');
  ctx.fillStyle = 'rgba(255,255,255,.25)'; ctx.fillRect(W / 2 - 80, 10, 160, 14);
  ctx.fillStyle = '#ffcf33'; ctx.fillRect(W / 2 - 80, 10, 160 * g.coins / NEED, 14); text(`${g.coins}/${NEED}`, W / 2, 17, 12, '#fff');
  text(`Distance ${g.maxRow}`, W - 10, 17, 16, '#fff', 'right');
  let y = 50; if (g.power.up > 0) { text(`Speed Up ${Math.ceil(g.power.up)}s`, 10, y, 14, '#7dffb0', 'left'); y += 18; }
  if (g.power.down > 0) text(`Double Jump ${Math.ceil(g.power.down)}s`, 10, y, 14, '#7dd0ff', 'left');
  if (g.msgT > 0) text(g.msg, W / 2, 70, 18, '#fff');
}
function drawVote() {
  ctx.fillStyle = 'rgba(0,0,0,.72)'; ctx.fillRect(0, 0, W, H);
  text('POWER-UP TIME', W / 2, 110, 34, '#ffcf33');
  text('Both players press the SAME key to claim it', W / 2, 150, 17);
  const opts = [['up', '↑', 'Speed Up'], ['down', '↓', 'Double Jump'], ['left', '←', 'Extra Life']];
  opts.forEach(([d, sym, name], i) => { const x = 60 + i * 180;
    const picked = g.phase === 'reveal' ? g.votes.map((v, j) => v === d ? j : -1).filter(j => j >= 0) : [];
    ctx.fillStyle = picked.length ? 'rgba(255,207,51,.25)' : 'rgba(255,255,255,.12)'; rrect(x, 190, 160, 150, 14); ctx.fill();
    text(sym, x + 80, 240, 46); text(name, x + 80, 295, 18); picked.forEach((j, n) => text('P' + (j + 1), x + 80 + (n ? 28 : -28 * (picked.length - 1)), 322, 15, PCOL[j])); });
  [0, 1].forEach(i => { const keys = i ? '↑ ↓ ←' : 'W S A', v = g.votes[i];
    text(`P${i + 1} (${keys}): ` + (v ? 'locked in ✓' : 'choosing...'), W / 2, 390 + i * 30, 20, PCOL[i]); });
  if (g.phase === 'reveal') text(g.votes[0] === g.votes[1] ? 'MATCH!' : 'No match - no power-up', W / 2, 480, 30, g.votes[0] === g.votes[1] ? '#7dffb0' : '#ff8a8a');
}
function drawSelect() {
  const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#2c5e3a'); gr.addColorStop(1, '#16301f'); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  text('CRITTER CROSSING', W / 2, 70, 40, '#ffcf33'); text('2-player co-op hopper', W / 2, 105, 16);
  ANIMALS.forEach((a, i) => { const x = 14 + i * 120, y = 160;
    ctx.fillStyle = 'rgba(255,255,255,.1)'; rrect(x, y, 108, 150, 12); ctx.fill();
    [0, 1].forEach(p => { if (sel[p] === i) { ctx.strokeStyle = PCOL[p]; ctx.lineWidth = 4; rrect(x + 2 + p * 4, y + 2 + p * 4, 104 - p * 8, 146 - p * 8, 10); ctx.stroke();
      text('P' + (p + 1) + (ready[p] ? ' ✓' : ''), x + 30 + p * 48, y + 168 + (i % 2) * 0, 15, PCOL[p]); } });
    ctx.save(); ctx.translate(x + 54, y + 85); ctx.scale(1.5, 1.5); drawAnimal(a); ctx.restore(); text(a.name, x + 54, y + 130, 14); });
  const lines = ['P1: A / D pick, W ready      P2: ← / → pick, ↑ ready', 'Pick two different animals', '',
    'Hop over roads, logs and bridges. Gates need BOTH of you:', 'stand on one plate each.', '',
    'Every 10 coins: vote with the SAME key', '↑ Speed Up   ↓ Double Jump   ← Extra Life', 'Different keys = no power-up'];
  lines.forEach((l, i) => text(l, W / 2, 400 + i * 26, 16, '#e8f5e0', 'center', false));
}
function render() {
  ctx.clearRect(0, 0, W, H);
  if (state === 'select') return drawSelect();
  bottom = g.cam - 5.5;
  for (let r = Math.max(0, Math.floor(bottom) - 1); r <= bottom + VR + 1 && g.rows[r]; r++) drawRow(g.rows[r], r);
  g.players.slice().sort((a, b) => b.row - a.row).forEach(drawPlayer);
  g.bubbles.forEach(b => { const x = b.x * T, y = rowY(b.row) - 20 - (1.3 - b.t) * 25; text(b.text, x, y, 22, '#fff04d'); });
  hud();
  if (g.state === 'vote') drawVote();
  if (state === 'over') { ctx.fillStyle = 'rgba(0,0,0,.7)'; ctx.fillRect(0, 0, W, H);
    text('GAME OVER', W / 2, 250, 44, '#ff6b81'); text(`Distance ${g.maxRow}`, W / 2, 310, 24); text('Press Enter or Space to play again', W / 2, 360, 18); }
}

let last = performance.now();
(function loop(now) {
  const dt = Math.min(.05, (now - last) / 1000); last = now; clock += dt;
  update(dt); render(); requestAnimationFrame(loop);
})(last);
})();
