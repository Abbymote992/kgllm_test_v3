"""
测试风控智能体
"""

import asyncio
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.risk_agent import RiskAgent
from agents.context import AgentContext
from models.agent_models import IntentType, RiskLevel, RiskEvent  


# ==================== Mock数据 ====================

def create_mock_analysis_result():
    """创建Mock分析结果"""
    return {
        "kit_rate": 0.75,
        "total_materials": 10,
        "kitted_count": 7,
        "shortages": [
            {
                "material_code": "MTL-THR-001",
                "material_name": "推力器阀门",
                "required_quantity": 4,
                "available_quantity": 0,
                "shortage_quantity": 4,
                "status": "critical",
                "supplier_name": "航天阀门厂",
                "expected_arrival_date": "2026-04-20"
            },
            {
                "material_code": "MTL-SEN-004",
                "material_name": "压力传感器",
                "required_quantity": 8,
                "available_quantity": 0,
                "shortage_quantity": 8,
                "status": "critical",
                "supplier_name": "电子科技集团",
                "expected_arrival_date": None
            },
            {
                "material_code": "MTL-PIP-003",
                "material_name": "高压管路",
                "required_quantity": 20,
                "available_quantity": 15,
                "shortage_quantity": 5,
                "status": "risk",
                "supplier_name": "标准件厂",
                "expected_arrival_date": "2026-04-10"
            }
        ],
        "bottleneck_materials": [
            {"material_code": "MTL-THR-001", "material_name": "推力器阀门", "bottleneck_score": 85},
            {"material_code": "MTL-SEN-004", "material_name": "压力传感器", "bottleneck_score": 75}
        ],
        "health_score": 45
    }


def create_mock_standardized_view():
    """创建Mock标准化数据视图"""
    return {
        "materials": [
            {"material_code": "MTL-THR-001", "material_name": "推力器阀门", "is_key_material": True},
            {"material_code": "MTL-SEN-004", "material_name": "压力传感器", "is_key_material": True},
            {"material_code": "MTL-PIP-003", "material_name": "高压管路", "is_key_material": False}
        ],
        "suppliers": [
            {
                "supplier_name": "航天阀门厂",
                "rating": "A",
                "on_time_delivery_rate": 0.95,
                "aerospace_qualified": True
            },
            {
                "supplier_name": "电子科技集团",
                "rating": "B",
                "on_time_delivery_rate": 0.80,
                "aerospace_qualified": True
            },
            {
                "supplier_name": "标准件厂",
                "rating": "D",
                "on_time_delivery_rate": 0.60,
                "aerospace_qualified": False
            }
        ],
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
        "schedule": {
            "work_orders": [
                {
                    "wo_id": "WO-PROP-001",
                    "planned_start": "2026-04-01",
                    "planned_end": "2026-06-01"
                }
            ]
        }
    }


def create_mock_no_risk_data():
    """创建无风险数据"""
    return {
        "kit_rate": 1.0,
        "total_materials": 5,
        "kitted_count": 5,
        "shortages": [],
        "bottleneck_materials": [],
        "health_score": 100
    }


# ==================== 测试函数 ====================

async def test_shortage_risk_assessment():
    """测试缺料风险评估"""
    print("\n" + "=" * 60)
    print("测试1: 缺料风险评估")
    print("=" * 60)

    agent = RiskAgent()
    analysis_result = create_mock_analysis_result()
    standardized_view = create_mock_standardized_view()

    shortages = analysis_result.get("shortages", [])

    shortage_risk, risk_events = await agent._assess_shortage_risk(
        shortages, standardized_view
    )

    print(f"\n缺料风险等级: {shortage_risk.value}")
    print(f"风险事件数: {len(risk_events)}")

    for event in risk_events:
        print(f"  - {event.event_type}: {event.level.value} - {event.description[:50]}...")

    assert shortage_risk in [RiskLevel.HIGH, RiskLevel.MEDIUM], "缺料风险等级错误"
    assert len(risk_events) > 0, "应该有风险事件"

    print("\n✅ 缺料风险评估测试通过")


async def test_supplier_risk_assessment():
    """测试供应商风险评估"""
    print("\n" + "=" * 60)
    print("测试2: 供应商风险评估")
    print("=" * 60)

    agent = RiskAgent()
    analysis_result = create_mock_analysis_result()
    standardized_view = create_mock_standardized_view()

    shortages = analysis_result.get("shortages", [])

    supplier_risk, risk_events = await agent._assess_supplier_risk(
        shortages, standardized_view
    )

    print(f"\n供应商风险评估结果:")
    for supplier, level in supplier_risk.items():
        print(f"  - {supplier}: {level}")

    print(f"\n风险事件数: {len(risk_events)}")

    # 标准件厂应该是高风险
    if "标准件厂" in supplier_risk:
        print(f"  标准件厂风险: {supplier_risk['标准件厂']}")

    assert len(supplier_risk) > 0, "应该有供应商风险"

    print("\n✅ 供应商风险评估测试通过")


async def test_schedule_risk_assessment():
    """测试进度风险评估"""
    print("\n" + "=" * 60)
    print("测试3: 进度风险评估")
    print("=" * 60)

    agent = RiskAgent()
    analysis_result = create_mock_analysis_result()
    standardized_view = create_mock_standardized_view()

    shortages = analysis_result.get("shortages", [])

    schedule_risk, risk_events = await agent._assess_schedule_risk(
        shortages, standardized_view
    )

    print(f"\n进度风险等级: {schedule_risk.value}")
    print(f"风险事件数: {len(risk_events)}")

    for event in risk_events:
        print(f"  - {event.description}")

    print("\n✅ 进度风险评估测试通过")


async def test_overall_risk_calculation():
    """测试综合风险计算"""
    print("\n" + "=" * 60)
    print("测试4: 综合风险计算")
    print("=" * 60)

    agent = RiskAgent()

    # 测试场景1：高风险
    overall = agent._calculate_overall_risk(
        RiskLevel.HIGH,
        {"supplier1": "high"},
        RiskLevel.HIGH
    )
    print(f"\n场景1（高+高+高）: {overall.value}")
    assert overall == RiskLevel.HIGH, "应为高风险"

    # 测试场景2：中风险
    overall = agent._calculate_overall_risk(
        RiskLevel.MEDIUM,
        {"supplier1": "low"},
        RiskLevel.LOW
    )
    print(f"场景2（中+低+低）: {overall.value}")
    assert overall == RiskLevel.MEDIUM, "应为中风险"

    # 测试场景3：无风险
    overall = agent._calculate_overall_risk(
        RiskLevel.NONE,
        {},
        RiskLevel.NONE
    )
    print(f"场景3（无风险）: {overall.value}")
    assert overall == RiskLevel.NONE, "应为无风险"

    print("\n✅ 综合风险计算测试通过")


async def test_alert_generation():
    """测试预警生成"""
    print("\n" + "=" * 60)
    print("测试5: 预警生成")
    print("=" * 60)

    agent = RiskAgent()
    standardized_view = create_mock_standardized_view()

    # 创建风险事件
    risk_events = [
        RiskEvent(
            event_type="shortage",
            level=RiskLevel.HIGH,
            description="推力器阀门严重缺货",
            affected_materials=["MTL-THR-001"],
            estimated_impact_days=5,
            suggestion="立即催货"
        ),
        RiskEvent(
            event_type="supplier",
            level=RiskLevel.MEDIUM,
            description="标准件厂交付率低",
            affected_materials=["MTL-PIP-003"],
            estimated_impact_days=0,
            suggestion="加强监控"
        )
    ]

    alerts = agent._generate_alerts(
        RiskLevel.HIGH,
        risk_events,
        standardized_view
    )

    print(f"\n生成预警数: {len(alerts)}")

    for i, alert in enumerate(alerts):
        print(f"\n预警 {i + 1}:")
        print(f"  等级: {alert.get('level')}")
        print(f"  标题: {alert.get('title')}")
        print(f"  接收人: {alert.get('recipients')}")

    assert len(alerts) > 0, "应生成预警"
    assert alerts[0].get("level") == "high", "首条预警应为高风险"

    print("\n✅ 预警生成测试通过")


async def test_full_execution():
    """测试完整执行"""
    print("\n" + "=" * 60)
    print("测试6: 完整执行")
    print("=" * 60)

    agent = RiskAgent()

    # 创建上下文
    context = AgentContext(
        session_id="test_session",
        question="评估当前供应链风险"
    )
    context.set_intent(IntentType.RISK, {"project_id": "PROJ-EAST4-001"})

    # 设置分析结果和数据上下文
    context.analysis_result = create_mock_analysis_result()
    context.data_context = {
        "standardized_view": create_mock_standardized_view()
    }

    result = await agent.execute(context)

    print(f"\n执行结果:")
    print(f"  综合风险等级: {result['overall_risk_level']}")
    print(f"  缺料风险: {result['shortage_risk']}")
    print(f"  进度风险: {result['schedule_risk']}")
    print(f"  供应商风险数: {len(result['supplier_risk'])}")
    print(f"  风险事件数: {len(result['risk_events'])}")
    print(f"  预警数: {len(result['alerts'])}")
    print(f"\n摘要:\n{result['summary']}")

    assert result['overall_risk_level'] != "none", "应有风险"
    assert len(result['alerts']) > 0, "应生成预警"

    print("\n✅ 完整执行测试通过")


async def test_no_risk_scenario():
    """测试无风险场景"""
    print("\n" + "=" * 60)
    print("测试7: 无风险场景")
    print("=" * 60)

    agent = RiskAgent()

    context = AgentContext(
        session_id="test_session",
        question="评估风险"
    )
    context.set_intent(IntentType.RISK, {})

    # 设置无风险的分析结果
    context.analysis_result = create_mock_no_risk_data()
    context.data_context = {
        "standardized_view": {
            "suppliers": [],
            "purchases": [],
            "schedule": None
        }
    }

    result = await agent.execute(context)

    print(f"\n执行结果:")
    print(f"  综合风险等级: {result['overall_risk_level']}")
    print(f"  预警数: {len(result['alerts'])}")

    assert result['overall_risk_level'] == "none", "无风险时应为none"
    assert len(result['alerts']) == 0, "无风险时应无预警"

    print("\n✅ 无风险场景测试通过")


async def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 60)
    print("测试8: 健康检查")
    print("=" * 60)

    agent = RiskAgent()
    health = await agent.health_check()

    print(f"\n健康状态:")
    print(f"  智能体: {health['agent']}")
    print(f"  健康: {health['healthy']}")
    print(f"  风险阈值: {list(health['risk_thresholds'].keys())}")
    print(f"  预警等级: {health['alert_levels']}")

    assert health['healthy'] is True

    print("\n✅ 健康检查测试通过")


async def main():
    print("=" * 60)
    print("风控智能体测试")
    print("=" * 60)

    await test_shortage_risk_assessment()
    await test_supplier_risk_assessment()
    await test_schedule_risk_assessment()
    await test_overall_risk_calculation()
    await test_alert_generation()
    await test_full_execution()
    await test_no_risk_scenario()
    await test_health_check()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())