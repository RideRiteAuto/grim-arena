#!/usr/bin/env python3
"""Ship a build of Grim World, and tell everyone who is playing.

    python3 ship.py "what changed, in plain language"
    python3 ship.py --dry "..."     stamp and pack, do not commit or push
    python3 ship.py --no-wait "..." push without waiting for the deploy

What it does, in order:

  1. Refuses to run on a dirty index.html/bundle you edited by hand, and
     refuses if PATCH-NOTES.md has no entry newer than the last commit.
  2. Stamps a build id into the game source AND version.json. Those two
     matching is the whole update mechanism: a running client polls
     version.json every 60s and compares it to the build it booted with.
  3. Packs both bundles through repack.py (which verifies the round trip).
  4. Commits, rebases onto origin, pushes.
  5. Waits until GitHub Pages is actually serving the new build id, and until
     the Cloudflare worker reports healthy, then prints what players will see.

Every client that is mid-game picks up the new version.json within a minute,
shows GAME UPDATE READY with a 30 second countdown, holds while its player is
in combat, saves, and logs out to the front door. Nobody has to be told.
"""
import io, json, os, re, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = '/tmp/game-src.html'
VERSION = os.path.join(ROOT, 'version.json')
STAMP_RE = re.compile(r"var GRIM_BUILD = '[^']*';")
PAGES = 'https://rideriteauto.github.io/grim-arena/'
HEALTH = 'https://grim-arena.kevin-230.workers.dev/health'
MESSAGE = ['']


def run(*a, **kw):
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True, **kw)


def die(msg):
    print('\n  STOP: ' + msg + '\n')
    sys.exit(1)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def embedded(ref):
    """The game source out of a bundle at some git ref."""
    blob = run('git', 'show', ref + ':index.html').stdout
    for ln in blob.split('\n'):
        s = ln.strip()
        if s.startswith('"<!DOCTYPE') or s.startswith('"\\u003c!DOCTYPE'):
            return json.loads(s.rstrip().rstrip(';,'))
    die('could not find the embedded document in ' + ref + ':index.html')


def three_way(mine, base, theirs, label):
    """git merge-file on three strings. Returns merged text or None on conflict."""
    for nm, txt in (('m', mine), ('b', base), ('t', theirs)):
        io.open('/tmp/_mg_' + nm, 'w', encoding='utf-8').write(txt)
    r = run('git', 'merge-file', '-L', 'ours', '-L', 'base', '-L', 'theirs',
            '/tmp/_mg_m', '/tmp/_mg_b', '/tmp/_mg_t')
    out = io.open('/tmp/_mg_m', encoding='utf-8').read()
    if r.returncode != 0 and '<<<<<<<' in out:
        print('    conflict in ' + label)
        return None
    return out


def keep_both(text):
    """Resolve conflict hunks by keeping ours then theirs, in that order.

    Only ever used on PATCH-NOTES.md. A changelog where both sides added an
    entry at the top is not a real conflict: the answer is always both entries,
    newest first. Anywhere else a conflict means two people changed the same
    thing and a human has to look."""
    out, i, lines = [], 0, text.split('\n')
    while i < len(lines):
        if lines[i].startswith('<<<<<<<'):
            i += 1
            ours = []
            while i < len(lines) and not lines[i].startswith('======='):
                ours.append(lines[i]); i += 1
            i += 1
            theirs = []
            while i < len(lines) and not lines[i].startswith('>>>>>>>'):
                theirs.append(lines[i]); i += 1
            i += 1
            out.extend(ours)
            if ours and theirs and ours[-1].strip():
                out.append('')
            out.extend(theirs)
        else:
            out.append(lines[i]); i += 1
    return '\n'.join(out)


def rebase_onto_origin():
    """Rebase, merging the bundle by its EMBEDDED SOURCE rather than as text.

    index.html is one enormous line, so git can only ever see it as a total
    rewrite. Merging the document inside it is the only thing that actually
    works when two people ship on the same day."""
    r = run('git', 'rebase', 'origin/master')
    if r.returncode == 0:
        return
    run('git', 'rebase', '--abort')
    print('  collision     someone else pushed; merging the bundle by its source')

    base = run('git', 'merge-base', 'HEAD', 'origin/master').stdout.strip()
    merged_src = three_way(embedded('HEAD'), embedded(base), embedded('origin/master'), 'game source')
    if merged_src is None:
        die('the two builds changed the same lines of the game source. Resolve by hand.')

    changed = set()
    for rng in (base + '..HEAD', base + '..origin/master'):
        for f in run('git', 'diff', '--name-only', rng).stdout.split():
            if f not in ('index.html', 'grim-arena-standalone.html'):
                changed.add(f)

    keep = {}
    for f in sorted(changed):
        def at(ref):
            rr = run('git', 'show', ref + ':' + f)
            return rr.stdout if rr.returncode == 0 else ''
        m = three_way(at('HEAD'), at(base), at('origin/master'), f)
        if m is None:
            if f == 'PATCH-NOTES.md':
                m = keep_both(io.open('/tmp/_mg_m', encoding='utf-8').read())
                print('    resolved ' + f + ': kept both entries, newest first')
            else:
                die('conflict in ' + f + '. Resolve by hand, then run ship.py again.')
        keep[f] = m

    run('git', 'reset', '--hard', 'origin/master')
    for f, txt in keep.items():
        d = os.path.dirname(os.path.join(ROOT, f))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        io.open(os.path.join(ROOT, f), 'w', encoding='utf-8').write(txt)
    io.open(SRC, 'w', encoding='utf-8').write(merged_src)
    r = run('python3', 'repack.py', 'pack')
    if r.returncode != 0:
        die('repack after merge failed:\n' + r.stdout + r.stderr)
    print('  merged        %d file(s) + the bundle, repacked' % len(keep))
    run('git', 'add', '-A')
    r = run('git', 'commit', '-m', MESSAGE[0])
    if r.returncode != 0 and 'nothing to commit' not in (r.stdout + r.stderr):
        die('commit after merge failed:\n' + r.stdout + r.stderr)


def main():
    args = [a for a in sys.argv[1:]]
    dry = '--dry' in args
    nowait = '--no-wait' in args
    args = [a for a in args if not a.startswith('--')]
    if not args:
        die('give me a commit message: python3 ship.py "what changed"')
    message = args[0]
    MESSAGE[0] = message

    # ---- 1. sanity -------------------------------------------------------
    # The note can be sitting in the working tree OR already committed and
    # waiting to go out. Only the first version of this check looked at the
    # working tree, which meant it fired on anyone who had already committed.
    st = run('git', 'status', '--porcelain').stdout
    ahead = run('git', 'diff', '--name-only', 'origin/master...HEAD').stdout
    if 'PATCH-NOTES.md' not in st and 'PATCH-NOTES.md' not in ahead and not dry:
        die('PATCH-NOTES.md has no new entry, in the working tree or in anything '
            'waiting to be pushed. Every push gets one, in plain language, '
            'newest on top. That is the rule that lets Kevin refresh and see '
            'what is done.')

    # ---- 2. stamp --------------------------------------------------------
    build = time.strftime('%Y%m%d-%H%M%S', time.gmtime())
    print('  build id      ' + build)

    run('python3', 'repack.py', 'extract')
    src = io.open(SRC, encoding='utf-8').read()
    if not STAMP_RE.search(src):
        die("the build stamp line is missing from the game source. Expected "
            "exactly: var GRIM_BUILD = '...';")
    src = STAMP_RE.sub("var GRIM_BUILD = '%s';" % build, src, count=1)
    io.open(SRC, 'w', encoding='utf-8').write(src)
    io.open(VERSION, 'w', encoding='utf-8').write(
        json.dumps({'build': build, 'note': message}, indent=1) + '\n')
    print('  stamped       game source + version.json')

    # ---- 3. pack ---------------------------------------------------------
    r = run('python3', 'repack.py', 'pack')
    if r.returncode != 0:
        die('repack failed:\n' + r.stdout + r.stderr)
    print('  packed        both bundles, round trip verified')

    # syntax-check the thing we are about to ship to real people
    blk = max(re.findall(r'<script[^>]*>(.*?)</script>',
                         io.open(SRC, encoding='utf-8').read(), re.S), key=len)
    io.open('/tmp/_ship_check.mjs', 'w', encoding='utf-8').write(blk)
    r = run('node', '--check', '/tmp/_ship_check.mjs')
    if r.returncode != 0:
        die('the packed game does not parse:\n' + r.stderr[:1500])
    for f in ('relay-worker.js', 'sim.js'):
        r = run('node', '--check', f)
        if r.returncode != 0:
            die(f + ' does not parse:\n' + r.stderr[:800])
    print('  checked       game, relay and sim all parse')

    if dry:
        print('\n  --dry: stopping before commit. Nothing was pushed.\n')
        return

    # ---- 4. push ---------------------------------------------------------
    run('git', 'add', '-A')
    r = run('git', 'commit', '-m', message)
    if r.returncode != 0 and 'nothing to commit' not in (r.stdout + r.stderr):
        die('commit failed:\n' + r.stdout + r.stderr)
    print('  committed     ' + message.splitlines()[0][:60])

    tok = os.environ.get('GITHUB_TOKEN', '')
    auth = []
    if tok:
        import base64
        b = base64.b64encode(('x-access-token:' + tok).encode()).decode()
        auth = ['-c', 'http.extraheader=AUTHORIZATION: basic ' + b]
    run('git', *auth, 'fetch', 'origin')
    rebase_onto_origin()
    r = run('git', *auth, 'push', 'origin', 'master')
    if r.returncode != 0:
        die('push failed:\n' + (r.stdout + r.stderr).replace(tok, '[redacted]' if tok else ''))
    print('  pushed        origin/master')

    if nowait:
        print('\n  --no-wait: not waiting for the deploy.\n')
        return

    # ---- 5. wait for it to actually be live ------------------------------
    print('  waiting       GitHub Pages (usually under 2 minutes)')
    live = False
    for _ in range(40):
        time.sleep(10)
        try:
            v = json.loads(get(PAGES + 'version.json?t=%d' % time.time()))
            if v.get('build') == build:
                live = True
                break
        except Exception:
            pass
        print('.', end='', flush=True)
    print()
    if not live:
        die('Pages never started serving build %s. The push went through, so '
            'check the Actions tab; players will pick it up whenever it lands.' % build)
    print('  live          Pages is serving ' + build)

    try:
        h = json.loads(get(HEALTH))
        print('  relay         proto %s, %s player(s), %s monsters, simErr=%s'
              % (h.get('proto'), h.get('players'), h.get('simNpcs'), h.get('simErr')))
        if h.get('players'):
            print('\n  %d player(s) online. Within a minute each of them sees'
                  '\n  GAME UPDATE READY, a 30 second countdown that waits out'
                  '\n  any fight they are in, then saves and drops them at the'
                  '\n  front door with their name already filled in.' % h['players'])
        else:
            print('\n  Nobody online. Next person to load gets the new build.')
    except Exception as e:
        print('  relay         could not read health: %s' % e)
    print()


if __name__ == '__main__':
    main()
