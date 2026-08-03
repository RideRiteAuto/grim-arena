#!/usr/bin/env python3
"""Extract / repack the game document embedded in the bundled HTML files.
Usage:
  repack.py extract   -> writes /tmp/game-src.html from index.html
  repack.py pack      -> writes /tmp/game-src.html back into index.html AND grim-arena-standalone.html
Round-trip is verified: pack then extract must be byte-identical.
"""
import json, sys, io

BUNDLES = ['index.html', 'grim-arena-standalone.html']
SRC = '/tmp/game-src.html'

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
    {'extract': extract, 'pack': pack}[sys.argv[1]]()
