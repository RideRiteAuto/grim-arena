#!/usr/bin/env bash
# Rebuild the bundle from the committed bundle plus every patch in order.
#
# This is the whole edit path in one command: extract the embedded game source,
# replay each patch script against it, and pack it back into both bundles with a
# verified byte-exact round trip. Re-running it after someone else pushes a
# bundle change is how the two tracks stay merged without hand-editing the
# bundle, which would brick the live site.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 repack.py extract
for p in harness/patches/*.py; do
  echo "-- $p"
  python3 "$p"
done

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
