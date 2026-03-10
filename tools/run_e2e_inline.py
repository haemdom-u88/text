import os
import sys
import threading
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "2521571840"
BASE = "http://127.0.0.1:5001"

from app import app
from werkzeug.serving import make_server
import requests


def start_server():
    server = make_server("127.0.0.1", 5001, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread


def print_hdr(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def upload_extract_and_graph(path: str):
    print_hdr("1) 单文件上传并生成图谱（含入库尝试）")
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, "text/plain")}
        r = requests.post(BASE + "/api/upload_extract_and_graph", files=files, timeout=120)
    print("status:", r.status_code)
    data = r.json()
    print("success:", data.get("success"))
    extraction = data.get("extraction", {})
    nodes = extraction.get("nodes", []) or []
    edges = extraction.get("edges", []) or []
    print(f"nodes: {len(nodes)} edges: {len(edges)} filename: {data.get('filename')}")
    return extraction, data.get("graph", {})


def save_graph(nodes, edges):
    print_hdr("2) 显式保存到 Neo4j（若已自动入库可再次验证）")
    payload = {"nodes": nodes, "edges": edges}
    r = requests.post(BASE + "/api/save_graph", json=payload, timeout=60)
    print("status:", r.status_code)
    print("resp:", r.text)


def fetch_subgraph(center: str | None):
    print_hdr("3) 从 Neo4j 加载子图")
    params = {"center": center or "", "depth": 1, "limit_nodes": 200, "limit_edges": 800, "include_props": 1}
    r = requests.get(BASE + "/api/neo4j/subgraph", params=params, timeout=60)
    print("status:", r.status_code)
    try:
        data = r.json()
        if data.get("success"):
            nodes = data.get("nodes", []) or []
            edges = data.get("edges", []) or []
            print(f"loaded nodes: {len(nodes)} edges: {len(edges)} center: {center}")
        else:
            print("error:", data.get("error"))
    except Exception:
        print("resp:", r.text)


def batch_extract(paths: list[str]):
    print_hdr("4) 批量抽取（多文件）")
    files = []
    for p in paths:
        files.append(("files", (os.path.basename(p), open(p, "rb"), "text/plain")))
    try:
        r = requests.post(BASE + "/api/batch_extract", files=files, timeout=180)
        print("status:", r.status_code)
        data = r.json()
        print("success:", data.get("success"))
        merged_nodes = data.get("nodes") or data.get("merged_nodes") or (data.get("merged") or {}).get("nodes") or []
        merged_edges = data.get("edges") or data.get("merged_edges") or (data.get("merged") or {}).get("edges") or []
        print("merged nodes:", len(merged_nodes), "merged edges:", len(merged_edges))
        per = data.get("per_file", []) or []
        for item in per:
            print(f"- {item.get('filename')}: success={item.get('success')} nodes={item.get('nodes')} edges={item.get('edges')} error={item.get('error')}")
    finally:
        for _, (_, fh, _) in files:
            try:
                fh.close()
            except Exception:
                pass


if __name__ == "__main__":
    server, thread = start_server()
    time.sleep(1)

    print_hdr("0) 健康检查")
    health = requests.get(BASE + "/api/health", timeout=20)
    print("status:", health.status_code, "resp:", health.text)

    sample_path = Path("data") / "sample.txt"
    if not sample_path.exists():
        raise SystemExit("样本文件缺失: " + str(sample_path))

    extraction, graph = upload_extract_and_graph(str(sample_path))
    save_graph(extraction.get("nodes", []) or [], extraction.get("edges", []) or [])
    center = None
    nodes = extraction.get("nodes", []) or []
    if nodes:
        center = nodes[0].get("name") if isinstance(nodes[0], dict) else nodes[0]
    fetch_subgraph(center)
    batch_extract([str(sample_path), str(sample_path)])

    server.shutdown()
    thread.join(timeout=5)
    print("\n测试完成")
