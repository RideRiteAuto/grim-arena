#!/usr/bin/env python3
"""Patch 79.115: retry once on a failed edit-layer fetch, log why on give-up.

Kevin's report: a map edit he saved (and which took effect live) sometimes
shows the plain generated world instead after "a patch" goes out. Traced the
whole path this session:

  - The relay's stored edit layer itself is fine. Fetched it directly
    (https://grim-arena.kevin-230.workers.dev/world/main/edits) and it is
    Kevin's real work: rev 55, 566 KB, his copper/stone placements and paint
    all present and correct.
  - Booted the actual shipped bundle against that exact saved data (via the
    harness, three.js vendor path fixed so it is a real boot, not a stub)
    and it loads and applies correctly: GRIM_EDIT.on is true, every object
    streams in, nothing is missing.
  - A code patch to the game never touches the relay's stored layer at all;
    it is Durable Object storage on Cloudflare, completely separate from the
    GitHub Pages bundle. There is no path from "ship a patch" to "the saved
    layer is gone."

So this could not be reproduced as data loss. What IS a real, found gap:
doLoad() in editor-core.js gives the layer fetch a firm 2.5s timeout (right
call, boot should never hang on the network) but on ANY failure - timeout, a
dropped connection, a slow cold start on the relay - it gives up after one
try and silently falls back to the generated world. No retry, nothing in the
console beyond api.err being set (which nothing reads). If that fetch ever
loses a single race, a player sees the bare generated map with zero sign of
why, which is exactly what "the map reset" would look like from the outside,
even though nothing was lost.

Fix: try twice before giving up (worst case ~5.5s of the original 2.5s
budget, still well inside "never make a player stare at a black screen"),
and log a clear console.warn on the final failure so this is diagnosable
from the console next time instead of a mystery. Editing editor-core.js
directly on disk since it is synced into EDITOR-BEGIN/END on every build.
"""
import io

CORE = 'editor-core.js'
c = io.open(CORE, encoding='utf-8').read()
n = 0

old = """  async function doLoad(url) {
    if (!CFG.LAYER) { setLayer(null); api.on = false; return api; }
    const u = url || CFG.URL;
    if (!u) { setLayer(null); return api; }
    // Boot must never wait on the network for longer than it takes a player
    // to notice. If the relay is slow or unreachable the generated world is
    // shown immediately; the layer is not worth a black screen.
    let ac = null, timer = null;
    try {
      try { ac = new AbortController(); } catch (e) { ac = null; }
      if (ac) timer = setTimeout(() => { try { ac.abort(); } catch (e) {} }, 2500);
      const res = await fetch(u + (u.indexOf('?') < 0 ? '?' : '&') + 'b=' + Date.now(), {
        method: 'GET', cache: 'no-store', signal: ac ? ac.signal : undefined
      });
      if (!res.ok) throw new Error('http ' + res.status);
      rev = +(res.headers.get('x-edit-rev') || 0) || 0;
      const body = await res.json();
      api.rev = rev;
      setLayer(body && body.empty ? null : body);
    } catch (e) {
      // A world edit layer that cannot be fetched must never stop the game
      // booting. The generated world is a complete, playable world; the
      // authored layer is an improvement on it, not a dependency.
      api.err = String((e && e.message) || e);
      setLayer(null);
    } finally {
      if (timer) clearTimeout(timer);
    }
    return api;
  }"""

assert c.count(old) == 1, 'patch 79.115: doLoad anchor found %d times, wanted 1' % c.count(old)

new = """  // One attempt at the fetch, with its own hard timeout. Broken out so
  // doLoad can retry it once without duplicating the abort/timer plumbing.
  async function fetchLayerOnce(u, ms) {
    let ac = null, timer = null;
    try {
      try { ac = new AbortController(); } catch (e) { ac = null; }
      if (ac) timer = setTimeout(() => { try { ac.abort(); } catch (e) {} }, ms);
      const res = await fetch(u + (u.indexOf('?') < 0 ? '?' : '&') + 'b=' + Date.now(), {
        method: 'GET', cache: 'no-store', signal: ac ? ac.signal : undefined
      });
      if (!res.ok) throw new Error('http ' + res.status);
      const gotRev = +(res.headers.get('x-edit-rev') || 0) || 0;
      const body = await res.json();
      return { rev: gotRev, body };
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  async function doLoad(url) {
    if (!CFG.LAYER) { setLayer(null); api.on = false; return api; }
    const u = url || CFG.URL;
    if (!u) { setLayer(null); return api; }
    // Boot must never wait on the network for longer than it takes a player
    // to notice. If the relay is slow or unreachable the generated world is
    // shown immediately; the layer is not worth a black screen. A single
    // dropped connection or a cold Durable Object used to mean one lost race
    // silently showed the bare generated map with zero sign of why, so this
    // gets one retry before it gives up - still well inside that budget.
    let lastErr = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const got = await fetchLayerOnce(u, 2500);
        rev = got.rev;
        api.rev = rev;
        setLayer(got.body && got.body.empty ? null : got.body);
        return api;
      } catch (e) {
        lastErr = e;
      }
    }
    // A world edit layer that cannot be fetched must never stop the game
    // booting. The generated world is a complete, playable world; the
    // authored layer is an improvement on it, not a dependency. But two
    // failed tries is worth a clear console line, so this is diagnosable
    // instead of a mystery next time.
    api.err = String((lastErr && lastErr.message) || lastErr);
    try { console.warn('[GRIM_EDIT] authored layer failed to load after 2 tries, showing the generated world:', api.err); } catch (e) {}
    setLayer(null);
    return api;
  }"""

c = c.replace(old, new)
n += 1
io.open(CORE, 'w', encoding='utf-8').write(c)

print('79.115_edit_layer_load_retry: %d edits applied' % n)
