/**
 * Grim World relay.
 *
 * One Durable Object per world. Every player holds a WebSocket to it, so there
 * is no peer to peer connection anywhere in the system.
 *
 * State lives on the sockets, not in this object's memory. A Durable Object can
 * be evicted or hibernated at any moment; anything held in a field would be
 * silently lost. Each socket's attachment carries {id, name, color, joined,
 * seen, bg, owner} and is the only source of truth, so a restart is invisible.
 *
 * SIMULATION OWNERSHIP (v3): exactly one player runs monsters. The flag lives
 * on that player's socket attachment. Three things move it, all announced with
 * a 'sim' broadcast so no two clients can ever disagree:
 *   - the owner disconnects: oldest remaining player takes over
 *   - the owner's tab goes hidden and sends 'yield': the most recently active
 *     VISIBLE player takes over (a hidden Chrome tab freezes the simulation -
 *     monsters stop animating, stop fighting, and never process deaths - so a
 *     hidden owner is a frozen world for everyone)
 *   - the owner goes silent for 8s while others keep talking: same handover,
 *     for tabs that froze without managing to say anything
 */

const PROTO = 6;
const RATE_LIMIT = 60;              // msgs/sec per player; the game sends ~20
const OWNER_STALE_MS = 8000;

// Messages the relay forwards. Anything else is dropped.
const RELAYED = new Set(['s', 'w', 'nhit', 'ndead', 'rhit', 'rdead', 'phit', 'lreq', 'lok', 'lno', 'skupd', 'sknew', 'skgone', 'chat']);
// Only the simulation owner may speak world truth.
const OWNER_ONLY = new Set(['w', 'ndead', 'rdead', 'phit', 'lok', 'lno', 'skupd', 'sknew', 'skgone']);
// Claims the owner alone needs to see (movement-only traffic).
const TO_OWNER = new Set(['rhit']);

// ---------------------------------------------------------------------------
// SERVER-AUTHORITATIVE COMBAT (v5)
//
// Monster health, death, respawn, kill credit and every loot sack now live
// here, not in a player's browser. A frozen or slow tab can no longer stop a
// monster taking damage, dying, or dropping anything, and no client can grant
// itself loot. Players still draw monster movement locally; only the facts
// that matter are decided here.
//
// State is persisted, because a Durable Object hibernates while sockets stay
// open and anything held only in memory would silently vanish mid-fight.
// ---------------------------------------------------------------------------

/* SHARED-RULES-BEGIN */
const GRIM_RULES = {
  V: 1,

  // ---- world bounds -------------------------------------------------------
  WORLD_R: 168,          // open-world edge, clamped identically on both sides
  ARENA_R: 23,           // legacy duel arena

  // ---- movement -----------------------------------------------------------
  SPEED: 5.6,
  SPRINT: 8.4,
  DIFF: { squire: 0.62, veteran: 1.0, champion: 1.42 },

  // ---- attacks ------------------------------------------------------------
  // wind = telegraph, act = damage frame, rec = recovery. range/arc define the
  // hit shape; a client judges only ITSELF against this shape, so these numbers
  // are what makes a dodge fair.
  MOVES: {
    light:  { wind: .32, act: .12, rec: .22, dmg: [8, 12],  range: 3.0, arc: 1.9, stam: 6 },
    heavy:  { wind: .48, act: .15, rec: .40, dmg: [22, 30], range: 3.4, arc: 2.5, stam: 18, heavy: true },
    glight: { wind: .30, act: .16, rec: .34, dmg: [18, 26], range: 3.6, arc: 2.7, stam: 12 },
    gheavy: { wind: .60, act: .18, rec: .52, dmg: [34, 46], range: 3.9, arc: 3.0, stam: 26, heavy: true },
    frost:  { wind: .62, act: .06, rec: .34, mana: 22 },
    snare:  { wind: .48, act: .05, rec: .42, mana: 14 },
    volley: { wind: .7,  act: .05, rec: .5,  mana: 20 },
    heal:   { wind: 1.2, act: .06, rec: .3,  mana: 30 },
    storm:  { wind: .5,  act: .06, rec: .36, mana: 26 },
    bash:   { wind: .3,  act: .1,  rec: .3,  dmg: [4, 7],   range: 2.3, arc: 1.7, stam: 8, bash: true },
    slam:   { wind: .72, act: .18, rec: .52, dmg: [24, 36], range: 5.4, arc: 6.3, stam: 0, heavy: true },
    chop:   { wind: .24, act: .12, rec: .3,  stam: 4 },
    shot:   { wind: .06, act: .04, rec: .30 },
    rapid:  { wind: .12, act: .62, rec: .26, stam: 14 }
  },

  // ---- safe ground --------------------------------------------------------
  // Nothing picks a fight inside these, and anything dragged in breaks off.
  SAFE: [
    { x: 0, z: 0, r: 26, follows: 'town' },   // Hollowrest / Northreach, centre filled in from the live town position
    { x: 41, z: 31, r: 15 }                   // starting camp
  ],
  LEASH_R: 46,           // dragged this far from home, a monster gives up
  DEAGGRO_R: 32,         // lose interest past this
  RESPAWN_MS: 120000,
  RESPAWN_BOSS_MS: 150000,

  // ---- loot ---------------------------------------------------------------
  // Pure data so the game and the server roll the same table. qty may be a
  // number or a [min,max] inclusive range.
  LOOT: {
    gold: { king: 900, captain: 280, wraith: 75, bandit: 48, wolf: 24, deer: 9, rat: 130, goblin: 6, other: 32 },
    // first matching rule wins, mirroring the original if/else chain exactly
    extra: [
      { tag: 'wolf',  items: [{ item: 'WOLF PELT', qty: 1 }] },
      { tag: 'deer',  items: [{ item: 'DEER HIDE', qty: 1 }, { item: 'VENISON', qty: [1, 2] }] },
      { tag: 'king',  items: [{ item: 'HOLLOW PLATE', qty: 1 }, { item: 'HOLLOW AMULET', qty: 1 }] },
      { tag: 'rat',   items: [{ item: 'RAT TAIL', qty: 1 }] },
      { notTags: ['goblin', 'bandit', 'wraith', 'captain'], items: [{ item: 'TESLA PAYCHECK', qty: 1 }] }
    ]
  },

  // ---- sacks --------------------------------------------------------------
  SACK_OWN_MS: 60000,    // killer's exclusive claim
  SACK_LIFE_MS: 240000,  // then public, then gone
  SACK_CAP: 40,

  // ---- networking ---------------------------------------------------------
  SIM_HZ: 8,             // server simulation timestep
  SNAP_HZ: 8,            // snapshot rate for monsters in a fight
  SNAP_IDLE_HZ: 1,       // snapshot rate for monsters doing nothing
  INTEREST_R: 60,        // a player is only told about monsters this close
  CLOCK_SAMPLES: 8       // rolling median window for server-time offset
};

// Roll a loot table entry set. Both sides call this with the same tag object.
// `rnd` is injected so the server can use a seeded generator and the client can
// use Math.random without either importing the other's plumbing.
function grimRollLoot(tag, rnd) {
  tag = tag || {};
  rnd = rnd || Math.random;
  const G = GRIM_RULES.LOOT.gold;
  const gold = tag.king ? G.king : tag.captain ? G.captain : tag.wraith ? G.wraith
             : tag.bandit ? G.bandit : tag.wolf ? G.wolf : tag.deer ? G.deer
             : tag.rat ? G.rat : tag.goblin ? G.goblin : G.other;
  const out = [{ item: 'GOLD CROWNS', qty: gold }];
  for (const rule of GRIM_RULES.LOOT.extra) {
    let match;
    if (rule.tag) match = !!tag[rule.tag];
    else match = !rule.notTags.some(t => tag[t]);
    if (!match) continue;
    for (const it of rule.items) {
      const q = Array.isArray(it.qty) ? it.qty[0] + Math.floor(rnd() * (it.qty[1] - it.qty[0] + 1)) : it.qty;
      out.push({ item: it.item, qty: q });
    }
    break;                                   // first match only, like the original
  }
  return out;
}

// Stable order-independent-ish fingerprint of the world manifest. Both sides
// compute it the same way, so a mismatch is detected on join instead of
// showing up later as a monster standing inside a wall.
function grimHash(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h.toString(36);
}
/* SHARED-RULES-END */

export class World {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.mem = null;                        // {npcs, sacks, seq} cache of stored world state
  }

  // ------------------------------------------------------- world state (durable)

  async world() {
    if (this.mem) return this.mem;
    const w = await this.state.storage.get('world');
    this.mem = w || { npcs: null, sacks: {}, seq: 0 };
    return this.mem;
  }
  async saveWorld() {
    if (!this.mem) return;
    try { await this.state.storage.put('world', this.mem); } catch (e) {}
  }

  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname.endsWith('/health') || request.headers.get('Upgrade') !== 'websocket') {
      const socks = this.sockets();
      const owner = this.resolveOwner(socks);
      return json({
        ok: true,
        proto: PROTO,
        players: socks.length,
        sim: owner ? owner.meta.id : null,
        names: socks.map(s => (this.meta(s) || {}).name || '?')
      });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];
    this.state.acceptWebSocket(server);

    const now = Date.now();
    const id = 'p' + Math.random().toString(36).slice(2, 8) + now.toString(36).slice(-3);
    server.serializeAttachment({ id, name: 'PLAYER', color: 0, joined: now, seen: now, bg: 0, sec: 0, count: 0 });

    this.send(server, { t: 'welcome', proto: PROTO, id, sv: now });
    const socks = this.sockets();
    const owner = this.resolveOwner(socks);
    this.broadcast(socks, { t: 'sim', i: owner ? owner.meta.id : null });

    return new Response(null, { status: 101, webSocket: client });
  }

  // ---------------------------------------------------------------- handlers

  async webSocketMessage(ws, raw) {
    const meta = this.meta(ws);
    if (!meta) return;
    const now = Date.now();

    const sec = Math.floor(now / 1000);
    if (sec !== meta.sec) { meta.sec = sec; meta.count = 0; }
    meta.count++;
    meta.seen = now;

    let m;
    try { m = JSON.parse(raw); } catch (e) { this.setMeta(ws, meta); return; }
    if (!m || typeof m.t !== 'string') { this.setMeta(ws, meta); return; }
    if (m.t === 's') meta.bg = m.bg ? 1 : 0;
    this.setMeta(ws, meta);
    if (meta.count > RATE_LIMIT) return;

    const socks = this.sockets();

    if (m.t === 'hello') {
      meta.name = String(m.n || 'PLAYER').slice(0, 14).toUpperCase();
      meta.color = (m.c | 0) || 0;
      this.setMeta(ws, meta);
      const owner = this.resolveOwner(socks);
      this.send(ws, {
        t: 'roster',
        sim: owner ? owner.meta.id : null,
        players: socks.map(s => { const x = this.meta(s) || {}; return { i: x.id, n: x.name, c: x.color }; })
      });
      this.broadcast(socks, { t: 'join', i: meta.id, n: meta.name, c: meta.color }, ws);
      return;
    }

    if (m.t === 'ping') { this.send(ws, { t: 'pong', ts: m.ts, sv: now }); return; }
    if (m.t === 'bye') { try { ws.close(1000, 'bye'); } catch (e) {} return; }

    if (m.t === 'yield') {                          // hidden owner hands the world off
      if (meta.owner) {
        const nb = this.pickNewOwner(socks, ws, true);
        if (nb) { delete meta.owner; this.setMeta(ws, meta); this.makeOwner(socks, nb.ws, nb.meta); }
      }
      return;
    }

    // A frozen owner that never even said goodbye: anyone else's traffic
    // evicts it after 8 silent seconds.
    let owner = this.resolveOwner(socks);
    if (owner && owner.ws !== ws && now - (owner.meta.seen || 0) > OWNER_STALE_MS) {
      const nb = this.pickNewOwner(socks, owner.ws);
      if (nb) { const om = owner.meta; delete om.owner; this.setMeta(owner.ws, om); this.makeOwner(socks, nb.ws, nb.meta); owner = { ws: nb.ws, meta: nb.meta }; }
    }

    // ---- server-authoritative combat ------------------------------------
    if (m.t === 'manifest' || m.t === 'nreg' || m.t === 'nhit' || m.t === 'lreq' || m.t === 'lall') {
      await this.combat(ws, meta, m, socks);
      return;
    }
    // The owner no longer speaks for monster health or death; the server does.
    if (m.t === 'ndead' || m.t === 'lok' || m.t === 'lno' || m.t === 'skupd' || m.t === 'sknew' || m.t === 'skgone') return;

    if (!RELAYED.has(m.t)) return;
    if (OWNER_ONLY.has(m.t) && (!owner || meta.id !== owner.meta.id)) return;

    m._p = meta.id;                                 // sender, stamped here and never trusted from the client
    delete m.to_;                                   // reserved

    if (m.to) {                                     // directed reply, used for loot grants
      const target = socks.find(s => { const x = this.meta(s); return x && x.id === m.to; });
      if (target) this.send(target, m);
      return;
    }

    if (TO_OWNER.has(m.t)) {
      if (owner && owner.ws !== ws) this.send(owner.ws, m);
      return;
    }

    this.broadcast(socks, m, ws);
  }

  // -------------------------------------------------------------- combat

  async combat(ws, meta, m, socks) {
    const w = await this.world();
    const now = Date.now();

    // A client hands over the monster roster once. The server owns health from
    // that moment on; later registrations are ignored so nobody can reset a
    // fight by reloading.
    // The world manifest: colliders, safe ground and monster spawns, uploaded
    // once with a fingerprint. The server keeps the first one it is given. A
    // client arriving with a different fingerprint is told so and defers to the
    // stored copy, which is what stops one player's stale build from putting
    // monsters where nobody else can see them. A genuinely new build replaces
    // it only when the world is empty of other players.
    if (m.t === 'manifest') {
      const mf = m.w;
      const alone = socks.length <= 1;
      if (!mf || typeof mf.hash !== 'string') return;
      if (!w.manifest || (w.manifest.hash !== mf.hash && alone)) {
        w.manifest = mf;
        w.npcs = null;                        // a new world means new monsters
        w.sacks = {};
        await this.saveWorld();
      }
      const agreed = w.manifest.hash === mf.hash;
      if (!w.npcs && Array.isArray(w.manifest.spawns)) {
        w.npcs = w.manifest.spawns.map(s => ({
          hp: Math.max(1, s.max | 0), max: Math.max(1, s.max | 0), tag: s.tag || {},
          xp: s.xp | 0, boss: !!s.boss, dead: 0, at: 0, by: null
        }));
        await this.saveWorld();
      }
      this.send(ws, {
        t: 'msync', hash: w.manifest.hash, agreed, sv: Date.now(),
        n: (w.npcs || []).map(n => [n.hp, n.dead ? 1 : 0])
      });
      return;
    }

    if (m.t === 'nreg') {
      if (!w.npcs && Array.isArray(m.n) && m.n.length && m.n.length < 400) {
        w.npcs = m.n.map(x => ({ hp: Math.max(1, x.m | 0), max: Math.max(1, x.m | 0), tag: x.tag || {}, xp: x.xp | 0, boss: !!x.boss, dead: 0, at: 0, by: null }));
        await this.saveWorld();
      }
      this.send(ws, { t: 'nsync', n: (w.npcs || []).map(n => [n.hp, n.dead ? 1 : 0]) });
      return;
    }

    if (m.t === 'nhit') {
      if (!w.npcs) return;
      const i = m.i | 0;
      const n = w.npcs[i];
      if (!n || n.dead || n.hp <= 0) return;
      const dmg = Math.max(0, Math.min(9999, Math.round(+m.d || 0)));
      if (!dmg) return;
      n.hp = Math.max(0, n.hp - dmg);
      n.by = meta.id;
      // Everyone hears the hit: the attacker for confirmation, the others so
      // the health bar matches. The monster's own reaction rides along.
      this.broadcast(socks, { t: 'nhp', i: i, hp: n.hp, d: dmg, k: m.k || 'hit', by: meta.id, p: m.p || null, o: m.o || null });
      if (n.hp <= 0) {
        n.dead = 1;
        n.at = now + (n.boss ? GRIM_RULES.RESPAWN_BOSS_MS : GRIM_RULES.RESPAWN_MS);
        const entries = grimRollLoot(n.tag).filter(e => e && e.qty > 0);
        let sack = null;
        if (entries.length) {
          w.seq = (w.seq || 0) + 1;
          const id = 'k' + w.seq.toString(36) + now.toString(36).slice(-4);
          sack = { id, x: (m.p && +(+m.p[0]).toFixed(2)) || 0, z: (m.p && +(+m.p[2]).toFixed(2)) || 0,
                   entries: entries.map((e, k) => ({ e: k, item: e.item, qty: Math.floor(e.qty) })),
                   owner: meta.id, pub: now + GRIM_RULES.SACK_OWN_MS, die: now + GRIM_RULES.SACK_LIFE_MS };
          w.sacks[id] = sack;
          const ids = Object.keys(w.sacks);
          if (ids.length > GRIM_RULES.SACK_CAP) {
            let oldest = ids[0];
            for (const k2 of ids) if (w.sacks[k2].die < w.sacks[oldest].die) oldest = k2;
            delete w.sacks[oldest];
            this.broadcast(socks, { t: 'skgone', id: oldest });
          }
        }
        this.broadcast(socks, { t: 'ndead', i: i, xp: n.xp, tag: n.tag, killer: meta.id, p: m.p || null, at: n.at - now });
        if (sack) this.broadcast(socks, { t: 'sknew', s: this.wire(sack, now) });
        await this.setAlarm(n.at);
      }
      await this.saveWorld();
      return;
    }

    if (m.t === 'lreq') {                    // take from a sack
      const s = w.sacks[m.id];
      if (!s) { this.send(ws, { t: 'lno', tok: m.tok }); return; }
      if (now < s.pub && meta.id !== s.owner) { this.send(ws, { t: 'lno', tok: m.tok, locked: 1 }); return; }
      const en = s.entries.find(x => x.e === (m.e | 0));
      if (!en || en.qty < 1) { this.send(ws, { t: 'lno', tok: m.tok }); return; }
      const take = Math.max(1, Math.min(Math.floor(+m.q) || 1, en.qty));
      en.qty -= take;
      this.send(ws, { t: 'lok', tok: m.tok, item: en.item, qty: take });
      if (en.qty <= 0) s.entries = s.entries.filter(x => x.qty > 0);
      if (!s.entries.length) { delete w.sacks[m.id]; this.broadcast(socks, { t: 'skgone', id: m.id }); }
      else this.broadcast(socks, { t: 'skupd', id: m.id, e: en.e, qty: en.qty });
      await this.saveWorld();
      return;
    }

    if (m.t === 'lall') {                    // a player asks for everything present
      this.send(ws, { t: 'lsync', sacks: Object.keys(w.sacks).map(k => this.wire(w.sacks[k], now)) });
      return;
    }
  }

  wire(s, now) {
    return { id: s.id, x: s.x, z: s.z, entries: s.entries, owner: s.owner,
             pubIn: Math.max(0, s.pub - now), dieIn: Math.max(0, s.die - now) };
  }

  // Respawns and sack expiry must survive hibernation, so they run on an alarm
  // rather than a timer, which a hibernated object would never fire.
  async setAlarm(at) {
    try {
      const cur = await this.state.storage.getAlarm();
      if (cur === null || at < cur) await this.state.storage.setAlarm(at);
    } catch (e) {}
  }

  async alarm() {
    const w = await this.world();
    const now = Date.now();
    const socks = this.sockets();
    let next = 0;
    if (w.npcs) {
      for (let i = 0; i < w.npcs.length; i++) {
        const n = w.npcs[i];
        if (!n.dead) continue;
        if (n.at <= now) { n.dead = 0; n.hp = n.max; n.by = null; n.at = 0; this.broadcast(socks, { t: 'nrsp', i: i, hp: n.hp }); }
        else if (!next || n.at < next) next = n.at;
      }
    }
    for (const k of Object.keys(w.sacks)) {
      const s = w.sacks[k];
      if (s.die <= now) { delete w.sacks[k]; this.broadcast(socks, { t: 'skgone', id: k }); }
      else if (!next || s.die < next) next = s.die;
    }
    await this.saveWorld();
    if (next) { try { await this.state.storage.setAlarm(next); } catch (e) {} }
  }

  async webSocketClose(ws) { this.gone(ws); }
  async webSocketError(ws) { this.gone(ws); }

  gone(ws) {
    const meta = this.meta(ws);
    const socks = this.sockets().filter(s => s !== ws);
    if (meta) this.broadcast(socks, { t: 'left', i: meta.id });
    const flagged = socks.find(s => { const x = this.meta(s); return x && x.owner; });
    if (!flagged) {
      const nb = this.pickNewOwner(socks, null);
      if (nb) { this.makeOwner(socks, nb.ws, nb.meta); return; }   // makeOwner broadcasts 'sim'
    }
    const owner = this.resolveOwner(socks);
    this.broadcast(socks, { t: 'sim', i: owner ? owner.meta.id : null });
  }

  // ------------------------------------------------------------------ owner

  // The sticky flag wins; with no flag in the room the oldest connection is
  // stamped. Always resolved from the live socket set, so hibernation and
  // restarts cannot fork ownership.
  resolveOwner(socks) {
    for (const s of socks) { const x = this.meta(s); if (x && x.owner) return { ws: s, meta: x }; }
    let best = null;
    for (const s of socks) {
      const x = this.meta(s);
      if (!x || !x.id) continue;
      if (!best || x.joined < best.meta.joined || (x.joined === best.meta.joined && x.id < best.meta.id)) best = { ws: s, meta: x };
    }
    if (best) { best.meta.owner = true; this.setMeta(best.ws, best.meta); }
    return best;
  }

  makeOwner(socks, ws, meta) {
    for (const s of socks) { const x = this.meta(s); if (x && x.owner && s !== ws) { delete x.owner; this.setMeta(s, x); } }
    meta.owner = true; this.setMeta(ws, meta);
    this.broadcast(socks, { t: 'sim', i: meta.id });
  }

  // Prefer the most recently active VISIBLE player; a hidden tab would just
  // freeze the world all over again. Falls back to most recently active.
  pickNewOwner(socks, exceptWs, onlyVisible) {
    let best = null;
    for (const s of socks) {
      if (s === exceptWs) continue;
      const x = this.meta(s);
      if (!x || !x.id) continue;
      if (onlyVisible && x.bg) continue;
      const score = (x.bg ? 0 : 1e15) + (x.seen || 0);
      if (!best || score > best.score) best = { ws: s, meta: x, score };
    }
    return best;
  }

  // ------------------------------------------------------------------ utils

  sockets() { try { return this.state.getWebSockets(); } catch (e) { return []; } }
  meta(ws) { try { return ws.deserializeAttachment(); } catch (e) { return null; } }
  setMeta(ws, meta) { try { ws.serializeAttachment(meta); } catch (e) {} }
  send(ws, obj) { try { ws.send(JSON.stringify(obj)); } catch (e) {} }
  broadcast(socks, obj, except) {
    const s = JSON.stringify(obj);
    for (const w of socks) { if (w === except) continue; try { w.send(s); } catch (e) {} }
  }
}

function json(o) {
  return new Response(JSON.stringify(o), {
    headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' }
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*' } });
    }
    const parts = url.pathname.split('/').filter(Boolean);
    if (parts.length && parts[0] !== 'world' && parts[0] !== 'health') {
      return json({ ok: false, hint: 'connect to /world/<name>' });
    }
    const world = (parts[0] === 'world' && parts[1]) ? parts[1] : 'main';
    const id = env.WORLD.idFromName(world);
    return env.WORLD.get(id).fetch(request);
  }
};
