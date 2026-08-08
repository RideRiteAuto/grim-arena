#!/usr/bin/env python3
"""Patch 82.283: stop updateHUD() rebuilding two ~19-string arrays every
single frame just to index one element out of each.

updateHUD runs every frame during open-world play. The DOM write right below
this was already diffed against the last value (cheap), but the title/obj
array construction ran unconditionally every frame regardless of whether
quest state changed. This gates the (unmodified, byte-identical) array
construction behind a key of every value the array literals actually read
(q.stage, q.kills, bars, ore, cle, q.wolves, WOOL count, DEER HIDE count,
q.captain, q.king) and only rebuilds when that key changes. Everything else
about a normal exploring/fighting frame - the overwhelming majority - now
skips 38 string-literal allocations and 2 array allocations it was throwing
away unread.

No behavior change: same strings, same stage mapping, same fallback to
'QUEST' / ''. The array text is unchanged, just moved behind the gate.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """        const q = this.quest;
        const bars = this.invCount('IRON BAR'), ore = this.invCount('IRON ORE'), cle = this.invCount('GRIM CLEAVER') > 0;
        const title = ['QUEST', 'DAILY PMS', 'DAILY PMS', 'TRACK DOWN MR. SAILERS', 'TRACK DOWN MR. SAILERS', 'NEW QUEST WAITING', 'IRONS IN THE FIRE', 'IRONS IN THE FIRE', 'NEW QUEST WAITING', 'THE MERE ROAD', 'FELL THE PLAGUE RAT', 'FELL THE PLAGUE RAT', 'SEEK HOLLOWREST', 'HOLLOWREST', 'WOLVES AT THE DOOR', 'HIDE AND HAIR', 'THE BANDIT CAPTAIN', 'THE HOLLOW KING', 'ALL QUESTS DONE'][q.stage] || 'QUEST';
        const obj = [
          'TALK TO BALL PELLINGER',
          'SLAY GOBLINS — ' + q.kills + ' / 10',
          'RETURN TO BALL PELLINGER',
          'FIND AND FELL MR. SAILERS — THE FAR FIELD',
          'RETURN TO BALL PELLINGER',
          'TALK TO BALL PELLINGER',
          cle ? 'RETURN TO BALL PELLINGER'
            : bars >= 10 ? 'FORGE AT THE ANVIL — BY THE CAMP'
            : 'SMELT IRON BARS — ' + Math.min(bars, 10) + ' / 10' + (ore > 0 ? ' · ORE ×' + ore : ' · MINE MORE ORE'),
          'RETURN TO BALL PELLINGER',
          'TALK TO BALL PELLINGER',
          'WOOL — ' + Math.min(this.invCount('WOOL'), 3) + ' / 3 · FOLLOW THE MAIN ROAD SOUTH',
          'SLAY THE PLAGUE RAT — NORTH OF THE LAKE',
          'RETURN TO BALL PELLINGER',
          'TALK TO BALL PELLINGER — HE HAS NEWS FROM THE NORTH',
          'TRAVEL NORTH TO HOLLOWREST — FIND MARGARET VANCE',
          'SLAY DIRE WOLVES — ' + Math.min(q.wolves || 0, 8) + ' / 8',
          'DEER HIDES — ' + Math.min(this.invCount('DEER HIDE'), 3) + ' / 3 · HUNT THE RED DEER',
          q.captain ? 'RETURN TO MARGARET VANCE' : 'SLAY THE BANDIT CAPTAIN — THE SOUTH ROAD',
          q.king ? 'RETURN TO MARGARET VANCE' : 'SLAY THE HOLLOW KING — THE BARROW',
          'ALL QUESTS COMPLETE'
        ][q.stage] || '';
        if (this.questTitleRef.current.textContent !== title) this.questTitleRef.current.textContent = title;
        if (this.questObjRef.current.textContent !== obj) this.questObjRef.current.textContent = obj;
"""

NEW = """        const q = this.quest;
        const bars = this.invCount('IRON BAR'), ore = this.invCount('IRON ORE'), cle = this.invCount('GRIM CLEAVER') > 0;
        const wool = this.invCount('WOOL'), hide = this.invCount('DEER HIDE');
        const qKey = q.stage + '|' + q.kills + '|' + bars + '|' + ore + '|' + (cle ? 1 : 0) + '|' + (q.wolves || 0) + '|' + wool + '|' + hide + '|' + (q.captain ? 1 : 0) + '|' + (q.king ? 1 : 0);
        if (this._questKey !== qKey) {
          this._questKey = qKey;
          this._questTitle = ['QUEST', 'DAILY PMS', 'DAILY PMS', 'TRACK DOWN MR. SAILERS', 'TRACK DOWN MR. SAILERS', 'NEW QUEST WAITING', 'IRONS IN THE FIRE', 'IRONS IN THE FIRE', 'NEW QUEST WAITING', 'THE MERE ROAD', 'FELL THE PLAGUE RAT', 'FELL THE PLAGUE RAT', 'SEEK HOLLOWREST', 'HOLLOWREST', 'WOLVES AT THE DOOR', 'HIDE AND HAIR', 'THE BANDIT CAPTAIN', 'THE HOLLOW KING', 'ALL QUESTS DONE'][q.stage] || 'QUEST';
          this._questObj = [
            'TALK TO BALL PELLINGER',
            'SLAY GOBLINS — ' + q.kills + ' / 10',
            'RETURN TO BALL PELLINGER',
            'FIND AND FELL MR. SAILERS — THE FAR FIELD',
            'RETURN TO BALL PELLINGER',
            'TALK TO BALL PELLINGER',
            cle ? 'RETURN TO BALL PELLINGER'
              : bars >= 10 ? 'FORGE AT THE ANVIL — BY THE CAMP'
              : 'SMELT IRON BARS — ' + Math.min(bars, 10) + ' / 10' + (ore > 0 ? ' · ORE ×' + ore : ' · MINE MORE ORE'),
            'RETURN TO BALL PELLINGER',
            'TALK TO BALL PELLINGER',
            'WOOL — ' + Math.min(wool, 3) + ' / 3 · FOLLOW THE MAIN ROAD SOUTH',
            'SLAY THE PLAGUE RAT — NORTH OF THE LAKE',
            'RETURN TO BALL PELLINGER',
            'TALK TO BALL PELLINGER — HE HAS NEWS FROM THE NORTH',
            'TRAVEL NORTH TO HOLLOWREST — FIND MARGARET VANCE',
            'SLAY DIRE WOLVES — ' + Math.min(q.wolves || 0, 8) + ' / 8',
            'DEER HIDES — ' + Math.min(hide, 3) + ' / 3 · HUNT THE RED DEER',
            q.captain ? 'RETURN TO MARGARET VANCE' : 'SLAY THE BANDIT CAPTAIN — THE SOUTH ROAD',
            q.king ? 'RETURN TO MARGARET VANCE' : 'SLAY THE HOLLOW KING — THE BARROW',
            'ALL QUESTS COMPLETE'
          ][q.stage] || '';
        }
        const title = this._questTitle, obj = this._questObj;
        if (this.questTitleRef.current.textContent !== title) this.questTitleRef.current.textContent = title;
        if (this.questObjRef.current.textContent !== obj) this.questObjRef.current.textContent = obj;
"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
