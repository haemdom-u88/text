"""
属性与元数据稠密化（Attribute Densification）
- Bloom认知层级、难度系数、学习时长、多风格定义
"""
from typing import Dict

class AttributeDensifier:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def densify(self, concept_name: str, concept_desc: str) -> Dict:
        prompt = (
            f"请为知识点『{concept_name}』进行属性稠密化。\n"
            f"描述：{concept_desc}\n"
            "严格JSON输出：{\n"
            "  \"bloom_level\": \"记忆\"|\"理解\"|\"应用\"|\"分析\"|\"评价\"|\"创造\",\n"
            "  \"difficulty\": 0.0-1.0,\n"
            "  \"estimated_hours\": number,\n"
            "  \"definitions\": {\n"
            "     \"simple_analogy\": string,\n"
            "     \"academic\": string\n"
            "  }\n"
            "}"
        )
        resp = self.llm_client.generate(prompt, system_prompt="属性稠密化助手")
        try:
            import json
            data = json.loads(resp)
            return {
                "bloom_level": data.get("bloom_level", "理解"),
                "difficulty": float(data.get("difficulty", 0.5)),
                "estimated_hours": float(data.get("estimated_hours", 2.0)),
                "definitions": data.get("definitions", {})
            }
        except Exception:
            return {
                "bloom_level": "理解",
                "difficulty": 0.5,
                "estimated_hours": 2.0,
                "definitions": {
                    "simple_analogy": f"通俗解释：{concept_name}是……",
                    "academic": f"学术定义：{concept_name}指……"
                }
            }
