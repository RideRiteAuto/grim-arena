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

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
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
      .replace('https://unpkg.com/three@0.160.1/build/three.module.js', '/vendor/three.module.js');
  }
  res.writeHead(200, { 'content-type': TYPES[ext] || 'application/octet-stream' });
  res.end(body);
});

server.listen(PORT, () => console.log('harness serving ' + ROOT + ' on http://127.0.0.1:' + PORT));
