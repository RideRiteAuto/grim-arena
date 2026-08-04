#!/usr/bin/env python3
"""Phase 1, part 5: XP splats in skill colour.

The plan asks for the gather splat to read in the skill's own colour, wood
green, ore orange, forage teal, so a glance tells you which skill just moved
without reading the words. Combat XP keeps the existing gold.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# splat() takes a kind, so the three gathering skills get their own kinds
# rather than a colour argument threaded through every call site.
sub(
    "      xp:    { bg: 'none', fg: '#e8c774', s: 0, f: 13 },",
    "      xp:    { bg: 'none', fg: '#e8c774', s: 0, f: 13 },\n"
    "      // Gathering XP reads in its skill's colour so a glance tells you which\n"
    "      // skill moved. Wood green, ore orange, forage teal.\n"
    "      xpwood:  { bg: 'none', fg: '#8fc46a', s: 0, f: 13 },\n"
    "      xpore:   { bg: 'none', fg: '#e0932e', s: 0, f: 13 },\n"
    "      xpforage:{ bg: 'none', fg: '#4fd0b8', s: 0, f: 13 },",
    'splat palette')

# Every place that treats a splat as XP has to treat the three new kinds the
# same way, or they would go through the hitsplat stacker and land in the wrong
# spot with a coloured box behind them.
sub(
    "    const slot = kind === 'xp' ? { x: sx, y: sy } : this.splatSlot(sx, sy);",
    "    const isXp = kind === 'xp' || kind.indexOf('xp') === 0;\n"
    "    const slot = isXp ? { x: sx, y: sy } : this.splatSlot(sx, sy);",
    'splat slot')

sub(
    "    if (kind === 'xp') {\n"
    "      // XP toasts are plain floating text, not hitsplats: they sit above the\n"
    "      // head and drift straight up, fading out. Several skills gained at once\n"
    "      // stack downward so each line stays readable.",
    "    if (isXp) {\n"
    "      // XP toasts are plain floating text, not hitsplats: they sit above the\n"
    "      // head and drift straight up, fading out. Several skills gained at once\n"
    "      // stack downward so each line stays readable.",
    'splat xp branch')

sub(
    "      if (n > 0) this.splat(at, '+' + n + ' ' + this.skillLabel(k) + ' XP', 'xp');",
    "      if (n > 0) this.splat(at, '+' + n + ' ' + this.skillLabel(k) + ' XP', this.xpSplatKind(k));",
    'toast kind')

sub(
    "  flushXpToasts(force) {",
    "  // Which splat colour a skill's XP uses.\n"
    "  xpSplatKind(skill) {\n"
    "    return skill === 'WOODCUTTING' ? 'xpwood'\n"
    "         : skill === 'MINING' ? 'xpore'\n"
    "         : skill === 'FORAGING' ? 'xpforage' : 'xp';\n"
    "  }\n"
    "\n"
    "  flushXpToasts(force) {",
    'xpSplatKind')

out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
