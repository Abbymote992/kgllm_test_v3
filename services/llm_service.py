# backend/services/llm_service.py
from openai import OpenAI
import json
import logging
import hashlib
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
    """大模型服务 - 带缓存"""

    def __init__(self, api_base: str, api_key: str, model: str, cache_enabled=True):
        self.client = OpenAI(
            base_url=api_base,
            api_key=api_key,
            timeout=120.0  # 增加超时到120秒
        )
        self.model = model
        self.cache_enabled = cache_enabled
        self.cache = SimpleCache(max_size=100, ttl=3600) if cache_enabled else None

    def _get_data_hash(self, data: List[Dict]) -> str:
        """计算数据hash，用于缓存判断"""
        data_str = json.dumps(data[:50], sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()

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
        """实际生成回答（流式）"""
        prompt = self._build_answer_prompt(question, data, count)

        try:
            # 使用流式响应
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的供应链助手，根据知识图谱查询结果回答问题。请简洁、准确。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800,
                stream=True  # 启用流式
            )

            # 收集流式响应
            full_answer = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    full_answer += chunk.choices[0].delta.content

            return full_answer if full_answer else self._format_raw_data(data, count)

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
                    {"role": "system", "content": "你是一个专业的供应链助手，根据知识图谱查询结果回答问题。请简洁、准确。"},
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

            # 保存缓存
            if self.cache_enabled and self.cache and full_answer:
                data_hash = self._get_data_hash(data)
                self.cache.set(question, data_hash, full_answer)

        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            yield self._format_raw_data(data, count)

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