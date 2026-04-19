# backend/services/llm_service.py
from openai import OpenAI
import json
import logging
import hashlib
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import OrderedDict

logger = logging.getLogger(__name__)


class SimpleCache:
    """简单的内存缓存，支持TTL和LRU"""

    def __init__(self, max_size=100, ttl=3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def _make_key(self, question: str, data_hash: str) -> str:
        """生成缓存key"""
        content = f"{question}_{data_hash}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, question: str, data_hash: str) -> Optional[str]:
        """获取缓存"""
        key = self._make_key(question, data_hash)
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                # 移到末尾（LRU）
                self.cache.move_to_end(key)
                logger.info(f"缓存命中: {question[:30]}...")
                return value
            else:
                del self.cache[key]
        return None

    def set(self, question: str, data_hash: str, answer: str):
        """设置缓存"""
        key = self._make_key(question, data_hash)
        self.cache[key] = (answer, datetime.now())
        # 保持最大大小
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
        logger.info(f"缓存保存: {question[:30]}...")


class LLMService:
    """大模型服务 - 带缓存和流式支持"""

    def __init__(self, api_base: str, api_key: str, model: str, cache_enabled=True):
        self.client = OpenAI(
            base_url=api_base,
            api_key=api_key,
            timeout=120.0
        )
        self.model = model
        self.cache_enabled = cache_enabled
        self.cache = SimpleCache(max_size=100, ttl=3600) if cache_enabled else None

    async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: int = 1200
    ) -> str:
        """
        给多智能体统一使用的异步生成接口（BaseAgent._call_llm 依赖此方法）
        """
        import asyncio

        system_text = system_prompt or "你是一个专业的供应链分析助手。"

        def _sync_call() -> str:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            content = response.choices[0].message.content if response.choices else ""
            return (content or "").strip()

        return await asyncio.get_event_loop().run_in_executor(None, _sync_call)

    def _get_data_hash(self, data: List[Dict]) -> str:
        """计算数据hash，用于缓存判断"""
        data_str = json.dumps(data[:50], sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()

    def _clean_cypher(self, cypher: str) -> str:
        """清理 Cypher 语句"""
        if not cypher:
            return cypher

        # 移除 markdown 代码块标记
        cypher = re.sub(r'^```cypher\n?', '', cypher)
        cypher = re.sub(r'^```\n?', '', cypher)
        cypher = re.sub(r'\n?```$', '', cypher)

        # 只取第一个分号之前的内容
        if ';' in cypher:
            cypher = cypher.split(';')[0]

        # 按行处理，移除多余的中文说明
        lines = cypher.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过包含中文提示的行
            if any(keyword in line for keyword in ['请告诉我', '帮助', '需要', '如有', '如果', '有任何', '问题']):
                continue

            # 如果行包含中文但不是 Cypher 关键字，跳过
            if re.search(r'[\u4e00-\u9fff]', line):
                if not any(kw in line.upper() for kw in
                           ['MATCH', 'RETURN', 'WHERE', 'WITH', 'CREATE', 'MERGE', 'OPTIONAL']):
                    continue

            cleaned_lines.append(line)

        cypher = ' '.join(cleaned_lines).strip()

        # 确保有 RETURN 子句
        if cypher and 'RETURN' not in cypher.upper():
            cypher += ' RETURN 1'

        return cypher

    def generate_answer(self, question: str, query_result: Dict[str, Any]) -> str:
        """根据查询结果生成自然语言回答（带缓存）"""
        if not query_result.get("success", False):
            return f"查询失败: {query_result.get('error', '未知错误')}"

        data = query_result.get("data", [])
        count = query_result.get("count", 0)

        if count == 0:
            return "未找到相关信息，请尝试换个问题。"

        # 检查缓存
        if self.cache_enabled and self.cache:
            data_hash = self._get_data_hash(data)
            cached_answer = self.cache.get(question, data_hash)
            if cached_answer:
                return cached_answer

        # 生成新回答
        answer = self._do_generate_answer(question, data, count)

        # 保存缓存
        if self.cache_enabled and self.cache and answer:
            data_hash = self._get_data_hash(data)
            self.cache.set(question, data_hash, answer)

        return answer

    def _do_generate_answer(self, question: str, data: List[Dict], count: int) -> str:
        """实际生成回答"""
        prompt = self._build_answer_prompt(question, data, count)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的供应链助手，根据知识图谱查询结果回答问题。请简洁、准确，只输出答案，不要添加额外说明。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            answer = response.choices[0].message.content.strip()

            # 清理多余内容
            answer = self._clean_answer(answer)

            return answer if answer else self._format_raw_data(data, count)

        except Exception as e:
            logger.error(f"生成回答失败: {e}")
            return self._format_raw_data(data, count)

    def generate_answer_stream(self, question: str, query_result: Dict[str, Any]):
        """流式生成回答（生成器）"""
        if not query_result.get("success", False):
            yield f"查询失败: {query_result.get('error', '未知错误')}"
            return

        data = query_result.get("data", [])
        count = query_result.get("count", 0)

        if count == 0:
            yield "未找到相关信息，请尝试换个问题。"
            return

        # 检查缓存
        if self.cache_enabled and self.cache:
            data_hash = self._get_data_hash(data)
            cached_answer = self.cache.get(question, data_hash)
            if cached_answer:
                yield cached_answer
                return

        prompt = self._build_answer_prompt(question, data, count)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的供应链助手，根据知识图谱查询结果回答问题。请简洁、准确，只输出答案，不要添加额外说明。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800,
                stream=True
            )

            full_answer = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    yield content

            # 清理并保存缓存
            full_answer = self._clean_answer(full_answer)
            if self.cache_enabled and self.cache and full_answer:
                data_hash = self._get_data_hash(data)
                self.cache.set(question, data_hash, full_answer)

        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            yield self._format_raw_data(data, count)

    def _clean_answer(self, answer: str) -> str:
        """清理回答中的多余内容"""
        if not answer:
            return answer

        # 移除常见的多余开头
        prefixes_to_remove = [
            "好的", "没问题", "根据查询结果", "以下是", "为您查询到",
            "根据知识图谱", "根据数据", "查询结果显示"
        ]

        for prefix in prefixes_to_remove:
            if answer.startswith(prefix):
                answer = answer[len(prefix):].lstrip('，').lstrip('：').lstrip()

        # 移除多余的结尾
        suffixes_to_remove = [
            "如果您还有其他问题", "如有其他问题", "需要帮助请随时",
            "希望以上信息", "以上是查询结果"
        ]

        for suffix in suffixes_to_remove:
            if suffix in answer:
                answer = answer.split(suffix)[0]

        return answer.strip()

    def _build_answer_prompt(self, question: str, data: List[Dict], count: int) -> str:
        """构建回答Prompt"""
        data_str = json.dumps(data[:15], ensure_ascii=False, indent=2)

        return f"""
用户问题: {question}

知识图谱查询结果 (共{count}条):
{data_str}

请根据以上结果，用简洁、清晰的中文回答用户问题。
要求:
1. 如果结果有多个，用列表形式展示
2. 突出关键信息（物料名称、供应商名称等）
3. 回答要简洁，不要超过200字
4. 只输出答案，不要添加"好的"、"以下是"等开场白

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
