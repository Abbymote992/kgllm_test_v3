"""
智能体上下文管理

负责：
- 上下文创建和传递
- 执行日志记录
- 中间结果存储
"""

import uuid
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

# 导入模型
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.agent_models import (
    AgentContext as AgentContextModel,
    IntentType,
    SubTask,
    TaskStatus
)


class AgentContext:
    """智能体执行上下文"""

    def __init__(
            self,
            session_id: str,
            question: str,
            user_id: Optional[str] = None
    ):
        """
        初始化上下文

        Args:
            session_id: 会话ID
            question: 用户问题
            user_id: 用户ID（可选）
        """
        self.session_id = session_id
        self.question = question
        self.user_id = user_id

        # 意图和参数
        self.intent: Optional[IntentType] = None
        self.extracted_params: Dict[str, Any] = {}

        # 各智能体结果
        self.data_context: Optional[Dict[str, Any]] = None
        self.analysis_result: Optional[Dict[str, Any]] = None
        self.risk_result: Optional[Dict[str, Any]] = None
        self.decision_result: Optional[Dict[str, Any]] = None

        # 执行日志
        self.execution_log: List[Dict] = []

        # 时间记录
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # 错误信息
        self.error: Optional[str] = None

    def start_execution(self):
        """开始执行"""
        self.start_time = datetime.now()
        self._log("execution_started", {"question": self.question})

    def end_execution(self, success: bool = True):
        """结束执行"""
        self.end_time = datetime.now()
        self._log("execution_ended", {"success": success})

    def set_intent(self, intent: IntentType, params: Dict[str, Any] = None):
        """设置意图"""
        self.intent = intent
        if params:
            self.extracted_params.update(params)
        self._log("intent_set", {"intent": intent.value, "params": params})

    def set_agent_result(self, agent_name: str, result: Dict[str, Any]):
        """设置智能体结果"""
        if agent_name == "data_knowledge":
            self.data_context = result
        elif agent_name == "analysis":
            self.analysis_result = result
        elif agent_name == "risk":
            self.risk_result = result
        elif agent_name == "decision":
            self.decision_result = result

        self._log(f"{agent_name}_result", {"result_keys": list(result.keys())})

    def get_agent_result(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """获取智能体结果"""
        if agent_name == "data_knowledge":
            return self.data_context
        elif agent_name == "analysis":
            return self.analysis_result
        elif agent_name == "risk":
            return self.risk_result
        elif agent_name == "decision":
            return self.decision_result
        return None

    def _log(self, event: str, data: Dict[str, Any] = None):
        """记录日志"""
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data or {}
        })

    def set_error(self, error: str):
        """设置错误"""
        self.error = error
        self._log("error", {"error": error})

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "question": self.question,
            "user_id": self.user_id,
            "intent": self.intent.value if self.intent else None,
            "extracted_params": self.extracted_params,
            "execution_log": self.execution_log,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error": self.error,
            "has_data_context": self.data_context is not None,
            "has_analysis_result": self.analysis_result is not None,
            "has_risk_result": self.risk_result is not None,
            "has_decision_result": self.decision_result is not None,
        }

    def get_execution_time_ms(self) -> float:
        """获取执行时间（毫秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0


class ContextManager:
    """上下文管理器 - 管理多个会话的上下文"""

    def __init__(self, max_contexts: int = 100):
        """
        初始化上下文管理器

        Args:
            max_contexts: 最大缓存上下文数量
        """
        self._contexts: Dict[str, AgentContext] = {}
        self._max_contexts = max_contexts

    def create_context(
            self,
            session_id: str,
            question: str,
            user_id: Optional[str] = None
    ) -> AgentContext:
        """
        创建新上下文

        Args:
            session_id: 会话ID
            question: 用户问题
            user_id: 用户ID

        Returns:
            新创建的上下文
        """
        # 清理旧上下文（如果超出限制）
        if len(self._contexts) >= self._max_contexts:
            self._cleanup_old_contexts()

        context = AgentContext(session_id, question, user_id)
        self._contexts[session_id] = context
        return context

    def get_context(self, session_id: str) -> Optional[AgentContext]:
        """获取上下文"""
        return self._contexts.get(session_id)

    def update_context(self, session_id: str, context: AgentContext):
        """更新上下文"""
        self._contexts[session_id] = context

    def delete_context(self, session_id: str):
        """删除上下文"""
        if session_id in self._contexts:
            del self._contexts[session_id]

    def _cleanup_old_contexts(self):
        """清理旧的上下文（按时间排序，删除最旧的）"""
        # 按开始时间排序
        sorted_contexts = sorted(
            self._contexts.items(),
            key=lambda x: x[1].start_time or datetime.min
        )
        # 删除最旧的20%
        remove_count = int(self._max_contexts * 0.2)
        for session_id, _ in sorted_contexts[:remove_count]:
            del self._contexts[session_id]

    def get_all_contexts(self) -> List[AgentContext]:
        """获取所有上下文"""
        return list(self._contexts.values())

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        active_contexts = len(self._contexts)
        completed_contexts = sum(
            1 for ctx in self._contexts.values()
            if ctx.end_time is not None
        )

        return {
            "total_contexts": active_contexts,
            "completed_contexts": completed_contexts,
            "pending_contexts": active_contexts - completed_contexts,
            "max_contexts": self._max_contexts
        }