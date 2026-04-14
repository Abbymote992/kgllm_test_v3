"""
测试Mock适配器
"""

import asyncio
from mock_adapters import MockAdapterFactory
from platform_models import PlatformType


async def test_bom_adapter():
    """测试BOM适配器"""
    print("=" * 50)
    print("测试BOM适配器")
    print("=" * 50)

    adapter = MockAdapterFactory.get_adapter(PlatformType.PLATFORM1_BOM)

    # 查询推进舱BOM
    bom = await adapter.fetch_bom({
        "project_id": "PROJ-EAST4-001",
        "module_id": "MOD-PROP-001"
    })

    if bom:
        print(f"项目: {bom.project_name}")
        print(f"舱段: {bom.module_name}")
        print("物料清单:")
        for item in bom.items:
            print(
                f"  - {item.material_name}({item.material_code}): {item.quantity}{item.unit}, 宇航级: {item.grade == 'aerospace'}")
    print()


async def test_schedule_adapter():
    """测试排程适配器"""
    print("=" * 50)
    print("测试排程适配器")
    print("=" * 50)

    adapter = MockAdapterFactory.get_adapter(PlatformType.PLATFORM2_SCHEDULE)

    schedule = await adapter.fetch_schedule({"project_id": "PROJ-EAST4-001"})

    if schedule:
        print(f"项目: {schedule.project_name}")
        print("工单列表:")
        for wo in schedule.work_orders:
            print(f"  - {wo.wo_id}: {wo.planned_start.date()} -> {wo.planned_end.date()}, 优先级: {wo.priority}")
    print()


async def test_srm_adapter():
    """测试SRM适配器"""
    print("=" * 50)
    print("测试SRM适配器")
    print("=" * 50)

    adapter = MockAdapterFactory.get_adapter(PlatformType.SRM)

    # 获取所有采购订单
    orders = await adapter.fetch_purchase_orders({})
    print(f"采购订单数量: {len(orders)}")
    for po in orders:
        print(f"  PO: {po.po_id}, 供应商: {po.supplier_name}, 状态: {po.status}")
        for item in po.items:
            print(f"    - {item.material_name}: {item.quantity}件, 承诺交期: {item.promised_date.date()}")

    # 获取供应商
    suppliers = await adapter.fetch_suppliers({})
    print(f"\n供应商数量: {len(suppliers)}")
    for sup in suppliers:
        print(f"  {sup.supplier_name}: 评级{sup.rating}, 宇航级资质: {sup.aerospace_qualified}")
    print()


async def test_wms_adapter():
    """测试WMS适配器"""
    print("=" * 50)
    print("测试WMS适配器")
    print("=" * 50)

    adapter = MockAdapterFactory.get_adapter(PlatformType.WMS)

    inventory = await adapter.fetch_inventory({})
    print("库存清单:")
    for item in inventory:
        print(f"  {item.material_name}: 可用{item.available_quantity}件, 库位: {item.warehouse_location}")
    print()


async def main():
    """运行所有测试"""
    await test_bom_adapter()
    await test_schedule_adapter()
    await test_srm_adapter()
    await test_wms_adapter()

    print("=" * 50)
    print("所有测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())