"""
graph_builder.py
知识图谱构建器：将抽取结果转为图结构，支持查询与导出
"""
from typing import List, Dict

class KnowledgeGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []

    def build_from_extraction(self, extraction: Dict):
        """
        extraction: {"nodes": [...], "edges": [...]}
        """
        for node in extraction.get("nodes", []):
            self.nodes[node["id"]] = node
        for edge in extraction.get("edges", []):
            # 兼容不同字段命名：relation/type
            e = {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "relation": edge.get("relation") or edge.get("type"),
                "confidence": edge.get("confidence"),
                "reasoning": edge.get("reasoning")
            }
            self.edges.append(e)

    def to_dict(self) -> Dict:
        return {"nodes": list(self.nodes.values()), "edges": self.edges}

    def find_prerequisites(self, concept_id: str) -> List[str]:
        """返回所有 concept_id 的直接前置概念 id"""
        return [e["source"] for e in self.edges if e["target"] == concept_id]

    def find_dependents(self, concept_id: str) -> List[str]:
        """返回所有 concept_id 的直接后继概念 id"""
        return [e["target"] for e in self.edges if e["source"] == concept_id]
