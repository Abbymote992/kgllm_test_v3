"""
智能体日志模块

提供结构化的日志记录功能
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps


class AgentLogger:
    """智能体日志记录器"""

    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        初始化日志记录器

        Args:
            name: 日志记录器名称
            log_file: 日志文件路径（可选）
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # 控制台输出
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # 文件输出（如果指定）
            if log_file:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)

    def info(self, message: str, extra: Dict[str, Any] = None):
        """记录INFO级别日志"""
        if extra:
            message = f"{message} | {json.dumps(extra, ensure_ascii=False)}"
        self.logger.info(message)

    def warning(self, message: str, extra: Dict[str, Any] = None):
        """记录WARNING级别日志"""
        if extra:
            message = f"{message} | {json.dumps(extra, ensure_ascii=False)}"
        self.logger.warning(message)

    def error(self, message: str, extra: Dict[str, Any] = None):
        """记录ERROR级别日志"""
        if extra:
            message = f"{message} | {json.dumps(extra, ensure_ascii=False)}"
        self.logger.error(message)

    def debug(self, message: str, extra: Dict[str, Any] = None):
        """记录DEBUG级别日志"""
        if extra:
            message = f"{message} | {json.dumps(extra, ensure_ascii=False)}"
        self.logger.debug(message)


def log_agent_execution(logger: AgentLogger):
    """智能体执行日志装饰器"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, context, *args, **kwargs):
            logger.info(
                f"开始执行 {self.name}",
                {"session_id": context.session_id, "question": context.question[:50]}
            )

            start_time = datetime.now()
            try:
                result = await func(self, context, *args, **kwargs)

                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.info(
                    f"{self.name} 执行成功",
                    {"session_id": context.session_id, "elapsed_ms": elapsed_ms}
                )
                return result
            except Exception as e:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.error(
                    f"{self.name} 执行失败: {str(e)}",
                    {"session_id": context.session_id, "elapsed_ms": elapsed_ms}
                )
                raise

        return wrapper

    return decorator