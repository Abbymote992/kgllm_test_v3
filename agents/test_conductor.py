"""
测试指挥协调智能体
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print(f"项目根目录: {project_root}")

# 导入模块
from agents.conductor_agent import ConductorAgent
from agents.context import AgentContext
from models.agent_models import IntentType, AgentType


# ==================== Mock服务 ====================

class MockLLMService:
    """Mock LLM服务 - 智能识别"""

    async def generate(self, prompt, system_prompt=None, temperature=0.7):
        """模拟LLM响应，根据问题内容智能判断"""
        prompt_lower = prompt.lower() if prompt else ""

        # 根据问题内容判断意图
        if "什么是" in prompt_lower or "是什么" in prompt_lower:
            return '{"intent": "simple_qa", "params": {}}'
        elif "怎么办" in prompt_lower or "如何处理" in prompt_lower:
            return '{"intent": "complex", "params": {"project_id": "PROJ-EAST4-001"}}'
        elif "风险" in prompt_lower:
            return '{"intent": "risk", "params": {"project_id": "PROJ-EAST4-001"}}'
        elif "采购" in prompt_lower:
            return '{"intent": "procurement", "params": {"project_id": "PROJ-EAST4-001"}}'
        elif "齐套" in prompt_lower or "缺料" in prompt_lower:
            return '{"intent": "analysis", "params": {"project_id": "PROJ-EAST4-001"}}'
        else:
            return '{"intent": "simple_qa", "params": {}}'

    async def generate_stream(self, prompt, system_prompt=None):
        yield "这是"
        yield "模拟"
        yield "的流式"
        yield "回答"


class MockDataKnowledgeAgent:
    async def execute(self, context):
        return {
            "graph_data": {"nodes": [], "relationships": []},
            "knowledge_context": [],
            "business_rules": {"kit_rate_formula": "已到货/总需求"},
            "standardized_view": {
                "materials": [
                    {"code": "MTL-001", "name": "推力器阀门", "required": 4, "available": 0},
                    {"code": "MTL-002", "name": "压力传感器", "required": 8, "available": 2}
                ]
            }
        }


class MockAnalysisAgent:
    async def execute(self, context):
        return {
            "kit_rate": 0.75,
            "total_materials": 10,
            "kitted_count": 7,
            "shortages": [
                {"material_code": "MTL-001", "material_name": "推力器阀门",
                 "required_quantity": 4, "available_quantity": 0, "shortage_quantity": 4, "status": "critical"},
                {"material_code": "MTL-002", "material_name": "压力传感器",
                 "required_quantity": 8, "available_quantity": 2, "shortage_quantity": 6, "status": "risk"}
            ],
            "health_score": 65
        }


class MockRiskAgent:
    async def execute(self, context):
        return {
            "overall_risk_level": "medium",
            "shortage_risk": "high",
            "supplier_risk": {"航天阀门厂": "low", "电子科技集团": "medium"},
            "alerts": [{"level": "high", "message": "推力器阀门严重缺货，可能影响生产"}]
        }


class MockDecisionAgent:
    async def execute(self, context):
        return {
            "urgency": "紧急",
            "procurement_actions": [{"material": "推力器阀门", "action": "立即催货", "priority": "高"}],
            "recommended_action": "立即联系供应商确认推力器阀门交期，同时启动备选供应商评估"
        }


# ==================== 测试函数 ====================

async def test_intent_recognition():
    """测试意图识别"""
    print("\n" + "=" * 60)
    print("测试1: 意图识别")
    print("=" * 60)

    llm_service = MockLLMService()
    conductor = ConductorAgent(llm_service)

    test_questions = [
        ("推进舱的齐套率是多少？", "analysis"),
        ("东四平台卫星存在哪些供应风险？", "risk"),
        ("缺货物料应该怎么采购？", "procurement"),
        ("什么是宇航级元器件？", "simple_qa"),
        ("推进舱缺料怎么办？需要分析原因、评估风险并给出采购建议", "complex")
    ]

    passed = 0
    for question, expected_intent in test_questions:
        context = AgentContext(f"session_{question[:10]}", question)
        result = await conductor._recognize_intent(context)

        print(f"\n问题: {question}")
        print(f"  识别意图: {result['intent'].value}")
        print(f"  期望意图: {expected_intent}")

        if result['intent'].value == expected_intent:
            print("  ✅ 通过")
            passed += 1
        else:
            print(f"  ❌ 失败")

    print(f"\n意图识别通过率: {passed}/{len(test_questions)}")


async def test_execution_plan_creation():
    """测试执行计划创建"""
    print("\n" + "=" * 60)
    print("测试2: 执行计划创建")
    print("=" * 60)

    llm_service = MockLLMService()
    conductor = ConductorAgent(llm_service)

    test_cases = [
        (IntentType.ANALYSIS, 2),
        (IntentType.RISK, 2),
        (IntentType.PROCUREMENT, 4),
        (IntentType.COMPLEX, 4),
        (IntentType.SIMPLE_QA, 0)
    ]

    for intent, expected_count in test_cases:
        context = AgentContext(f"session_{intent.value}", f"测试问题")
        context.set_intent(intent, {})

        plan = await conductor._create_execution_plan(context)

        print(f"\n意图: {intent.value}")
        print(f"  子任务数量: {len(plan.subtasks)}")

        if len(plan.subtasks) == expected_count:
            print("  ✅ 通过")
        else:
            print(f"  ❌ 失败 (期望 {expected_count})")


async def test_full_execution():
    """测试完整执行流程"""
    print("\n" + "=" * 60)
    print("测试3: 完整执行流程")
    print("=" * 60)

    llm_service = MockLLMService()
    conductor = ConductorAgent(llm_service)

    # 注册Mock智能体
    conductor.register_agent(AgentType.DATA_KNOWLEDGE, MockDataKnowledgeAgent())
    conductor.register_agent(AgentType.ANALYSIS, MockAnalysisAgent())
    conductor.register_agent(AgentType.RISK, MockRiskAgent())
    conductor.register_agent(AgentType.DECISION, MockDecisionAgent())

    context = AgentContext(
        session_id="test_session_001",
        question="东四平台卫星推进舱下周总装，当前物料齐套情况如何？"
    )

    print("\n开始执行...")
    result = await conductor.execute(context)

    print(f"\n执行结果:")
    print(f"  意图: {result['intent']}")
    print(f"  答案: {result['answer'][:200]}...")

    print("\n✅ 完整执行流程测试通过")


async def test_simple_qa():
    """测试简单问答"""
    print("\n" + "=" * 60)
    print("测试4: 简单问答")
    print("=" * 60)

    llm_service = MockLLMService()
    conductor = ConductorAgent(llm_service)

    # 简单问答不需要注册任何智能体

    context = AgentContext(
        session_id="test_session_002",
        question="什么是宇航级元器件？"
    )

    result = await conductor.execute(context)

    print(f"\n问题: {context.question}")
    print(f"意图: {result['intent']}")
    print(f"答案: {result['answer']}")

    if result['intent'] == "simple_qa":
        print("\n✅ 简单问答测试通过")
    else:
        print(f"\n❌ 简单问答测试失败")


async def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 60)
    print("测试5: 健康检查")
    print("=" * 60)

    llm_service = MockLLMService()
    conductor = ConductorAgent(llm_service)

    conductor.register_agent(AgentType.DATA_KNOWLEDGE, MockDataKnowledgeAgent())
    conductor.register_agent(AgentType.ANALYSIS, MockAnalysisAgent())

    health = await conductor.health_check()

    print(f"\n健康状态:")
    print(f"  智能体: {health['agent']}")
    print(f"  健康: {health['healthy']}")
    print(f"  已注册智能体数: {health['registered_count']}")

    if health['healthy']:
        print("\n✅ 健康检查测试通过")


async def main():
    print("=" * 60)
    print("指挥协调智能体测试")
    print("=" * 60)

    await test_intent_recognition()
    await test_execution_plan_creation()
    await test_full_execution()
    await test_simple_qa()
    await test_health_check()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())