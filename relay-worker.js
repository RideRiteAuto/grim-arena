/**
 * Grim World relay.
 *
 * One Durable Object per world. Every player holds a WebSocket to it, so there
 * is no peer to peer connection anywhere in the system. That single change
 * removes the whole class of failures the old design suffered from:
 *
 *   - no NAT traversal, so a blocked home network cannot silently exclude a player
 *   - no host election, so two players can never end up in separate worlds
 *   - no dependency on one player's machine staying awake
 *   - instant, announced handover of simulation duty when the owner leaves
 *
 * State lives on the sockets, not in this object's memory. A Durable Object can
 * be evicted or hibernated at any moment; anything held in a field would be
 * silently lost and every player would then be told they are the host. The
 * socket set from getWebSockets() and each socket's own attachment are the only
 * sources of truth here, so a restart is invisible to players.
 */

const PROTO = 2;

// A player may not exceed this many messages per second. The game sends about
// 20. This exists so a bug cannot burn the daily message budget.
const RATE_LIMIT = 60;

// Messages the relay forwards. Anything not on this list is dropped, so a
// malformed or hostile client cannot make the relay echo arbitrary data.
const RELAYED = new Set(['s', 'w', 'nhit', 'ndead', 'rhit', 'rdead', 'phit', 'lreq', 'lok', 'skupd', 'sknew', 'chat']);

// Only the simulation owner may speak world truth.
const OWNER_ONLY = new Set(['w', 'ndead', 'rdead', 'phit', 'lok', 'skupd', 'sknew']);

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
      return json({
        ok: true,
        proto: PROTO,
        players: socks.length,
        sim: this.ownerId(socks),
        names: socks.map(s => (this.meta(s) || {}).name || '?')
      });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];

    // Hibernation-aware accept: the runtime owns the socket, not this object.
    this.state.acceptWebSocket(server);

    const now = Date.now();
    const id = 'p' + Math.random().toString(36).slice(2, 8) + now.toString(36).slice(-3);
    server.serializeAttachment({ id, name: 'PLAYER', color: 0, joined: now, sec: 0, count: 0 });

    this.send(server, { t: 'welcome', proto: PROTO, id });
    this.reelect();

    return new Response(null, { status: 101, webSocket: client });
  }

  // ---------------------------------------------------------------- handlers

  async webSocketMessage(ws, raw) {
    const meta = this.meta(ws);
    if (!meta) return;

    const sec = Math.floor(Date.now() / 1000);
    if (sec !== meta.sec) { meta.sec = sec; meta.count = 0; }
    meta.count++;
    this.setMeta(ws, meta);
    if (meta.count > RATE_LIMIT) return;

    let m;
    try { m = JSON.parse(raw); } catch (e) { return; }
    if (!m || typeof m.t !== 'string') return;

    const socks = this.sockets();

    if (m.t === 'hello') {
      meta.name = String(m.n || 'PLAYER').slice(0, 14).toUpperCase();
      meta.color = (m.c | 0) || 0;
      this.setMeta(ws, meta);
      this.send(ws, {
        t: 'roster',
        sim: this.ownerId(socks),
        players: socks.map(s => { const x = this.meta(s) || {}; return { i: x.id, n: x.name, c: x.color }; })
      });
      this.broadcast(socks, { t: 'join', i: meta.id, n: meta.name, c: meta.color }, ws);
      return;
    }

    if (m.t === 'ping') { this.send(ws, { t: 'pong', ts: m.ts }); return; }
    if (m.t === 'bye') { try { ws.close(1000, 'bye'); } catch (e) {} return; }

    if (!RELAYED.has(m.t)) return;

    const ownerId = this.ownerId(socks);
    if (OWNER_ONLY.has(m.t) && meta.id !== ownerId) return;

    m.i = meta.id;                       // stamped here, never trusted from the client

    if (m.to) {                          // directed reply, used for loot grants
      const target = socks.find(s => { const x = this.meta(s); return x && x.id === m.to; });
      if (target) this.send(target, m);
      return;
    }

    if (TO_OWNER.has(m.t)) {
      const owner = socks.find(s => { const x = this.meta(s); return x && x.id === ownerId; });
      if (owner && owner !== ws) this.send(owner, m);
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
    this.reelect(socks);
  }

  // ------------------------------------------------------------------ owner

  // The oldest live connection owns simulation. Recomputed fresh from the live
  // socket set every time, so it survives an eviction and can never disagree
  // between two players.
  ownerId(socks) {
    const list = socks || this.sockets();
    let best = null;
    for (const s of list) {
      const x = this.meta(s);
      if (!x || !x.id) continue;
      if (!best || x.joined < best.joined || (x.joined === best.joined && x.id < best.id)) best = x;
    }
    return best ? best.id : null;
  }

  reelect(socks) {
    const list = socks || this.sockets();
    this.broadcast(list, { t: 'sim', i: this.ownerId(list) });
  }

  // ------------------------------------------------------------------ utils

  sockets() {
    try { return this.state.getWebSockets(); } catch (e) { return []; }
  }

  meta(ws) {
    try { return ws.deserializeAttachment(); } catch (e) { return null; }
  }

  setMeta(ws, meta) {
    try { ws.serializeAttachment(meta); } catch (e) {}
  }

  send(ws, obj) {
    try { ws.send(JSON.stringify(obj)); } catch (e) {}
  }

  broadcast(socks, obj, except) {
    const s = JSON.stringify(obj);
    for (const w of socks) {
      if (w === except) continue;
      try { w.send(s); } catch (e) {}
    }
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
