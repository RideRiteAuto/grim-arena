# Patch 70.744: tree-fell boom now decays naturally instead of cutting off.
#
# Kevin's follow-up on 69.318 (which fixed the dead-air gap between crackle
# and boom): the crackle-to-boom timing was right, but the boom's ENDING
# sounded cut off rather than settling. Direct quote: "at the very end right
# now, it feels like you're cutting out the last little bit of the boom...
# The boom at the end should kinda settle and taper off... the tree hits the
# ground, makes a lot of boom, and then everything settles."
#
# Root cause, confirmed by re-analyzing both the shipped clip and the
# original untouched ElevenLabs take (elevenlabs-tree-fell.mp3, the raw
# generation from patch 67.803, kept in scratch): the boom segment used by
# 69.318 was the take's first-second burst (0.2-0.6s of the original 5.04s
# generation), hard-bounded at exactly 1.0s because that boundary was where
# Kevin originally said "the first second" during the reorder request
# (patch 69.204). That 1.0s cutoff was never a natural decay point, just an
# arbitrary edit boundary, so every downstream edit inherited an abrupt stop.
#
# The original take actually contains a SECOND, much bigger and more
# boom-like event later in its own timeline: a crescendo peaking at 2.35-2.60s
# (hits full 1.0 normalized peak at 2.35-2.40s) that decays smoothly and
# completely to near-silence by ~3.6s, with one small natural secondary
# settling thump around 3.5s. This was sitting unused in the middle of the
# audio, doing nothing, while the abrupt burst got reused as the ending.
#
# Fix: kept the approved crackle intro exactly as shipped in 69.318 (first
# 2.20s of the live clip, no reprocessing, its existing 20ms fadeout is
# already baked in), then spliced in the ORIGINAL take's real boom-plus-decay
# segment (2.10s-3.75s of elevenlabs-tree-fell.mp3, 15ms fade-in / 60ms
# fade-out) in place of the truncated burst. That segment already tapers to
# near-silence on its own; no synthetic reverb or artificial fade was needed,
# just using the part of the original recording that actually decays.
#
# Net: 3.24s -> 3.85s (the real decay tail needs room to play out; this is
# not dead air, every added moment is audible settling content, confirmed by
# 50ms-windowed envelope: boom peak ~2.25-2.65s, smooth decay 2.7-3.6s with
# the one natural secondary thump at 3.55-3.60s, true near-silence (peak
# < 0.015) from 3.65s to the end).
#
# No change to 'treeimpact' (separate ground-thud cue, still fires at t=3.0s
# in the fall animation) or anything else. Same structural-regex,
# key-count-asserted, mp3-signature-checked method as every prior tree-fell
# patch. model-lab/sfx-samples.js was already updated directly with the new
# audio before this patch runs; this patch propagates that into the bundle.
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
print('patch 70.744 applied: tree-fell boom now decays naturally '
      '(%d -> %d bytes of base64 source)' % (len(old_block), len(new_bundle_block)))
