# backend/config.py
import os
from typing import Dict, Any


class Config:
    """应用配置 - 统一配置中心"""

    # ==================== 基础配置 ====================
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # CORS配置
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8080"
    ]

    # ==================== Neo4j 配置 ====================
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jj")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

    # ==================== LLM 配置 (Ollama) ====================
    LLM_API_BASE = os.getenv("LLM_API_BASE", "http://localhost:11434/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen2:1.5b")  # 实验用小模型
    LLM_API_KEY = os.getenv("LLM_API_KEY", "local-test-key")
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 60))

    # ==================== 缓存配置 ====================
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))  # 缓存1小时

    # ==================== 智能体配置 ====================
    AGENT_CONFIG = {
        "enable_multi_agent": True,      # 是否启用多智能体模式
        "enable_streaming": True,         # 是否启用流式响应
        "max_retries": 3,                 # 最大重试次数
        "retry_delay": 1.0,               # 重试延迟（秒）
        "timeout": 120,                   # 超时时间（秒）
        "enable_debug": os.getenv("DEBUG", "True").lower() == "true"
    }

    # ==================== 数据源配置 ====================
    DATA_SOURCE_CONFIG = {
        "use_mock": True,                  # 是否使用Mock数据（实验阶段）
        "platform1_bom": {
            "enabled": True,
            "type": "mock",                # mock / rest_api / database
            "endpoint": None
        },
        "platform2_schedule": {
            "enabled": True,
            "type": "mock",
            "endpoint": None
        },
        "srm": {
            "enabled": True,
            "type": "mock",
            "endpoint": None
        },
        "wms": {
            "enabled": True,
            "type": "mock",
            "endpoint": None
        }
    }

    # ==================== 查询限制 ====================
    MAX_QUERY_LIMIT = 100
    DEFAULT_GRAPH_LIMIT = 50

    # ==================== 日志配置 ====================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


# 创建全局配置实例
config = Config()


# ==================== 兼容旧代码的函数 ====================
def get_cors_origins() -> list:
    """获取CORS允许的源"""
    return config.CORS_ORIGINS


def get_neo4j_config() -> Dict[str, str]:
    """获取Neo4j配置字典"""
    return {
        "uri": config.NEO4J_URI,
        "user": config.NEO4J_USER,
        "password": config.NEO4J_PASSWORD,
        "database": config.NEO4J_DATABASE
    }


def get_ollama_config() -> Dict[str, Any]:
    """获取Ollama配置字典"""
    return {
        "base_url": config.LLM_API_BASE.replace("/v1", ""),  # 去掉/v1后缀
        "model": config.LLM_MODEL,
        "timeout": config.LLM_TIMEOUT
    }


# ==================== 兼容旧代码的别名 ====================
# 让其他模块可以使用 from config import NEO4J_URI 的方式
NEO4J_URI = config.NEO4J_URI
NEO4J_USER = config.NEO4J_USER
NEO4J_PASSWORD = config.NEO4J_PASSWORD
LLM_API_BASE = config.LLM_API_BASE
LLM_MODEL = config.LLM_MODEL
LLM_API_KEY = config.LLM_API_KEY
CACHE_ENABLED = config.CACHE_ENABLED
CACHE_TTL = config.CACHE_TTL
DEBUG = config.DEBUG
HOST = config.HOST
PORT = config.PORT
MAX_QUERY_LIMIT = config.MAX_QUERY_LIMIT
DEFAULT_GRAPH_LIMIT = config.DEFAULT_GRAPH_LIMIT
AGENT_CONFIG = config.AGENT_CONFIG