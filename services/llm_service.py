# backend/services/llm_service.py
from openai import OpenAI
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """大模型服务 - 负责生成自然语言回答"""

    def __init__(self, api_base: str, api_key: str, model: str):
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.model = model

    def generate_answer(self, question: str, query_result: Dict[str, Any]) -> str:
        """根据查询结果生成自然语言回答"""
        if not query_result.get("success", False):
            return f"查询失败: {query_result.get('error', '未知错误')}"

        data = query_result.get("data", [])
        count = query_result.get("count", 0)

        if count == 0:
            return "未找到相关信息，请尝试换个问题。"

        # 构建Prompt
        prompt = self._build_answer_prompt(question, data, count)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的供应链助手，根据知识图谱查询结果回答问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"生成回答失败: {e}")
            # 降级方案：直接返回原始数据
            return self._format_raw_data(data, count)

    def _build_answer_prompt(self, question: str, data: List[Dict], count: int) -> str:
        """构建回答Prompt"""
        # 截取前20条数据
        data_str = json.dumps(data[:20], ensure_ascii=False, indent=2)

        return f"""
用户问题: {question}

知识图谱查询结果 (共{count}条):
{data_str}

请根据以上结果，用简洁、清晰的中文回答用户问题。
要求:
1. 如果结果有多个，用列表或表格形式展示
2. 突出关键信息
3. 如果结果包含项目、物料、供应商等信息，清晰说明它们之间的关系

回答:
"""

    def _format_raw_data(self, data: List[Dict], count: int) -> str:
        """格式化原始数据作为降级方案"""
        if not data:
            return "未找到相关信息"

        lines = [f"查询到 {count} 条结果:\n"]
        for i, item in enumerate(data[:10], 1):
            lines.append(f"{i}. {item}")

        if count > 10:
            lines.append(f"\n... 还有 {count - 10} 条结果")

        return "\n".join(lines)