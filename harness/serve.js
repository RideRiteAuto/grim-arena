// Local boot harness server.
//
// Serves the built bundle with the three.js importmap pointed at a local copy
// so the game boots with no network at all. Everything else is served straight
// off disk. Kept out of the bundle: this is tooling, not game code.
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const THREE_LOCAL = path.resolve(__dirname, '../../node_modules/three/build/three.module.js');
const PORT = Number(process.env.PORT || 8123);

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json',
  '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml'
};

// The world editor's edit layer. Served locally so a boot test exercises the
// REAL path (fetch, validate, index, apply) instead of the network-failure
// path, and so the editor harness can hand the game a layer to draw.
// Set GRIM_EDITS to a json file to boot the game with that layer applied.
const EDITS_FILE = process.env.GRIM_EDITS || '/tmp/grim-edits.json';
const EDIT_KEY = 'harness-key';

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';

  if (p === '/edits' || p.endsWith('/edits')) {
    const head = {
      'access-control-allow-origin': '*',
      'access-control-allow-headers': '*',
      'access-control-allow-methods': 'GET, PUT, POST, HEAD, OPTIONS',
      'access-control-expose-headers': 'x-edit-rev'
    };
    if (req.method === 'OPTIONS') { res.writeHead(204, head); return res.end(); }
    if (req.method === 'HEAD') {
      const ok = req.headers['x-edit-key'] === EDIT_KEY;
      res.writeHead(ok ? 204 : 403, head); return res.end();
    }
    if (req.method === 'PUT' || req.method === 'POST') {
      let body = '';
      req.on('data', c => body += c);
      req.on('end', () => {
        if (req.headers['x-edit-key'] !== EDIT_KEY) {
          res.writeHead(403, Object.assign({ 'content-type': 'application/json' }, head));
          return res.end('{"ok":false,"err":"bad-key"}');
        }
        try { fs.writeFileSync(EDITS_FILE, body); } catch (e) {}
        res.writeHead(200, Object.assign({ 'content-type': 'application/json' }, head));
        res.end('{"ok":true,"rev":1,"bytes":' + body.length + '}');
      });
      return;
    }
    let body = '{"v":1,"empty":true}';
    try { if (fs.existsSync(EDITS_FILE)) body = fs.readFileSync(EDITS_FILE, 'utf8'); } catch (e) {}
    res.writeHead(200, Object.assign({
      'content-type': 'application/json', 'cache-control': 'no-cache', 'x-edit-rev': '1'
    }, head));
    return res.end(body);
  }

  if (p === '/vendor/three.module.js') {
    res.writeHead(200, { 'content-type': TYPES['.js'] });
    return res.end(fs.readFileSync(THREE_LOCAL));
  }
  const file = path.join(ROOT, p);
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); return res.end('not found');
  }
  const ext = path.extname(file);
  let body = fs.readFileSync(file);
  if (ext === '.html') {
    // Point the importmap at the local three, and only that. The bundle is
    // otherwise served byte for byte as it will ship.
    body = body.toString('utf8')
      .replace('https://unpkg.com/three@0.160.1/build/three.module.js', '/vendor/three.module.js')
      // and the edit layer at the local one above, so no test ever depends on
      // the live relay being reachable. The bundle carries the URL literally:
      // repack only escapes "</", and this string has none.
      .split('https://grim-arena.kevin-230.workers.dev/world/main/edits').join('/edits');
  }
  res.writeHead(200, { 'content-type': TYPES[ext] || 'application/octet-stream' });
  res.end(body);
});

server.listen(PORT, () => console.log('harness serving ' + ROOT + ' on http://127.0.0.1:' + PORT));
