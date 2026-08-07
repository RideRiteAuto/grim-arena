# Patch 67.512: fix the "absolutely terrible" tree-fall sound.
#
# Kevin's ask was to replace this via ElevenLabs against a named MMO
# reference (Dragonwilds primary, WoW fallback). No ELEVENLABS_API_KEY is
# available in this environment to do that generation, so this patch does
# the diagnosis-and-fix that IS possible without one: measuring what is
# actually shipping today against real reference audio, and correcting it.
#
# WHAT'S ACTUALLY PLAYING. The routing looked suspicious at first (the game
# calls sfx('treefell') with no hyphen, the sample is keyed 'tree-fell' with
# one) but Game.sfxVoice_'s NAT table maps them correctly - not a routing
# bug. 'treefell' fires once at the start of the fall (the crack/creak/
# whoosh); 'treeimpact' fires SEPARATELY at t=3.0s in the fall animation
# (the ground hit), for every kind except the starter 'tree'. Both samples
# were extracted from the shipped bundle and measured (peak/rms/crest,
# spectral centroid, sub-200Hz share, 4kHz+ share, peak position - the same
# metrics the sound track's SOUND-TRACK-HANDOFF.md used to fix 'timber'
# through v1/v2/v3):
#
#   shipped tree-fell:    sub200=0.134  top4k=0.404  centroid=3603Hz  peak@3%
#   shipped tree-impact:  sub200=0.386  top4k=0.027  centroid=658Hz   peak@82%
#   established floor (from the timber v1/v2 postmortem): sub200 >= 0.15,
#   top4k <= 0.28
#
# tree-impact passes comfortably. tree-fell FAILS both floors, by a wide
# margin, in the exact same "thin, bright, no bass" shape that made timber
# v1 read as "electronic" and v2 as "a banshee squeal" before those were
# fixed. Its loudest moment also sits 3% into the clip (front-loaded) while
# every real reference pulled for comparison peaks late (0.6-0.8) - a tree
# should build TO the crash, not open with it and fade.
#
# REAL REFERENCE AUDIO. Per Kevin's own fallback instruction ("if you can't
# find those sounds, we'll use World of Warcraft as a fallback"), Dragonwilds
# has no accessible sound-effects index (its wiki's audio category is
# organized by creature/context name across 1833 files with no tree/chop
# section, and Woodcutting-related pages embed no audio); Wowhead's public
# sound database does, including several literal tree-felling assets pulled
# and measured for this patch (ids only - the files themselves are Blizzard's
# and are not committed, same policy the WoW spell-sound work already
# follows):
#   sound=41510  FX_TreeFall01/02.ogg      (WoD Frostfire Ridge felling quest)
#     sub200 0.41-0.47, top4k 0.12-0.20, centroid 1400-1950Hz, peak@0.73-0.79
#   sound=272468 11.0_Foley_..._Movement_Impact_Large_Slow_Long_01 (current-
#     patch foley, the creak/topple motion)
#     sub200 0.28-0.49, top4k 0.06-0.10, centroid 815-1414Hz
#   sound=282419 11.0_Foley_Wood_Tree_Impact_Large_01 (current-patch foley,
#     the isolated ground thud)
#     sub200 0.87-0.91, top4k <=0.01, centroid 160-230Hz, peak@~0.02 (i.e. a
#     hit is a hit right away - matches the shape our own tree-impact sample
#     already has)
#
# THE FIX. Re-EQ the shipped tree-fell clip toward that reference profile
# rather than regenerate blind: a low shelf boost around 140Hz and a high
# shelf cut above 3.5kHz (ffmpeg bass=g=10:f=140:w=0.7,treble=g=-14:f=3500:
# w=0.7, limited to avoid clipping). This is exactly the "build it, don't
# pick it" method timber v3 used. Timing is untouched on purpose - the crack
# still lands at t=0 and the animation's separate ground-impact cue still
# fires at t=3.0 via 'treeimpact', so nothing about the fall fx desyncs.
# Result: sub200 0.41, top4k 0.05, centroid 1300Hz - now inside the
# reference band on every measured axis. Spectrograms compared before/after
# (see ART-TRACK-STATUS.md) show the crack and the branch-whoosh section
# both preserved, just re-balanced away from the harsh top end.
#
# THIS IS NOT THE ELEVENLABS REPLACEMENT KEVIN ASKED FOR - it is the largest
# improvement possible without API credentials, done honestly rather than
# skipped or faked. See ART-TRACK-STATUS.md for the full writeup and the
# ready-to-run generation spec for whenever a key is available.
#
# One anchored edit: the 'tree-fell' sample's base64, pulled fresh from
# model-lab/sfx-samples.js (already corrected there) and rebuilt as a fresh
# chunk list rather than reindented text, because this file's key indentation
# is NOT uniform across entries written by different patches over time (a
# naive "next 2-space-indented key" boundary search silently swallowed
# several unrelated keys on the first attempt at this patch - fixed by
# bounding the value with a structural regex on BOTH sides instead of
# guessing at whitespace).
import io, os, re

SRC = '/tmp/game-src.html'
HERE = os.path.dirname(__file__)
MODULE = os.path.join(HERE, '..', '..', 'model-lab', 'sfx-samples.js')

VALUE_RE = r"'tree-fell':\s*((?:\s*(?:'[^']*'|\+)\s*)+),"

s = io.open(SRC, encoding='utf-8').read()
mod = io.open(MODULE, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# pull the corrected base64 out of the lab module, structurally (not by
# assuming any particular indentation on the surrounding keys)
# ---------------------------------------------------------------------------
mm = re.search(VALUE_RE, mod)
assert mm, "'tree-fell' value not found in model-lab/sfx-samples.js"
b64 = ''.join(re.findall(r"'([^']*)'", mm.group(1)))
assert len(b64) > 10000, 'suspiciously little base64 pulled (%d chars)' % len(b64)

# sanity: it has to actually decode to something MP3-shaped
import base64
raw = base64.b64decode(b64)
assert raw[:3] == b'ID3' or raw[:2] == b'\xff\xfb', 'decoded tree-fell does not look like an mp3'

# ---------------------------------------------------------------------------
# rebuild the bundle-style block from scratch: 4-space key indent, 8-space
# first chunk, 6-space continuation chunks - matches every other entry in
# the bundle's SFX_SAMPLES object (checked against 'tree-impact' and
# 'timber', both original patch-56-era entries).
# ---------------------------------------------------------------------------
CHUNK = 100
chunks = [b64[i:i + CHUNK] for i in range(0, len(b64), CHUNK)]
lines = ["    'tree-fell':", "        '%s'" % chunks[0]]
lines += ["      + '%s'" % c for c in chunks[1:]]
lines[-1] += ','
new_bundle_block = '\n'.join(lines)

# ---------------------------------------------------------------------------
# find and replace the existing 'tree-fell' value in the bundle, bounded the
# same structural way
# ---------------------------------------------------------------------------
sm = re.search(VALUE_RE, s)
assert sm, "'tree-fell' value not found in the bundle"
old_full = sm.group(0)  # "'tree-fell': ...chunks..., " including the trailing comma
# widen to the whole line(s): back up to the start of the key's own line
line_start = s.rfind('\n', 0, sm.start()) + 1
old_block = s[line_start:sm.end()]

assert s.count(old_block) == 1, 'old tree-fell block is not unique in the bundle'
before_count = s.count("'tree-fell':")
s = s.replace(old_block, new_bundle_block, 1)
after_count = s.count("'tree-fell':")
assert before_count == after_count == 1, 'tree-fell key count changed (%d -> %d)' % (before_count, after_count)

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 67.512 applied: tree-fell re-EQ\'d toward the WoW reference band '
      '(%d -> %d bytes of base64 source)' % (len(old_block), len(new_bundle_block)))
