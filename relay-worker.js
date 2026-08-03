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

const PROTO = 4;
const RATE_LIMIT = 60;              // msgs/sec per player; the game sends ~20
const OWNER_STALE_MS = 8000;

// Messages the relay forwards. Anything else is dropped.
const RELAYED = new Set(['s', 'w', 'nhit', 'ndead', 'rhit', 'rdead', 'phit', 'lreq', 'lok', 'lno', 'skupd', 'sknew', 'skgone', 'chat']);
// Only the simulation owner may speak world truth.
const OWNER_ONLY = new Set(['w', 'ndead', 'rdead', 'phit', 'lok', 'lno', 'skupd', 'sknew', 'skgone']);
// Claims the owner alone needs to see.
const TO_OWNER = new Set(['nhit', 'rhit', 'lreq']);

export class World {
  constructor(state, env) {
    this.state = state;
    this.env = env;
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

    this.send(server, { t: 'welcome', proto: PROTO, id });
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

    if (m.t === 'ping') { this.send(ws, { t: 'pong', ts: m.ts }); return; }
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
