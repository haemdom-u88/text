import json
import os
import threading
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

import app_state
from src.file_parser import parse_file
from src.graph_builder import KnowledgeGraph
from src.simple_extractor import SimpleExtractor

bp = Blueprint("batch", __name__)


def _save_uploaded_file(file_obj, index: int):
    display_name, _safe_name, ext = app_state.normalize_upload_filename(file_obj.filename)
    if ext not in [".txt", ".pdf", ".doc", ".docx"]:
        raise ValueError(f"暂不支持的文件类型: {ext}")
    os.makedirs("output", exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join("output", f"upload_{stamp}_{index}{ext}")
    file_obj.save(temp_path)
    return {"path": temp_path, "display_name": display_name}


@bp.route("/api/batch_extract", methods=["POST"])
def batch_extract():
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"success": False, "error": "未检测到上传文件"}), 400
        fast_mode = str(request.form.get("fast", "")).strip() in {"1", "true", "yes"}

        merged_nodes = []
        merged_edges = []
        per_file = []
        warnings = []
        skipped = 0

        for idx, file_obj in enumerate(files, 1):
            try:
                item = _save_uploaded_file(file_obj, idx)
            except Exception as exc:
                per_file.append({"filename": file_obj.filename, "success": False, "error": str(exc)})
                skipped += 1
                continue
            try:
                text = parse_file(item["path"])
            except Exception as exc:
                per_file.append({"filename": item["display_name"], "success": False, "error": f"解析失败: {exc}"})
                skipped += 1
                continue
            if not text or not text.strip():
                per_file.append({"filename": item["display_name"], "success": False, "error": "文件内容为空或解析失败"})
                skipped += 1
                continue
            try:
                extraction = app_state.extractor.extract_concepts_and_edges(text[:20000])
                nodes = extraction.get("nodes", []) or []
                edges = extraction.get("edges", []) or []
                if not nodes and not edges:
                    se = app_state.simple_extractor or SimpleExtractor()
                    simple_result = se.extract_all(text[:20000])
                    extraction = app_state.build_nodes_edges_from_simple(simple_result)
                    nodes = extraction.get("nodes", []) or []
                    edges = extraction.get("edges", []) or []
                merged_nodes.extend(nodes)
                merged_edges.extend(edges)
                per_file.append({"filename": item["display_name"], "success": True, "nodes": len(nodes), "edges": len(edges)})
            except Exception as exc:
                per_file.append({"filename": item["display_name"], "success": False, "error": f"抽取失败: {exc}"})
                skipped += 1

        uniq_nodes, uniq_edges = app_state.dedupe_nodes_edges(merged_nodes, merged_edges)
        kg_tmp = KnowledgeGraph()
        kg_tmp.build_from_extraction({"nodes": uniq_nodes, "edges": uniq_edges})
        graph = kg_tmp.to_dict()

        result = {
            "merged": {"nodes": uniq_nodes, "edges": uniq_edges},
            "graph": graph,
            "stats": {
                "files": len(files),
                "processed": len(files) - skipped,
                "skipped": skipped,
                "nodes": len(uniq_nodes),
                "edges": len(uniq_edges)
            },
            "per_file": per_file,
            "warnings": warnings
        }

        os.makedirs("output", exist_ok=True)
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        output_path = os.path.join("output", f"batch_job_{job_id}.json")
        with open(output_path, "w", encoding="utf-8") as file_obj:
            json.dump(result, file_obj, ensure_ascii=False, indent=2)

        if fast_mode:
            return jsonify({
                "success": True,
                "stats": result["stats"],
                "per_file": result["per_file"],
                "warnings": warnings,
                "job_id": job_id,
                "download_url": f"/api/batch_download?job_id={job_id}"
            })

        return jsonify({"success": True, "result": result})
    except Exception as exc:
        app_state.logger.error("Batch extract failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/batch_enqueue", methods=["POST"])
def batch_enqueue():
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"success": False, "error": "未检测到上传文件"}), 400
        persist = str(request.form.get("persist", "")).strip() in {"1", "true", "yes"}

        saved_items = []
        for idx, file_obj in enumerate(files, 1):
            item = _save_uploaded_file(file_obj, idx)
            saved_items.append(item)

        job_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        with app_state.BATCH_LOCK:
            app_state.BATCH_JOBS[job_id] = {
                "status": "queued",
                "created_at": datetime.now().isoformat(),
                "total": len(saved_items),
                "processed": 0,
                "skipped": 0
            }

        thread = threading.Thread(target=app_state.run_batch_job, args=(job_id, saved_items, persist), daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "job_id": job_id,
            "status_url": f"/api/batch_status?job_id={job_id}"
        })
    except Exception as exc:
        app_state.logger.error("Batch enqueue failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/batch_status", methods=["GET"])
def batch_status():
    try:
        job_id = request.args.get("job_id", "").strip()
        if not job_id:
            return jsonify({"success": False, "error": "缺少 job_id"}), 400
        with app_state.BATCH_LOCK:
            job = app_state.BATCH_JOBS.get(job_id)
        if not job:
            return jsonify({"success": False, "error": "任务不存在"}), 404
        return jsonify({"success": True, "job": job})
    except Exception as exc:
        app_state.logger.error("Batch status failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/batch_download", methods=["GET"])
def batch_download():
    try:
        job_id = request.args.get("job_id", "").strip()
        if not job_id:
            return jsonify({"success": False, "error": "缺少 job_id"}), 400
        path = os.path.join("output", f"batch_job_{job_id}.json")
        if not os.path.exists(path):
            return jsonify({"success": False, "error": "文件不存在"}), 404
        return send_file(path, as_attachment=True, download_name=f"batch_job_{job_id}.json")
    except Exception as exc:
        app_state.logger.error("Batch download failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500
