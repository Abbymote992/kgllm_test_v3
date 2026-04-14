"""
测试分析智能体
"""

import asyncio
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.analysis_agent import AnalysisAgent
from agents.context import AgentContext
from models.agent_models import IntentType


# ==================== Mock数据 ====================

def create_mock_standardized_view():
    """创建Mock标准化数据视图"""
    return {
        "materials": [
            {
                "material_code": "MTL-THR-001",
                "material_name": "推力器阀门",
                "required_quantity": 4,
                "unit": "件",
                "grade": "aerospace",
                "is_key_material": True,
                "lead_time": 90
            },
            {
                "material_code": "MTL-PRP-002",
                "material_name": "推进剂储箱",
                "required_quantity": 1,
                "unit": "套",
                "grade": "aerospace",
                "is_key_material": True,
                "lead_time": 180
            },
            {
                "material_code": "MTL-PIP-003",
                "material_name": "高压管路",
                "required_quantity": 20,
                "unit": "米",
                "grade": "aerospace",
                "is_key_material": False,
                "lead_time": 60
            },
            {
                "material_code": "MTL-SEN-004",
                "material_name": "压力传感器",
                "required_quantity": 8,
                "unit": "件",
                "grade": "aerospace",
                "is_key_material": True,
                "lead_time": 120
            },
            {
                "material_code": "MTL-VAL-005",
                "material_name": "安全阀",
                "required_quantity": 4,
                "unit": "件",
                "grade": "industrial",
                "is_key_material": False,
                "lead_time": 45
            }
        ],
        "inventory": [
            {
                "material_code": "MTL-PIP-003",
                "material_name": "高压管路",
                "available_quantity": 50,
                "reserved_quantity": 20,
                "warehouse_location": "B-02-03"
            },
            {
                "material_code": "MTL-VAL-005",
                "material_name": "安全阀",
                "available_quantity": 10,
                "reserved_quantity": 0,
                "warehouse_location": "C-01-02"
            },
            {
                "material_code": "MTL-TRA-007",
                "material_name": "转发器",
                "available_quantity": 1,
                "reserved_quantity": 0,
                "warehouse_location": "A-02-01"
            }
        ],
        "purchases": [
            {
                "po_id": "PO-2024-001",
                "material_code": "MTL-THR-001",
                "material_name": "推力器阀门",
                "quantity": 4,
                "promised_date": "2026-04-20",
                "status": "shipped",
                "supplier_name": "航天阀门厂"
            },
            {
                "po_id": "PO-2024-002",
                "material_code": "MTL-PRP-002",
                "material_name": "推进剂储箱",
                "quantity": 1,
                "promised_date": "2026-05-01",
                "status": "ordered",
                "supplier_name": "精密机械公司"
            }
        ],
        "suppliers": [
            {
                "supplier_id": "SUP-001",
                "supplier_name": "航天阀门厂",
                "rating": "A",
                "aerospace_qualified": True,
                "on_time_delivery_rate": 0.95
            },
            {
                "supplier_id": "SUP-002",
                "supplier_name": "精密机械公司",
                "rating": "B",
                "aerospace_qualified": True,
                "on_time_delivery_rate": 0.85
            }
        ],
        "schedule": {
            "project_id": "PROJ-EAST4-001",
            "project_name": "东四平台卫星",
            "work_orders": [
                {
                    "wo_id": "WO-PROP-001",
                    "planned_start": "2026-05-07",
                    "planned_end": "2026-07-06",
                    "priority": "high"
                }
            ]
        }
    }


def create_mock_standardized_view_all_kitted():
    """创建全部齐套的Mock数据"""
    return {
        "materials": [
            {
                "material_code": "MTL-THR-001",
                "material_name": "推力器阀门",
                "required_quantity": 4,
                "is_key_material": True
            }
        ],
        "inventory": [
            {
                "material_code": "MTL-THR-001",
                "available_quantity": 5
            }
        ],
        "purchases": [],
        "suppliers": [],
        "schedule": None
    }


def create_mock_standardized_view_empty():
    """创建空数据的Mock"""
    return {
        "materials": [],
        "inventory": [],
        "purchases": [],
        "suppliers": [],
        "schedule": None
    }


# ==================== 测试函数 ====================

async def test_kit_rate_calculation():
    """测试齐套率计算"""
    print("\n" + "=" * 60)
    print("测试1: 齐套率计算")
    print("=" * 60)

    agent = AnalysisAgent()
    standardized_view = create_mock_standardized_view()

    result = await agent._calculate_kit_rate(standardized_view)

    print(f"\n计算结果:")
    print(f"  齐套率: {result['kit_rate']:.1%}")
    print(f"  总物料数: {result['total_materials']}")
    print(f"  已齐套数: {result['kitted_count']}")

    # 验证：推力器阀门有采购在途，算作已齐套
    # 推进剂储箱有采购在途，算作已齐套
    # 高压管路有库存，算作已齐套
    # 压力传感器无库存无采购，未齐套
    # 安全阀有库存，算作已齐套
    # 预期齐套率 = 4/5 = 80%

    expected_rate = 0.8
    assert abs(result['kit_rate'] - expected_rate) < 0.01, f"齐套率计算错误: {result['kit_rate']}"

    print(f"\n✅ 齐套率计算测试通过 (预期 {expected_rate:.0%})")


async def test_shortage_identification():
    """测试缺料识别"""
    print("\n" + "=" * 60)
    print("测试2: 缺料识别")
    print("=" * 60)

    agent = AnalysisAgent()
    standardized_view = create_mock_standardized_view()

    shortages = await agent._identify_shortages(standardized_view)

    print(f"\n识别到 {len(shortages)} 种缺货物料:")
    for s in shortages:
        print(f"  - {s.material_name}: 缺 {s.shortage_quantity}/{s.required_quantity} ({s.status.value})")
        print(f"    原因: {s.reason}")

    # 预期：压力传感器缺货
    assert len(shortages) > 0, "未识别到缺料"

    pressure_sensor = next(
        (s for s in shortages if s.material_code == "MTL-SEN-004"),
        None
    )
    assert pressure_sensor is not None, "未识别到压力传感器缺料"
    assert pressure_sensor.shortage_quantity == 8, f"缺货数量错误: {pressure_sensor.shortage_quantity}"

    print("\n✅ 缺料识别测试通过")


async def test_bottleneck_analysis():
    """测试瓶颈分析"""
    print("\n" + "=" * 60)
    print("测试3: 瓶颈分析")
    print("=" * 60)

    agent = AnalysisAgent()
    standardized_view = create_mock_standardized_view()

    # 先识别缺料
    shortages = await agent._identify_shortages(standardized_view)

    # 分析瓶颈
    bottlenecks = await agent._analyze_bottlenecks(shortages, standardized_view)

    print(f"\n瓶颈物料 TOP {len(bottlenecks)}:")
    for i, b in enumerate(bottlenecks[:3]):
        print(f"  {i + 1}. {b['material_name']} (分数: {b['bottleneck_score']})")
        print(f"     关键物料: {b['is_key_material']}, 等级: {b['grade']}")

    assert len(bottlenecks) > 0, "未识别到瓶颈物料"

    # 压力传感器应该是最高分
    top_bottleneck = bottlenecks[0]
    assert top_bottleneck['material_code'] == "MTL-SEN-004", "瓶颈物料识别错误"

    print("\n✅ 瓶颈分析测试通过")


async def test_health_score():
    """测试健康度评分"""
    print("\n" + "=" * 60)
    print("测试4: 健康度评分")
    print("=" * 60)

    agent = AnalysisAgent()

    # 测试场景1：部分缺料
    standardized_view1 = create_mock_standardized_view()
    shortages1 = await agent._identify_shortages(standardized_view1)
    kit_result1 = await agent._calculate_kit_rate(standardized_view1)

    health1 = agent._calculate_health_score(
        kit_result1["kit_rate"],
        shortages1,
        standardized_view1
    )

    print(f"\n场景1（部分缺料）: 健康度 = {health1}")

    # 测试场景2：全部齐套
    standardized_view2 = create_mock_standardized_view_all_kitted()
    shortages2 = await agent._identify_shortages(standardized_view2)
    kit_result2 = await agent._calculate_kit_rate(standardized_view2)

    health2 = agent._calculate_health_score(
        kit_result2["kit_rate"],
        shortages2,
        standardized_view2
    )

    print(f"场景2（全部齐套）: 健康度 = {health2}")

    # 测试场景3：空数据
    standardized_view3 = create_mock_standardized_view_empty()
    shortages3 = await agent._identify_shortages(standardized_view3)
    kit_result3 = await agent._calculate_kit_rate(standardized_view3)

    health3 = agent._calculate_health_score(
        kit_result3["kit_rate"],
        shortages3,
        standardized_view3
    )

    print(f"场景3（空数据）: 健康度 = {health3}")

    # 验证：全部齐套时健康度应该较高
    assert health2 > health1, "全部齐套时健康度应该更高"

    print("\n✅ 健康度评分测试通过")


async def test_summary_generation():
    """测试摘要生成"""
    print("\n" + "=" * 60)
    print("测试5: 摘要生成")
    print("=" * 60)

    agent = AnalysisAgent()
    standardized_view = create_mock_standardized_view()

    kit_result = await agent._calculate_kit_rate(standardized_view)
    shortages = await agent._identify_shortages(standardized_view)
    bottlenecks = await agent._analyze_bottlenecks(shortages, standardized_view)
    health_score = agent._calculate_health_score(
        kit_result["kit_rate"],
        shortages,
        standardized_view
    )

    summary = await agent._generate_summary(
        kit_result,
        shortages,
        bottlenecks,
        health_score
    )

    print(f"\n生成的摘要:\n")
    print(summary)

    # 验证摘要包含关键信息
    assert "齐套率" in summary, "摘要缺少齐套率"
    assert "健康度" in summary, "摘要缺少健康度"
    assert "缺料" in summary or "瓶颈" in summary, "摘要缺少缺料信息"

    print("\n✅ 摘要生成测试通过")


async def test_full_execution():
    """测试完整执行"""
    print("\n" + "=" * 60)
    print("测试6: 完整执行")
    print("=" * 60)

    agent = AnalysisAgent()

    # 创建上下文，包含数据上下文
    context = AgentContext(
        session_id="test_session",
        question="分析推进舱物料齐套情况"
    )
    context.set_intent(IntentType.ANALYSIS, {"project_id": "PROJ-EAST4-001"})

    # 设置数据上下文
    context.data_context = {
        "standardized_view": create_mock_standardized_view()
    }

    result = await agent.execute(context)

    print(f"\n执行结果:")
    print(f"  齐套率: {result['kit_rate']:.1%}")
    print(f"  健康度: {result['health_score']}")
    print(f"  缺料数: {len(result['shortages'])}")
    print(f"  瓶颈数: {len(result['bottleneck_materials'])}")
    print(f"\n摘要:\n{result['summary']}")

    assert result['kit_rate'] > 0, "齐套率计算错误"
    assert result['health_score'] >= 0, "健康度评分错误"

    print("\n✅ 完整执行测试通过")


async def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("测试7: 边界情况")
    print("=" * 60)

    agent = AnalysisAgent()

    # 测试空数据上下文
    context = AgentContext("test_session", "测试")
    context.data_context = None

    result = await agent.execute(context)

    print(f"\n空数据上下文结果:")
    print(f"  齐套率: {result['kit_rate']:.0%}")
    print(f"  错误信息: {result.get('error', '无')}")

    # 应该返回默认值而不是崩溃
    assert result['kit_rate'] == 0, "空数据时应返回0"

    print("\n✅ 边界情况测试通过")


async def main():
    print("=" * 60)
    print("分析智能体测试")
    print("=" * 60)

    await test_kit_rate_calculation()
    await test_shortage_identification()
    await test_bottleneck_analysis()
    await test_health_score()
    await test_summary_generation()
    await test_full_execution()
    await test_edge_cases()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())