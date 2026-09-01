const { listRelations, getRelation, getNeighbors, getEvidence } = require('./store');

function usage() {
  console.log(`用法：
  node src/cli.js relations [--type partner] [--status confirmed] [--minConfidence 70] [--asOf 2026-08-29]
  node src/cli.js relation <id>
  node src/cli.js entity <id>
  node src/cli.js evidence <id>`);
}
function options(tokens) {
  const result = {};
  for (let i = 0; i < tokens.length; i += 2) {
    if (!tokens[i].startsWith('--') || tokens[i + 1] === undefined) throw new Error(`无效参数：${tokens[i]}`);
    result[tokens[i].slice(2)] = tokens[i + 1];
  }
  return result;
}
try {
  const [command, id, ...rest] = process.argv.slice(2);
  if (!command || command === '--help') { usage(); process.exit(0); }
  if (command === 'relations') console.log(JSON.stringify(listRelations(options([id, ...rest].filter(Boolean))), null, 2));
  else if (command === 'relation') { const item = getRelation(id); if (!item) throw new Error('关系不存在。'); console.log(JSON.stringify(item, null, 2)); }
  else if (command === 'entity') { const item = getNeighbors(id); if (!item) throw new Error('实体不存在。'); console.log(JSON.stringify(item, null, 2)); }
  else if (command === 'evidence') { const item = getEvidence(id); if (!item) throw new Error('证据不存在。'); console.log(JSON.stringify(item, null, 2)); }
  else { usage(); process.exitCode = 1; }
} catch (error) { console.error(`错误：${error.message}`); process.exitCode = 1; }
