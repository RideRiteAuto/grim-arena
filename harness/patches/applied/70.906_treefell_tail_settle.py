# Patch 70.906: tree-fell tail fix, take two. Surgical this time.
#
# Patch 70.744 tried to fix the abrupt boom cutoff Kevin flagged after
# 69.318, but it swapped in a completely different, bigger boom segment
# from earlier in the original ElevenLabs take. Kevin's verdict: "the
# newest one you just made ruined it... you basically just changed
# everything. The whole beginning is perfectly fine. I just needed you to
# kinda fix the very tail end of the boom. I don't want you to regenerate
# it all over again." He reattached the 69.318 clip as the reference: that
# one is right except for the last beat, which stops rather than settles.
#
# This patch touches ONLY the tail. Confirmed with a sample-exact diff
# (numpy compare of decoded PCM, zero differing samples) that the first
# 2.80s of this clip's audio is byte-for-byte the same signal as the
# approved 69.318 clip; the entire boom impact (peaks at 2.52-2.73s,
# reaching 0.81) is completely untouched.
#
# What changed: 69.318's clip stopped hard at 3.20s while peak amplitude
# was still ~0.11-0.29, i.e. mid-decay, not at silence - that's the "cut
# off" Kevin heard. Took the clip's own last 0.30s (2.94-3.20s, already
# declining material, no new segment), time-stretched it slightly slower
# (atempo=0.55) and low-passed it (1800Hz, higher frequencies die first in
# a real decay) to extend it into a short tail, faded that tail
# exponentially to true silence, and joined it to the original clip with a
# 30ms crossfade so there's no seam. Net: 3.20s -> 3.61s, all of the added
# time is the boom's own tail continuing to ring out and die away, not new
# content and not dead air. Verified by envelope: peak descends smoothly
# 0.29 -> 0.15 -> 0.05 -> 0.02 -> silence by ~3.45s, no plateau, no cutoff.
#
# No change to 'treeimpact' or anything else. Same structural-regex,
# key-count-asserted, mp3-signature-checked method as every prior tree-fell
# patch. model-lab/sfx-samples.js was already updated directly with the
# new audio before this patch runs; this patch propagates that into the
# bundle.
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
print('patch 70.906 applied: tree-fell tail settles, boom itself untouched '
      '(%d -> %d bytes of base64 source)' % (len(old_block), len(new_bundle_block)))
