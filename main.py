# backend/main.py
"""
FastAPI主入口

启动命令: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import os

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config, get_cors_origins, get_neo4j_config, get_ollama_config
from api import chat_router, agent_router, kg_router

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="供应链知识图谱多智能体系统",
    description="基于Neo4j + LLM + 多智能体的供应链智能问答系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(kg_router)


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("正在初始化智能体系统...")
    logger.info(f"配置: DEBUG={config.DEBUG}, LLM模型={config.LLM_MODEL}")

    try:
        # 初始化Mock适配器
        sys.path.append(os.path.join(os.path.dirname(__file__), "models"))
        from models.mock_adapters import MockAdapterFactory
        from models.platform_models import PlatformType

        # 创建服务实例（使用统一配置）
        from services.llm_service import LLMService
        from services.kg_service import KnowledgeGraphService
        from services.rag_service import RAGService

        # 使用配置初始化服务
        llm_service = LLMService(
            api_base=config.LLM_API_BASE,
            api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL,
            cache_enabled=True
        )

        kg_service = KnowledgeGraphService(
            uri=config.NEO4J_URI,
            user=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD,
            # database=config.NEO4J_DATABASE
        )

        rag_service = RAGService()

        # 创建数据知识智能体并注册适配器
        from agents.data_knowledge_agent import DataKnowledgeAgent
        data_knowledge_agent = DataKnowledgeAgent(llm_service, kg_service)

        # 注册Mock适配器
        data_knowledge_agent.register_adapter(
            PlatformType.PLATFORM1_BOM,
            MockAdapterFactory.get_adapter(PlatformType.PLATFORM1_BOM)
        )
        data_knowledge_agent.register_adapter(
            PlatformType.PLATFORM2_SCHEDULE,
            MockAdapterFactory.get_adapter(PlatformType.PLATFORM2_SCHEDULE)
        )
        data_knowledge_agent.register_adapter(
            PlatformType.SRM,
            MockAdapterFactory.get_adapter(PlatformType.SRM)
        )
        data_knowledge_agent.register_adapter(
            PlatformType.WMS,
            MockAdapterFactory.get_adapter(PlatformType.WMS)
        )
        data_knowledge_agent.set_rag_service(rag_service)

        # 创建其他智能体
        from agents.analysis_agent import AnalysisAgent
        from agents.risk_agent import RiskAgent
        from agents.decision_agent import DecisionAgent
        from agents.conductor_agent import ConductorAgent

        analysis_agent = AnalysisAgent(llm_service, kg_service)
        risk_agent = RiskAgent(llm_service, kg_service)
        decision_agent = DecisionAgent(llm_service, kg_service)
        conductor_agent = ConductorAgent(llm_service, kg_service)

        # 注册智能体到指挥协调器
        from models.agent_models import AgentType
        conductor_agent.register_agent(AgentType.DATA_KNOWLEDGE, data_knowledge_agent)
        conductor_agent.register_agent(AgentType.ANALYSIS, analysis_agent)
        conductor_agent.register_agent(AgentType.RISK, risk_agent)
        conductor_agent.register_agent(AgentType.DECISION, decision_agent)

        # 初始化API
        from api.chat_api import init_agents as init_chat_agents
        init_chat_agents(
            conductor_agent, data_knowledge_agent,
            analysis_agent, risk_agent, decision_agent
        )

        from api.agent_api import init_agents as init_api_agents
        init_api_agents({
            "conductor": conductor_agent,
            "data_knowledge": data_knowledge_agent,
            "analysis": analysis_agent,
            "risk": risk_agent,
            "decision": decision_agent
        })

        logger.info("智能体系统初始化完成！")

    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("正在关闭智能体系统...")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "供应链知识图谱多智能体系统",
        "version": "1.0.0",
        "status": "running",
        "config": {
            "debug": config.DEBUG,
            "llm_model": config.LLM_MODEL,
            "neo4j_uri": config.NEO4J_URI
        },
        "endpoints": {
            "docs": "/docs",
            "chat": "/api/chat",
            "agent": "/api/agent",
            "kg": "/api/kg"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )