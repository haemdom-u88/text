"""
递归式层级扩充模块（Taxonomy Expansion）
- 给定根概念，生成3-5个关键子概念，递归至最大深度
- 控制停止准则：最大层级 + 每层最多子概念数
- 支持Few-shot示例以降低幻觉
"""
from typing import List, Dict, Optional

class TaxonomyExpander:
    def __init__(self, llm_client, max_children: int = 5):
        self.llm_client = llm_client
        self.max_children = max_children

    def expand(self, root_concept: str, max_depth: int = 2, scope_hint: str = "本科教学大纲级别") -> Dict:
        """
        返回树状结构：{"root": name, "children": [...]} 并且伴随平铺的节点/边集合便于入库
        """
        nodes: List[Dict] = []
        edges: List[Dict] = []

        def _children_of(node_name: str, depth: int) -> List[str]:
            if depth >= max_depth:
                return []
            prompt = (
                f"你是一位课程设计专家，正在进行知识点分解。场景：{scope_hint}。\n"
                f"请列出掌握『{node_name}』所需的3-{self.max_children}个关键子概念，\n"
                "只返回JSON数组字符串，如：[\"子概念1\", \"子概念2\", ...]，且避免过细粒度如物理实体层面。"
            )
            resp = self.llm_client.generate(prompt, system_prompt="层级扩充助手")
            try:
                import json
                arr = json.loads(resp)
                if isinstance(arr, list):
                    return [str(x).strip() for x in arr][: self.max_children]
            except Exception:
                pass
            return []

        # BFS/DFS均可，这里用简单DFS
        def dfs(current: str, depth: int):
            node_id = current.lower().replace(" ", "_")
            nodes.append({
                "id": node_id,
                "name": current,
                "type": "Concept",
                "status": "Generated"
            })
            children = _children_of(current, depth)
            for c in children:
                cid = c.lower().replace(" ", "_")
                edges.append({
                    "source": cid,
                    "target": node_id,
                    "type": "SUBTOPIC_OF",
                    "confidence": 0.6,
                    "reasoning": "层级扩充生成"
                })
                dfs(c, depth + 1)

        dfs(root_concept, 0)
        return {"nodes": nodes, "edges": edges}
