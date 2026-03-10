import os






















import os
import json
import requests

BASE = os.getenv("APP_BASE_URL", "http://localhost:5000")
SAMPLE_PATH = os.path.join("data", "sample.txt")


def print_hdr(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def upload_extract_and_graph(path: str):
    print_hdr("1) 单文件上传并生成图谱（含入库尝试）")
    try:
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
    except Exception as e:
        print("upload_extract_and_graph error:", e)
        return {}, {}


def save_graph(nodes, edges):
    print_hdr("2) 显式保存到 Neo4j（若已自动入库可再次验证）")
    try:
        payload = {"nodes": nodes, "edges": edges}
        r = requests.post(BASE + "/api/save_graph", json=payload, timeout=60)
        print("status:", r.status_code)
        print("resp:", r.text)
    except Exception as e:
        print("save_graph error:", e)


def fetch_subgraph(center: str | None):
    print_hdr("3) 从 Neo4j 加载子图")
    try:
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
    except Exception as e:
        print("fetch_subgraph error:", e)


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
        result = data.get("result") or {}
        merged = result.get("merged") or {}
        merged_nodes = merged.get("nodes") or []
        merged_edges = merged.get("edges") or []
        stats = result.get("stats") or {}
        print(
            "merged nodes:", len(merged_nodes),
            "merged edges:", len(merged_edges),
            "files:", stats.get("files"),
            "processed:", stats.get("processed"),
            "skipped:", stats.get("skipped")
        )
        per = result.get("per_file", []) or []
        for item in per:
            print(f"- {item.get('filename')}: success={item.get('success')} nodes={item.get('nodes')} edges={item.get('edges')} error={item.get('error')}")
    except Exception as e:
        print("batch_extract error:", e)
    finally:
        for _, (_, fh, _) in files:
            try:
                fh.close()
            except Exception:
                pass


if __name__ == "__main__":
    if not os.path.exists(SAMPLE_PATH):
        raise SystemExit("样本文件缺失: " + SAMPLE_PATH)
    extraction, graph = upload_extract_and_graph(SAMPLE_PATH)
    save_graph(extraction.get("nodes", []) or [], extraction.get("edges", []) or [])
    center = None
    nodes = extraction.get("nodes", []) or []
    if nodes:
        center = nodes[0].get("name") or nodes[0]
        if isinstance(center, dict):
            center = center.get("name")
    fetch_subgraph(center)
    batch_extract([SAMPLE_PATH, SAMPLE_PATH])
