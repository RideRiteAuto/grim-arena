# Patch 69.204: reorder the tree-fell sound - crack/creak first, boom last.
#
# Kevin's ear-check on 67.803's ElevenLabs generation: the first second of the
# clip IS a proper ground-impact boom, but it's the FIRST thing you hear, and
# the crackling/creaking that should lead into the fall only starts at the
# one-second mark. Order is backwards - a tree cracks and creaks before it
# falls, not after.
#
# Verified against the actual waveform, not just by ear: 100ms-windowed
# amplitude envelope of the shipped clip showed a loud low-rms burst at
# 0.2-0.6s (peak 0.79-0.86, the boom Kevin describes) then a quieter crackly
# texture from 0.6-2.0s building to an even bigger crescendo at 2.2-2.6s
# (peak 1.0+), then a long decay to near silence by ~3.6s. Matches his
# description exactly: cut at the 1.0s mark he named, move [0,1.0) to the
# end, keep everything from 1.0s onward in front.
#
# New order: old[1.0:end] + old[0:1.0], with a 20ms edge fade at the new
# file's absolute start and end only - both are artificial cuts made at the
# same t=1.0s point in the original (moderate signal there, not silence), so
# a bare concat risked an audible click; the internal seam (old end meeting
# old start) needs no fade since both sides are already the clip's natural,
# near-silent boundaries.
#
# Also recovers a clobber: a later, unrelated patch (68.001, footstep sfx)
# rewrote model-lab/sfx-samples.js from a copy taken before 67.803 landed,
# silently reverting tree-fell back to 67.512's older EQ'd sample (38967
# bytes, 3.9s) while correctly keeping its own 12 new footstep entries. This
# patch's module-side edit (already applied directly to model-lab/
# sfx-samples.js in the companion commit) restores the real ElevenLabs
# generation, reordered, without touching any footstep entry - confirmed 50
# keys before and after on the module side. Bundle-side edit here is scoped
# to 'tree-fell' alone, same structural-regex method as every prior tree-fell
# patch.
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
assert len(b64) > 10000, 'suspiciously little base64 pulled (%d chars)' % len(b64)

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
print('patch 69.204 applied: tree-fell reordered (crack/creak first, boom last), '
      'clobber from 68.001 recovered (%d -> %d bytes of base64 source)' % (len(old_block), len(new_bundle_block)))
