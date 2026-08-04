#!/usr/bin/env python3
"""Extract / repack the game document embedded in the bundled HTML files.
Usage:
  repack.py extract   -> writes /tmp/game-src.html from index.html
  repack.py pack      -> writes /tmp/game-src.html back into index.html AND grim-arena-standalone.html
Round-trip is verified: pack then extract must be byte-identical.
"""
import json, sys, io, re

BUNDLES = ['index.html', 'grim-arena-standalone.html']
SRC = '/tmp/game-src.html'
RULES = 'shared-rules.js'
BEGIN = '/* SHARED-RULES-BEGIN */'
END = '/* SHARED-RULES-END */'

def inject(text, rules, what):
    """Replace everything between the markers with the shared rules body.

    One source of truth, two outputs. If the markers are missing the caller is
    told loudly rather than silently shipping a stale copy."""
    a = text.find(BEGIN)
    b = text.find(END)
    if a < 0 or b < 0 or b < a:
        raise SystemExit('shared-rules markers missing in ' + what)
    return text[:a] + BEGIN + '\n' + rules.rstrip() + '\n' + text[b:]

def sync_rules():
    rules = io.open(RULES, encoding='utf-8').read()
    # strip the file's own leading banner comment; the markers carry the notice
    rules = re.sub(r'^// =+.*?// =+\n', '', rules, flags=re.S)
    src = io.open(SRC, encoding='utf-8').read()
    out = inject(src, rules, SRC)
    if out != src:
        io.open(SRC, 'w', encoding='utf-8').write(out)
    n = len(rules)
    for f in ['relay-worker.js']:
        t = io.open(f, encoding='utf-8').read()
        o = inject(t, rules, f)
        if o != t:
            io.open(f, 'w', encoding='utf-8').write(o)
    print('shared rules synced (%d bytes) into game source + relay-worker.js' % n)

def find_doc_line(lines):
    # The document payload is the JSON string line starting with "<!DOCTYPE
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith('"<!DOCTYPE') or s.startswith('"\\u003c!DOCTYPE'):
            return i
    raise SystemExit('doc line not found')

def extract():
    lines = io.open(BUNDLES[0], encoding='utf-8').read().split('\n')
    i = find_doc_line(lines)
    doc = json.loads(lines[i].rstrip().rstrip(';,'))
    io.open(SRC, 'w', encoding='utf-8').write(doc)
    print('extracted line %d -> %s (%d bytes)' % (i+1, SRC, len(doc)))

def pack():
    sync_rules()
    doc = io.open(SRC, encoding='utf-8').read()
    payload = json.dumps(doc, ensure_ascii=False).replace('</', '<\\u002F')
    for b in BUNDLES:
        lines = io.open(b, encoding='utf-8').read().split('\n')
        i = find_doc_line(lines)
        # preserve any trailing characters after the JSON string (comma etc.)
        tail = ''
        s = lines[i].rstrip()
        # figure out original tail by re-serializing original
        orig = json.loads(s.rstrip(';,'))
        for t in (';', ','):
            if s.endswith(t): tail = t
        lines[i] = payload + tail
        io.open(b, 'w', encoding='utf-8').write('\n'.join(lines))
        print('packed into %s (line %d, %d -> %d bytes)' % (b, i+1, len(orig), len(doc)))
    # verify round trip
    lines = io.open(BUNDLES[0], encoding='utf-8').read().split('\n')
    i = find_doc_line(lines)
    back = json.loads(lines[i].rstrip().rstrip(';,'))
    assert back == doc, 'ROUND TRIP MISMATCH'
    print('round-trip verified OK')

if __name__ == '__main__':
    {'extract': extract, 'pack': pack, 'rules': sync_rules}[sys.argv[1]]()
