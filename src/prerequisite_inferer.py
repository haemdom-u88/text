"""
前置关系推断（Relational Inference via CoT）
- 判断概念A是否为概念B的必要前置：输出YES/NO、置信度与推理摘要
"""
from typing import Dict

class PrerequisiteInferer:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def judge(self, concept_a: str, concept_b: str) -> Dict:
        prompt = (
            "任务：判断概念A是否是概念B的必要前置知识。\n"
            f"概念A：{concept_a}\n"
            f"概念B：{concept_b}\n"
            "指令：让我们一步步思考。简要定义概念B，并列出理解它所需的核心基础知识。\n"
            "检查概念A是否涵盖上述基础中的任何一项。如果没有概念A，学生能否完全掌握概念B？\n"
            "根据以上分析，输出关系判定结果（是/否）及置信度（0-1），严格JSON：\n"
            "{\"is_prerequisite\": true|false, \"confidence\": number, \"reasoning\": string}"
        )
        resp = self.llm_client.generate(prompt, system_prompt="CoT推理助手")
        try:
            import json
            data = json.loads(resp)
            return {
                "is_prerequisite": bool(data.get("is_prerequisite", False)),
                "confidence": float(data.get("confidence", 0.5)),
                "reasoning": str(data.get("reasoning", ""))
            }
        except Exception:
            # 兜底：弱判定
            return {"is_prerequisite": False, "confidence": 0.3, "reasoning": "解析失败，返回默认弱判定"}
