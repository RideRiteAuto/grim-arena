// A lightweight scripted "player" for testing relay-worker.js message-routing
// logic (interest culling, event batching, redundant-advance, position
// precision) without needing a second full 3D Playwright client. Two full
// clients booted in this sandbox proved unstable (browser crashes when
// manually driving both via tick() to bypass rAF throttling -- see
// TIER2-NETWORKING-EDITOR-PLAN.md history). One real client is stable
// (harness/relay-local-test.js); this bot is the other half of the pair.
//
// Speaks the real wire protocol directly over `ws`, matching what
// relay-worker.js's webSocketMessage() expects and what the real client's
// myWorldState()/netWorldSend() actually send (verified against the client
// source, not guessed):
//   connect -> {t:'welcome', proto, id, sv}
//   send {t:'hello', n, c} -> {t:'roster', sim, players:[...]}, broadcasts {t:'join',...}
//   send {t:'s', p:[x,y,z], y:<yaw>, h:<hp, NOT heading>, bg} at whatever
//     cadence the caller wants (real client does ~10Hz via netWorldSend)
//   receives whatever the server relays/broadcasts back (other players' 's',
//   'w' npc snapshots if host, 'sim' ownership announcements, etc.)
// Server-side, m.p feeds meta.px/meta.pz and m.h feeds meta.php (player hp,
// used for NPC aggro/interest at relay-worker.js:893) -- both matter for
// testing item #1 (interest culling) and #4 (nhit's redundant advance()).
//
// Usage as a module: const {RelayBot} = require('./relay-bot');
//   const bot = new RelayBot('ws://127.0.0.1:8787/world/main', {name: 'BOT1'});
//   await bot.connect();
//   await bot.hello();
//   bot.setPos(10, 0, 10);       // update what future 's' sends contain
//   bot.startPositionPump(100);  // send 's' every 100ms, like the real client's ~10Hz
//   ... inspect bot.lastSeen (map of id -> last message of each relayed type) ...
//   bot.stop(); bot.close();
//
// Usage standalone: node harness/relay-bot.js [wsUrl] [durationMs]
// Prints a JSON summary of what it saw and exits.

const WebSocket = require('ws');

class RelayBot {
  constructor(url, opts = {}) {
    this.url = url;
    this.name = opts.name || 'BOT';
    this.color = opts.color || 0xffffff;
    this.id = null;
    this.ws = null;
    this.pos = [0, 0, 0];
    this.yaw = 0;
    this.hp = 100;
    this._pumpTimer = null;
    this.received = [];         // every parsed message, in order, capped
    this.lastSeen = {};         // t -> most recent message of that type
    this.seenFromIds = new Set(); // sender ids ('_p' or 'i') seen in any relayed msg
    this._maxLog = opts.maxLog || 500;
  }

  connect(timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      const to = setTimeout(() => reject(new Error('connect timeout')), timeoutMs);
      this.ws = new WebSocket(this.url);
      this.ws.on('open', () => {});
      this.ws.on('message', (raw) => {
        let m;
        try { m = JSON.parse(raw.toString()); } catch (e) { return; }
        this._record(m);
        if (m.t === 'welcome') {
          this.id = m.id;
          clearTimeout(to);
          resolve(m);
        }
      });
      this.ws.on('error', (e) => { clearTimeout(to); reject(e); });
    });
  }

  _record(m) {
    this.received.push(m);
    if (this.received.length > this._maxLog) this.received.shift();
    this.lastSeen[m.t] = m;
    const sender = m._p || m.i;
    if (sender && sender !== this.id) this.seenFromIds.add(sender);
  }

  send(m) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(m));
  }

  hello(timeoutMs = 5000) {
    return new Promise((resolve, reject) => {
      const to = setTimeout(() => reject(new Error('hello/roster timeout')), timeoutMs);
      const prevHandler = this.ws.listeners('message').slice();
      const onMsg = (raw) => {
        let m;
        try { m = JSON.parse(raw.toString()); } catch (e) { return; }
        if (m.t === 'roster') {
          clearTimeout(to);
          this.ws.removeListener('message', onMsg);
          resolve(m);
        }
      };
      this.ws.on('message', onMsg);
      this.send({ t: 'hello', n: this.name, c: this.color });
    });
  }

  setPos(x, y, z, yaw) {
    this.pos = [x, y, z];
    if (typeof yaw === 'number') this.yaw = yaw;
  }

  setHp(hp) { this.hp = hp; }

  sendPos(bg) {
    // Mirrors myWorldState()'s shape closely enough for server-side routing
    // logic (px/pz/php, RELAYED/OWNER_ONLY checks) -- not a full client, so
    // fields the server doesn't read (fr, mv, w, etc.) are omitted.
    this.send({
      t: 's', n: this.name, c: this.color, p: this.pos, y: this.yaw,
      st: 'idle', sst: 0, h: this.hp, m: 100, bg: bg ? 1 : 0
    });
  }

  startPositionPump(intervalMs = 100) {
    this.stopPositionPump();
    this._pumpTimer = setInterval(() => this.sendPos(false), intervalMs);
  }

  stopPositionPump() {
    if (this._pumpTimer) { clearInterval(this._pumpTimer); this._pumpTimer = null; }
  }

  // Convenience: how many distinct OTHER senders have we heard from for a
  // given message type since connecting (or since last reset)?
  sendersSeenFor(type) {
    const set = new Set();
    for (const m of this.received) {
      if (m.t === type) {
        const sender = m._p || m.i;
        if (sender && sender !== this.id) set.add(sender);
      }
    }
    return [...set];
  }

  countOfType(type) {
    return this.received.filter(m => m.t === type).length;
  }

  close() {
    this.stopPositionPump();
    if (this.ws) { try { this.ws.close(); } catch (e) {} }
  }
}

if (require.main === module) {
  (async () => {
    const url = process.argv[2] || 'ws://127.0.0.1:8787/world/main';
    const durationMs = parseInt(process.argv[3] || '8000', 10);
    const bot = new RelayBot(url, { name: 'PROBE' });
    const welcome = await bot.connect();
    const roster = await bot.hello();
    bot.setPos(5, 0, 5, 0);
    bot.startPositionPump(100);
    await new Promise(r => setTimeout(r, durationMs));
    bot.close();
    console.log(JSON.stringify({
      welcome, roster,
      totalReceived: bot.received.length,
      typeCounts: bot.received.reduce((acc, m) => { acc[m.t] = (acc[m.t] || 0) + 1; return acc; }, {}),
      distinctSenders: [...bot.seenFromIds]
    }, null, 2));
  })().catch(e => { console.error('ERROR', e); process.exit(1); });
}

module.exports = { RelayBot };
