import json

from flask import Blueprint, jsonify, request

import app_state

bp = Blueprint("llm", __name__)


@bp.route("/api/qa", methods=["POST"])
def qa_answer():
    try:
        data = request.get_json() or {}
        question = (data.get("question") or "").strip()
        knowledge = data.get("knowledge")
        if not question:
            return jsonify({"success": False, "error": "请输入问题"}), 400

        context = ""
        if knowledge:
            context = json.dumps(knowledge, ensure_ascii=False)[:2000]
        prompt = (
            "请结合以下知识库内容，回答用户问题，并给出推理链路：\n"
            f"知识库：{context}\n"
            f"问题：{question}\n"
            "请用简明中文回答，格式：\n答案：...\n推理链路：..."
        )
        if not app_state.llm_client:
            return jsonify({"success": False, "error": "LLM 未初始化"}), 500
        answer = app_state.llm_client.generate(prompt, system_prompt="智能问答助手")

        if isinstance(answer, dict):
            result = answer
        else:
            ans = ""
            chain = ""
            if "答案：" in answer:
                parts = answer.split("答案：", 1)[-1].split("推理链路：")
                ans = parts[0].strip()
                if len(parts) > 1:
                    chain = parts[1].strip()
            else:
                ans = answer
            result = {"answer": ans, "reasoning": chain}

        return jsonify({"success": True, "result": result})
    except Exception as exc:
        app_state.logger.error("QA failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": f"处理失败: {exc}"}), 500


@bp.route("/api/expand_taxonomy", methods=["POST"])
def api_expand_taxonomy():
    try:
        if app_state.rate_limited("expand_taxonomy"):
            return jsonify({"success": False, "error": "请求过于频繁，请稍后再试"}), 429
        data = request.get_json() or {}
        concept = (data.get("concept") or "").strip()
        max_depth = int(data.get("max_depth", 2))
        if not concept:
            return jsonify({"success": False, "error": "请提供concept"}), 400
        result = app_state.taxonomy_expander.expand(concept, max_depth=max_depth)
        try:
            if app_state.neo4j_store:
                app_state.neo4j_store.upsert_nodes_edges(result.get("nodes", []), result.get("edges", []))
        except Exception:
            app_state.logger.warning("Neo4j upsert failed", exc_info=True)
        return jsonify({"success": True, "extraction": result})
    except Exception as exc:
        app_state.logger.error("Expand taxonomy failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/infer_prerequisite", methods=["POST"])
def api_infer_prerequisite():
    try:
        if app_state.rate_limited("infer_prerequisite"):
            return jsonify({"success": False, "error": "请求过于频繁，请稍后再试"}), 429
        data = request.get_json() or {}
        concept_a = (data.get("a") or data.get("concept_a") or "").strip()
        concept_b = (data.get("b") or data.get("concept_b") or "").strip()
        if not concept_a or not concept_b:
            return jsonify({"success": False, "error": "请提供概念A和概念B"}), 400
        judge = app_state.prereq_inferer.judge(concept_a, concept_b)
        edges = []
        if judge.get("is_prerequisite"):
            edges.append({
                "source": concept_a.lower().replace(" ", "_"),
                "target": concept_b.lower().replace(" ", "_"),
                "type": "PREREQUISITE_OF",
                "confidence": judge.get("confidence"),
                "reasoning": judge.get("reasoning")
            })
        try:
            if app_state.neo4j_store and edges:
                app_state.neo4j_store.upsert_nodes_edges(
                    [{"name": concept_a, "type": "Concept"}, {"name": concept_b, "type": "Concept"}],
                    edges
                )
        except Exception:
            app_state.logger.warning("Neo4j upsert failed", exc_info=True)
        return jsonify({"success": True, "judge": judge, "edges": edges})
    except Exception as exc:
        app_state.logger.error("Infer prerequisite failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/densify_attributes", methods=["POST"])
def api_densify_attributes():
    try:
        if app_state.rate_limited("densify_attributes"):
            return jsonify({"success": False, "error": "请求过于频繁，请稍后再试"}), 429
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        desc = (data.get("description") or "").strip()
        if not name:
            return jsonify({"success": False, "error": "请提供知识点名称"}), 400
        attrs = app_state.attr_densifier.densify(name, desc)
        return jsonify({"success": True, "attributes": attrs})
    except Exception as exc:
        app_state.logger.error("Densify attributes failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/api/verify", methods=["POST"])
def api_verify():
    try:
        data = request.get_json() or {}
        triplets = data.get("triplets") or []
        result = app_state.verifier.validate_triplets(triplets)
        return jsonify({"success": True, "result": result})
    except Exception as exc:
        app_state.logger.error("Verify failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500
