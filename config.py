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


# 环境配置
config = Config()