#!/usr/bin/env python3
"""Retire the curve migration for cloud saves instead of running it once more.

Patch 10 gated the migration on the blob version: run it when v < 2. That is
the right shape and the wrong threshold, and it would have cost every player
exactly one more level.

Every cloud save row in the database is v:1, because charSave has always
written v:1. And every one of those rows has ALREADY been migrated, over and
over, because the old applySaveBlob ran the migration on every single login.
That is the bug patch 10 exists to stop. So "v < 2" is true for every existing
row, and the very next login after patch 10 would have deflated everyone one
last time before stamping v:2.

The migration is therefore dead. It has no un-migrated saves left to convert.

The one case this misses is an account that has not logged in since before the
zone update. That save would keep old-curve XP read on the new curve, which
reads HIGH, not low. Erring upward for a returning stranger is the right side
to be wrong on when the alternative is taking a level off an active player.

Guests are untouched either way: their path stamps skills.__curve into the
object it writes to localStorage, so their stamp round-trips and their
migration already ran exactly once.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


sub(
    "      // Saves written before the zone update carry the old curve. The blob\n"
    "      // version is the only trustworthy signal here: rows written before\n"
    "      // the v:2 fix have no skillCurve stamp at all, so keying on the stamp\n"
    "      // would migrate every already-migrated save one more time.\n"
    "      if (Number(raw.v) < 2) {\n"
    "        const wrap = { skills: this.skills, skillCurve: 0 };\n"
    "        if (this.migrateSkillCurve(wrap)) { this._curveMigrated = true; this.scheduleSave && this.scheduleSave(); }\n"
    "      } else { this._curveMigrated = true; if (raw.skillXpV1) this._skillXpV1 = raw.skillXpV1; }",

    "      // The curve migration is RETIRED for cloud saves. Do not put it back.\n"
    "      //\n"
    "      // Every row in the database is v:1, and every one of them has already\n"
    "      // been migrated many times over, because the old code ran the\n"
    "      // migration on every login. Running it once more on the way past\n"
    "      // would take one more level off every active player. There are no\n"
    "      // un-migrated saves left for it to convert.\n"
    "      //\n"
    "      // An account that has not logged in since before the zone update is\n"
    "      // the only case this misses, and it errs upward: that character reads\n"
    "      // a little high rather than losing levels somebody earned. That is the\n"
    "      // right side to be wrong on.\n"
    "      this._curveMigrated = true;\n"
    "      if (raw.skillXpV1) this._skillXpV1 = raw.skillXpV1;",
    'retire cloud curve migration')

for old, new, label in edits:
    assert src.count(old) == 1, 'anchor %s went stale' % label
    src = src.replace(old, new)

io.open(SRC, 'w', encoding='utf-8').write(src)
print('patched %d anchors -> %s' % (len(edits), SRC))
