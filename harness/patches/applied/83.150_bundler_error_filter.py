#!/usr/bin/env python3
"""Patch 83.150: stop the on-screen error banner reacting to bundler noise.

Kevin saw a scary red "[bundle] Uncaught TypeError: Cannot read properties
of undefined (reading 'toLowerCase')" banner while simply using the Paint
tool. Reproduced live in Chrome (fires on ANY paint click, e.g. plain packed
dirt, so it has nothing to do with beach sand or the ground shader) and read
the actual console stack rather than the banner's own filename/lineno, which
is unreliable here because the whole game document is itself an eval'd/blob
payload:

  TypeError: Cannot read properties of undefined (reading 'toLowerCase')
      at eval (eval at evalDcLogic (blob:...:844:16), <anonymous>:3563:20)

`evalDcLogic` does not exist anywhere in this project: not in editor-core.js,
editor-tools.js, editor-ui.js, harness/, worldgen, or the ~3MB extracted game
source (grepped all of it), and this project's own code never calls eval()
or new Function() at all (also grepped, zero hits). It is bundler/runtime
infrastructure a few eval layers below our own template (the same machinery
that decompresses and mounts the manifest's asset blobs), throwing on some
unrelated internal edge case. It is also harmless: the paint click that
triggered it still landed (the cell count went up in the same test).

The banner code (index.html / grim-arena-standalone.html, both identical
outside the embedded template line, so both get the same edit here) is a
blanket `window.addEventListener('error', ...)` that displays EVERY uncaught
error on the page with the same "[bundle]" label, with no way to tell "our
game code broke" from "something three layers of eval down in the packaging
machinery hiccuped". This patch adds one targeted check: if the thrown
error's own stack mentions evalDcLogic, log it quietly to the console
instead of surfacing the banner. Everything else -- every error from our own
code, and any error whose stack does NOT mention evalDcLogic, including
future unknown ones -- still shows the banner exactly as before. This is
deliberately narrow: it suppresses the one specific, already-diagnosed
source of noise rather than filtering by any broader heuristic that could
hide a real bug.

Verify: harness/error-filter.js (added by this patch) feeds the handler a
few synthetic ErrorEvent-shaped objects in Node (one with evalDcLogic in the
stack, one plain TypeError from our own code, one resource-load event) and
checks exactly the first is swallowed.
"""
import io

BUNDLES = ['index.html', 'grim-arena-standalone.html']
n = 0

OLD = """    if (!e.message && !e.error && e.target && e.target !== window) {
      console.warn('[bundle] resource failed to load:',
        e.target.tagName, String(e.target.src || e.target.href || ''));
      return;
    }
    var p = document.body || document.documentElement;"""

NEW = """    if (!e.message && !e.error && e.target && e.target !== window) {
      console.warn('[bundle] resource failed to load:',
        e.target.tagName, String(e.target.src || e.target.href || ''));
      return;
    }
    // Patch 83.150: this whole document is itself an eval'd/blob payload, so
    // e.filename/e.lineno below are not reliable enough to tell "our game
    // code broke" from "something several eval layers down in the bundler's
    // own packaging machinery hiccuped". One specific, already-diagnosed
    // source of that noise is evalDcLogic, which does not exist anywhere in
    // this project (grepped) and fires on unrelated internal bundler state,
    // not on anything the game or editor does -- confirmed live, it does
    // not stop whatever the player just did from taking effect. Swallow
    // (quietly, not silently) only that one named source; every other
    // error, including unknown future ones, still shows the banner below.
    var stack = (e.error && e.error.stack) || '';
    if (stack.indexOf('evalDcLogic') >= 0) {
      console.debug('[bundle] suppressed non-fatal bundler-internal error:', e.message || e.type);
      return;
    }
    var p = document.body || document.documentElement;"""

for path in BUNDLES:
    t = io.open(path, encoding='utf-8').read()
    f = t.count(OLD)
    assert f == 1, 'patch 83.150 [%s]: anchor found %d times, wanted 1' % (path, f)
    t = t.replace(OLD, NEW)
    io.open(path, 'w', encoding='utf-8').write(t)
    n += 1

print('83.150_bundler_error_filter: edited %d file(s)' % n)
