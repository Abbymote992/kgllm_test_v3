# backend/services/task_manager.py
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TaskManager:
    """异步任务管理器"""

    def __init__(self, task_timeout=180):  # 3分钟超时
        self.tasks: Dict[str, Dict] = {}
        self.task_timeout = task_timeout
        self._cleanup_task = None

    def create_task(self, question: str) -> str:
        """创建新任务，返回task_id"""
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "id": task_id,
            "question": question,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now(),
            "result": None,
            "error": None,
            "cypher": None,
            "steps": []
        }
        logger.info(f"创建任务: {task_id}, 问题: {question[:50]}...")

        # 启动清理任务
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        return task_id

    def update_task(self, task_id: str, **kwargs):
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)

    def add_step(self, task_id: str, step_name: str, step_data: Any = None):
        """添加执行步骤"""
        if task_id in self.tasks:
            self.tasks[task_id]["steps"].append({
                "name": step_name,
                "data": step_data,
                "timestamp": datetime.now().isoformat()
            })

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        task = self.tasks.get(task_id)
        if task:
            # 检查是否超时
            elapsed = (datetime.now() - task["created_at"]).total_seconds()
            if elapsed > self.task_timeout and task["status"] not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task["status"] = TaskStatus.TIMEOUT
                task["error"] = "任务执行超时"
        return task

    def complete_task(self, task_id: str, result: str, cypher: str = None):
        """完成任务"""
        if task_id in self.tasks:
            self.tasks[task_id].update({
                "status": TaskStatus.COMPLETED,
                "result": result,
                "cypher": cypher
            })
            logger.info(f"任务完成: {task_id}")

    def fail_task(self, task_id: str, error: str):
        """任务失败"""
        if task_id in self.tasks:
            self.tasks[task_id].update({
                "status": TaskStatus.FAILED,
                "error": error
            })
            logger.error(f"任务失败: {task_id}, 错误: {error}")

    async def _cleanup_loop(self):
        """定期清理过期任务"""
        while True:
            await asyncio.sleep(300)  # 5分钟清理一次
            now = datetime.now()
            to_delete = []
            for task_id, task in self.tasks.items():
                # 删除超过1小时的任务
                if (now - task["created_at"]).total_seconds() > 3600:
                    to_delete.append(task_id)

            for task_id in to_delete:
                del self.tasks[task_id]

            if to_delete:
                logger.info(f"清理了 {len(to_delete)} 个过期任务")


# 全局任务管理器实例
task_manager = TaskManager()