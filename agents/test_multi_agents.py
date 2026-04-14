"""
快速验证多智能体系统
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def test_multi_agent():
    """测试多智能体完整流程"""

    print("=" * 60)
    print("多智能体系统验证")
    print("=" * 60)

    # 1. 验证模块导入
    print("\n1. 验证模块导入...")
    try:
        from agents.conductor_agent import ConductorAgent
        from agents.data_knowledge_agent import DataKnowledgeAgent
        from agents.analysis_agent import AnalysisAgent
        from agents.risk_agent import RiskAgent
        from agents.decision_agent import DecisionAgent
        print("   ✅ 所有智能体模块导入成功")
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        return

    # 2. 验证配置
    print("\n2. 验证配置...")
    try:
        from config import config
        print(f"   ✅ 配置加载成功")
        print(f"      - LLM模型: {config.LLM_MODEL}")
        print(f"      - Neo4j: {config.NEO4J_URI}")
        print(f"      - 多智能体启用: {config.AGENT_CONFIG['enable_multi_agent']}")
    except Exception as e:
        print(f"   ❌ 配置失败: {e}")

    # 3. 验证API路由
    print("\n3. 验证API路由...")
    try:
        from api.chat_api import router as chat_router
        from api.agent_api import router as agent_router
        print("   ✅ API路由加载成功")
        print(f"      - 聊天接口: /api/chat")
        print(f"      - 智能体接口: /api/agent")
    except Exception as e:
        print(f"   ❌ API失败: {e}")

    print("\n" + "=" * 60)
    print("验证完成！请启动服务: uvicorn main:app --reload")
    print("访问 http://localhost:8000/docs 查看API文档")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_multi_agent())