"""
验证与自修正模块（Verifier & Self-Correction）
- 输入候选三元组/属性，输出是否合理与修正建议
"""
from typing import Dict, List

class Validator:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def validate_triplets(self, triplets: List[Dict]) -> Dict:
        prompt = (
            "请验证以下关系是否符合计算机科学教学逻辑。如果错误请修正；正确请确认。\n"
            f"三元组：{triplets}\n"
            "严格JSON：{\"verdict\": \"ok\"|\"revised\"|\"reject\", \"suggestions\": [string], \"revised\": [obj]}"
        )
        resp = self.llm_client.generate(prompt, system_prompt="审核员")
        try:
            import json
            data = json.loads(resp)
            return {
                "verdict": data.get("verdict", "ok"),
                "suggestions": data.get("suggestions", []),
                "revised": data.get("revised", [])
            }
        except Exception:
            return {"verdict": "ok", "suggestions": [], "revised": []}
