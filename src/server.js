const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { loadSnapshot, listRelations, getRelation, getNeighbors, getEvidence, getEntities } = require('./store');

const publicDir = path.join(__dirname, '..', 'public');
function send(res, status, body, type = 'application/json; charset=utf-8') { res.writeHead(status, { 'content-type': type }); res.end(typeof body === 'string' ? body : JSON.stringify(body)); }
function notFound(res) { send(res, 404, { error: 'NOT_FOUND', message: '资源不存在。' }); }
function serveStatic(res, pathname) {
  const file = pathname === '/' ? 'index.html' : pathname.slice(1);
  if (!/^[\w.-]+$/.test(file)) return notFound(res);
  const target = path.join(publicDir, file);
  if (!target.startsWith(publicDir) || !fs.existsSync(target)) return notFound(res);
  const type = file.endsWith('.css') ? 'text/css; charset=utf-8' : file.endsWith('.js') ? 'application/javascript; charset=utf-8' : 'text/html; charset=utf-8';
  send(res, 200, fs.readFileSync(target), type);
}
function createServer() {
  return http.createServer((req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      const q = Object.fromEntries(url.searchParams);
      if (req.method !== 'GET') return send(res, 405, { error: 'METHOD_NOT_ALLOWED', message: '仅支持 GET。' });
      if (url.pathname === '/api/health') return send(res, 200, { ok: true, snapshot: loadSnapshot().snapshot });
      if (url.pathname === '/api/entities') return send(res, 200, { items: getEntities(q) });
      if (url.pathname === '/api/relations') return send(res, 200, listRelations(q));
      if (url.pathname.startsWith('/api/relations/')) { const item = getRelation(decodeURIComponent(url.pathname.split('/').pop())); return item ? send(res, 200, item) : notFound(res); }
      if (url.pathname.startsWith('/api/entities/') && url.pathname.endsWith('/neighbors')) { const id = decodeURIComponent(url.pathname.split('/')[3]); const item = getNeighbors(id); return item ? send(res, 200, item) : notFound(res); }
      if (url.pathname.startsWith('/api/evidence/')) { const item = getEvidence(decodeURIComponent(url.pathname.split('/').pop())); return item ? send(res, 200, item) : notFound(res); }
      return serveStatic(res, url.pathname);
    } catch (error) { return send(res, 400, { error: 'INVALID_QUERY', message: error.message }); }
  });
}
if (require.main === module) { const port = Number(process.env.PORT || 3000); createServer().listen(port, () => console.log(`EmbodiedGraph 正在运行：http://localhost:${port}`)); }
module.exports = { createServer };
