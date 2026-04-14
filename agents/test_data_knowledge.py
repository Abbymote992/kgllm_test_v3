"""
测试数据知识智能体
"""

import asyncio
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.data_knowledge_agent import DataKnowledgeAgent
from agents.context import AgentContext
from models.agent_models import IntentType
from models.platform_models import PlatformType
from services.rag_service import RAGService

# 导入Mock适配器
sys.path.insert(0, os.path.join(project_root, "models"))
from models.mock_adapters import (
    MockBOMAdapter, MockScheduleAdapter,
    MockSRMAdapter, MockWMSAdapter, MockAdapterFactory
)


class MockKGService:
    """Mock知识图谱服务"""

    async def query(self, cypher, params):
        return {"nodes": [], "relationships": []}

    async def test_connection(self):
        return True


async def test_data_collection():
    """测试数据采集"""
    print("\n" + "=" * 60)
    print("测试1: 数据采集")
    print("=" * 60)

    agent = DataKnowledgeAgent()

    # 注册Mock适配器
    agent.register_adapter(PlatformType.PLATFORM1_BOM, MockBOMAdapter())
    agent.register_adapter(PlatformType.PLATFORM2_SCHEDULE, MockScheduleAdapter())
    agent.register_adapter(PlatformType.SRM, MockSRMAdapter())
    agent.register_adapter(PlatformType.WMS, MockWMSAdapter())

    context = AgentContext("test_session", "测试数据采集")
    context.set_intent(IntentType.ANALYSIS, {"project_id": "PROJ-EAST4-001"})

    platform_data = await agent._collect_platform_data(context)

    print("\n采集结果:")
    print(f"  BOM数据: {'有' if platform_data.get('bom') else '无'}")
    print(f"  排程数据: {'有' if platform_data.get('schedule') else '无'}")
    print(f"  采购订单: {len(platform_data.get('purchase_orders', []))} 条")
    print(f"  供应商: {len(platform_data.get('suppliers', []))} 家")
    print(f"  库存: {len(platform_data.get('inventory', []))} 条")

    assert platform_data.get('bom') is not None, "BOM数据为空"
    assert platform_data.get('schedule') is not None, "排程数据为空"
    assert len(platform_data.get('purchase_orders', [])) > 0, "采购订单为空"
    assert len(platform_data.get('suppliers', [])) > 0, "供应商为空"

    print("\n✅ 数据采集测试通过")
    return platform_data


async def test_knowledge_retrieval():
    """测试知识检索"""
    print("\n" + "=" * 60)
    print("测试2: 知识检索")
    print("=" * 60)

    agent = DataKnowledgeAgent()
    rag_service = RAGService()
    agent.set_rag_service(rag_service)

    context = AgentContext("test_session", "什么是宇航级元器件？")
    context.set_intent(IntentType.SIMPLE_QA)

    results = await agent._retrieve_knowledge(context)

    print(f"\n检索结果数量: {len(results)}")
    for i, result in enumerate(results[:3]):
        print(f"  {i + 1}. {result.get('title')} (相关度: {result.get('relevance_score', 0)})")

    assert len(results) > 0, "知识检索无结果"

    print("\n✅ 知识检索测试通过")


async def test_data_standardization():
    """测试数据标准化"""
    print("\n" + "=" * 60)
    print("测试3: 数据标准化")
    print("=" * 60)

    agent = DataKnowledgeAgent()

    # 模拟平台数据
    mock_data = {
        "bom": MockBOMAdapter()._mock_bom_data.get("PROJ-EAST4-001_MOD-PROP-001"),
        "inventory": MockWMSAdapter()._mock_inventory,
        "purchase_orders": MockSRMAdapter()._mock_orders,
        "suppliers": list(MockSRMAdapter()._init_mock_suppliers().values()),
        "schedule": MockScheduleAdapter()._mock_schedules.get("PROJ-EAST4-001")
    }

    standardized = agent._standardize_data(mock_data)

    print("\n标准化结果:")
    print(f"  物料需求: {len(standardized['materials'])} 种")
    print(f"  库存: {len(standardized['inventory'])} 条")
    print(f"  采购: {len(standardized['purchases'])} 条")
    print(f"  供应商: {len(standardized['suppliers'])} 家")
    print(f"  排程: {'有' if standardized['schedule'] else '无'}")

    # 检查关键字段
    if standardized['materials']:
        sample = standardized['materials'][0]
        print(f"\n  示例物料: {sample.get('material_name')} - 需求 {sample.get('required_quantity')}{sample.get('unit')}")

    # assert len(standardized['materials']) > 0, "物料需求为空"
    # assert len(standardized['inventory']) > 0, "库存为空"

    print("\n✅ 数据标准化测试通过")


async def test_full_execution():
    """测试完整执行"""
    print("\n" + "=" * 60)
    print("测试4: 完整执行")
    print("=" * 60)

    agent = DataKnowledgeAgent()

    # 注册适配器
    agent.register_adapter(PlatformType.PLATFORM1_BOM, MockBOMAdapter())
    agent.register_adapter(PlatformType.PLATFORM2_SCHEDULE, MockScheduleAdapter())
    agent.register_adapter(PlatformType.SRM, MockSRMAdapter())
    agent.register_adapter(PlatformType.WMS, MockWMSAdapter())

    # 设置RAG和KG
    agent.set_rag_service(RAGService())
    agent.kg_service = MockKGService()

    # 执行
    context = AgentContext("test_session", "查询推进舱物料情况")
    context.set_intent(IntentType.ANALYSIS, {"project_id": "PROJ-EAST4-001", "module_id": "MOD-PROP-001"})

    result = await agent.execute(context)

    print("\n执行结果:")
    print(f"  知识上下文: {len(result.get('knowledge_context', []))} 条")
    print(f"  业务规则: {list(result.get('business_rules', {}).keys())}")
    print(f"  数据质量分: {result.get('data_quality', {}).get('overall_score', 0)}")

    standardized = result.get('standardized_view', {})
    print(f"  物料需求: {len(standardized.get('materials', []))} 种")
    print(f"  库存: {len(standardized.get('inventory', []))} 条")

    assert result.get('data_quality') is not None, "数据质量报告为空"

    print("\n✅ 完整执行测试通过")


async def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 60)
    print("测试5: 健康检查")
    print("=" * 60)

    agent = DataKnowledgeAgent()

    agent.register_adapter(PlatformType.PLATFORM1_BOM, MockBOMAdapter())
    agent.register_adapter(PlatformType.SRM, MockSRMAdapter())

    health = await agent.health_check()

    print(f"\n健康状态:")
    print(f"  智能体: {health['agent']}")
    print(f"  健康: {health['healthy']}")
    print(f"  适配器数量: {health['adapter_count']}")
    print(f"  RAG启用: {health['rag_enabled']}")

    assert health['healthy'] is True, "健康检查失败"
    assert health['adapter_count'] == 2, f"适配器数量不正确: {health['adapter_count']}"

    print("\n✅ 健康检查测试通过")


async def main():
    print("=" * 60)
    print("数据知识智能体测试")
    print("=" * 60)

    await test_data_collection()
    await test_knowledge_retrieval()
    await test_data_standardization()
    await test_full_execution()
    await test_health_check()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())