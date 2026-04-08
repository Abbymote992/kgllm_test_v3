# backend/config.py
import os


class Config:
    """应用配置"""

    # Neo4j 配置
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jj")

    # LLM 配置 (Ollama)
    LLM_API_BASE = os.getenv("LLM_API_BASE", "http://localhost:11434/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-r1:7b")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "local-test-key")

    # 应用配置
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # CORS
    CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    # 查询限制
    MAX_QUERY_LIMIT = 100
    DEFAULT_GRAPH_LIMIT = 50

#
# """
# 系统配置文件
# """
#
# import os
# from typing import Dict, Any
#
# # 项目根目录
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#
# # Neo4j配置
# NEO4J_CONFIG = {
#     "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
#     "user": os.getenv("NEO4J_USER", "neo4j"),
#     "password": os.getenv("NEO4J_PASSWORD", "neo4jj"),
#     "database": os.getenv("NEO4J_DATABASE", "graph07.db")
# }
#
# # Ollama配置
# OLLAMA_CONFIG = {
#     "base_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
#     "model": os.getenv("OLLAMA_MODEL", "qwen2:1.5b"),
#     "timeout": 60
# }
#
# # 智能体配置
# AGENT_CONFIG = {
#     "enable_multi_agent": True,      # 是否启用多智能体模式
#     "enable_streaming": True,         # 是否启用流式响应
#     "max_retries": 3,                 # 最大重试次数
#     "retry_delay": 1.0,               # 重试延迟（秒）
#     "timeout": 120                    # 超时时间（秒）
# }
#
# # 数据源配置（Mock/真实）
# DATA_SOURCE_CONFIG = {
#     "use_mock": True,                  # 是否使用Mock数据
#     "platform1_bom": {
#         "enabled": True,
#         "type": "mock",                # mock / rest_api / database
#         "endpoint": None
#     },
#     "platform2_schedule": {
#         "enabled": True,
#         "type": "mock",
#         "endpoint": None
#     },
#     "srm": {
#         "enabled": True,
#         "type": "mock",
#         "endpoint": None
#     },
#     "wms": {
#         "enabled": True,
#         "type": "mock",
#         "endpoint": None
#     }
# }
#
# # 日志配置
# LOG_CONFIG = {
#     "level": "INFO",
#     "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     "file": os.path.join(BASE_DIR, "logs", "app.log")
# }
#
# # CORS配置
# CORS_CONFIG = {
#     "allow_origins": ["http://localhost:5173", "http://localhost:3000"],
#     "allow_methods": ["*"],
#     "allow_headers": ["*"]
# }

# 环境配置
config = Config()