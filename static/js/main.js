console.log('main.js loaded');

// Toast 通知封装，默认替代 window.alert
function notify(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) { window.alert(message); return; }
  const toastEl = document.createElement('div');
  const color = {
    success: 'bg-success text-white',
    danger: 'bg-danger text-white',
    warning: 'bg-warning text-dark',
    info: 'bg-info text-dark'
  }[type] || 'bg-secondary text-white';
  toastEl.className = `toast align-items-center ${color}`;
  toastEl.setAttribute('role', 'alert');
  toastEl.setAttribute('aria-live', 'assertive');
  toastEl.setAttribute('aria-atomic', 'true');
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>`;
  container.appendChild(toastEl);
  const bsToast = new bootstrap.Toast(toastEl, { delay: 2600 });
  bsToast.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}
// 覆盖 alert
window.alert = (msg) => notify(msg, 'warning');

function setStatus(message, type = 'info') {
  const el = document.getElementById('status-indicator');
  if (!el) return;
  const cls = {
    success: 'bg-success',
    info: 'bg-info',
    warning: 'bg-warning text-dark',
    danger: 'bg-danger'
  }[type] || 'bg-secondary';
  el.className = `badge ${cls}`;
  el.innerHTML = `<i class="fas fa-circle"></i> ${message}`;
  const txt = document.getElementById('status-text');
  if (txt) txt.textContent = message;
}

function setSaveStatus(message, type = 'info') {
  const el = document.getElementById('save-status');
  if (!el) return;
  const cls = {
    success: 'text-success',
    info: 'text-muted',
    warning: 'text-warning',
    danger: 'text-danger'
  }[type] || 'text-muted';
  el.className = `mt-1 small ${cls}`;
  el.textContent = message;
}

function setButtonLoading(btn, isLoading, loadingText = '处理中...') {
  if (!btn) return;
  if (isLoading) {
    if (!btn.dataset.originalHtml) btn.dataset.originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>${loadingText}`;
  } else {
    btn.disabled = false;
    if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
  }
}

const input = document.getElementById('input-text');
const charCount = document.getElementById('char-count');
if (input && charCount) {
  input.addEventListener('input', () => {
    charCount.textContent = input.value.length;
  });
}

const appState = {
  lastAnalysis: null,
  currentMode: 'single',
  chart: null,
  selection: { a: null, b: null },
  inflight: { extract: false, expand: false, infer: false, save: false, neo4j: false, batch: false },
  controllers: { expand: null, infer: null, densify: null },
  lastCallAt: { expand: 0, infer: 0, densify: 0 }
};

const AI_COOLDOWN_MS = 3000;
const AI_CACHE_TTL_MS = 5 * 60 * 1000;
const aiCache = new Map();

function makeCacheKey(action, payload) {
  return `${action}:${JSON.stringify(payload)}`;
}

function getCached(key) {
  const hit = aiCache.get(key);
  if (!hit) return null;
  if (Date.now() - hit.ts > AI_CACHE_TTL_MS) { aiCache.delete(key); return null; }
  return hit.value;
}

function setCached(key, value) {
  aiCache.set(key, { ts: Date.now(), value });
}

function canCall(action) {
  const last = appState.lastCallAt[action] || 0;
  const now = Date.now();
  if (now - last < AI_COOLDOWN_MS) {
    notify('请求过于频繁，请稍候再试', 'warning');
    return false;
  }
  appState.lastCallAt[action] = now;
  return true;
}

function normalizeEdge(edge) {
  return {
    source: edge.source || edge.subject || '',
    target: edge.target || edge.object || '',
    relation: edge.relation || edge.type || ''
  };
}

function mergeGraphData(baseGraph, nodes, edges) {
  const merged = baseGraph || { nodes: [], edges: [] };
  const nodeKey = (n) => (n.name || n.id || n.label || '').toString();
  const edgeKey = (e) => `${e.source}||${e.relation}||${e.target}`;
  const nodeMap = new Map((merged.nodes || []).map(n => [nodeKey(n), n]));
  const edgeMap = new Map((merged.edges || []).map(e => [edgeKey(normalizeEdge(e)), e]));

  (nodes || []).forEach(n => {
    const key = nodeKey(n);
    if (!key) return;
    if (!nodeMap.has(key)) nodeMap.set(key, n);
  });
  (edges || []).forEach(e => {
    const ne = normalizeEdge(e);
    if (!ne.source || !ne.target) return;
    const key = edgeKey(ne);
    if (!edgeMap.has(key)) edgeMap.set(key, ne);
  });

  merged.nodes = Array.from(nodeMap.values());
  merged.edges = Array.from(edgeMap.values());
  return merged;
}

function updateProgress(percent, message) {
  const bar = document.getElementById('loading-progress');
  if (bar) bar.style.width = Math.max(0, Math.min(100, percent)) + '%';
  const msg = document.getElementById('loading-message');
  if (msg && message) msg.textContent = message;
}
function showGraphLoading(container) {
  if (!container) return;
  hideGraphLoading(container);
  const overlay = document.createElement('div');
  overlay.className = 'graph-loading-overlay';
  overlay.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.6);z-index:10;';
  overlay.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">加载中...</span></div>';
  container.style.position = 'relative';
  container.appendChild(overlay);
}
function hideGraphLoading(container) {
  if (!container) return;
  const overlay = container.querySelector('.graph-loading-overlay');
  if (overlay) overlay.remove();
}

function renderGraph(graph) {
  const graphContainer = document.getElementById('graph-container');
  if (!graphContainer) return;
  try {
    const existing = (window.echarts && echarts.getInstanceByDom) ? echarts.getInstanceByDom(graphContainer) : null;
    if (existing) existing.dispose();
    if (appState.chart && appState.chart.instance) {
      try { appState.chart.instance.dispose(); } catch(_) {}
    }
    appState.chart = null;
  } catch (_) {}
  graphContainer.innerHTML = '';
  showGraphLoading(graphContainer);

  const typeColor = (t) => {
    const map = {
      '人物': '#ef4444', '地点': '#22c55e', '组织': '#2563eb', '产品': '#f59e0b',
      '概念': '#8b5cf6', '事件': '#06b6d4', '时间': '#84cc16'
    };
    return map[t] || '#4da6ff';
  };

  const rawNodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const rawEdges = Array.isArray(graph.edges) ? graph.edges : [];
  const nodes = rawNodes.filter(n => n && typeof n === 'object');
  const edges = rawEdges.filter(e => e && typeof e === 'object');
  const usableNodes = nodes.filter(n => (n.name || n.id || n.label));
  if (!usableNodes.length) {
    const empty = document.createElement('div');
    empty.className = 'text-muted text-center py-5';
    empty.innerHTML = '<i class="fas fa-info-circle"></i> 暂无图谱数据';
    graphContainer.appendChild(empty);
    hideGraphLoading(graphContainer);
    return;
  }

  const categories = Array.from(new Set(usableNodes.map(n => n.type || n.category || '实体'))).map(name => ({ name }));
  const nodeNameById = new Map();
  usableNodes.forEach(n => {
    if (n && n.id && n.name) nodeNameById.set(String(n.id), String(n.name));
    if (n && n.name) nodeNameById.set(String(n.name), String(n.name));
  });
  const nodeNameSet = new Set();
  const nodeData = usableNodes.map(n => ({
    name: n.name || n.id || n.label,
    value: n.value || 1,
    draggable: true,
    symbolSize: Math.min(44, 12 + (n.value || 1) * 3),
    itemStyle: { color: typeColor(n.type || n.category || '实体') },
    category: n.type || n.category || '实体',
    meta: n
  }));
  nodeData.forEach(n => { if (n && n.name) nodeNameSet.add(String(n.name)); });
  const linkData = edges.map(e => {
    const source = nodeNameById.get(String(e.source)) || e.source || e.subject;
    const target = nodeNameById.get(String(e.target)) || e.target || e.object;
    return {
      source,
      target,
      label: { show: !!(e.label || e.relation), formatter: (e.label || e.relation || '') },
      lineStyle: { curveness: 0.12 },
      meta: e
    };
  }).filter(e => e.source && e.target && nodeNameSet.has(String(e.source)) && nodeNameSet.has(String(e.target)));

  if (window.echarts) {
    try {
      const myChart = echarts.init(graphContainer);
      const option = {
        tooltip: {
          trigger: 'item',
          formatter: (params) => {
            if (params.dataType === 'node') {
              const m = params.data.meta || {};
              return [
                `<b>${m.name || ''}</b>`,
                m.type ? `类型：${m.type}` : '',
                m.description ? `描述：${m.description}` : '',
                m.bloom_level ? `Bloom：${m.bloom_level}` : '',
                m.difficulty ? `难度：${m.difficulty}` : '',
                m.status ? `状态：${m.status}` : ''
              ].filter(Boolean).join('<br>');
            }
            if (params.dataType === 'edge') {
              const m = params.data.meta || {};
              return [
                `<b>${m.source} → ${m.target}</b>`,
                m.relation ? `关系：${m.relation}` : '',
                m.confidence ? `置信度：${m.confidence}` : '',
                m.reasoning ? `推理：${m.reasoning}` : ''
              ].filter(Boolean).join('<br>');
            }
            return params.name || '';
          }
        },
        legend: [{ data: categories.map(c => c.name) }],
        series: [{
          type: 'graph', layout: 'force', roam: true, focusNodeAdjacency: true,
          label: { show: true, position: 'right', fontSize: 12, color: '#333' },
          force: { repulsion: 300, edgeLength: 120, gravity: 0.1 },
          data: nodeData.map(node => ({
            ...node,
            symbolSize: Math.max(20, Math.min(80, node.symbolSize + (node.meta?.difficulty || 0) * 5)), // 根据难度调整体积
            itemStyle: {
              ...node.itemStyle,
              borderWidth: 2,
              borderColor: node.meta?.status === 'active' ? '#ff6b6b' : '#ddd',
              shadowBlur: node.meta?.bloom_level ? 10 : 0,
              shadowColor: node.itemStyle.color
            },
            animationDelay: Math.random() * 1000 // 随机动画延迟
          })),
          links: linkData.map(link => ({
            ...link,
            lineStyle: {
              ...link.lineStyle,
              width: link.meta?.confidence ? Math.max(1, link.meta.confidence * 3) : 1,
              color: link.meta?.status === 'verified' ? '#4CAF50' : '#aaa',
              curveness: 0.2,
              type: 'solid' // 可以改为 'dashed' 表示推理关系
            },
            animation: link.meta?.status === 'new' // 新关系有粒子效果
          })),
          categories,
          emphasis: {
            scale: true,
            lineStyle: { width: 5 },
            label: { show: true, fontSize: 14, fontWeight: 'bold' }
          },
          animationDuration: 1500,
          animationEasingUpdate: 'quinticInOut'
        }]
      };
      myChart.setOption(option, true);
      setTimeout(() => { try { myChart.resize(); } catch(_){} }, 0);
      myChart.off('click');
      myChart.on('click', (params) => {
        if (params && params.dataType === 'node') {
          const name = params.name;
          if (!appState.selection.a || appState.selection.a === name) {
            appState.selection.a = name; appState.selection.b = null;
          } else if (!appState.selection.b || appState.selection.b === name) {
            appState.selection.b = name;
          } else {
            appState.selection.a = name; appState.selection.b = null;
          }
          const status = document.getElementById('selection-status');
          if (status) status.textContent = `当前选择：A=${appState.selection.a || '未选'}，B=${appState.selection.b || '未选'}`;
        }
      });
      appState.chart = { instance: myChart, option, graph };
    } catch (e) {
      console.warn('echarts 渲染失败，使用回退 SVG：', e);
      renderSimpleSVG(graphContainer, graph);
    }
  } else {
    renderSimpleSVG(graphContainer, graph);
  }
  hideGraphLoading(graphContainer);
}
// 暴露渲染函数以便一键演示脚本调用
window.renderGraph = renderGraph;

const modeButtons = {
  single: document.getElementById('mode-single'),
  multi: document.getElementById('mode-multi'),
  qa: document.getElementById('mode-qa')
};
const panels = {
  single: document.getElementById('panel-single'),
  multi: document.getElementById('panel-multi'),
  qa: document.getElementById('panel-qa')
};
function switchMode(mode) {
  appState.currentMode = mode;
  Object.keys(panels).forEach(k => {
    if (!panels[k]) return;
    panels[k].style.display = k === mode ? '' : 'none';
    panels[k].classList.toggle('active', k === mode);
  });
  Object.keys(modeButtons).forEach(k => {
    const btn = modeButtons[k];
    if (btn) btn.classList.toggle('active', k === mode);
  });
  try { localStorage.setItem('mode', mode); } catch(e){}
}
Object.entries(modeButtons).forEach(([mode, btn]) => { if (btn) btn.addEventListener('click', () => switchMode(mode)); });
try { const saved = localStorage.getItem('mode'); if (saved && panels[saved]) switchMode(saved); else switchMode('single'); } catch(e) { switchMode('single'); }
setTimeout(() => {
  const anyVisible = Object.values(panels).some(p => p && getComputedStyle(p).display !== 'none');
  if (!anyVisible && panels.single) switchMode('single');
}, 0);

// 示例加载
const btnExample = document.getElementById('btn-example');
if (btnExample && window.fetch) {
  btnExample.addEventListener('click', () => {
    fetch('/api/examples')
      .then(res => res.json())
      .then(data => {
        const examples = data.examples || data.data || [];
        if (Array.isArray(examples) && examples.length) {
          const first = examples[0];
          const content = first.content || first.text || '';
          document.getElementById('input-text').value = content;
          if (charCount) charCount.textContent = content.length;
          return;
        }
        if (data.data && data.data.extracted && data.data.extracted.sample) {
          const sample = data.data.extracted.sample;
          const content = sample.content || sample.text || '';
          document.getElementById('input-text').value = content;
          if (charCount) charCount.textContent = content.length;
          return;
        }
        alert('未返回示例数据');
      }).catch(() => { alert('加载示例出错'); });
  });
}

// 单文档抽取
const btnExtract = document.getElementById('btn-extract');
if (btnExtract && window.fetch) {
  btnExtract.addEventListener('click', async () => {
    if (appState.inflight.extract) { notify('正在处理，请稍候', 'warning'); return; }
    const text = (document.getElementById('input-text') || {}).value || '';
    if (!text.trim()) { notify('请输入要分析的文本', 'warning'); setStatus('请输入文本', 'warning'); return; }
    try {
      appState.inflight.extract = true;
      setButtonLoading(btnExtract, true, '分析中...');
      const t0 = performance.now();
      const modalEl = document.getElementById('loading-modal');
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
      updateProgress(10, '正在提交分析请求...');
      const res = await fetch('/api/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
      updateProgress(45, '分析中，请稍候...');
      const data = await res.json();
      updateProgress(70, '分析完成，正在渲染图谱...');
      if (!data || !data.success) { modal.hide(); notify('抽取失败：' + (data && data.error ? data.error : '未知错误'), 'danger'); setStatus('抽取失败', 'danger'); return; }
      const extracted = data.data.extracted || { entities: [], relations: [] };
      const warnings = data.data.warnings || [];
      const graph = data.data.graph || { nodes: [], edges: [] };
      appState.lastAnalysis = data.data;
      document.getElementById('entity-count').textContent = (extracted.entities || []).length;
      document.getElementById('relation-count').textContent = (extracted.relations || []).length;
      const entitiesTable = document.getElementById('entities-table');
      const relationsTable = document.getElementById('relations-table');
      if (entitiesTable) {
        entitiesTable.innerHTML = '';
        (extracted.entities || []).forEach((e, i) => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${e.name || ''}</td><td>${e.type || ''}</td><td>${e.id || i}</td><td>${e.score || ''}</td>`;
          entitiesTable.appendChild(tr);
        });
      }
      if (relationsTable) {
        relationsTable.innerHTML = '';
        (extracted.relations || []).forEach(rel => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${rel.subject || ''}</td><td>${rel.relation || ''}</td><td>${rel.object || ''}</td>`;
          relationsTable.appendChild(tr);
        });
      }
      const jsonOutput = document.getElementById('json-output');
      if (jsonOutput) jsonOutput.textContent = JSON.stringify(data.data, null, 2);
      renderGraph(graph);
      if (warnings.length) {
        notify(warnings.join('；'), 'warning');
      }
      updateProgress(100, '完成');
      setTimeout(() => { try { modal.hide(); } catch(_){} }, 200);
      setStatus(`构建完成，用时 ${(performance.now()-t0).toFixed(0)} ms`, 'success');
    } catch (err) {
      try { document.getElementById('loading-modal') && bootstrap.Modal.getInstance(document.getElementById('loading-modal')).hide(); } catch(e){}
      notify('抽取过程出错：' + (err && err.message ? err.message : err), 'danger');
      setStatus('构建失败', 'danger');
    } finally {
      appState.inflight.extract = false;
      setButtonLoading(btnExtract, false);
    }
  });
}

// 清空
const btnClear = document.getElementById('btn-clear');
if (btnClear) {
  btnClear.addEventListener('click', () => {
    if (input) input.value = '';
    if (charCount) charCount.textContent = '0';
    document.getElementById('entity-count') && (document.getElementById('entity-count').textContent = '0');
    document.getElementById('relation-count') && (document.getElementById('relation-count').textContent = '0');
    const entitiesTable = document.getElementById('entities-table');
    const relationsTable = document.getElementById('relations-table');
    const jsonOutput = document.getElementById('json-output');
    entitiesTable && (entitiesTable.innerHTML = '');
    relationsTable && (relationsTable.innerHTML = '');
    jsonOutput && (jsonOutput.textContent = '');
    const graphContainer = document.getElementById('graph-container');
    graphContainer && (graphContainer.innerHTML = '');
    appState.lastAnalysis = null;
  });
}

// 图谱重置与导出
const btnResetView = document.getElementById('btn-reset-view');
const btnExportGraph = document.getElementById('btn-export-graph');
const btnAiExpand = document.getElementById('btn-ai-expand-node');
const btnAiInfer = document.getElementById('btn-ai-infer-edge');
const btnSaveGraph = document.getElementById('btn-save-graph');
const btnNeo4jLoad = document.getElementById('btn-neo4j-load');
if (btnResetView) {
  btnResetView.addEventListener('click', () => {
    if (appState.chart && appState.chart.graph) {
      renderGraph(appState.chart.graph);
    } else if (appState.chart && appState.chart.instance && appState.chart.option) {
      appState.chart.instance.clear();
      appState.chart.instance.setOption(appState.chart.option, true);
      try { appState.chart.instance.resize(); } catch(_) {}
    }
  });
}
if (btnExportGraph) {
  btnExportGraph.addEventListener('click', () => {
    try {
      if (appState.chart && appState.chart.instance) {
        const url = appState.chart.instance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' });
        const a = document.createElement('a');
        a.href = url; a.download = 'knowledge_graph.png';
        document.body.appendChild(a); a.click(); a.remove();
      } else {
        alert('当前图谱不可导出');
      }
    } catch(e) { alert('导出失败：' + e.message); }
  });
}

// AI 扩展：选中节点
if (btnAiExpand) {
  btnAiExpand.addEventListener('click', async () => {
    if (appState.inflight.expand) {
      if (appState.controllers.expand) appState.controllers.expand.abort();
      notify('已取消上一次扩展请求', 'warning');
      return;
    }
    if (!canCall('expand')) return;
    const concept = appState.selection.a;
    if (!concept) { notify('请先在图上选择一个节点', 'warning'); return; }
    const payload = { concept, max_depth: 2 };
    const key = makeCacheKey('expand', payload);
    const cached = getCached(key);
    if (cached) {
      const merged = mergeGraphData(appState.lastAnalysis ? appState.lastAnalysis.graph : null, cached.nodes, cached.edges);
      appState.lastAnalysis = appState.lastAnalysis || {};
      appState.lastAnalysis.graph = merged;
      renderGraph(merged);
      setStatus('层级扩充完成（缓存命中）', 'success');
      notify('层级扩充完成（缓存命中）', 'success');
      return;
    }
    try {
      appState.inflight.expand = true;
      setButtonLoading(btnAiExpand, true, '扩展中...');
      const controller = new AbortController();
      appState.controllers.expand = controller;
      const res = await fetch('/api/expand_taxonomy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      const d = await res.json();
      if (!d || !d.success) { notify('层级扩充失败：' + (d && d.error ? d.error : '未知错误'), 'danger'); return; }
      const extraction = d.extraction || {};
      const nodes = extraction.nodes || [];
      const edges = extraction.edges || [];
      setCached(key, { nodes, edges });
      const merged = mergeGraphData(appState.lastAnalysis ? appState.lastAnalysis.graph : null, nodes, edges);
      appState.lastAnalysis = appState.lastAnalysis || {};
      appState.lastAnalysis.graph = merged;
      renderGraph(merged);
      const ec = document.getElementById('entity-count');
      const rc = document.getElementById('relation-count');
      if (ec) ec.textContent = merged.nodes.length;
      if (rc) rc.textContent = merged.edges.length;
      setStatus('层级扩充完成', 'success');
      notify(`已扩展：新增节点 ${nodes.length}，新增边 ${edges.length}`, 'success');
    } catch (e) {
      if (e && e.name === 'AbortError') return;
      notify('层级扩充出错：' + e.message, 'danger');
    } finally {
      appState.inflight.expand = false;
      appState.controllers.expand = null;
      setButtonLoading(btnAiExpand, false);
    }
  });
}

// AI 关系推理：选中两个节点
if (btnAiInfer) {
  btnAiInfer.addEventListener('click', async () => {
    if (appState.inflight.infer) {
      if (appState.controllers.infer) appState.controllers.infer.abort();
      notify('已取消上一次推理请求', 'warning');
      return;
    }
    if (!canCall('infer')) return;
    const a = appState.selection.a;
    const b = appState.selection.b;
    if (!a || !b) { notify('请在图上选择两个节点', 'warning'); return; }
    const payload = { a, b };
    const key = makeCacheKey('infer', payload);
    const cached = getCached(key);
    if (cached) {
      const merged = mergeGraphData(appState.lastAnalysis ? appState.lastAnalysis.graph : null, cached.nodes, cached.edges);
      appState.lastAnalysis = appState.lastAnalysis || {};
      appState.lastAnalysis.graph = merged;
      renderGraph(merged);
      setStatus('关系推理完成（缓存命中）', 'success');
      notify('关系推理完成（缓存命中）', 'success');
      return;
    }
    try {
      appState.inflight.infer = true;
      setButtonLoading(btnAiInfer, true, '推理中...');
      const controller = new AbortController();
      appState.controllers.infer = controller;
      const res = await fetch('/api/infer_prerequisite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      const d = await res.json();
      if (!d || !d.success) { notify('关系推理失败：' + (d && d.error ? d.error : '未知错误'), 'danger'); return; }
      const edges = d.edges || [];
      const nodes = [ { name: a, type: 'Concept' }, { name: b, type: 'Concept' } ];
      setCached(key, { nodes, edges });
      if (edges.length) {
        const merged = mergeGraphData(appState.lastAnalysis ? appState.lastAnalysis.graph : null, nodes, edges);
        appState.lastAnalysis = appState.lastAnalysis || {};
        appState.lastAnalysis.graph = merged;
        renderGraph(merged);
        const rc = document.getElementById('relation-count');
        if (rc) rc.textContent = merged.edges.length;
      }
      const judge = d.judge || {};
      const msg = judge.is_prerequisite ? '判定为前置关系' : '非前置关系';
      setStatus(`关系推理完成：${msg}`, 'success');
      notify(`关系推理完成：${msg}`, judge.is_prerequisite ? 'success' : 'info');
    } catch (e) {
      if (e && e.name === 'AbortError') return;
      notify('关系推理出错：' + e.message, 'danger');
    } finally {
      appState.inflight.infer = false;
      appState.controllers.infer = null;
      setButtonLoading(btnAiInfer, false);
    }
  });
}

// 从 Neo4j 拉取子图
if (btnNeo4jLoad) {
  btnNeo4jLoad.addEventListener('click', async () => {
    if (appState.inflight.neo4j) { notify('正在读取 Neo4j，请稍候', 'warning'); return; }
    const center = (document.getElementById('neo4j-center') || {}).value || '';
    const depthInput = (document.getElementById('neo4j-depth') || {}).value || '1';
    const depth = Math.max(0, Math.min(5, parseInt(depthInput || '1', 10)));
    const lnInput = (document.getElementById('neo4j-limit-nodes') || {}).value || '200';
    const leInput = (document.getElementById('neo4j-limit-edges') || {}).value || '800';
    const limitNodes = Math.max(10, Math.min(2000, parseInt(lnInput || '200', 10)));
    const limitEdges = Math.max(10, Math.min(5000, parseInt(leInput || '800', 10)));
    const includeProps = !!(document.getElementById('neo4j-include-props') && document.getElementById('neo4j-include-props').checked);
    try {
      appState.inflight.neo4j = true;
      setButtonLoading(btnNeo4jLoad, true, '加载中...');
      const t0 = performance.now();
      const params = new URLSearchParams();
      if (center) params.append('center', center);
      params.append('depth', depth.toString());
      params.append('limit_nodes', String(limitNodes));
      params.append('limit_edges', String(limitEdges));
      if (includeProps) params.append('include_props', '1');
      const res = await fetch('/api/neo4j/subgraph?' + params.toString());
      const d = await res.json();
      if (!d || !d.success) { notify('读取失败：' + (d && d.error ? d.error : '未知错误'), 'danger'); setStatus('Neo4j 读取失败', 'danger'); return; }
      const graph = { nodes: d.nodes || [], edges: d.edges || [] };
      appState.lastAnalysis = appState.lastAnalysis || {};
      appState.lastAnalysis.graph = graph;
      renderGraph(graph);
      const ec = document.getElementById('entity-count');
      const rc = document.getElementById('relation-count');
      if (ec) ec.textContent = graph.nodes.length;
      if (rc) rc.textContent = graph.edges.length;
      notify(`已读取子图：节点 ${graph.nodes.length}，边 ${graph.edges.length}`, 'success');
      setStatus(`Neo4j 读取完成，用时 ${(performance.now()-t0).toFixed(0)} ms`, 'success');
    } catch (e) {
      notify('读取出错：' + e.message, 'danger');
      setStatus('Neo4j 读取失败', 'danger');
    } finally {
      appState.inflight.neo4j = false;
      setButtonLoading(btnNeo4jLoad, false);
    }
  });
}

// 保存图谱到后端/Neo4j
if (btnSaveGraph) {
  btnSaveGraph.addEventListener('click', async () => {
    if (appState.inflight.save) { notify('正在保存，请稍候', 'warning'); return; }
    const la = appState.lastAnalysis || {};
    const nodes = (la.extracted && la.extracted.nodes) || (la.graph && la.graph.nodes) || [];
    const edges = (la.extracted && la.extracted.edges) || (la.graph && la.graph.edges) || [];
    if (!nodes.length && !edges.length) { notify('当前无可保存的图谱', 'warning'); setStatus('保存失败：图谱为空', 'warning'); setSaveStatus('最近保存/入库：图谱为空', 'warning'); return; }
    try {
      appState.inflight.save = true;
      setButtonLoading(btnSaveGraph, true, '保存中...');
      const t0 = performance.now();
      const payload = { nodes, edges };
      const res = await fetch('/api/save_graph', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const d = await res.json();
      if (d && d.success) {
        notify(`保存成功：节点 ${d.saved_nodes || 0} 个，边 ${d.saved_edges || 0} 条`, 'success');
        setStatus(`保存成功，用时 ${(performance.now()-t0).toFixed(0)} ms`, 'success');
        const ts = new Date().toLocaleTimeString();
        setSaveStatus(`最近保存/入库：节点 ${d.saved_nodes || 0}，边 ${d.saved_edges || 0}（${ts}）`, 'success');
      }
      else {
        notify('保存失败：' + (d && d.error ? d.error : '未知错误'), 'danger');
        setStatus('保存失败', 'danger');
        setSaveStatus(`最近保存/入库失败：${d && d.error ? d.error : '未知错误'}`, 'danger');
      }
    } catch (e) {
      notify('保存出错：' + e.message, 'danger');
      setStatus('保存失败', 'danger');
      setSaveStatus(`最近保存/入库失败：${e.message}`, 'danger');
    } finally {
      appState.inflight.save = false;
      setButtonLoading(btnSaveGraph, false);
    }
  });
}

// 导出报告
const btnExportReport = document.getElementById('btn-export-report');
if (btnExportReport) {
  btnExportReport.addEventListener('click', async () => {
    if (!appState.lastAnalysis || !appState.lastAnalysis.extracted) { alert('请先完成一次分析再导出报告'); return; }
    const format = window.prompt('选择导出格式：json / pdf / word', 'json');
    if (!format) return;
    const payload = { format: format.toLowerCase(), data: appState.lastAnalysis.extracted, mode: appState.currentMode };
    try {
      updateProgress(30, '正在生成文件...');
      const res = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const ct = res.headers.get('Content-Type') || '';
      if (ct.includes('application/json')) {
        const d = await res.json();
        if (d && d.success) alert('导出成功'); else alert('导出失败：' + (d && d.error ? d.error : '未知错误'));
      } else {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const filename = payload.format === 'pdf' ? 'analysis_report.pdf' : (payload.format === 'word' ? 'analysis_report.doc' : 'analysis_report.bin');
        a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      }
    } catch (e) { alert('导出失败：' + e.message); }
  });
}

const btnMultiExportReport = document.getElementById('btn-multi-export-report');
if (btnMultiExportReport) {
  btnMultiExportReport.addEventListener('click', async () => {
    if (!appState.lastAnalysis || !appState.lastAnalysis.extracted) { alert('请先完成一次多文档分析再导出'); return; }
    const format = window.prompt('选择导出格式：json / pdf / word', 'pdf');
    if (!format) return;
    const payload = { format: format.toLowerCase(), data: appState.lastAnalysis.extracted, mode: 'multi' };
    const modalEl = document.getElementById('loading-modal');
    const modal = modalEl ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;
    if (modal) modal.show();
    try {
      updateProgress(20, '准备导出...');
      const res = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const ct = res.headers.get('Content-Type') || '';
      if (ct.includes('application/json')) {
        const d = await res.json();
        if (d && d.success) { updateProgress(100, '导出完成'); alert('导出成功'); }
        else { alert('导出失败：' + (d && d.error ? d.error : '未知错误')); }
      } else {
        updateProgress(70, '正在生成文件...');
        const blob = await res.blob();
        updateProgress(90, '正在保存文件...');
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const filename = 'multi_analysis_report.' + (payload.format === 'pdf' ? 'pdf' : (payload.format === 'word' ? 'doc' : 'json'));
        a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
        updateProgress(100, '导出完成');
      }
    } catch (e) { alert('导出失败：' + e.message); }
    setTimeout(() => { try { modal.hide(); } catch(_){} }, 250);
  });
}

// 多文档批量处理
const multiFileInput = document.getElementById('multi-file-input');
const btnMultiAnalyze = document.getElementById('btn-multi-analyze');
const btnMultiClear = document.getElementById('btn-multi-clear');
const btnMultiExportMerged = document.getElementById('btn-multi-export-merged');
const btnMultiEnqueue = document.getElementById('btn-multi-enqueue');
const btnMultiCheck = document.getElementById('btn-multi-check');
const btnMultiDownload = document.getElementById('btn-multi-download');
const perFileTable = document.getElementById('multi-per-file');
const multiResults = document.getElementById('multi-analysis-results');
const multiQueueStatus = document.getElementById('multi-queue-status');
const multiFileHint = document.getElementById('multi-file-hint');
const multiFileList = document.getElementById('multi-file-list');
const multiUploadBar = document.getElementById('multi-upload-bar');
const multiUploadText = document.getElementById('multi-upload-text');
const multiQueueBar = document.getElementById('multi-queue-bar');
const multiQueueText = document.getElementById('multi-queue-text');
let currentBatchJobId = null;
let batchPollTimer = null;
let currentBatchOutputPath = null;

function setUploadProgress(percent, message, state = 'info') {
  if (multiUploadBar) {
    const pct = Math.max(0, Math.min(100, percent));
    multiUploadBar.style.width = pct + '%';
    multiUploadBar.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-info');
    const cls = {
      success: 'bg-success',
      warning: 'bg-warning',
      danger: 'bg-danger',
      info: 'bg-info'
    }[state] || 'bg-info';
    multiUploadBar.classList.add(cls);
  }
  if (multiUploadText) {
    multiUploadText.textContent = message || `上传进度：${Math.round(percent)}%`;
  }
}

function uploadWithProgress(url, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.onreadystatechange = () => {
      if (xhr.readyState === 4) {
        const ok = xhr.status >= 200 && xhr.status < 300;
        const text = xhr.responseText || '';
        if (!ok) return reject(new Error(text || `HTTP ${xhr.status}`));
        try {
          resolve(JSON.parse(text));
        } catch (e) {
          reject(new Error('响应解析失败'));
        }
      }
    };
    xhr.onerror = () => reject(new Error('上传失败'));
    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          const pct = Math.round((evt.loaded / evt.total) * 100);
          onProgress(pct);
        }
      };
    }
    xhr.send(formData);
  });
}

function setQueueStatus(text, type = 'info') {
  if (!multiQueueStatus) return;
  const cls = {
    success: 'text-success',
    info: 'text-muted',
    warning: 'text-warning',
    danger: 'text-danger'
  }[type] || 'text-muted';
  multiQueueStatus.className = `mt-2 text-muted small ${cls}`;
  multiQueueStatus.textContent = text;
}

function setQueueProgress(percent, message, state = 'info') {
  if (multiQueueBar) {
    const pct = Math.max(0, Math.min(100, percent));
    multiQueueBar.style.width = pct + '%';
    multiQueueBar.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-info');
    const cls = {
      success: 'bg-success',
      warning: 'bg-warning',
      danger: 'bg-danger',
      info: 'bg-info'
    }[state] || 'bg-info';
    multiQueueBar.classList.add(cls);
  }
  if (multiQueueText) {
    multiQueueText.textContent = message || `队列进度：${Math.round(percent)}%`;
  }
}

async function fetchBatchStatus(jobId) {
  const res = await fetch(`/api/batch_status?job_id=${encodeURIComponent(jobId)}`);
  const data = await res.json();
  if (!data || !data.success) throw new Error(data && data.error ? data.error : '查询失败');
  return data.job;
}

async function pollBatch(jobId) {
  if (!jobId) return;
  try {
    const job = await fetchBatchStatus(jobId);
    const total = job.total || 0;
    const processed = job.processed || 0;
    const pct = total ? Math.round((processed / total) * 100) : 0;
    if (job.status === 'queued') {
      setQueueStatus(`队列状态：排队中（${job.processed || 0}/${job.total}）`, 'info');
      setQueueProgress(pct, `队列进度：${processed}/${total}`, 'info');
      return;
    }
    if (job.status === 'running') {
      setQueueStatus(`队列状态：处理中（${job.processed || 0}/${job.total}）`, 'info');
      setQueueProgress(pct, `队列进度：${processed}/${total}`, 'info');
      return;
    }
    if (job.status === 'error') {
      setQueueStatus(`队列失败：${job.error || '未知错误'}`, 'danger');
      setQueueProgress(pct, '队列失败', 'danger');
      if (batchPollTimer) { clearInterval(batchPollTimer); batchPollTimer = null; }
      return;
    }
    if (job.status === 'done') {
      setQueueStatus('队列完成：已生成结果', 'success');
      setQueueProgress(100, '队列进度：100%', 'success');
      if (batchPollTimer) { clearInterval(batchPollTimer); batchPollTimer = null; }
      currentBatchOutputPath = job.output_path || null;
      if (btnMultiDownload) btnMultiDownload.disabled = !currentBatchOutputPath;
      const result = job.result;
      if (result) {
        const merged = result.merged || { nodes: [], edges: [] };
        const graph = result.graph || { nodes: [], edges: [] };
        const stats = result.stats || {};
        const perFile = result.per_file || [];
        appState.lastAnalysis = { extracted: merged, graph, stats, per_file: perFile };

        if (multiResults) {
          multiResults.innerHTML = `
            <div class="alert alert-success">
              队列处理完成：${stats.processed || 0}/${stats.files || 0} 个文件；节点 ${stats.nodes || merged.nodes.length} 个，边 ${stats.edges || merged.edges.length} 条。
            </div>`;
        }
        if (perFileTable) {
          perFileTable.innerHTML = '';
          if (!perFile.length) {
            perFileTable.innerHTML = '<tr><td colspan="5" class="text-muted">暂无明细</td></tr>';
          } else {
            perFile.forEach(item => {
              const tr = document.createElement('tr');
              const badge = item.success ? 'success' : 'danger';
              const statusText = item.success ? '成功' : '失败';
              tr.innerHTML = `
                <td>${item.filename || ''}</td>
                <td><span class="badge bg-${badge}">${statusText}</span></td>
                <td>${item.nodes ?? '-'}</td>
                <td>${item.edges ?? '-'}</td>
                <td>${item.error || ''}</td>`;
              perFileTable.appendChild(tr);
            });
          }
        }

        switchMode('single');
        renderGraph(graph);
        document.getElementById('entity-count').textContent = (merged.nodes || []).length;
        document.getElementById('relation-count').textContent = (merged.edges || []).length;
        const jsonOutput = document.getElementById('json-output');
        jsonOutput && (jsonOutput.textContent = JSON.stringify({ merged, graph, stats, per_file: perFile }, null, 2));
      }
    }
  } catch (e) {
    setQueueStatus(`队列查询失败：${e.message}`, 'danger');
    if (batchPollTimer) { clearInterval(batchPollTimer); batchPollTimer = null; }
  }
}
if (btnMultiAnalyze && multiFileInput) {
  btnMultiAnalyze.addEventListener('click', async () => {
    if (appState.inflight.batch) { notify('正在批量处理，请稍候', 'warning'); return; }
    const files = Array.from(multiFileInput.files || []);
    if (!files.length) { notify('请先选择要上传的文档', 'warning'); return; }
    const modalEl = document.getElementById('loading-modal');
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
    updateProgress(8, `准备分析，共 ${files.length} 个文件...`);
    try {
      appState.inflight.batch = true;
      setButtonLoading(btnMultiAnalyze, true, '入队中...');
      const fd = new FormData();
      files.forEach(f => fd.append('files', f));
      updateProgress(25, '正在上传并入队...');
      setUploadProgress(0, '上传进度：0%', 'info');
      const d = await uploadWithProgress('/api/batch_enqueue', fd, (pct) => {
        setUploadProgress(pct, `上传进度：${pct}%`, pct >= 100 ? 'success' : 'info');
      });
      if (!d || !d.success) { notify('多文档入队失败：' + (d && d.error ? d.error : '未知错误'), 'danger'); return; }

      currentBatchJobId = d.job_id;
      currentBatchOutputPath = null;
      if (btnMultiDownload) btnMultiDownload.disabled = true;

      updateProgress(70, '已入队，后台处理中...');
      setUploadProgress(100, '上传完成：100%', 'success');
      setQueueStatus(`已入队：${currentBatchJobId}`, 'info');
      setQueueProgress(0, '队列进度：0%', 'info');
      if (multiResults) {
        multiResults.innerHTML = `
          <div class="alert alert-info">
            已入队，后台处理中。你可以点击“查询状态”或等待自动刷新。
          </div>`;
      }
      if (perFileTable) {
        perFileTable.innerHTML = '<tr><td colspan="5" class="text-muted">处理中，稍后刷新结果</td></tr>';
      }
      if (batchPollTimer) clearInterval(batchPollTimer);
      batchPollTimer = setInterval(() => pollBatch(currentBatchJobId), 2000);
      updateProgress(100, '处理中');
    } catch (e) {
      const msg = e && e.name === 'AbortError' ? '多文档入队超时，请减少文件数量或稍后重试' : ('多文档入队失败：' + e.message);
      notify(msg, 'danger');
      setUploadProgress(0, '上传失败', 'danger');
    } finally {
      try { if (modal) modal.hide(); } catch(_){}
      appState.inflight.batch = false;
      setButtonLoading(btnMultiAnalyze, false);
    }
  });
}

if (btnMultiEnqueue && multiFileInput) {
  btnMultiEnqueue.addEventListener('click', async () => {
    const files = Array.from(multiFileInput.files || []);
    if (!files.length) { notify('请先选择要上传的文档', 'warning'); return; }
    try {
      setButtonLoading(btnMultiEnqueue, true, '入队中...');
      const fd = new FormData();
      files.forEach(f => fd.append('files', f));
      setUploadProgress(0, '上传进度：0%', 'info');
      const d = await uploadWithProgress('/api/batch_enqueue', fd, (pct) => {
        setUploadProgress(pct, `上传进度：${pct}%`, pct >= 100 ? 'success' : 'info');
      });
      if (!d || !d.success) { notify('入队失败：' + (d && d.error ? d.error : '未知错误'), 'danger'); return; }
      currentBatchJobId = d.job_id;
      currentBatchOutputPath = null;
      if (btnMultiDownload) btnMultiDownload.disabled = true;
      setQueueStatus(`已入队：${currentBatchJobId}`, 'info');
      setQueueProgress(0, '队列进度：0%', 'info');
      if (batchPollTimer) clearInterval(batchPollTimer);
      batchPollTimer = setInterval(() => pollBatch(currentBatchJobId), 2000);
    } catch (e) {
      notify('入队出错：' + e.message, 'danger');
      setUploadProgress(0, '上传失败', 'danger');
    } finally {
      setButtonLoading(btnMultiEnqueue, false);
    }
  });
}

if (btnMultiCheck) {
  btnMultiCheck.addEventListener('click', async () => {
    if (!currentBatchJobId) { notify('暂无任务，请先入队', 'warning'); return; }
    await pollBatch(currentBatchJobId);
  });
}

if (btnMultiDownload) {
  btnMultiDownload.addEventListener('click', () => {
    if (!currentBatchJobId) { notify('暂无任务结果可下载', 'warning'); return; }
    window.open(`/api/batch_download?job_id=${encodeURIComponent(currentBatchJobId)}`, '_blank');
  });
}
if (btnMultiClear && multiFileInput && perFileTable) {
  btnMultiClear.addEventListener('click', () => {
    multiFileInput.value = '';
    perFileTable.innerHTML = '<tr><td colspan="5" class="text-muted">尚无结果</td></tr>';
    if (multiResults) multiResults.innerHTML = '';
    if (multiFileHint) multiFileHint.textContent = '已选择 0 个文件';
    if (multiFileList) multiFileList.textContent = '';
    setUploadProgress(0, '上传进度：0%', 'info');
    setQueueStatus('队列状态：暂无', 'info');
    setQueueProgress(0, '队列进度：0%', 'info');
  });
}

if (multiFileInput) {
  multiFileInput.addEventListener('change', () => {
    const files = Array.from(multiFileInput.files || []);
    const names = files.map(f => f.name);
    const dupes = names.filter((n, i) => names.indexOf(n) !== i);
    if (multiFileHint) multiFileHint.textContent = `已选择 ${files.length} 个文件${dupes.length ? '（检测到同名文件）' : ''}`;
    if (multiFileList) {
      multiFileList.textContent = files.map(f => `${f.name} (${Math.round(f.size / 1024)} KB)`).join(' | ');
    }
    if (dupes.length) {
      notify('检测到同名文件：' + Array.from(new Set(dupes)).join('、') + '。服务端会用时间戳避免覆盖', 'warning');
    }
    setUploadProgress(0, '上传进度：0%', 'info');
  });
}
if (btnMultiExportMerged) {
  btnMultiExportMerged.addEventListener('click', () => {
    const la = appState.lastAnalysis;
    if (!la || !la.extracted) { alert('请先完成一次多文档批量分析'); return; }
    const payload = { merged: la.extracted, stats: la.stats, per_file: la.per_file };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'merged_results.json';
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  });
}

// 智能问答
const btnQaAsk = document.getElementById('btn-qa-ask');
const qaInput = document.getElementById('qa-input');
if (btnQaAsk && qaInput) {
  btnQaAsk.addEventListener('click', async () => {
    const q = qaInput.value.trim();
    if (!q) { alert('请输入问题'); return; }
    try {
      const res = await fetch('/api/qa', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, knowledge: appState.lastAnalysis ? appState.lastAnalysis.extracted : null }) });
      const d = await res.json();
      if (d && d.success) {
        document.getElementById('qa-results').innerHTML = `
          <div class="card">
            <div class="card-body">
              <h5>答案</h5>
              <p>${(d.result && d.result.answer) || ''}</p>
              <h6 class="mt-3">推理链路</h6>
              <pre class="bg-light p-2 border rounded">${(d.result && d.result.reasoning) || ''}</pre>
            </div>
          </div>`;
      } else {
        alert('问答失败：' + (d && d.error ? d.error : '未知错误'));
      }
    } catch (e) { alert('问答出错：' + e.message); }
  });
}

// 简单 SVG 回退
function renderSimpleSVG(container, graph) {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const w = container.clientWidth || 600;
  const h = container.clientHeight || 400;
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', w);
  svg.setAttribute('height', h);
  svg.style.background = '#fff';
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 3;
  nodes.forEach((n, i) => { const angle = (i / nodes.length) * Math.PI * 2; n._x = cx + r * Math.cos(angle); n._y = cy + r * Math.sin(angle); });
  edges.forEach(e => {
    const source = nodes.find(n => n.id == e.source || n.name == e.source);
    const target = nodes.find(n => n.id == e.target || n.name == e.target);
    if (!source || !target) return;
    const line = document.createElementNS(svgNS, 'line');
    line.setAttribute('x1', source._x); line.setAttribute('y1', source._y);
    line.setAttribute('x2', target._x); line.setAttribute('y2', target._y);
    line.setAttribute('stroke', '#999');
    svg.appendChild(line);
  });
  nodes.forEach(n => {
    const g = document.createElementNS(svgNS, 'g');
    const circle = document.createElementNS(svgNS, 'circle');
    circle.setAttribute('cx', n._x); circle.setAttribute('cy', n._y); circle.setAttribute('r', 18); circle.setAttribute('fill', '#4da6ff'); circle.setAttribute('stroke', '#333');
    g.appendChild(circle);
    const text = document.createElementNS(svgNS, 'text');
    text.setAttribute('x', n._x); text.setAttribute('y', n._y + 4); text.setAttribute('text-anchor', 'middle'); text.setAttribute('font-size', '12'); text.setAttribute('fill', '#fff');
    text.textContent = n.name || n.id || '';
    g.appendChild(text);
    svg.appendChild(g);
  });
  container.appendChild(svg);
}

// 复制 / 导出 JSON
const btnCopyJson = document.getElementById('btn-copy-json');
if (btnCopyJson) {
  btnCopyJson.addEventListener('click', () => {
    const jsonText = document.getElementById('json-output').textContent || '';
    navigator.clipboard && navigator.clipboard.writeText(jsonText).then(() => { alert('JSON 已复制到剪贴板'); }).catch(() => { alert('复制失败'); });
  });
}
const btnExportJson = document.getElementById('btn-export-json');
if (btnExportJson) {
  btnExportJson.addEventListener('click', () => {
    const jsonText = document.getElementById('json-output').textContent || '';
    const blob = new Blob([jsonText], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'extraction_result.json';
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  });
}
