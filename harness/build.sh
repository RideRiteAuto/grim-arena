#!/usr/bin/env bash
# Rebuild the bundle from the committed bundle plus every patch in order.
#
# This is the whole edit path in one command: extract the embedded game source,
# apply every PENDING patch script against it, and pack it back into both
# bundles with a verified byte-exact round trip.
#
# harness/patches/ holds patches not yet in the committed bundle.
# harness/patches/applied/ holds the ones that are, kept only as a record of what
# each shipped change actually did. Once a patch is pushed, MOVE IT to applied/:
# replaying it against a bundle that already contains it fails on a missing
# anchor, which is the assert doing its job.
#
# Re-running this after the combat track pushes a bundle change is how the two
# tracks stay merged without hand-editing the bundle, which would brick the
# live site.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 repack.py extract
# nullglob: with no pending patches the glob would otherwise stay literal and
# python3 would fail on a file called "*.py", and set -e would abort the build
# before it ever packed. Silently shipping nothing looked exactly like success.
shopt -s nullglob
for p in harness/patches/*.py; do
  echo "-- $p"
  python3 "$p"
done
shopt -u nullglob

# Syntax gate before anything is written back into the bundle.
python3 - <<'EOF'
import io
s = io.open('/tmp/game-src.html', encoding='utf-8').read()
i = s.find('data-props='); i = s.find('>', i) + 1; j = s.find('</script>', i)
io.open('/tmp/gamecode.mjs', 'w', encoding='utf-8').write(s[i:j])
EOF
node --check /tmp/gamecode.mjs
echo "-- syntax ok"

python3 repack.py pack

# Second syntax gate, AFTER packing. The first one runs before repack injects
# shared-rules, worldgen and the editor, so a syntax error inside any of those
# three files would sail past it and ship. This one reads what is actually in
# the bundle.
python3 repack.py extract > /dev/null
python3 - <<'EOF'
import io
s = io.open('/tmp/game-src.html', encoding='utf-8').read()
i = s.find('data-props='); i = s.find('>', i) + 1; j = s.find('</script>', i)
io.open('/tmp/gamecode.mjs', 'w', encoding='utf-8').write(s[i:j])
EOF
node --check /tmp/gamecode.mjs
echo "-- packed bundle syntax ok"
