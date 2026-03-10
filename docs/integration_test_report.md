# 集成测试报告

日期：2026-02-21

## 环境
- OS: Windows
- Python: 3.12
- 服务端：Flask
- 依赖：reportlab, python-docx, neo4j driver

## 前置条件
- 已配置环境变量：QWEN_API_KEY, QWEN_BASE_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

## 测试步骤与结果
1) Qwen API 连通性
- 命令：python test_qwen_api.py
- 结果：通过

2) Neo4j 连接自检
- 命令：python tools/neo4j_check.py
- 结果：通过

3) 端到端接口验证
- 命令：python tools/e2e_sample_test.py
- 覆盖：单文件抽取、保存到 Neo4j、子图读取、批量抽取
- 结果：通过

4) 自动化冒烟测试
- 命令：python -m unittest discover -s tests
- 覆盖：health/extract/upload/batch/export/pdf/word/qa/neo4j 失败分支
- 结果：通过

## 观察到的提示
- Neo4j 返回属性不存在的告警（description 字段为空时提示），不影响功能。

## 结论
- 主要功能链路可用，LLM 与 Neo4j 均可正常工作。
