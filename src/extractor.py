"""
extractor.py
LLM抽取器：将教学大纲文本抽取为概念节点和先修关系边
"""
from typing import List, Dict
import os
import concurrent.futures
import json
import re


def _parse_json_response(response: str) -> Dict:
    if not response:
        raise ValueError("empty response")
    try:
        return json.loads(response)
    except Exception:
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(response[start:end + 1])
        raise


def _split_text(text: str, chunk_size: int) -> List[str]:
    sentences = [s for s in re.split(r'(?<=[。！？!?])', text) if s]
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= chunk_size:
            current += sentence
            continue
        if current:
            chunks.append(current)
        current = sentence
    if current:
        chunks.append(current)
    return chunks


def _merge_extractions(extractions: List[Dict]) -> Dict:
    merged_nodes = []
    merged_edges = []
    for item in extractions:
        merged_nodes.extend(item.get("nodes", []) or [])
        merged_edges.extend(item.get("edges", []) or [])

    uniq_nodes = []
    seen_nodes = set()
    for node in merged_nodes:
        key = (node.get("name") or node.get("id") or "").strip()
        if not key or key in seen_nodes:
            continue
        seen_nodes.add(key)
        uniq_nodes.append(node)

    uniq_edges = []
    seen_edges = set()
    for edge in merged_edges:
        key = (edge.get("source") or "") + "|" + (edge.get("target") or "") + "|" + (edge.get("type") or "")
        if key in seen_edges:
            continue
        seen_edges.add(key)
        uniq_edges.append(edge)

    return {"nodes": uniq_nodes, "edges": uniq_edges}



class OutlineExtractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def extract_concepts_and_edges(self, outline_text: str) -> Dict:
        """
        输入：教学大纲文本
        输出：{"nodes": [...], "edges": [...]}
        """
        # 构造 prompt
        schema_hint = (
            '{\n'
            '  "nodes": [\n'
            '    {"id": string, "name": string, "type": "Concept" | "Theorem" | "Tool",\n'
            '     "bloom_level": "记忆"|"理解"|"应用"|"分析"|"评价"|"创造",\n'
            '     "difficulty": number, "status": "Generated"|"Verified"}\n'
            '  ],\n'
            '  "edges": [\n'
            '    {"source": string, "target": string, "type": "PREREQUISITE_OF" | "SUBTOPIC_OF",\n'
            '     "confidence": number, "reasoning": string}\n'
            '  ]\n'
            '}'
        )
        prompt = (
            "你是一名课程设计专家。请从以下文本中提取核心概念及先修/组成关系，严格输出JSON，字段含义参考Schema。\n"
            "约束：节点id用英文或拼音短标识；难度0.0-1.0；bloom_level按认知维度分类；status默认Generated。\n"
            f"文本：\n{outline_text}"
        )
        timeout_s = int(os.environ.get("LLM_EXTRACT_TIMEOUT", "25"))
        chunk_size = int(os.environ.get("LLM_EXTRACT_CHUNK_SIZE", "12000"))
        max_workers = int(os.environ.get("LLM_EXTRACT_MAX_WORKERS", "1"))
        max_chunks = int(os.environ.get("LLM_EXTRACT_MAX_CHUNKS", str(max_workers * 4)))

        if len(outline_text) > chunk_size:
            return self._extract_from_chunks(outline_text, schema_hint, timeout_s, chunk_size, max_workers, max_chunks)

        response = None
        response, error = self._run_llm(schema_hint, prompt, timeout_s)
        if error:
            return {"nodes": [], "edges": [], "error": error}
        # 解析 LLM 返回的 JSON 结构
        try:
            result = _parse_json_response(response)
            assert "nodes" in result and "edges" in result
            return result
        except Exception as e:
            # 兜底：返回最小结构，便于前端继续流程
            return {"nodes": [], "edges": [], "error": str(e), "raw": response}

    def _run_llm(self, schema_hint: str, prompt: str, timeout_s: int):
        response = None
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self.llm_client.structured_extract, schema_hint, prompt)
            response = future.result(timeout=timeout_s)
            return response, None
        except concurrent.futures.TimeoutError:
            future.cancel()
            return None, f"llm_timeout_{timeout_s}s"
        except Exception as e:
            return None, str(e)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _extract_from_chunks(self, outline_text: str, schema_hint: str, timeout_s: int, chunk_size: int, max_workers: int, max_chunks: int) -> Dict:
        chunks = _split_text(outline_text, chunk_size)
        if len(chunks) > max_chunks:
            chunk_size = max(chunk_size, int(len(outline_text) / max_chunks) + 1)
            chunks = _split_text(outline_text, chunk_size)
        if not chunks:
            return {"nodes": [], "edges": [], "error": "empty_chunks"}

        def build_prompt(text: str) -> str:
            return (
                "你是一名课程设计专家。请从以下文本中提取核心概念及先修/组成关系，严格输出JSON，字段含义参考Schema。\n"
                "约束：节点id用英文或拼音短标识；难度0.0-1.0；bloom_level按认知维度分类；status默认Generated。\n"
                f"文本：\n{text}"
            )

        extractions = []
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self._extract_single_chunk, chunk, schema_hint, timeout_s, build_prompt): idx
                for idx, chunk in enumerate(chunks)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                except Exception as e:
                    errors.append(f"chunk_{idx}_error: {e}")
                    continue
                if result.get("error"):
                    errors.append(f"chunk_{idx}_error: {result.get('error')}")
                    continue
                extractions.append(result)

        merged = _merge_extractions(extractions)
        if not merged.get("nodes") and not merged.get("edges"):
            return {"nodes": [], "edges": [], "error": "llm_all_chunks_failed", "errors": errors}
        if errors:
            merged["errors"] = errors
        return merged

    def _extract_single_chunk(self, chunk: str, schema_hint: str, timeout_s: int, prompt_builder) -> Dict:
        prompt = prompt_builder(chunk)
        response, error = self._run_llm(schema_hint, prompt, timeout_s)
        if error:
            return {"nodes": [], "edges": [], "error": error}
        try:
            result = _parse_json_response(response)
            assert "nodes" in result and "edges" in result
            return result
        except Exception as e:
            return {"nodes": [], "edges": [], "error": str(e), "raw": response}
