#!/usr/bin/env python3
"""Patch 76.001: fix invLoad() SyntaxError (broken by v17.7 R/F hotkey commit).

ce22ed1 ("Fix R/F hotkey hijacking the action bar, grow bar to 8 slots") added
`this.bankV = [];` to invLoad() but its find/replace anchor was mis-scoped: it
deleted the `let raw = null; try { raw = JSON.parse(...) } catch (e) {}`
declaration that used to sit right there, and duplicated the following
`if (raw && raw.inv) {` line. The result parses as a hard SyntaxError
(Unexpected token '{' at migrateLegacy(), many lines later, since the extra
brace throws off nesting for the rest of the class) -- master currently does
not run at all.

Fix: restore the missing `raw` declaration in its original spot, keep the
new `this.bankV = [];` line (that part of the other commit was fine), and
drop the duplicate `if` line. This does not touch the R/F hotkey fix or the
6->8 action bar slot change themselves, only the corrupted three lines around
them.
"""
import io

PATH = '/tmp/game-src.html'
s = io.open(PATH, encoding='utf-8').read()

OLD = """    this.overflow = [];
    this.bankV = [];
    if (raw && raw.inv) {
    if (raw && raw.inv) {
      const IT = this.ITEMS();"""

NEW = """    this.overflow = [];
    let raw = null;
    try { raw = JSON.parse(localStorage.getItem('grim-inv-v1') || 'null'); } catch (e) {}
    this.bankV = [];
    if (raw && raw.inv) {
      const IT = this.ITEMS();"""

count = s.count(OLD)
assert count == 1, 'anchor matched %d times, expected 1' % count
s = s.replace(OLD, NEW)
io.open(PATH, 'w', encoding='utf-8').write(s)
print('patch 76.001: invLoad() raw declaration restored')
