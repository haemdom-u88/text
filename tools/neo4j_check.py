"""
最小 Neo4j 连接自检脚本
使用环境变量：NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
运行：python tools/neo4j_check.py
"""
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

if not (URI and USER and PASSWORD):
    print("❌ 缺少环境变量 NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD，无法检查连接")
    raise SystemExit(1)

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        result = session.run("RETURN 1 AS ok").single()
        print("✅ 连接成功，返回:", result.get("ok"))
    driver.close()
except Exception as e:
    print("❌ Neo4j 连接失败:", e)
    raise SystemExit(2)
