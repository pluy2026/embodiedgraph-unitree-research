async function applyFilters() {
  const type = document.querySelector('#type').value;
  const status = document.querySelector('#status').value;
  const min = document.querySelector('#minConfidence').value.trim();
  const params = new URLSearchParams({ page_size: '100' });
  if (type) params.set('relationship_type', type);
  if (status) params.set('status', status);
  if (min) params.set('min_confidence', min);
  const data = await api(`/relationships?${params.toString()}`);
  const confirmed = data.items.filter(item => item.status === 'confirmed').length;
  const unknown = data.items.filter(item => item.status === 'unknown').length;
  document.querySelector('#count').textContent = `${data.total} 条`;
  document.querySelector('#graph').innerHTML = `<span class="node">${data.total} 条关系</span><span class="node">${confirmed} 条已确认</span><span class="node">${unknown} 条未知</span>`;
  document.querySelector('#results').innerHTML = data.items.map(card).join('') || '<p>没有符合当前筛选条件的关系。</p>';
}
document.querySelector('#apply').addEventListener('click', () => applyFilters().catch(error => { document.querySelector('#results').textContent = error.message; }));
