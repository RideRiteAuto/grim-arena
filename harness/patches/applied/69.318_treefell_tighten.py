# Patch 69.318: tighten the tree-fell sound - boom right after the crackle,
# no dead air.
#
# Kevin's follow-up on 69.204's reorder: the order is right now (crack first,
# boom last), but there was a ~1.8s stretch of near-total silence between the
# crackle tail (~2.2s in) and the boom (~4.3s in) - the boom segment's own
# original position in the ElevenLabs take included a long quiet lead-in that
# made sense at the END of a 5s clip but reads as a dead gap once relocated
# earlier. Asked for exactly two things: move the boom right after the
# crackle finishes (~2s mark), and cut the dead air so there's no unfilled
# silence in the clip at all.
#
# Verified against the waveform before cutting anything: 50ms-windowed
# envelope of patch 69.204's shipped clip showed real crackle content through
# ~1.7s (including one last distinct pop) decaying to near-nothing by ~2.2s,
# then genuine near-silence (peak < 0.03) all the way to ~4.0s where the
# boom's own ramp-up begins. Cut at [0:2.20] (the crackle plus its natural
# decay tail, with a 20ms fadeout so the cut at low amplitude doesn't click)
# concatenated directly with [4.00:end] (the boom's ramp-in through its full
# tail, 20ms fade-in for the same reason) - the ~1.8s dead middle is GONE,
# not just shortened. Net: 5.04s -> 3.24s, boom peak now lands at ~2.4-2.5s
# in the new clip, roughly 0.2-0.3s after the crackle tail dies out - a
# natural short beat before impact, not a gap.
#
# No change to timing elsewhere: 'treeimpact' (the separate ground-thud cue)
# still fires at t=3.0s in the fall animation, untouched, and now lands about
# half a second after tree-fell's own crash finishes rather than overlapping
# it - still reads as one event, just no longer synchronized on top of each
# other, which is a fine outcome neither previous patch aimed for or against.
#
# Same structural-regex, key-count-asserted, mp3-signature-checked method as
# every prior tree-fell patch. 50 keys before and after on the module side
# (this file now also carries the footstep entries from patch 68.001).
import io, os, re, base64

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

VALUE_RE = r"'tree-fell':\s*((?:\s*(?:'[^']*'|\+)\s*)+),"

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

mm = re.search(VALUE_RE, mod)
assert mm, "'tree-fell' value not found in model-lab/sfx-samples.js"
b64 = ''.join(re.findall(r"'([^']*)'", mm.group(1)))
assert len(b64) > 5000, 'suspiciously little base64 pulled (%d chars)' % len(b64)

raw = base64.b64decode(b64)
assert raw[:3] == b'ID3' or raw[:2] == b'\xff\xfb', 'decoded tree-fell does not look like an mp3'

CHUNK = 100
chunks = [b64[i:i + CHUNK] for i in range(0, len(b64), CHUNK)]
lines = ["    'tree-fell':", "        '%s'" % chunks[0]]
lines += ["      + '%s'" % c for c in chunks[1:]]
lines[-1] += ','
new_bundle_block = '\n'.join(lines)

sm = re.search(VALUE_RE, s)
assert sm, "'tree-fell' value not found in the bundle"
line_start = s.rfind('\n', 0, sm.start()) + 1
old_block = s[line_start:sm.end()]

assert s.count(old_block) == 1, 'old tree-fell block is not unique in the bundle'
before_count = s.count("'tree-fell':")
s = s.replace(old_block, new_bundle_block, 1)
after_count = s.count("'tree-fell':")
assert before_count == after_count == 1, 'tree-fell key count changed (%d -> %d)' % (before_count, after_count)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 69.318 applied: tree-fell tightened, dead air removed '
      '(%d -> %d bytes of base64 source)' % (len(old_block), len(new_bundle_block)))
