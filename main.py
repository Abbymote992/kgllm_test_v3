# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

from config import config
from services.kg_service import KnowledgeGraphService
from services.llm_service import LLMService
from services.cypher_generator import CypherGenerator
from api import kg_api, chat_api

# backend/main.py (更新部分)
from config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO if not config.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="供应链知识图谱系统 API",
    description="基于知识图谱和大模型的供应链智能问答系统",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局服务实例
kg_service = None
llm_service = None
cypher_generator = None


@app.on_event("startup")
async def startup_event():
    """启动时初始化服务"""
    global kg_service, llm_service, cypher_generator

    logger.info("正在初始化服务...")

    # 初始化知识图谱服务
    try:
        kg_service = KnowledgeGraphService(
            uri=config.NEO4J_URI,
            user=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD
        )
        logger.info("知识图谱服务初始化成功")
    except Exception as e:
        logger.error(f"知识图谱服务初始化失败: {e}")
        raise

    # 初始化大模型服务
    try:
        # 在 startup_event 中初始化 LLM 服务时启用缓存
        llm_service = LLMService(
            api_base=config.LLM_API_BASE,
            api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL,
            cache_enabled=config.CACHE_ENABLED  # 启用缓存
        )
        logger.info(f"大模型服务初始化成功, 模型: {config.LLM_MODEL}")
    except Exception as e:
        logger.error(f"大模型服务初始化失败: {e}")
        llm_service = None

    # 初始化Cypher生成器
    try:
        cypher_generator = CypherGenerator(
            api_base=config.LLM_API_BASE,
            api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL
        )
        logger.info("Cypher生成器初始化成功")
    except Exception as e:
        logger.error(f"Cypher生成器初始化失败: {e}")
        cypher_generator = None

    logger.info("所有服务初始化完成")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    global kg_service
    if kg_service:
        kg_service.close()
        logger.info("知识图谱服务已关闭")


# 依赖注入函数
def get_kg_service():
    return kg_service


def get_llm_service():
    return llm_service


def get_cypher_generator():
    return cypher_generator


# 注册路由
app.include_router(kg_api.router, dependencies=[])
app.include_router(chat_api.router, dependencies=[])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "供应链知识图谱系统",
        "version": "1.0.0",
        "status": "running",
        "services": {
            "neo4j": kg_service.health_check() if kg_service else False,
            "llm": llm_service is not None
        }
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "neo4j": kg_service.health_check() if kg_service else False,
        "llm": llm_service is not None
    }