import os
from datetime import datetime

from flask import Blueprint, jsonify, request

import app_state
from src.file_parser import parse_file
from src.graph_builder import KnowledgeGraph
from src.simple_extractor import SimpleExtractor

bp = Blueprint("extract", __name__)


@bp.route("/api/upload_extract_and_graph", methods=["POST"])
def upload_extract_and_graph():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "未检测到上传文件"}), 400
        file_obj = request.files["file"]
        display_name, _safe_name, ext = app_state.normalize_upload_filename(file_obj.filename)
        if ext not in [".txt", ".pdf", ".doc", ".docx"]:
            return jsonify({"success": False, "error": f"暂不支持的文件类型: {ext}"}), 400
        os.makedirs("output", exist_ok=True)
        temp_path = os.path.join("output", f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
        file_obj.save(temp_path)
        text = parse_file(temp_path)
        if not text or text.strip() == "":
            return jsonify({"success": False, "error": "文件内容为空或解析失败"}), 400
        extraction = app_state.extractor.extract_concepts_and_edges(text[:20000])
        nodes = extraction.get("nodes", []) or []
        edges = extraction.get("edges", []) or []
        if not nodes and not edges:
            se = app_state.simple_extractor or SimpleExtractor()
            simple_result = se.extract_all(text[:20000])
            extraction = app_state.build_nodes_edges_from_simple(simple_result)
        kg_tmp = KnowledgeGraph()
        kg_tmp.build_from_extraction(extraction)
        graph = kg_tmp.to_dict()
        try:
            if app_state.neo4j_store:
                app_state.neo4j_store.upsert_nodes_edges(extraction.get("nodes", []), extraction.get("edges", []))
        except Exception:
            app_state.logger.warning("Neo4j upsert failed", exc_info=True)
        return jsonify({"success": True, "filename": display_name, "extraction": extraction, "graph": graph})
    except Exception as exc:
        app_state.logger.error("Upload extract+graph failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/upload_and_extract", methods=["POST"])
def upload_and_extract():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "未检测到上传文件"}), 400
        file_obj = request.files["file"]
        display_name, _safe_name, ext = app_state.normalize_upload_filename(file_obj.filename)
        if ext not in [".txt", ".pdf", ".doc", ".docx"]:
            return jsonify({"success": False, "error": f"暂不支持的文件类型: {ext}"}), 400
        os.makedirs("output", exist_ok=True)
        temp_path = os.path.join("output", f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
        file_obj.save(temp_path)
        text = parse_file(temp_path)
        if not text or text.strip() == "":
            return jsonify({"success": False, "error": "文件内容为空或解析失败"}), 400
        extraction = app_state.extractor.extract_concepts_and_edges(text[:20000])
        nodes = extraction.get("nodes", []) or []
        edges = extraction.get("edges", []) or []
        if not nodes and not edges:
            se = app_state.simple_extractor or SimpleExtractor()
            simple_result = se.extract_all(text[:20000])
            extraction = app_state.build_nodes_edges_from_simple(simple_result)
        try:
            if app_state.neo4j_store:
                app_state.neo4j_store.upsert_nodes_edges(extraction.get("nodes", []), extraction.get("edges", []))
        except Exception:
            app_state.logger.warning("Neo4j upsert failed", exc_info=True)
        return jsonify({"success": True, "filename": display_name, "extraction": extraction})
    except Exception as exc:
        app_state.logger.error("Upload extract failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/upload_file", methods=["POST"])
def upload_file():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "未检测到上传文件"}), 400
        file_obj = request.files["file"]
        display_name, _safe_name, ext = app_state.normalize_upload_filename(file_obj.filename)
        if ext not in [".txt", ".pdf", ".doc", ".docx"]:
            return jsonify({"success": False, "error": f"暂不支持的文件类型: {ext}"}), 400
        os.makedirs("output", exist_ok=True)
        temp_path = os.path.join("output", f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
        file_obj.save(temp_path)
        text = parse_file(temp_path)
        if not text or text.strip() == "":
            return jsonify({"success": False, "error": "文件内容为空或解析失败"}), 400
        return jsonify({"success": True, "filename": display_name, "text": text[:20000]})
    except Exception as exc:
        app_state.logger.error("Upload/parse failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/sample_text", methods=["GET"])
def api_sample_text():
    try:
        sample_path = os.path.join("data", "sample.txt")
        if not os.path.exists(sample_path):
            return jsonify({"success": False, "error": "样本文件不存在"}), 404
        with open(sample_path, "r", encoding="utf-8", errors="ignore") as file_obj:
            content = file_obj.read()
        return jsonify({"success": True, "text": content})
    except Exception as exc:
        app_state.logger.error("Read sample failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/examples", methods=["GET"])
def api_examples():
    try:
        sample_path = os.path.join("data", "sample.txt")
        content = ""
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                content = file_obj.read()
        examples = [{"title": "样本文本", "content": content}]
        return jsonify({"success": True, "examples": examples})
    except Exception as exc:
        app_state.logger.error("Examples failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/extract", methods=["POST"])
def api_extract():
    try:
        data = request.get_json() or {}
        text = data.get("text") or ""
        if isinstance(text, dict):
            text = text.get("value") or text.get("text") or ""
        elif not isinstance(text, str):
            text = str(text)
        text = text.strip()
        if not text:
            return jsonify({"success": False, "error": "请提供文本"}), 400

        warnings = []
        extraction = app_state.extractor.extract_concepts_and_edges(text[:10000])
        llm_error = extraction.get("error") if isinstance(extraction, dict) else None
        if llm_error and "llm_timeout" in str(llm_error):
            warnings.append("LLM 抽取超时，已启用兜底抽取")

        nodes = extraction.get("nodes", []) or []
        edges = extraction.get("edges", []) or []
        if not nodes and not edges:
            se = app_state.simple_extractor or SimpleExtractor()
            simple_result = se.extract_all(text[:10000])
            extraction = app_state.build_nodes_edges_from_simple(simple_result)
            nodes = extraction.get("nodes", []) or []
            edges = extraction.get("edges", []) or []

        entities = []
        for i, node in enumerate(nodes):
            entities.append({
                "name": node.get("name") or node.get("id") or f"node_{i}",
                "type": node.get("type") or "概念",
                "id": node.get("id") or i,
                "score": node.get("confidence") or node.get("bloom_level")
            })
        relations = []
        for edge in edges:
            relations.append({
                "subject": edge.get("source"),
                "relation": edge.get("relation") or edge.get("type"),
                "object": edge.get("target")
            })

        kg_tmp = KnowledgeGraph()
        kg_tmp.build_from_extraction({"nodes": nodes, "edges": edges})
        graph = kg_tmp.to_dict()

        return jsonify({
            "success": True,
            "data": {
                "extracted": {"entities": entities, "relations": relations},
                "graph": graph,
                "warnings": warnings
            }
        })
    except Exception as exc:
        app_state.logger.error("Extract failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/upload_outline", methods=["POST"])
def upload_outline():
    try:
        data = request.get_json() or {}
        outline_text = (data.get("text") or "").strip()
        if not outline_text:
            return jsonify({"success": False, "error": "请提供教学大纲文本"}), 400
        if len(outline_text) > 20000:
            return jsonify({"success": False, "error": "文本过长（最多20000字符）"}), 400
        extraction = app_state.extractor.extract_concepts_and_edges(outline_text)
        return jsonify({"success": True, "extraction": extraction})
    except Exception as exc:
        app_state.logger.error("Outline extract failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/generate_graph", methods=["POST"])
def generate_graph():
    try:
        data = request.get_json() or {}
        extraction = data.get("extraction")
        if not extraction:
            return jsonify({"success": False, "error": "请先上传并抽取大纲"}), 400
        app_state.kg.build_from_extraction(extraction)
        graph = app_state.kg.to_dict()
        try:
            if app_state.neo4j_store:
                app_state.neo4j_store.upsert_nodes_edges(extraction.get("nodes", []), extraction.get("edges", []))
        except Exception:
            app_state.logger.warning("Neo4j upsert failed", exc_info=True)
        return jsonify({"success": True, "graph": graph})
    except Exception as exc:
        app_state.logger.error("Generate graph failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500
