const test = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('./server');

let server, base;
test.before(async () => { server = createServer(); await new Promise((resolve) => server.listen(0, resolve)); base = `http://127.0.0.1:${server.address().port}`; });
test.after(async () => new Promise((resolve) => server.close(resolve)));
async function get(path) { const res = await fetch(base + path); return { status: res.status, body: await res.json() }; }

test('完整路径：筛选关系、读取详情与证据', async () => {
  const list = await get('/api/relations?type=partner&status=confirmed');
  assert.equal(list.status, 200); assert.equal(list.body.items.length, 2);
  const detail = await get(`/api/relations/${list.body.items[0].id}`);
  assert.equal(detail.status, 200); assert.ok(detail.body.evidence[0].url);
  assert.equal((await get(`/api/evidence/${detail.body.evidence[0].id}`)).status, 200);
});
test('拒绝非法关系类型、分页和置信度', async () => {
  assert.equal((await get('/api/relations?type=made_up')).status, 400);
  assert.equal((await get('/api/relations?page=0')).status, 400);
  assert.equal((await get('/api/relations?minConfidence=101')).status, 400);
});
test('实体、关系与证据不存在时返回 404', async () => {
  assert.equal((await get('/api/entities/nope/neighbors')).status, 404);
  assert.equal((await get('/api/relations/nope')).status, 404);
  assert.equal((await get('/api/evidence/nope')).status, 404);
});
test('未知关系和缺失来源显式保留', async () => {
  const list = await get('/api/relations?status=unknown');
  assert.equal(list.status, 200); assert.equal(list.body.items[0].evidenceIds[0], 'ev-investor-gap');
  assert.equal((await get('/api/evidence/ev-investor-gap')).body.availability, 'unavailable');
});
