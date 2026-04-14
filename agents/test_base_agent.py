"""
测试智能体基类和上下文管理
"""

import asyncio
import sys
import os

# 添加路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent
from agents.context import AgentContext, ContextManager
from models.agent_models import IntentType, AgentType  # 添加 IntentType 导入


class MockLLMService:
    """Mock LLM服务"""
    async def generate(self, prompt, system_prompt=None, temperature=0.7):
        return f"Mock响应: {prompt[:50]}..."


class MockKGService:
    """Mock KG服务"""
    async def test_connection(self):
        return True


class TestAgent(BaseAgent):
    """测试用智能体"""

    def __init__(self):
        super().__init__(
            name="TestAgent",
            agent_type=AgentType.ANALYSIS,
            llm_service=MockLLMService(),
            kg_service=MockKGService()
        )

    async def execute(self, context: AgentContext) -> dict:
        """执行测试任务"""
        import time
        start_time = time.time()

        self._log_execution(start_time)

        return {
            "test_result": "success",
            "question": context.question,
            "session_id": context.session_id
        }


async def test_context_manager():
    """测试上下文管理器"""
    print("=" * 50)
    print("测试上下文管理器")
    print("=" * 50)

    manager = ContextManager(max_contexts=10)

    # 创建上下文
    context = manager.create_context(
        session_id="session-001",
        question="测试问题：推进舱缺料情况？",
        user_id="user-001"
    )

    context.start_execution()
    context.set_intent(IntentType.ANALYSIS, {"project_id": "PROJ-EAST4-001"})

    print(f"上下文创建成功: {context.session_id}")
    print(f"问题: {context.question}")
    print(f"意图: {context.intent}")
    print(f"参数: {context.extracted_params}")

    context.end_execution(success=True)

    # 获取统计
    stats = manager.get_stats()
    print(f"\n管理器统计: {stats}")

    return context


async def test_base_agent():
    """测试智能体基类"""
    print("\n" + "=" * 50)
    print("测试智能体基类")
    print("=" * 50)

    agent = TestAgent()

    # 健康检查
    health = await agent.health_check()
    print(f"健康检查: {health}")

    # 创建上下文
    context = AgentContext(
        session_id="session-002",
        question="推进舱齐套率是多少？"
    )

    # 执行
    result = await agent.execute(context)
    print(f"执行结果: {result}")

    # 获取统计
    stats = agent.get_stats()
    print(f"智能体统计: {stats}")

    return agent


async def test_context_lifecycle():
    """测试上下文生命周期"""
    print("\n" + "=" * 50)
    print("测试上下文生命周期")
    print("=" * 50)

    manager = ContextManager(max_contexts=3)

    # 创建多个上下文
    for i in range(5):
        context = manager.create_context(
            session_id=f"session-{i}",
            question=f"测试问题 {i}"
        )
        context.start_execution()
        context.set_intent(IntentType.SIMPLE_QA)
        context.end_execution(success=True)
        print(f"创建上下文 session-{i}")

    stats = manager.get_stats()
    print(f"\n最终统计（应只保留3个）: {stats}")

    # 验证清理
    contexts = manager.get_all_contexts()
    print(f"实际保留上下文数: {len(contexts)}")


async def main():
    """运行所有测试"""
    print("智能体基类和上下文管理测试")
    print("=" * 50)

    await test_context_manager()
    await test_base_agent()
    await test_context_lifecycle()

    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())