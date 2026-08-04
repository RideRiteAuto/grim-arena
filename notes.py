#!/usr/bin/env python3
"""Prepend a patch-notes entry and prune old ones so the file never bloats.
Usage: python3 notes.py "## <date> (<tag>) - <title>" "<body text>"
Keeps the newest MAX_ENTRIES entries; older ones are dropped automatically."""
import io, sys
MAX_ENTRIES = 12
p = 'PATCH-NOTES.md'
title, body = sys.argv[1], sys.argv[2]
s = io.open(p, encoding='utf-8').read()
head = '# Grim World — patch notes'
assert s.startswith(head)
rest = s[len(head):].lstrip('\n')
entries = ['## ' + e for e in rest.split('\n## ') if e.strip()]
if entries and entries[0].startswith('## ## '):
    entries[0] = entries[0][3:]
entries = [e if e.startswith('## ') else '## ' + e.lstrip('# ') for e in entries]
new_entry = title + '\n\n' + body.strip() + '\n'
entries = [new_entry] + entries
kept = entries[:MAX_ENTRIES]
dropped = len(entries) - len(kept)
io.open(p, 'w', encoding='utf-8').write(head + '\n\n' + '\n\n'.join(e.strip() + '\n' for e in kept))
print('patch notes updated, %d entr%s kept%s' % (len(kept), 'y' if len(kept) == 1 else 'ies', (', %d old pruned' % dropped) if dropped > 0 else ''))
