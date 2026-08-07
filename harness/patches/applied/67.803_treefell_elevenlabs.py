# Patch 67.803: replace the tree-fall sound with a real ElevenLabs generation,
# which is what Kevin actually asked for (patch 67.512 was the interim DSP-EQ
# fix shipped while no API key was available; a key arrived after that patch
# shipped, so this supersedes it with the real thing).
#
# METHOD, per the ready-to-run spec written into ART-TRACK-STATUS.md while
# waiting for a key: python3 harness/sfx.py already had a well-considered
# 'tree-fell' prompt and 3 takes (influence 0.35/0.55/0.75). All 3 came back
# almost bass-free (sub200 0.007-0.022, badly under the >=0.15 floor) even
# though top4k and tonality were fine - the model just does not add low end
# unless the prompt names it, the same lesson "thick blade" already taught on
# combat-swing-heavy. Two more rounds followed, naming the bass explicitly and
# then explicitly ordering the ground impact as the loudest moment (real
# references all peak late, 0.73-0.79 into the clip, and the original shipped
# sample's defect was peaking at 0.03 - the opposite failure):
#
#   round 1 (original prompt):      sub200 0.007-0.022  top4k 0.20-0.24  peak_pos 0.01-0.52
#   round 2 (+explicit bass):       sub200 0.36-0.93     top4k 0.02-0.24  peak_pos 0.00-0.52
#   round 3 (+explicit late peak):  sub200 0.57-0.69     top4k 0.04-0.10  peak_pos 0.24-0.48
#
# 11 takes total, 550 credits of a 30,000/month allowance. Winner:
# tree-fell-v3-p055 (prompt_influence 0.55, round 3's "ending impact far
# louder than the opening crack" prompt): sub200=0.638, top4k=0.089,
# centroid=1054Hz, peak_pos=0.48, crest=20.0dB. Clears the established floor
# (sub200>=0.15, top4k<=0.28) comfortably and lands inside or very close to
# the real WoW Foley reference on top4k (ref 0.06-0.10) and centroid (ref
# 815-1414Hz) specifically; sub200 runs higher than the ~0.28-0.49 reference
# band but that overshoots toward MORE bass, the safe direction, not the thin/
# bright direction that made the original sample and v1 timber fail. Re-encoded
# 44100Hz mono 80k (matching the bundle's other samples) after selection, not
# before, so the take was judged on what actually ships.
#
# Fall animation is 5.4s total (this.fx life:5.4); 'treefell' fires at t=0,
# 'treeimpact' fires separately at t=3.0 as its own dedicated ground-thud cue
# (untouched, already passing the floor). This take's own internal crash sits
# at t=2.4 (peak_pos 0.48 * 5.0s), close enough to the 3.0s impact cue that the
# two blend into one crash rather than reading as two disconnected hits - a
# real felling crash is exactly this kind of stacked-impulse layering.
#
# One anchored edit, same structural-regex method as 67.512 (this file's key
# indentation is not uniform across entries written by different patches).
import io, os, re

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

import base64
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
print('patch 67.803 applied: tree-fell replaced with real ElevenLabs generation '
      '(%d -> %d bytes of base64 source)' % (len(old_block), len(new_bundle_block)))
