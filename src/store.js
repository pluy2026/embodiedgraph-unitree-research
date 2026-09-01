const fs = require('node:fs');
const path = require('node:path');

const dataPath = path.join(__dirname, '..', 'data', 'snapshot.json');
const TYPES = new Set(['supplier', 'customer', 'partner', 'investor_or_investee', 'peer']);
const STATUSES = new Set(['confirmed', 'inferred', 'unknown']);

function loadSnapshot() { return JSON.parse(fs.readFileSync(dataPath, 'utf8')); }
function indexById(items) { return new Map(items.map((item) => [item.id, item])); }

function parsePagination(query) {
  const page = query.page === undefined ? 1 : Number(query.page);
  const pageSize = query.pageSize === undefined ? 20 : Number(query.pageSize);
  if (!Number.isInteger(page) || page < 1 || !Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
    throw new Error('page 必须是正整数，pageSize 必须在 1 到 100 之间。');
  }
  return { page, pageSize };
}

function listRelations(query = {}) {
  const snapshot = loadSnapshot();
  if (query.type && !TYPES.has(query.type)) throw new Error(`未知关系类型：${query.type}`);
  if (query.status && !STATUSES.has(query.status)) throw new Error(`未知事实状态：${query.status}`);
  const minConfidence = query.minConfidence === undefined ? null : Number(query.minConfidence);
  if (minConfidence !== null && (!Number.isFinite(minConfidence) || minConfidence < 0 || minConfidence > 100)) throw new Error('minConfidence 必须在 0 到 100 之间。');
  const { page, pageSize } = parsePagination(query);
  let items = snapshot.relations;
  if (query.type) items = items.filter((item) => item.type === query.type);
  if (query.status) items = items.filter((item) => item.status === query.status);
  if (minConfidence !== null) items = items.filter((item) => item.confidence.score >= minConfidence);
  if (query.asOf) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(query.asOf)) throw new Error('asOf 必须是 YYYY-MM-DD。');
    items = items.filter((item) => (!item.validity.from || item.validity.from <= query.asOf) && (!item.validity.to || item.validity.to >= query.asOf));
  }
  const entities = indexById(snapshot.entities);
  const enriched = items.map((item) => ({ ...item, fromEntity: entities.get(item.from), toEntity: entities.get(item.to) }));
  return { snapshot: snapshot.snapshot, pagination: { page, pageSize, total: enriched.length, totalPages: Math.ceil(enriched.length / pageSize) }, items: enriched.slice((page - 1) * pageSize, page * pageSize) };
}

function getRelation(id) {
  const snapshot = loadSnapshot();
  const relation = snapshot.relations.find((item) => item.id === id);
  if (!relation) return null;
  const entities = indexById(snapshot.entities);
  const evidence = indexById(snapshot.evidence);
  return { ...relation, fromEntity: entities.get(relation.from), toEntity: entities.get(relation.to), evidence: relation.evidenceIds.map((id) => evidence.get(id)) };
}

function getNeighbors(entityId) {
  const snapshot = loadSnapshot();
  const entity = snapshot.entities.find((item) => item.id === entityId);
  if (!entity) return null;
  return { entity, relations: snapshot.relations.filter((item) => item.from === entityId || item.to === entityId) };
}

function getEvidence(id) { return loadSnapshot().evidence.find((item) => item.id === id) || null; }
function getEntities(query = {}) {
  const entities = loadSnapshot().entities;
  const keyword = (query.q || '').trim().toLowerCase();
  return keyword ? entities.filter((item) => [item.name, ...item.aliases].join(' ').toLowerCase().includes(keyword)) : entities;
}

module.exports = { TYPES, STATUSES, loadSnapshot, listRelations, getRelation, getNeighbors, getEvidence, getEntities };
