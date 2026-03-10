# 基于LLM的知识图谱构建系统（毕业设计）

## 项目简介
使用大语言模型（LLM）进行知识图谱构建与补全扩充：从教学文本抽取概念与关系，进行层级扩充、前置关系判别与属性稠密化，并支持验证与自修正。

## 核心功能
- 文本数据加载与解析（txt/pdf/docx）
- LLM结构化抽取（严格JSON，含节点的 bloom_level/difficulty/status 与关系的 confidence/reasoning）
- 知识图谱构建与可视化数据准备
- 纵向层级扩充（Taxonomy Expansion）
- 横向前置关系推断（CoT）
- 属性与元数据稠密化（Bloom/难度/工时/多风格定义）
- 验证与自修正（Verifier）

## 运行
### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 Qwen API Key
推荐使用环境变量（或复制 .env.example 为 .env）：
```bash
QWEN_API_KEY=your_actual_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```
不建议在 [config/api_config.yaml](config/api_config.yaml) 中保存真实密钥。

### 3. 启动后端
```bash
python app.py
```
访问： http://127.0.0.1:5000

### 4. 前端演示
- 页面右上角有“一键演示”按钮，可自动执行：加载样本 → 单文档抽取 → 批量抽取 → Neo4j 子图读取。
- 手动验证入口（按钮 ID）：
  - 单文档：`btn-example`、`btn-extract`、`btn-export-report`
  - 批量：`multi-file-input`、`btn-multi-analyze`（入队并自动轮询）、`btn-multi-enqueue`（仅入队）、`btn-multi-export-merged`
  - Neo4j 子图：`btn-neo4j-load`（配合 `neo4j-center`/`neo4j-depth` 等输入框）

示例启动命令（PowerShell）：
```powershell
& D:/viscodeproject/text/.venv/Scripts/Activate.ps1
D:/viscodeproject/text/.venv/Scripts/python.exe app.py
```

一键演示脚本（PowerShell）：
```powershell
powershell -ExecutionPolicy Bypass -File tools/run_demo.ps1
```

### 可选：启用 Neo4j 持久化
- 在环境变量中配置：
  - `NEO4J_URI`（如 `neo4j+s://<your-uri>`）
  - `NEO4J_USER`
  - `NEO4J_PASSWORD`
- 安装依赖：`pip install -r requirements.txt`（已包含 neo4j 驱动）
- 未配置时会自动跳过入库，不影响功能。
- 连接自检：`python tools/neo4j_check.py`

#### Neo4j/AuraDB 示例配置
可以参考 [\.env.example](.env.example)（复制为 .env），本地 Neo4j 示例：
- `NEO4J_URI=bolt://localhost:7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASSWORD=your_password_here`

#### 最小 Cypher 示例
```cypher
MATCH (n:Concept) RETURN n LIMIT 5;
```

### 前端辅助接口
- GET /api/sample_text：返回 data/sample.txt，用于一键演示
- GET /api/examples：返回示例列表（首个为 sample.txt）
- POST /api/extract：纯文本抽取，返回 `entities/relations + graph`

## LLM驱动的补全与扩充 API
- 层级扩充：POST /api/expand_taxonomy
  - 示例：{"concept": "机器学习", "max_depth": 2}
- 前置关系判别（CoT）：POST /api/infer_prerequisite
  - 示例：{"a": "线性代数", "b": "主成分分析"}
- 属性稠密化：POST /api/densify_attributes
  - 示例：{"name": "决策树", "description": "用于分类与回归的树模型..."}
- 关系验证与自修正：POST /api/verify
  - 示例：{"triplets": [{"source": "线性代数", "target": "主成分分析", "type": "PREREQUISITE_OF"}]}
- 批量持久化（可选Neo4j）：POST /api/save_graph
  - 示例：{"nodes": [...], "edges": [...]} （未配置 Neo4j 时返回提示）
- Neo4j 子图读取（可选Neo4j）：GET /api/neo4j/subgraph?center=概念&depth=1&limit_nodes=200&limit_edges=800
  - 未传 center 时随机取部分节点作为种子
- 多文件批量抽取与合并：POST /api/batch_extract （multipart/form-data，字段 files[]）
  - 返回去重后的 nodes/edges、合并图 graph、每文件处理结果 per_file、统计 stats

### 快速批量（只返回统计）
当批量文件很大时，可使用 fast 模式减少响应体积：

```
POST /api/batch_extract (multipart/form-data)
fields: files[], fast=1
```

返回字段：`stats`、`per_file`、`warnings`、`job_id`、`download_url`。
完整结果将落盘到 output/batch_job_<job_id>.json，可通过 `download_url` 下载。

### 批量队列处理（落盘到 output）
- 入队：POST /api/batch_enqueue（multipart/form-data，字段 files[]，可选 persist=1）
  - 返回 job_id 与 status_url
- 状态查询：GET /api/batch_status?job_id=...
  - 处理完成后返回 result，并写入 output/batch_job_<job_id>.json
- 下载结果：GET /api/batch_download?job_id=...

节点属性：bloom_level, difficulty, status；关系属性：confidence, reasoning。

## PowerShell UTF-8 发送（避免中文乱码）
如果你用 PowerShell 调用 API 并传中文 JSON，推荐用 UTF-8 发送脚本：

```7
powershell -ExecutionPolicy Bypass -File tools/neo4j_utf8_post.ps1
```

也可以在 PowerShell profile 中设置 UTF-8 默认输出（已在当前环境配置）。

## 评估（Precision / Recall / F1）
- 示例金标准：data/gold_sample.json
- 评估脚本：tools/eval_f1.py（支持 `entities/relations`、`nodes/edges`、`data.extracted` 三类常见结构）
  ```bash
  python tools/eval_f1.py --pred output/extraction_20260116_135525.json --gold data/gold_sample.json
  ```
  可选参数：
  - `--ignore-case` 忽略大小写匹配
  - `--strip-symbols` 将下划线/连字符规范为空格再匹配
  - `--report report.json` 导出 FP/FN 详情，便于误差分析

## 测试与验收
自动化测试：
```bash
python -m unittest discover -s tests
```

端到端接口验证：
```bash
python tools/e2e_sample_test.py
```

前端手动验收清单：
- 见 [docs/frontend_checklist.md](docs/frontend_checklist.md)

集成测试报告：
- 见 [docs/integration_test_report.md](docs/integration_test_report.md)
