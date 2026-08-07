#!/usr/bin/env python3
"""Patch 53: the menu patch notes go LIVE. Edits /tmp/game-src.html.

The menu's PATCH NOTES box was a block of markup hand-written at V13 and never
touched again, while every agent has been faithfully updating PATCH-NOTES.md
with each push (notes.py enforces the format). Two sources of truth, one of
them dead.

Fix: the box now fetches PATCH-NOTES.md from the same host at menu build and
renders it - the file GitHub Pages already serves right next to index.html.
Agents keep doing exactly what they already do (python3 notes.py "title"
"body" before every push) and the menu updates itself on the next deploy,
no bundle edit, forever.

Rendering is DOM-built with textContent only - no innerHTML, so nothing in a
notes file can ever inject markup into the menu. Entry titles become dim
dividers, the ALL-CAPS keyword before " - " on each line (NEW, FIXED,
CHANGED...) gets the gold highlight the old block used. The box gets a
max-height and scrolls, because twelve entries is a lot of menu.

The static V13 markup stays in the template as the offline fallback: the
standalone file opened from disk (file://, fetch fails) still shows notes.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'anchor matched %d times (wanted %d): %s | %s' % (f, count, tag, old[:110].replace('\n', ' / '))
    s = s.replace(old, new)
    n += 1


# ------------------------------------------------ refs on the two note divs
sub('<div style="font-size:10px; letter-spacing:0.2em; color:#7d8a63;">PATCH NOTES · V13</div>',
    '<div ref="{{ notesHeadRef }}" style="font-size:10px; letter-spacing:0.2em; color:#7d8a63;">PATCH NOTES · V13</div>',
    tag='notes head ref')

sub('<div style="font-size:11.5px; line-height:1.8; color:#b3afa0; margin-top:6px; text-wrap:pretty;">',
    '<div ref="{{ notesBodyRef }}" style="font-size:11.5px; line-height:1.8; color:#b3afa0; margin-top:6px; text-wrap:pretty;">',
    tag='notes body ref')

sub('  assistRef = React.createRef(); musicRef = React.createRef(); musicVolRef = React.createRef(); pvpRef = React.createRef();',
    '  assistRef = React.createRef(); musicRef = React.createRef(); musicVolRef = React.createRef(); pvpRef = React.createRef(); notesHeadRef = React.createRef(); notesBodyRef = React.createRef();',
    tag='ref decl')

sub('      assistRef: this.assistRef, musicRef: this.musicRef, musicVolRef: this.musicVolRef, pvpRef: this.pvpRef,',
    '      assistRef: this.assistRef, musicRef: this.musicRef, musicVolRef: this.musicVolRef, pvpRef: this.pvpRef, notesHeadRef: this.notesHeadRef, notesBodyRef: this.notesBodyRef,',
    tag='ref map')

# ------------------------------------------------------- kick off at menu build
sub("""    if (!ov) return;
    this.syncPvpBtn();""",
    """    if (!ov) return;
    this.syncPvpBtn();
    this.loadPatchNotes();""",
    tag='buildLoginUi hook')

# ---------------------------------------------------------------- the loader
sub('  syncPvpBtn() {',
    """  // The menu patch notes are LIVE: fetched from PATCH-NOTES.md on the same
  // host, so the notes every agent already writes with notes.py show up on
  // the menu automatically on the next deploy. The static V13 markup in the
  // template is only the offline fallback (file:// standalone, fetch fails).
  // DOM-built with textContent only - notes files can never inject markup.
  loadPatchNotes() {
    const head = this.notesHeadRef && this.notesHeadRef.current;
    const body = this.notesBodyRef && this.notesBodyRef.current;
    if (!head || !body || this._notesLive) return;
    fetch('PATCH-NOTES.md?v=' + Date.now(), { cache: 'no-store' })
      .then(r => (r.ok ? r.text() : null))
      .then(md => {
        if (!md || md.charCodeAt(0) !== 35) return;   // not our file: keep the fallback
        const entries = md.split('\\n## ').slice(1).map(e => e.trim()).filter(Boolean);
        if (!entries.length) return;
        this._notesLive = true;
        const tag = (entries[0].match(/\\((v[^)]{1,8})\\)/i) || [])[1];
        head.textContent = 'PATCH NOTES · ' + (tag ? tag.toUpperCase() : 'LIVE');
        body.textContent = '';
        body.style.maxHeight = '340px';
        body.style.overflowY = 'auto';
        body.style.paddingRight = '8px';
        for (let i = 0; i < entries.length; i++) {
          const lines = entries[i].split('\\n').map(l => l.trim()).filter(Boolean);
          const title = lines.shift() || '';
          const t = document.createElement('div');
          t.style.cssText = 'color:#7d8a63; letter-spacing:0.14em; font-size:10.5px;' + (i ? ' margin-top:12px;' : '');
          t.textContent = title.toUpperCase();
          body.appendChild(t);
          for (const l of lines) {
            const row = document.createElement('div');
            const m = l.match(/^([A-Z][A-Z ]{1,14}) - /);
            if (m) {
              const k = document.createElement('span');
              k.style.color = '#e8c774';
              k.textContent = m[1];
              row.appendChild(k);
              row.appendChild(document.createTextNode(' - ' + l.slice(m[0].length)));
            } else {
              row.appendChild(document.createTextNode(l));
            }
            body.appendChild(row);
          }
        }
      })
      .catch(() => {});
  }
  syncPvpBtn() {""",
    tag='loadPatchNotes method')


io.open(SRC, 'w', encoding='utf-8').write(s)
print('53_live_patch_notes: %d edits applied' % n)
