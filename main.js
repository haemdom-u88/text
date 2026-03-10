/**
 * 主JavaScript文件 - 处理前端交互
 */

// 全局变量
let chartInstance = null;
let currentData = null;
let examples = [];

// DOM加载完成后执行
$(document).ready(function() {
        // 单文档导出分析报告
        $('#btn-export-report').click(function() {
            exportAnalysisReport(currentData, 'single');
        });
        // 多文档导出分析报告
        $('#btn-multi-export-report').click(function() {
            if (window.allEntities && window.allRelations) {
                exportAnalysisReport({entities: Object.values(window.allEntities), relations: Object.values(window.allRelations)}, 'multi');
            } else {
                showToast('请先完成多文档分析', 'warning');
            }
        });
    // 导出分析报告（PDF/Word，默认PDF）
    function exportAnalysisReport(data, mode) {
        if (!data) {
            showToast('暂无可导出的分析结果', 'warning');
            return;
        }
        // 可扩展导出格式选择，这里默认PDF
        $.ajax({
            url: '/api/export',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ format: 'pdf', data: data, mode: mode }),
            xhrFields: { responseType: 'blob' },
            success: function(blob, status, xhr) {
                const disposition = xhr.getResponseHeader('Content-Disposition');
                let filename = 'analysis_report.pdf';
                if (disposition && disposition.indexOf('filename=') !== -1) {
                    filename = decodeURIComponent(disposition.split('filename=')[1]);
                }
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                showToast('分析报告已导出', 'success');
            },
            error: function(xhr) {
                showToast('导出失败: ' + (xhr.responseJSON?.error || '未知错误'), 'error');
            }
        });
    }
    // 初始化
    init();

    // 绑定事件
    bindEvents();

    // 检查系统状态
    checkSystemStatus();

    // 加载示例
    loadExamples();

    // 模式切换逻辑
    $('.mode-panel').hide();
    $('#panel-single').show(); // 默认显示单文档分析
    $('.btn-group [data-mode]').removeClass('active');
    $('#mode-single').addClass('active');

    $('.btn-group [data-mode]').click(function() {
        var mode = $(this).data('mode');
        $('.mode-panel').hide();
        $('#panel-' + mode).show();
        $('.btn-group [data-mode]').removeClass('active');
        $(this).addClass('active');

        // 智能问答按钮事件
        $('#btn-qa-ask').click(function() {
            handleQAAsk();
        });
    });
// 智能问答主流程
function handleQAAsk() {
    const question = $('#qa-input').val().trim();
    if (!question) {
        showToast('请输入您的问题', 'warning');
        return;
    }
    $('#qa-results').html('<div class="text-info">正在推理，请稍候...</div>');

    // 默认用多文档整合知识库（如有）
    let knowledge = null;
    if (window.allEntities && window.allRelations) {
        knowledge = {
            entities: Object.values(window.allEntities),
            relations: Object.values(window.allRelations)
        };
    } else if (currentData && currentData.extracted) {
        knowledge = currentData.extracted;
    }

    $.ajax({
        url: '/api/qa',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ question: question, knowledge: knowledge }),
        success: function(response) {
            if (response.success) {
                const result = response.result;
                let html = `<div class="card"><div class="card-header bg-warning text-dark"><i class="fas fa-lightbulb"></i> 答案</div><div class="card-body">`;
                html += `<b>答案：</b>${result.answer || ''}<br/><b>推理链路：</b>${result.reasoning || ''}`;
                html += '</div></div>';
                $('#qa-results').html(html);
            } else {
                $('#qa-results').html('<div class="alert alert-danger">' + (response.error || '问答失败') + '</div>');
            }
        },
        error: function(xhr) {
            $('#qa-results').html('<div class="alert alert-danger">' + (xhr.responseJSON?.error || '问答失败') + '</div>');
        }
    });
}

    // 多文档分析按钮事件
    $('#btn-multi-analyze').click(function() {
        handleMultiDocAnalyze();
    });
});
// 多文档统一分析主流程
function handleMultiDocAnalyze() {
    const files = $('#multi-file-input')[0].files;
    if (!files || files.length === 0) {
        showToast('请先选择要分析的文档', 'warning');
        return;
    }
    $('#multi-analysis-results').html('<div class="text-info">正在分析多个文档，请稍候...</div>');

    // 依次上传并分析所有文档，收集结果
    let results = [];
    let completed = 0;
    for (let i = 0; i < files.length; i++) {
        const formData = new FormData();
        formData.append('file', files[i]);
        $.ajax({
            url: '/api/extract',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                results[i] = response;
            },
            error: function(xhr) {
                results[i] = { success: false, error: xhr.responseJSON?.error || '分析失败' };
            },
            complete: function() {
                completed++;
                if (completed === files.length) {
                    showMultiDocResults(results);
                }
            }
        });
    }
}

// 多文档分析结果整合与展示
function showMultiDocResults(results) {
    let html = '';
    let allEntities = [];
    let allRelations = [];
    let fileCount = 0;
    results.forEach((res, idx) => {
        if (res && res.success) {
            fileCount++;
            const entities = res.data.visualization.entities.list || [];
            const relations = res.data.visualization.relations.list || [];
            allEntities = allEntities.concat(entities);
            allRelations = allRelations.concat(relations);
            html += `<div class="card mb-3"><div class="card-header bg-light">文档${idx+1}分析结果</div><div class="card-body">`;
            html += `<b>实体：</b> ${entities.map(e => e.name + '(' + e.type + ')').join('，') || '无'}<br/>`;
            html += `<b>关系：</b> ${relations.map(r => r.subject + '→' + r.relation + '→' + r.object).join('，') || '无'}<br/>`;
            html += '</div></div>';
        } else {
            html += `<div class="alert alert-danger">文档${idx+1}分析失败：${res?.error || '未知错误'}</div>`;
        }
    });

    // 跨文档整合分析（简单去重、统计）
    const uniqueEntities = {};
    allEntities.forEach(e => {
        const key = e.name + '|' + e.type;
        if (!uniqueEntities[key]) uniqueEntities[key] = e;
    });
    const uniqueRelations = {};
    allRelations.forEach(r => {
        const key = r.subject + '|' + r.relation + '|' + r.object;
        if (!uniqueRelations[key]) uniqueRelations[key] = r;
    });

    html = `<div class="mb-3"><b>共分析文档：</b>${fileCount}个，<b>整合实体：</b>${Object.keys(uniqueEntities).length}个，<b>整合关系：</b>${Object.keys(uniqueRelations).length}条</div>` + html;

    // 可视化整合知识网络（可用ECharts等，简化为列表）
    html += '<div class="card mt-4"><div class="card-header bg-success text-white">跨文档整合知识网络</div><div class="card-body">';
    html += `<b>实体：</b> ${Object.values(uniqueEntities).map(e => e.name + '(' + e.type + ')').join('，') || '无'}<br/>`;
    html += `<b>关系：</b> ${Object.values(uniqueRelations).map(r => r.subject + '→' + r.relation + '→' + r.object).join('，') || '无'}<br/>`;
    html += '</div></div>';

    $('#multi-analysis-results').html(html);
}

// 初始化
function init() {
    // 初始化ECharts图表
    initChart();
    
    // 初始化字符计数器
    $('#input-text').on('input', function() {
        const charCount = $(this).val().length;
        $('#char-count').text(charCount);
    });
}

// 初始化ECharts图表
function initChart() {
    const chartDom = document.getElementById('graph-container');
    chartInstance = echarts.init(chartDom, 'light');
    
    // 初始空配置
    const option = {
        title: {
            text: '知识图谱',
            subtext: '等待输入文本...',
            left: 'center'
        },
        tooltip: {
            formatter: function(params) {
                if (params.dataType === 'node') {
                    return `${params.data.name}<br/>类型: ${params.data.category}`;
                } else if (params.dataType === 'edge') {
                    return `关系: ${params.data.value}`;
                }
            }
        },
        legend: {
            show: true,
            top: 'bottom'
        },
        series: [{
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            focusNodeAdjacency: true,
            edgeSymbol: ['circle', 'arrow'],
            edgeSymbolSize: [4, 10],
            edgeLabel: {
                show: true,
                formatter: '{c}'
            },
            force: {
                repulsion: 200,
                gravity: 0.1,
                edgeLength: 100
            },
            label: {
                show: true,
                position: 'right',
                formatter: '{b}'
            },
            lineStyle: {
                color: 'source',
                curveness: 0.3,
                width: 2
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: 14,
                    fontWeight: 'bold'
                },
                lineStyle: {
                    width: 3
                }
            }
        }]
    };
    
    chartInstance.setOption(option);
    
    // 窗口大小变化时重绘图表
    $(window).resize(function() {
        if (chartInstance) {
            chartInstance.resize();
        }
    });
}

// 绑定事件
function bindEvents() {
    // 构建图谱按钮
    $('#btn-extract').click(function() {
        extractText();
    });
    
    // 清空按钮
    $('#btn-clear').click(function() {
        $('#input-text').val('');
        $('#char-count').text('0');
        clearResults();
    });
    
    // 加载示例按钮
    $('#btn-example').click(function() {
        showExampleSelector();
    });
    
    // 重置视图按钮
    $('#btn-reset-view').click(function() {
        if (chartInstance && currentData) {
            updateChart(currentData);
        }
    });
    
    // 导出图谱按钮
    $('#btn-export-graph').click(function() {
        if (chartInstance) {
            const url = chartInstance.getDataURL({
                type: 'png',
                pixelRatio: 2,
                backgroundColor: '#fff'
            });
            const link = document.createElement('a');
            link.href = url;
            link.download = `knowledge_graph_${new Date().getTime()}.png`;
            link.click();
        }
    });
    
    // 复制JSON按钮
    $('#btn-copy-json').click(function() {
        const jsonText = $('#json-output').text();
        navigator.clipboard.writeText(jsonText).then(() => {
            showToast('JSON已复制到剪贴板', 'success');
        });
    });
    
    // 导出JSON按钮
    $('#btn-export-json').click(function() {
        if (!currentData) return;
        
        const jsonStr = JSON.stringify(currentData, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `extraction_result_${new Date().getTime()}.json`;
        link.click();
        URL.revokeObjectURL(url);
        
        showToast('JSON文件已导出', 'success');
    });
    
    // 输入框回车键提交
    $('#input-text').keydown(function(e) {
        if (e.ctrlKey && e.keyCode === 13) {
            extractText();
        }
    });
}

// 检查系统状态
function checkSystemStatus() {
    $.ajax({
        url: '/api/health',
        method: 'GET',
        success: function(response) {
            if (response.initialized) {
                $('#status-indicator').removeClass('bg-warning bg-danger')
                                     .addClass('bg-success')
                                     .html('<i class="fas fa-check-circle"></i> 系统就绪');
            } else {
                $('#status-indicator').removeClass('bg-success bg-warning')
                                     .addClass('bg-danger')
                                     .html('<i class="fas fa-exclamation-circle"></i> 系统异常');
            }
        },
        error: function() {
            $('#status-indicator').removeClass('bg-success bg-warning')
                                 .addClass('bg-danger')
                                 .html('<i class="fas fa-exclamation-circle"></i> 连接失败');
        }
    });
}

// 加载示例
function loadExamples() {
    $.ajax({
        url: '/api/examples',
        method: 'GET',
        success: function(response) {
            if (response.success && response.examples) {
                examples = response.examples;
                displayExamples();
            }
        },
        error: function() {
            // 使用默认示例
            examples = [
                {
                    id: 1,
                    title: '科技公司',
                    content: '苹果公司由史蒂夫·乔布斯、史蒂夫·沃兹尼亚克和罗纳德·韦恩于1976年创立，总部位于加利福尼亚州库比蒂诺。'
                }
            ];
            displayExamples();
        }
    });
}

// 显示示例
function displayExamples() {
    const container = $('#examples-container');
    container.empty();
    
    examples.forEach(example => {
        const cardHtml = `
            <div class="col-md-4 mb-3">
                <div class="card example-card h-100" data-example-id="${example.id}">
                    <div class="card-body">
                        <h6 class="card-title">${example.title}</h6>
                        <p class="card-text example-content">${example.content}</p>
                        <small class="text-muted">点击使用此示例</small>
                    </div>
                </div>
            </div>
        `;
        container.append(cardHtml);
    });
    
    // 绑定示例点击事件
    $('.example-card').click(function() {
        const exampleId = $(this).data('example-id');
        const example = examples.find(e => e.id == exampleId);
        if (example) {
            $('#input-text').val(example.content);
            $('#char-count').text(example.content.length);
            showToast(`已加载示例: ${example.title}`, 'info');
        }
    });
}

// 显示示例选择器
function showExampleSelector() {
    // 显示一个模态框让用户选择示例
    const modalHtml = `
        <div class="modal fade" id="example-modal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">选择示例文本</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="list-group">
                            ${examples.map(example => `
                                <a href="#" class="list-group-item list-group-item-action example-item" 
                                   data-example-id="${example.id}">
                                    <div class="d-flex w-100 justify-content-between">
                                        <h6 class="mb-1">${example.title}</h6>
                                        <small>${example.content.length} 字符</small>
                                    </div>
                                    <p class="mb-1">${example.content.substring(0, 150)}...</p>
                                </a>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 移除旧的模态框（如果存在）
    $('#example-modal').remove();
    $('body').append(modalHtml);
    
    const exampleModal = new bootstrap.Modal(document.getElementById('example-modal'));
    exampleModal.show();
    
    // 绑定示例选择事件
    $('.example-item').click(function(e) {
        e.preventDefault();
        const exampleId = $(this).data('example-id');
        const example = examples.find(e => e.id == exampleId);
        if (example) {
            $('#input-text').val(example.content);
            $('#char-count').text(example.content.length);
            exampleModal.hide();
            showToast(`已加载示例: ${example.title}`, 'info');
        }
    });
}

// 抽取文本
function extractText() {
    const text = $('#input-text').val().trim();
    
    if (!text) {
        showToast('请输入文本内容', 'warning');
        return;
    }
    
    if (text.length > 10000) {
        showToast('文本过长，最多支持10000字符', 'warning');
        return;
    }
    
    // 显示加载模态框
    const loadingModal = new bootstrap.Modal(document.getElementById('loading-modal'));
    $('#loading-message').text('正在抽取文本信息并构建知识图谱，请稍候...');
    $('#loading-progress').css('width', '30%');
    loadingModal.show();
    
    // 发送请求
    $.ajax({
        url: '/api/extract',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ text: text }),
        success: function(response) {
            $('#loading-progress').css('width', '100%');
            
            setTimeout(() => {
                loadingModal.hide();
                
                if (response.success) {
                    currentData = response.data;
                    displayResults(response);
                    showToast('知识图谱构建成功', 'success');
                } else {
                    showToast(response.error || '处理失败', 'error');
                }
            }, 500);
        },
        error: function(xhr, status, error) {
            loadingModal.hide();
            showToast('请求失败: ' + (xhr.responseJSON?.error || error), 'error');
        }
    });
}

// 显示结果
function displayResults(response) {
    const data = response.data;
    const stats = response.stats;

    // 更新统计信息
    $('#entity-count').text(stats.entity_count);
    $('#relation-count').text(stats.relation_count);

    // 更新图谱
    updateChart(data.visualization.graph);

    // 更新实体分类
    updateEntityCategories(data.visualization.entities);

    // 更新实体表格
    updateEntityTable(data.visualization.entities);

    // 更新关系表格
    updateRelationTable(data.visualization.relations);

    // 更新JSON显示
    updateJsonDisplay(data.extracted);

    // 多维度可视化：时间线
    if (data.visualization.timeline && data.visualization.timeline.events.length > 0) {
        showTimeline(data.visualization.timeline.events);
    }

    // 多维度可视化：主题聚类（预留，后端可扩展）
    if (data.visualization.topics) {
        showTopics(data.visualization.topics);
    }

    // 显示详细结果面板
    $('#results-section').show();
}

// 时间线可视化（简单文本/表格，后续可用ECharts等增强）
function showTimeline(events) {
    let html = '<div class="card mt-3"><div class="card-header bg-secondary text-white"><i class="fas fa-stream"></i> 事件时间线</div><div class="card-body"><ul class="timeline-list">';
    events.forEach(ev => {
        html += `<li><b>${ev.time || ''}</b>：${ev.content || ''}</li>`;
    });
    html += '</ul></div></div>';
    if ($('#timeline-panel').length) {
        $('#timeline-panel').replaceWith(html);
    } else {
        $('#panel-single .col-lg-6:last').append(`<div id="timeline-panel">${html}</div>`);
    }
}

// 主题聚类可视化（预留）
function showTopics(topics) {
    // 可用ECharts词云、饼图等展示
    // 这里只做占位
    let html = '<div class="card mt-3"><div class="card-header bg-info text-white"><i class="fas fa-layer-group"></i> 主题聚类</div><div class="card-body">';
    html += '<pre>' + JSON.stringify(topics, null, 2) + '</pre>';
    html += '</div></div>';
    if ($('#topics-panel').length) {
        $('#topics-panel').replaceWith(html);
    } else {
        $('#panel-single .col-lg-6:last').append(`<div id="topics-panel">${html}</div>`);
    }
}

// 更新图表
function updateChart(graphData) {
    if (!chartInstance || !graphData) return;
    
    const option = {
        title: {
            text: '知识图谱',
            subtext: `${graphData.nodes.length}个节点，${graphData.links.length}条关系`,
            left: 'center'
        },
        legend: {
            data: graphData.categories.map(cat => cat.name),
            top: 'bottom'
        },
        series: [{
            type: 'graph',
            layout: 'force',
            data: graphData.nodes,
            links: graphData.links,
            categories: graphData.categories,
            roam: true,
            draggable: true,
            focusNodeAdjacency: true,
            edgeSymbol: ['circle', 'arrow'],
            edgeSymbolSize: [4, 10],
            edgeLabel: {
                show: true,
                formatter: '{c}'
            },
            force: {
                repulsion: 200,
                gravity: 0.1,
                edgeLength: 100
            },
            label: {
                show: true,
                position: 'right',
                formatter: '{b}'
            },
            lineStyle: {
                color: 'source',
                curveness: 0.3,
                width: 2
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: 14,
                    fontWeight: 'bold'
                },
                lineStyle: {
                    width: 3
                }
            }
        }]
    };
    
    chartInstance.setOption(option, true);
}

// 更新实体分类显示
function updateEntityCategories(entitiesData) {
    const container = $('#entities-by-type');
    container.empty();
    
    entitiesData.type_stats.forEach(stat => {
        const badgeHtml = `
            <span class="entity-badge" style="background-color: ${stat.color}">
                ${stat.type} (${stat.count})
            </span>
        `;
        container.append(badgeHtml);
    });
}

// 更新实体表格
function updateEntityTable(entitiesData) {
    const tbody = $('#entities-table');
    tbody.empty();
    
    entitiesData.list.forEach(entity => {
        const row = `
            <tr>
                <td>${entity.name || ''}</td>
                <td><span class="badge" style="background-color: ${getEntityColor(entity.type)}">${entity.type || '未知'}</span></td>
                <td><small>${entity.id || ''}</small></td>
                <td>${entity.confidence ? entity.confidence.toFixed(2) : '1.00'}</td>
            </tr>
        `;
        tbody.append(row);
    });
}

// 更新关系表格
function updateRelationTable(relationsData) {
    const tbody = $('#relations-table');
    tbody.empty();
    
    relationsData.list.forEach(relation => {
        if (relation.length >= 3) {
            const row = `
                <tr>
                    <td>${relation[0]}</td>
                    <td><span class="badge bg-info">${relation[1]}</span></td>
                    <td>${relation[2]}</td>
                </tr>
            `;
            tbody.append(row);
        }
    });
}

// 更新JSON显示
function updateJsonDisplay(data) {
    $('#json-output').text(JSON.stringify(data, null, 2));
    
    // 语法高亮（简单版本）
    const jsonString = JSON.stringify(data, null, 2);
    const highlighted = jsonString
        .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|\b\d+\b)/g, function(match) {
            let cls = 'number';
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'key';
                } else {
                    cls = 'string';
                }
            } else if (/true|false/.test(match)) {
                cls = 'boolean';
            } else if (/null/.test(match)) {
                cls = 'null';
            }
            return `<span class="json-${cls}">${match}</span>`;
        });
    
    $('#json-output').html(highlighted);
}

// 获取实体颜色
function getEntityColor(type) {
    const colorMap = {
        'PERSON': '#FF6B6B',
        'ORGANIZATION': '#4ECDC4',
        'LOCATION': '#45B7D1',
        'EVENT': '#96CEB4',
        'DATE': '#FFEAA7',
        'PRODUCT': '#DDA0DD',
        'CONCEPT': '#98D8C8',
        'DISEASE': '#F7DC6F',
        'default': '#95A5A6'
    };
    return colorMap[type] || colorMap.default;
}

// 清空结果
function clearResults() {
    currentData = null;
    
    // 重置图表
    initChart();
    
    // 清空统计
    $('#entity-count').text('0');
    $('#relation-count').text('0');
    
    // 清空表格
    $('#entities-table').empty();
    $('#relations-table').empty();
    $('#entities-by-type').empty();
    
    // 清空JSON显示
    $('#json-output').text('{}');
    
    showToast('已清空所有结果', 'info');
}

// 显示提示信息
function showToast(message, type = 'info') {
    // 移除现有的提示
    $('.toast').remove();
    
    const typeIcons = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    
    const typeClasses = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    };
    
    const icon = typeIcons[type] || 'info-circle';
    const bgClass = typeClasses[type] || 'bg-info';
    
    const toastHtml = `
        <div class="toast align-items-center text-white ${bgClass} border-0" 
             role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="3000">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${icon} me-2"></i> ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    $('body').append(toastHtml);
    
    const toastEl = $('.toast').last()[0];
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
}

// 工具函数：防抖
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}