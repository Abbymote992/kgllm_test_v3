"""
测试决策智能体
"""

import asyncio
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.decision_agent import DecisionAgent
from agents.context import AgentContext
from models.agent_models import IntentType


# ==================== Mock数据 ====================

def create_mock_analysis_result():
    """创建Mock分析结果"""
    return {
        "kit_rate": 0.65,
        "total_materials": 10,
        "kitted_count": 6,
        "shortages": [
            {
                "material_code": "MTL-THR-001",
                "material_name": "推力器阀门",
                "required_quantity": 4,
                "available_quantity": 0,
                "shortage_quantity": 4,
                "status": "critical",
                "supplier_name": "航天阀门厂",
                "expected_arrival_date": "2026-04-20",
                "is_key_material": True
            },
            {
                "material_code": "MTL-SEN-004",
                "material_name": "压力传感器",
                "required_quantity": 8,
                "available_quantity": 0,
                "shortage_quantity": 8,
                "status": "critical",
                "supplier_name": "电子科技集团",
                "expected_arrival_date": None,
                "is_key_material": True
            },
            {
                "material_code": "MTL-PIP-003",
                "material_name": "高压管路",
                "required_quantity": 20,
                "available_quantity": 15,
                "shortage_quantity": 5,
                "status": "risk",
                "supplier_name": "标准件厂",
                "expected_arrival_date": "2026-04-10",
                "is_key_material": False
            }
        ],
        "health_score": 45
    }


def create_mock_risk_result():
    """创建Mock风险结果"""
    return {
        "overall_risk_level": "high",
        "shortage_risk": "high",
        "supplier_risk": {
            "航天阀门厂": "low",
            "电子科技集团": "medium",
            "标准件厂": "high"
        },
        "schedule_risk": "medium"
    }


def create_mock_data_context():
    """创建Mock数据上下文"""
    return {
        "standardized_view": {
            "purchases": [
                {
                    "material_code": "MTL-THR-001",
                    "supplier_name": "航天阀门厂",
                    "quantity": 4,
                    "status": "shipped"
                },
                {
                    "material_code": "MTL-PIP-003",
                    "supplier_name": "标准件厂",
                    "quantity": 20,
                    "status": "delayed"
                }
            ],
            "suppliers": [
                {
                    "supplier_name": "航天阀门厂",
                    "rating": "A",
                    "on_time_delivery_rate": 0.95
                },
                {
                    "supplier_name": "电子科技集团",
                    "rating": "B",
                    "on_time_delivery_rate": 0.80
                },
                {
                    "supplier_name": "标准件厂",
                    "rating": "D",
                    "on_time_delivery_rate": 0.60
                }
            ]
        }
    }


def create_mock_no_shortage_data():
    """创建无缺料数据"""
    return {
        "kit_rate": 1.0,
        "total_materials": 5,
        "kitted_count": 5,
        "shortages": [],
        "health_score": 100
    }


# ==================== 测试函数 ====================

async def test_urgency_determination():
    """测试紧急程度判断"""
    print("\n" + "=" * 60)
    print("测试1: 紧急程度判断")
    print("=" * 60)

    agent = DecisionAgent()

    # 场景1：高紧急
    urgency = agent._determine_urgency(0.55, "high", [{"material": "test"}])
    print(f"\n场景1（齐套率55%+高风险+有缺料）: {urgency}")
    assert urgency == "urgent", "应为紧急"

    # 场景2：中紧急
    urgency = agent._determine_urgency(0.75, "medium", [{"material": "test"}])
    print(f"场景2（齐套率75%+中风险+有缺料）: {urgency}")
    assert urgency == "normal", "应为常规"

    # 场景3：低紧急
    urgency = agent._determine_urgency(0.95, "low", [])
    print(f"场景3（齐套率95%+低风险+无缺料）: {urgency}")
    assert urgency == "low", "应为低优先级"

    print("\n✅ 紧急程度判断测试通过")


async def test_priority_score_calculation():
    """测试优先级分数计算"""
    print("\n" + "=" * 60)
    print("测试2: 优先级分数计算")
    print("=" * 60)

    agent = DecisionAgent()

    # 测试高优先级物料
    shortage_high = {
        "shortage_quantity": 8,
        "required_quantity": 8,
        "status": "critical",
        "is_key_material": True
    }
    score_high = agent._calculate_priority_score(
        shortage_high, "high", "urgent"
    )
    print(f"\n高优先级物料分数: {score_high}")
    assert score_high >= 80, "高优先级物料分数应 >= 80"

    # 测试低优先级物料
    shortage_low = {
        "shortage_quantity": 2,
        "required_quantity": 10,
        "status": "risk",
        "is_key_material": False
    }
    score_low = agent._calculate_priority_score(
        shortage_low, "low", "normal"
    )
    print(f"低优先级物料分数: {score_low}")
    assert score_low <= 60, "低优先级物料分数应 <= 60"

    print("\n✅ 优先级分数计算测试通过")


async def test_procurement_actions_generation():
    """测试采购行动生成"""
    print("\n" + "=" * 60)
    print("测试3: 采购行动生成")
    print("=" * 60)

    agent = DecisionAgent()
    analysis_result = create_mock_analysis_result()
    risk_result = create_mock_risk_result()
    data_context = create_mock_data_context()

    shortages = analysis_result.get("shortages", [])
    overall_risk = risk_result.get("overall_risk_level", "none")
    urgency = "urgent"

    actions = await agent._generate_procurement_actions(
        shortages, overall_risk, urgency, data_context
    )

    print(f"\n生成 {len(actions)} 条采购行动:")
    for i, action in enumerate(actions):
        print(f"\n行动 {i + 1}:")
        print(f"  物料: {action.material_name}")
        print(f"  行动: {action.action}")
        print(f"  优先级: {action.priority}")
        print(f"  原因: {action.reason[:50]}...")

    assert len(actions) > 0, "应生成采购行动"
    assert actions[0].priority == "高", "最高优先级应为高"

    print("\n✅ 采购行动生成测试通过")


async def test_alternatives_generation():
    """测试替代方案生成"""
    print("\n" + "=" * 60)
    print("测试4: 替代方案生成")
    print("=" * 60)

    agent = DecisionAgent()
    analysis_result = create_mock_analysis_result()
    data_context = create_mock_data_context()

    shortages = analysis_result.get("shortages", [])

    alternatives = await agent._generate_alternatives(shortages, data_context)

    print(f"\n生成 {len(alternatives)} 条替代方案:")
    for i, alt in enumerate(alternatives):
        print(f"  {i + 1}. {alt}")

    assert len(alternatives) > 0, "应生成替代方案"

    print("\n✅ 替代方案生成测试通过")


async def test_cost_analysis():
    """测试成本分析"""
    print("\n" + "=" * 60)
    print("测试5: 成本分析")
    print("=" * 60)

    agent = DecisionAgent()

    # 创建模拟采购行动
    from models.agent_models import ProcurementAction

    actions = [
        ProcurementAction(
            material_code="MTL-001",
            material_name="物料1",
            action="立即催货",
            priority="高",
            reason="缺货严重",
            estimated_cost_impact=4000,
            suggested_deadline=None
        ),
        ProcurementAction(
            material_code="MTL-002",
            material_name="物料2",
            action="启动备选供应商",
            priority="中",
            reason="供应商风险高",
            estimated_cost_impact=6000,
            suggested_deadline=None
        )
    ]

    shortages = create_mock_analysis_result().get("shortages", [])

    cost_analysis = await agent._analyze_costs(actions, [], shortages)

    print(f"\n成本分析结果:")
    print(f"  预计总成本: ¥{cost_analysis['total_estimated_cost']:,.2f}")
    print(f"  紧急采购额外成本: ¥{cost_analysis['urgent_extra_cost']:,.2f}")
    print(f"  预计停工损失: ¥{cost_analysis['estimated_downtime_cost']:,.2f}")
    print(f"  建议: {cost_analysis['recommendation']}")

    assert cost_analysis['total_estimated_cost'] > 0, "总成本应大于0"

    print("\n✅ 成本分析测试通过")


async def test_full_execution():
    """测试完整执行"""
    print("\n" + "=" * 60)
    print("测试6: 完整执行")
    print("=" * 60)

    agent = DecisionAgent()

    # 创建上下文
    context = AgentContext(
        session_id="test_session",
        question="缺货物料应该怎么采购？"
    )
    context.set_intent(IntentType.PROCUREMENT, {"project_id": "PROJ-EAST4-001"})

    # 设置分析结果、风控结果和数据上下文
    context.analysis_result = create_mock_analysis_result()
    context.risk_result = create_mock_risk_result()
    context.data_context = create_mock_data_context()

    result = await agent.execute(context)

    print(f"\n执行结果:")
    print(f"  紧急程度: {result['urgency']}")
    print(f"  采购行动数: {len(result['procurement_actions'])}")
    print(f"  替代方案数: {len(result['alternative_suggestions'])}")
    print(f"  推荐行动: {result['recommended_action'][:80]}...")
    print(f"\n摘要:\n{result['summary']}")

    assert len(result['procurement_actions']) > 0, "应生成采购行动"
    assert result['recommended_action'] != "", "应有推荐行动"

    print("\n✅ 完整执行测试通过")


async def test_no_shortage_scenario():
    """测试无缺料场景"""
    print("\n" + "=" * 60)
    print("测试7: 无缺料场景")
    print("=" * 60)

    agent = DecisionAgent()

    context = AgentContext(
        session_id="test_session",
        question="评估采购需求"
    )
    context.set_intent(IntentType.PROCUREMENT, {})
    context.analysis_result = create_mock_no_shortage_data()
    context.risk_result = {"overall_risk_level": "none"}
    context.data_context = {"standardized_view": {}}

    result = await agent.execute(context)

    print(f"\n执行结果:")
    print(f"  采购行动数: {len(result['procurement_actions'])}")
    print(f"  推荐行动: {result['recommended_action']}")

    assert len(result['procurement_actions']) == 0, "无缺料时应无采购行动"

    print("\n✅ 无缺料场景测试通过")


async def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 60)
    print("测试8: 健康检查")
    print("=" * 60)

    agent = DecisionAgent()
    health = await agent.health_check()

    print(f"\n健康状态:")
    print(f"  智能体: {health['agent']}")
    print(f"  健康: {health['healthy']}")
    print(f"  行动模板: {health['action_templates']}")

    assert health['healthy'] is True

    print("\n✅ 健康检查测试通过")


async def main():
    print("=" * 60)
    print("决策智能体测试")
    print("=" * 60)

    await test_urgency_determination()
    await test_priority_score_calculation()
    await test_procurement_actions_generation()
    await test_alternatives_generation()
    await test_cost_analysis()
    await test_full_execution()
    await test_no_shortage_scenario()
    await test_health_check()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())