"""
智能体基类

所有智能体的抽象基类，提供通用功能：
- 日志记录
- 错误处理
- 重试机制
- LLM调用封装
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps

# 导入模型
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.agent_models import AgentContext, AgentType, TaskStatus


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        self.logger.warning(
                            f"{self.name} 执行失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        await asyncio.sleep(delay * (attempt + 1))
                    else:
                        self.logger.error(f"{self.name} 最终失败: {e}")
            raise last_error
        return wrapper
    return decorator


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(
        self,
        name: str,
        agent_type: AgentType,
        llm_service=None,
        kg_service=None
    ):
        """
        初始化智能体

        Args:
            name: 智能体名称
            agent_type: 智能体类型
            llm_service: LLM服务（可选，用于需要LLM的智能体）
            kg_service: 知识图谱服务（可选）
        """
        self.name = name
        self.agent_type = agent_type
        self.llm = llm_service
        self.kg = kg_service

        # 设置日志
        self.logger = logging.getLogger(f"agent.{name}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        # 统计信息
        self.stats = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "total_time_ms": 0
        }

    @abstractmethod
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        执行智能体任务

        Args:
            context: 智能体上下文

        Returns:
            执行结果字典
        """
        pass

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        调用LLM（封装）

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数

        Returns:
            LLM响应文本
        """
        if not self.llm:
            raise ValueError(f"{self.name} 未配置LLM服务")

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )
            return response
        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            raise

    def _log_execution(self, start_time: float, success: bool = True):
        """记录执行统计"""
        elapsed_ms = (time.time() - start_time) * 1000

        self.stats["total_calls"] += 1
        self.stats["total_time_ms"] += elapsed_ms

        if success:
            self.stats["success_calls"] += 1
        else:
            self.stats["failed_calls"] += 1

        self.logger.info(
            f"{self.name} 执行完成 - 耗时: {elapsed_ms:.2f}ms, "
            f"成功: {success}, 总调用: {self.stats['total_calls']}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_time = (
            self.stats["total_time_ms"] / self.stats["total_calls"]
            if self.stats["total_calls"] > 0 else 0
        )

        return {
            "name": self.name,
            "type": self.agent_type.value,
            "total_calls": self.stats["total_calls"],
            "success_calls": self.stats["success_calls"],
            "failed_calls": self.stats["failed_calls"],
            "success_rate": (
                self.stats["success_calls"] / self.stats["total_calls"]
                if self.stats["total_calls"] > 0 else 0
            ),
            "avg_time_ms": avg_time
        }

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查LLM服务（如果配置了）
            if self.llm:
                # 简单测试
                await self._call_llm("测试", temperature=0)

            # 检查KG服务（如果配置了）
            if self.kg:
                await self.kg.test_connection()

            return True
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return False