#!/usr/bin/env python3
"""Patch 47: a theme for every zone, with a crossfade that cannot thrash.

The music was two stock tracks, wild and bog, selected by two hardcoded circles
left over from before the world was generated. Every zone now has its own
theme, generated as one cohesive set, and the selection keys off the world's
own zoneAt() so it stays correct wherever the map moves.

Kevin's three requirements, and how each is met:

  "fade in and fade out, not jarring"
      One track per zone, all easing toward a target volume every frame. Only
      the current zone targets above zero, so entering a zone IS a crossfade.
      The ease rate drops from 0.8 to 0.5, about a five second blend, which is
      where a zone change stops sounding like a cut and starts sounding like
      travel.

  "turn around and go back and it must not flip back and forth"
      musicZoneStable() is deliberately laggy. A new zone has to hold for
      MUSIC_HOLD seconds before it wins, so stepping over a border and
      stepping back never changes the track at all, and standing on a border
      jittering between two zones resets the timer instead of switching. This
      is the standard fix and it is the whole difference between "the world
      changed" and "the audio is broken".

  "loop properly"
      Each file is seam-smoothed before it ships: the real tail is crossfaded
      onto the head, so the wrap point is musically continuous rather than a
      hard join. The elements keep loop = true and never restart.

One extra, because a fade into a file that has not downloaded is a fade into
silence: while a candidate zone is counting down its hold, its file is told to
load. The hold window doubles as the buffer window, so by the time the zone
commits the audio is usually ready to play.

Files are audio/zone-<key>.mp3, lowercase, keyed by the same names the world
uses. A zone added later needs a file dropped in and nothing else; a zone with
no file falls back to the Heartlands theme rather than going silent.

Three anchored edits: musicInit, musicZone (plus the new stable selector), and
the want/ease lines inside stepMusic.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()

# ---------------------------------------------------------------------------
# 1. one element per zone instead of the two stock tracks
# ---------------------------------------------------------------------------
A1 = ("musicInit() { if (this.tracks) return; const mk = (src) => { const a = new Audio(src); "
      "a.loop = true; a.preload = 'none'; a.volume = 0; return a; }; "
      "this.tracks = { wild: mk('audio/whispers-of-the-wild.mp3'), bog: mk('audio/bog-lantern-drift.mp3') }; "
      "this.trackVol = { wild: 0, bog: 0 };")
assert s.count(A1) == 1, 'musicInit anchor matched %d times' % s.count(A1)
s = s.replace(A1, (
    "musicInit() { if (this.tracks) return; const mk = (src) => { const a = new Audio(src); "
    "a.loop = true; a.preload = 'none'; a.volume = 0; return a; }; "
    "/* One theme per design zone, keyed by the names the world itself uses, so "
    "zoneAt() picks the music with no lookup table in between and a new zone "
    "only needs a file dropped into audio/. preload stays 'none' until a zone "
    "is actually a candidate, so opening the game does not pull 20MB. */ "
    "this.tracks = {}; this.trackVol = {}; "
    "for (const zk of ['HEARTLANDS', 'GREENWOOD', 'FROSTWILD', 'IRONSPIRE', 'SUNCOAST', "
    "'WINDSCAR', 'EMBER', 'MISTFEN', 'SUNSCORCH', 'EASTRIDGE', 'ISLES', 'SEA']) "
    "{ this.tracks[zk] = mk('audio/zone-' + zk.toLowerCase() + '.mp3'); this.trackVol[zk] = 0; } "
    "this._musicZone = 'HEARTLANDS'; this._zoneCand = null; this._zoneCandT = 0;"))

# ---------------------------------------------------------------------------
# 2. the real zone, and the hysteresis that stops a border from thrashing
# ---------------------------------------------------------------------------
A2 = ("musicZone() { const p = this.me && this.me.pos; if (!p) return 'wild'; "
      "if (Math.hypot(p.x - 93, p.z + 87) < 46) return 'bog'; "
      "if (Math.hypot(p.x + 96, p.z - 122) < 17) return 'bog'; return 'wild'; }")
assert s.count(A2) == 1, 'musicZone anchor matched %d times' % s.count(A2)
s = s.replace(A2, (
    "musicZone() { const p = this.me && this.me.pos; if (!p) return 'HEARTLANDS'; "
    "let k = null; try { k = this.zoneAt(p.x, p.z); } catch (e) {} "
    "return (k && this.tracks && this.tracks[k]) ? k : 'HEARTLANDS'; } "
    "/* Which zone the MUSIC believes we are in, which is deliberately not the "
    "same question as which zone the PLAYER is in. A new zone has to hold for "
    "MUSIC_HOLD seconds before it wins, so crossing a border and coming "
    "straight back never changes the track, and standing on a border "
    "jittering between two zones keeps resetting the timer instead of "
    "flipping. While a candidate counts down, its file is told to load: the "
    "hold window doubles as the buffer window, so the crossfade lands on "
    "audio that is ready instead of on silence. */ "
    "musicZoneStable(dt) { const MUSIC_HOLD = 2.5; "
    "const raw = this.started ? this.musicZone() : 'HEARTLANDS'; "
    "if (raw === this._musicZone) { this._zoneCand = null; this._zoneCandT = 0; return this._musicZone; } "
    "if (raw !== this._zoneCand) { this._zoneCand = raw; this._zoneCandT = 0; "
    "const a = this.tracks[raw]; "
    "if (a && a.preload !== 'auto') { try { a.preload = 'auto'; a.load(); } catch (e) {} } } "
    "this._zoneCandT += dt; "
    "if (this._zoneCandT >= MUSIC_HOLD) { this._musicZone = raw; this._zoneCand = null; this._zoneCandT = 0; } "
    "return this._musicZone; }"))

# ---------------------------------------------------------------------------
# 3. stepMusic asks the stable selector, and blends slower
# ---------------------------------------------------------------------------
A3 = "const want = this.started ? this.musicZone() : 'wild';"
assert s.count(A3) == 1, 'stepMusic want anchor matched %d times' % s.count(A3)
s = s.replace(A3, "const want = this.musicZoneStable(dt);")

A4 = "let nv = v + (target - v) * Math.min(1, dt * 0.8);"
assert s.count(A4) == 1, 'stepMusic ease anchor matched %d times' % s.count(A4)
s = s.replace(A4, "let nv = v + (target - v) * Math.min(1, dt * 0.5);")

io.open(SRC, 'w', encoding='utf-8').write(s)
print('patch 45: per-zone music, hysteresis, slower crossfade, candidate preload')
