import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime

from werkzeug.utils import secure_filename

from src.config_loader import ConfigLoader
from src.qwen_client import QwenAPIClient
from src.extractor import OutlineExtractor
from src.graph_builder import KnowledgeGraph
from src.simple_extractor import SimpleExtractor
from src.taxonomy_expander import TaxonomyExpander
from src.prerequisite_inferer import PrerequisiteInferer
from src.attribute_densifier import AttributeDensifier
from src.validator import Validator
from src.neo4j_store import get_store_if_configured
from src.file_parser import parse_file

logger = logging.getLogger(__name__)

llm_client = None
extractor = None
simple_extractor = None
kg = None
neo4j_store = None
taxonomy_expander = None
prereq_inferer = None
attr_densifier = None
verifier = None
is_initialized = False
init_lock = threading.Lock()

RATE_LIMIT_SECONDS = 3
_LAST_CALL = {}

BATCH_JOBS = {}
BATCH_LOCK = threading.Lock()


def initialize_services():
    global llm_client, extractor, simple_extractor, kg, is_initialized
    global neo4j_store, taxonomy_expander, prereq_inferer, attr_densifier, verifier
    with init_lock:
        if is_initialized:
            return True
        try:
            logger.info("Initializing services...")
            config_path = os.path.join("config", "api_config.yaml")
            config_loader = ConfigLoader(config_path)
            llm_client = QwenAPIClient(
                api_key=config_loader.get_api_key(),
                base_url=config_loader.get_base_url()
            )
            extractor = OutlineExtractor(llm_client)
            simple_extractor = SimpleExtractor()
            kg = KnowledgeGraph()
            neo4j_store = get_store_if_configured()
            taxonomy_expander = TaxonomyExpander(llm_client)
            prereq_inferer = PrerequisiteInferer(llm_client)
            attr_densifier = AttributeDensifier(llm_client)
            verifier = Validator(llm_client)
            is_initialized = True
            logger.info("Service initialization complete")
            return True
        except Exception as exc:
            logger.error("Service initialization failed: %s", exc, exc_info=True)
            return False


def rate_limited(action: str) -> bool:
    try:
        ip = getattr(threading.current_thread(), "_request_ip", None) or "unknown"
    except Exception:
        ip = "unknown"
    key = f"{ip}:{action}"
    now = time.time()
    last = _LAST_CALL.get(key, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return True
    _LAST_CALL[key] = now
    return False


def set_request_ip(ip: str):
    try:
        threading.current_thread()._request_ip = ip
    except Exception:
        pass


def normalize_upload_filename(raw_name: str):
    raw_name = raw_name or ""
    ext = os.path.splitext(raw_name)[1].lower()
    safe_name = secure_filename(raw_name)
    if not safe_name:
        suffix = ext if ext else ""
        safe_name = f"file_{uuid.uuid4().hex}{suffix}"
    display_name = raw_name or safe_name
    return display_name, safe_name, ext


def build_nodes_edges_from_simple(simple_result: dict) -> dict:
    nodes = []
    edges = []
    node_map = {}

    def add_node(name: str, ntype: str = "Concept"):
        if not name:
            return
        key = str(name)
        if key in node_map:
            return
        node = {"id": key, "name": key, "type": ntype or "Concept"}
        node_map[key] = node

    for ent in simple_result.get("entities", []) or []:
        add_node(ent.get("name", ""), ent.get("type", "Concept"))

    for rel in simple_result.get("relations", []) or []:
        source = rel.get("subject")
        target = rel.get("object")
        add_node(source, "Entity")
        add_node(target, "Entity")
        if source and target:
            edges.append({
                "source": source,
                "target": target,
                "relation": rel.get("relation") or ""
            })

    nodes = list(node_map.values())
    return {"nodes": nodes, "edges": edges}


def dedupe_nodes_edges(nodes, edges):
    uniq_nodes = []
    seen_nodes = set()
    for node in nodes:
        key = (node.get("name") or node.get("id") or "").strip()
        if not key or key in seen_nodes:
            continue
        seen_nodes.add(key)
        uniq_nodes.append(node)

    uniq_edges = []
    seen_edges = set()
    for edge in edges:
        key = (edge.get("source") or "") + "|" + (edge.get("target") or "") + "|" + (edge.get("relation") or edge.get("type") or "")
        if key in seen_edges:
            continue
        seen_edges.add(key)
        uniq_edges.append({
            "source": edge.get("source"),
            "target": edge.get("target"),
            "relation": edge.get("relation") or edge.get("type"),
            "confidence": edge.get("confidence"),
            "reasoning": edge.get("reasoning")
        })

    return uniq_nodes, uniq_edges


def run_batch_job(job_id: str, file_items: list, persist: bool):
    with BATCH_LOCK:
        BATCH_JOBS[job_id].update({"status": "running", "started_at": datetime.now().isoformat()})

    merged_nodes = []
    merged_edges = []
    per_file = []
    skipped = 0

    try:
        for idx, item in enumerate(file_items, 1):
            if isinstance(item, dict):
                path = item.get("path")
                filename = item.get("display_name") or os.path.basename(path or "")
            else:
                path = item
                filename = os.path.basename(path)
            try:
                text = parse_file(path)
            except Exception as exc:
                per_file.append({"filename": filename, "success": False, "error": f"解析失败: {exc}"})
                skipped += 1
                continue
            if not text or not text.strip():
                per_file.append({"filename": filename, "success": False, "error": "文件内容为空或解析失败"})
                skipped += 1
                continue
            try:
                extraction = extractor.extract_concepts_and_edges(text[:20000])
                nodes = extraction.get("nodes", []) or []
                edges = extraction.get("edges", []) or []
                if not nodes and not edges:
                    se = simple_extractor or SimpleExtractor()
                    simple_result = se.extract_all(text[:20000])
                    extraction = build_nodes_edges_from_simple(simple_result)
                    nodes = extraction.get("nodes", []) or []
                    edges = extraction.get("edges", []) or []
                merged_nodes.extend(nodes)
                merged_edges.extend(edges)
                per_file.append({"filename": filename, "success": True, "nodes": len(nodes), "edges": len(edges)})
            except Exception as exc:
                per_file.append({"filename": filename, "success": False, "error": f"抽取失败: {exc}"})
                skipped += 1
            with BATCH_LOCK:
                BATCH_JOBS[job_id]["processed"] = idx
                BATCH_JOBS[job_id]["skipped"] = skipped

        uniq_nodes, uniq_edges = dedupe_nodes_edges(merged_nodes, merged_edges)
        kg_tmp = KnowledgeGraph()
        kg_tmp.build_from_extraction({"nodes": uniq_nodes, "edges": uniq_edges})
        graph = kg_tmp.to_dict()

        if persist and neo4j_store:
            try:
                neo4j_store.upsert_nodes_edges(uniq_nodes, uniq_edges)
            except Exception:
                logger.warning("Neo4j batch upsert failed", exc_info=True)

        result = {
            "merged": {"nodes": uniq_nodes, "edges": uniq_edges},
            "graph": graph,
            "stats": {
                "files": len(file_items),
                "processed": len(file_items) - skipped,
                "skipped": skipped,
                "nodes": len(uniq_nodes),
                "edges": len(uniq_edges)
            },
            "per_file": per_file
        }

        os.makedirs("output", exist_ok=True)
        output_path = os.path.join("output", f"batch_job_{job_id}.json")
        with open(output_path, "w", encoding="utf-8") as file_obj:
            json.dump(result, file_obj, ensure_ascii=False, indent=2)

        with BATCH_LOCK:
            BATCH_JOBS[job_id].update({
                "status": "done",
                "finished_at": datetime.now().isoformat(),
                "result": result,
                "output_path": output_path
            })
    except Exception as exc:
        logger.error("Batch job failed: %s", exc, exc_info=True)
        with BATCH_LOCK:
            BATCH_JOBS[job_id].update({
                "status": "error",
                "error": str(exc),
                "finished_at": datetime.now().isoformat()
            })
