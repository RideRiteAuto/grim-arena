#!/usr/bin/env python3
"""Stop the skill-curve migration re-running on every cloud login.

The bug, exactly:

  charSave() builds the save blob and never writes `skillCurve`.
  applySaveBlob() reads `Number(raw.skillCurve) || 0`, always gets 0, decides
  the save predates the new curve, and runs migrateSkillCurve.
  migrateSkillCurve deflates every skill's XP for real (the `skills` it mutates
  is a live alias of this.skills) and then stamps `skillCurve = 2` onto the
  throwaway `wrap` object the caller built. The stamp and the `skillXpV1`
  backup both die on the next line.

So every login re-reads new-curve XP as if it were old-curve XP and pushes it
down a rung, then saves the result four seconds later. It is a one-way ratchet
across every skill at once. Measured: woodcutting 11 -> 7 -> 5 -> 4 -> 3.
Guests were never affected: the guest path stamps skills.__curve and that
round-trips through localStorage.

The fix keys on the blob version instead of a stamp, because existing rows in
the database have no stamp and keying on one would migrate every already-
migrated save exactly one more time. Saves written before the zone update are
v:1 and migrate once; everything written from here on is v:2 and never
migrates again.

Also stops a save the database REFUSED from being reported as a success.
grim_save returns a boolean and returns false on a hash mismatch or an
oversized blob, both as HTTP 200. Only r.ok was checked, so the body was never
read, _saveDirty was cleared, and the write was lost silently.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


# 1. The blob carries its own version, the curve stamp, and the pre-migration
#    XP so the next migration is actually reversible.
sub(
    "      v: 1, inv: this.inv, worn: this.worn, bar: this.bar, overflow: this.overflow,\n"
    "      bank: this.bankV || [], skills: this.skills, quest: this.quest, elem: this.element || 'fire',\n"
    "      unlocks: this.unlocks || {}, at: at, mount: mount",

    "      // v:2 means the skill XP in this blob is already on the post-zone-update\n"
    "      // curve. applySaveBlob migrates v:1 and below, once, and never again.\n"
    "      // Before v:2 the stamp was written to a temporary object and thrown\n"
    "      // away, so the migration re-ran on every login and deflated every\n"
    "      // skill a rung at a time.\n"
    "      v: 2, skillCurve: 2, skillXpV1: this._skillXpV1 || null,\n"
    "      inv: this.inv, worn: this.worn, bar: this.bar, overflow: this.overflow,\n"
    "      bank: this.bankV || [], skills: this.skills, quest: this.quest, elem: this.element || 'fire',\n"
    "      unlocks: this.unlocks || {}, at: at, mount: mount",
    'charSave version')

# 2. Gate the migration on the blob version, not on a stamp that was never
#    persisted. A v:2 blob is already converted, full stop.
sub(
    "      // Saves written before the zone update carry the old curve.\n"
    "      { const wrap = { skills: this.skills, skillCurve: Number(raw.skillCurve) || 0 };\n"
    "        if (this.migrateSkillCurve(wrap)) { this._curveMigrated = true; this.scheduleSave && this.scheduleSave(); } }",

    "      // Saves written before the zone update carry the old curve. The blob\n"
    "      // version is the only trustworthy signal here: rows written before\n"
    "      // the v:2 fix have no skillCurve stamp at all, so keying on the stamp\n"
    "      // would migrate every already-migrated save one more time.\n"
    "      if (Number(raw.v) < 2) {\n"
    "        const wrap = { skills: this.skills, skillCurve: 0 };\n"
    "        if (this.migrateSkillCurve(wrap)) { this._curveMigrated = true; this.scheduleSave && this.scheduleSave(); }\n"
    "      } else { this._curveMigrated = true; if (raw.skillXpV1) this._skillXpV1 = raw.skillXpV1; }",
    'applySaveBlob curve gate')

# 3. Keep the pre-migration XP somewhere that survives the function, so the
#    conversion can be undone if it ever goes wrong again.
sub(
    "    store.skillCurve = 2;\n"
    "    store.skillXpV1 = backup;\n"
    "    return true;",

    "    store.skillCurve = 2;\n"
    "    store.skillXpV1 = backup;\n"
    "    // The caller hands us a throwaway wrapper, so the stamp above cannot be\n"
    "    // the thing that stops a second run. It is charSave's v:2 that does\n"
    "    // that. This backup rides the save blob so the conversion is undoable.\n"
    "    this._skillXpV1 = backup;\n"
    "    return true;",
    'migrateSkillCurve backup')

# 4. grim_save answers with a boolean. false means the row was not written.
#    Read it. On unload the body may never arrive, and a save we cannot confirm
#    is treated as landed, which is the behaviour that was there before.
sub(
    "        }).then(r => { if (!r.ok) this._saveDirty = true; }).catch(() => { this._saveDirty = true; });",

    "        }).then(r => r.ok ? r.json().catch(() => true) : false)\n"
    "          .then(ok => { if (ok !== true) { this._saveDirty = true; console.error('[SAVE] refused by server'); } })\n"
    "          .catch(() => { this._saveDirty = true; });",
    'flushSave rpc body')

sub(
    "    }).then(r => { if (r.ok) { this._saveDirty = false; return 'cloud'; } return 'failed ' + r.status; })\n"
    "      .catch(() => 'offline');",

    "    }).then(r => r.ok ? r.json().catch(() => true).then(ok => ok === true ? 'cloud' : 'refused') : 'failed ' + r.status)\n"
    "      .then(res => { if (res === 'cloud') this._saveDirty = false; return res; })\n"
    "      .catch(() => 'offline');",
    'flushSaveAsync rpc body')

# 5. XP never legitimately goes down in this game. Say so out loud on the way
#    to the database, so the next bug of this shape is caught in one login
#    instead of after weeks of quiet corruption.
sub(
    "  flushSave(sync) {\n"
    "    if (!this.profile || !this._saveDirty) return;\n"
    "    this._saveDirty = false;\n"
    "    const blob = this.charSave();",

    "  flushSave(sync) {\n"
    "    if (!this.profile || !this._saveDirty) return;\n"
    "    this._saveDirty = false;\n"
    "    const blob = this.charSave();\n"
    "    this.assertXpMonotonic(blob);",
    'flushSave guard call')

sub(
    "  flushSaveAsync(ms) {\n"
    "    this._saveDirty = true;\n"
    "    const blob = this.charSave();",

    "  flushSaveAsync(ms) {\n"
    "    this._saveDirty = true;\n"
    "    const blob = this.charSave();\n"
    "    this.assertXpMonotonic(blob);",
    'flushSaveAsync guard call')

sub(
    "  migrateSkillCurve(store) {",

    "  // Nothing in this game lowers a skill. If a save is about to write less\n"
    "  // XP than the last one did, something upstream is eating progress and we\n"
    "  // want to know on the spot rather than from a player three weeks later.\n"
    "  assertXpMonotonic(blob) {\n"
    "    const prev = this._lastSavedSkills;\n"
    "    const now = (blob && blob.skills) || {};\n"
    "    if (prev) for (const k in now) {\n"
    "      if (prev[k] != null && Number(now[k]) < Number(prev[k])) {\n"
    "        console.error('[SAVE] XP WENT DOWN', k, prev[k], '->', now[k], blob);\n"
    "      }\n"
    "    }\n"
    "    this._lastSavedSkills = Object.assign({}, now);\n"
    "  }\n"
    "  migrateSkillCurve(store) {",
    'assertXpMonotonic')

for old, new, label in edits:
    assert src.count(old) == 1, 'anchor %s went stale' % label
    src = src.replace(old, new)

io.open(SRC, 'w', encoding='utf-8').write(src)
print('patched %d anchors -> %s' % (len(edits), SRC))
