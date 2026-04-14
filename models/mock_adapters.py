"""
Mock数据适配器 - 用于实验验证
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from platform_models import (
    PlatformType,
    BOMStructure, BOMItem,
    ProjectSchedule, WorkOrderSchedule,
    PurchaseOrder, PurchaseOrderItem,
    InventoryItem, SupplierInfo,
)


class MockBOMAdapter:
    """平台1 BOM系统 - Mock实现"""

    def __init__(self):
        self.platform_type = PlatformType.PLATFORM1_BOM
        self._mock_bom_data = self._init_mock_data()

    def _init_mock_data(self) -> Dict[str, BOMStructure]:
        """初始化Mock BOM数据"""

        # 卫星型号：东四平台
        bom_east4 = BOMStructure(
            project_id="PROJ-EAST4-001",
            project_name="东四平台卫星",
            module_id="MOD-PROP-001",
            module_name="推进舱",
            items=[
                BOMItem(
                    material_code="MTL-THR-001",
                    material_name="推力器阀门",
                    specification="DN50宇航级",
                    grade="aerospace",
                    quantity=4,
                    unit="件",
                    is_key_material=True,
                    lead_time=90
                ),
                BOMItem(
                    material_code="MTL-PRP-002",
                    material_name="推进剂储箱",
                    specification="200L钛合金",
                    grade="aerospace",
                    quantity=1,
                    unit="套",
                    is_key_material=True,
                    lead_time=180
                ),
                BOMItem(
                    material_code="MTL-PIP-003",
                    material_name="高压管路",
                    specification="DN20不锈钢",
                    grade="aerospace",
                    quantity=20,
                    unit="米",
                    is_key_material=False,
                    lead_time=60
                ),
                BOMItem(
                    material_code="MTL-SEN-004",
                    material_name="压力传感器",
                    specification="0-10MPa",
                    grade="aerospace",
                    quantity=8,
                    unit="件",
                    is_key_material=True,
                    lead_time=120
                ),
                BOMItem(
                    material_code="MTL-VAL-005",
                    material_name="安全阀",
                    specification="DN25",
                    grade="industrial",
                    quantity=4,
                    unit="件",
                    is_key_material=False,
                    lead_time=45
                ),
            ]
        )

        # 载荷舱BOM
        bom_east4_payload = BOMStructure(
            project_id="PROJ-EAST4-001",
            project_name="东四平台卫星",
            module_id="MOD-PAY-001",
            module_name="载荷舱",
            items=[
                BOMItem(
                    material_code="MTL-ANT-006",
                    material_name="天线单元",
                    specification="Ka波段",
                    grade="aerospace",
                    quantity=1,
                    unit="套",
                    is_key_material=True,
                    lead_time=150
                ),
                BOMItem(
                    material_code="MTL-TRA-007",
                    material_name="转发器",
                    specification="Ku波段",
                    grade="aerospace",
                    quantity=2,
                    unit="台",
                    is_key_material=True,
                    lead_time=200
                ),
                BOMItem(
                    material_code="MTL-CAB-008",
                    material_name="射频电缆",
                    specification="SMA接口",
                    grade="aerospace",
                    quantity=30,
                    unit="根",
                    is_key_material=False,
                    lead_time=30
                ),
            ]
        )

        # 另一型号：载人飞船
        bom_spaceship = BOMStructure(
            project_id="PROJ-SHIP-002",
            project_name="载人飞船",
            module_id="MOD-RET-001",
            module_name="返回舱",
            items=[
                BOMItem(
                    material_code="MTL-HS-009",
                    material_name="防热大底",
                    specification="碳复合材料",
                    grade="aerospace",
                    quantity=1,
                    unit="套",
                    is_key_material=True,
                    lead_time=300
                ),
                BOMItem(
                    material_code="MTL-PAR-010",
                    material_name="降落伞",
                    specification="主伞+备伞",
                    grade="aerospace",
                    quantity=1,
                    unit="套",
                    is_key_material=True,
                    lead_time=240
                ),
            ]
        )

        return {
            "PROJ-EAST4-001_MOD-PROP-001": bom_east4,
            "PROJ-EAST4-001_MOD-PAY-001": bom_east4_payload,
            "PROJ-SHIP-002_MOD-RET-001": bom_spaceship,
        }

    async def fetch_bom(self, query: Dict) -> Optional[BOMStructure]:
        """获取BOM数据"""
        project_id = query.get("project_id")
        module_id = query.get("module_id")

        if project_id and module_id:
            key = f"{project_id}_{module_id}"
            return self._mock_bom_data.get(key)
        elif project_id:
            for key, bom in self._mock_bom_data.items():
                if key.startswith(project_id):
                    return bom
        return None

    async def fetch_schedule(self, query: Dict) -> Optional[ProjectSchedule]:
        """BOM适配器不支持排程查询"""
        return None

    async def fetch_purchase_orders(self, query: Dict) -> List[PurchaseOrder]:
        """BOM适配器不支持采购订单查询"""
        return []

    async def fetch_inventory(self, query: Dict) -> List[InventoryItem]:
        """BOM适配器不支持库存查询"""
        return []

    async def fetch_suppliers(self, query: Dict) -> List[SupplierInfo]:
        """BOM适配器不支持供应商查询"""
        return []

    async def fetch_all_boms(self, project_id: str) -> List[BOMStructure]:
        """获取项目的所有BOM"""
        result = []
        for key, bom in self._mock_bom_data.items():
            if key.startswith(project_id):
                result.append(bom)
        return result


class MockScheduleAdapter:
    """平台2 排程系统 - Mock实现"""

    def __init__(self):
        self.platform_type = PlatformType.PLATFORM2_SCHEDULE
        self._mock_schedules = self._init_mock_data()

    def _init_mock_data(self) -> Dict[str, ProjectSchedule]:
        """初始化Mock排程数据"""
        now = datetime.now()

        schedule_east4 = ProjectSchedule(
            project_id="PROJ-EAST4-001",
            project_name="东四平台卫星",
            work_orders=[
                WorkOrderSchedule(
                    wo_id="WO-PROP-001",
                    project_id="PROJ-EAST4-001",
                    module_id="MOD-PROP-001",
                    planned_start=now + timedelta(days=30),
                    planned_end=now + timedelta(days=90),
                    status="pending",
                    priority="high"
                ),
                WorkOrderSchedule(
                    wo_id="WO-PAY-001",
                    project_id="PROJ-EAST4-001",
                    module_id="MOD-PAY-001",
                    planned_start=now + timedelta(days=60),
                    planned_end=now + timedelta(days=120),
                    status="pending",
                    priority="medium"
                ),
            ],
            overall_start=now + timedelta(days=30),
            overall_end=now + timedelta(days=120)
        )

        schedule_ship = ProjectSchedule(
            project_id="PROJ-SHIP-002",
            project_name="载人飞船",
            work_orders=[
                WorkOrderSchedule(
                    wo_id="WO-RET-001",
                    project_id="PROJ-SHIP-002",
                    module_id="MOD-RET-001",
                    planned_start=now + timedelta(days=60),
                    planned_end=now + timedelta(days=180),
                    status="pending",
                    priority="high"
                ),
            ],
            overall_start=now + timedelta(days=60),
            overall_end=now + timedelta(days=180)
        )

        return {
            "PROJ-EAST4-001": schedule_east4,
            "PROJ-SHIP-002": schedule_ship,
        }

    async def fetch_schedule(self, query: Dict) -> Optional[ProjectSchedule]:
        """获取排程数据"""
        project_id = query.get("project_id")
        if project_id:
            return self._mock_schedules.get(project_id)
        return None

    async def fetch_bom(self, query: Dict) -> Optional[BOMStructure]:
        """排程适配器不支持BOM查询"""
        return None

    async def fetch_purchase_orders(self, query: Dict) -> List[PurchaseOrder]:
        """排程适配器不支持采购订单查询"""
        return []

    async def fetch_inventory(self, query: Dict) -> List[InventoryItem]:
        """排程适配器不支持库存查询"""
        return []

    async def fetch_suppliers(self, query: Dict) -> List[SupplierInfo]:
        """排程适配器不支持供应商查询"""
        return []


class MockSRMAdapter:
    """SRM采购系统 - Mock实现"""

    def __init__(self):
        self.platform_type = PlatformType.SRM
        self._mock_orders = self._init_mock_orders()
        self._mock_suppliers = self._init_mock_suppliers()

    def _init_mock_suppliers(self) -> Dict[str, SupplierInfo]:
        """初始化供应商数据"""
        return {
            "SUP-001": SupplierInfo(
                supplier_id="SUP-001",
                supplier_name="航天阀门厂",
                rating="A",
                aerospace_qualified=True,
                on_time_delivery_rate=0.95,
                risk_level="low"
            ),
            "SUP-002": SupplierInfo(
                supplier_id="SUP-002",
                supplier_name="精密机械公司",
                rating="B",
                aerospace_qualified=True,
                on_time_delivery_rate=0.85,
                risk_level="medium"
            ),
            "SUP-003": SupplierInfo(
                supplier_id="SUP-003",
                supplier_name="电子科技集团",
                rating="A",
                aerospace_qualified=True,
                on_time_delivery_rate=0.92,
                risk_level="low"
            ),
            "SUP-004": SupplierInfo(
                supplier_id="SUP-004",
                supplier_name="标准件厂",
                rating="C",
                aerospace_qualified=False,
                on_time_delivery_rate=0.70,
                risk_level="high"
            ),
        }

    def _init_mock_orders(self) -> List[PurchaseOrder]:
        """初始化采购订单"""
        now = datetime.now()

        return [
            PurchaseOrder(
                po_id="PO-2024-001",
                supplier_id="SUP-001",
                supplier_name="航天阀门厂",
                order_date=now - timedelta(days=30),
                items=[
                    PurchaseOrderItem(
                        po_id="PO-2024-001",
                        material_code="MTL-THR-001",
                        material_name="推力器阀门",
                        quantity=4,
                        unit_price=50000,
                        order_date=now - timedelta(days=30),
                        promised_date=now + timedelta(days=10),
                        actual_arrival_date=None,
                        status="shipped",
                        supplier_id="SUP-001",
                        supplier_name="航天阀门厂",
                        tracking_no="SF-123456"
                    )
                ],
                total_amount=200000,
                status="shipped"
            ),
            PurchaseOrder(
                po_id="PO-2024-002",
                supplier_id="SUP-002",
                supplier_name="精密机械公司",
                order_date=now - timedelta(days=60),
                items=[
                    PurchaseOrderItem(
                        po_id="PO-2024-002",
                        material_code="MTL-PRP-002",
                        material_name="推进剂储箱",
                        quantity=1,
                        unit_price=300000,
                        order_date=now - timedelta(days=60),
                        promised_date=now + timedelta(days=20),
                        actual_arrival_date=None,
                        status="ordered",
                        supplier_id="SUP-002",
                        supplier_name="精密机械公司"
                    )
                ],
                total_amount=300000,
                status="ordered"
            ),
            PurchaseOrder(
                po_id="PO-2024-003",
                supplier_id="SUP-003",
                supplier_name="电子科技集团",
                order_date=now - timedelta(days=45),
                items=[
                    PurchaseOrderItem(
                        po_id="PO-2024-003",
                        material_code="MTL-SEN-004",
                        material_name="压力传感器",
                        quantity=8,
                        unit_price=8000,
                        order_date=now - timedelta(days=45),
                        promised_date=now - timedelta(days=5),  # 已延期
                        actual_arrival_date=None,
                        status="ordered",
                        supplier_id="SUP-003",
                        supplier_name="电子科技集团"
                    )
                ],
                total_amount=64000,
                status="ordered"
            ),
        ]

    async def fetch_purchase_orders(self, query: Dict) -> List[PurchaseOrder]:
        """获取采购订单"""
        material_code = query.get("material_code")
        if material_code:
            result = []
            for po in self._mock_orders:
                for item in po.items:
                    if item.material_code == material_code:
                        result.append(po)
                        break
            return result
        return self._mock_orders

    async def fetch_suppliers(self, query: Dict) -> List[SupplierInfo]:
        """获取供应商信息"""
        supplier_id = query.get("supplier_id")
        if supplier_id:
            supplier = self._mock_suppliers.get(supplier_id)
            return [supplier] if supplier else []
        return list(self._mock_suppliers.values())

    async def fetch_bom(self, query: Dict) -> Optional[BOMStructure]:
        """SRM适配器不支持BOM查询"""
        return None

    async def fetch_schedule(self, query: Dict) -> Optional[ProjectSchedule]:
        """SRM适配器不支持排程查询"""
        return None

    async def fetch_inventory(self, query: Dict) -> List[InventoryItem]:
        """SRM适配器不支持库存查询"""
        return []


class MockWMSAdapter:
    """WMS智能仓储系统 - Mock实现"""

    def __init__(self):
        self.platform_type = PlatformType.WMS
        self._mock_inventory = self._init_mock_inventory()

    def _init_mock_inventory(self) -> List[InventoryItem]:
        """初始化库存数据"""
        now = datetime.now()

        return [
            InventoryItem(
                inventory_id="INV-001",
                material_code="MTL-THR-001",
                material_name="推力器阀门",
                available_quantity=0,
                reserved_quantity=0,
                batch_no="BATCH-001",
                warehouse_location="A-01-01",
                last_updated=now
            ),
            InventoryItem(
                inventory_id="INV-002",
                material_code="MTL-PIP-003",
                material_name="高压管路",
                available_quantity=50,
                reserved_quantity=20,
                batch_no="BATCH-002",
                warehouse_location="B-02-03",
                last_updated=now
            ),
            InventoryItem(
                inventory_id="INV-003",
                material_code="MTL-VAL-005",
                material_name="安全阀",
                available_quantity=10,
                reserved_quantity=0,
                batch_no="BATCH-003",
                warehouse_location="C-01-02",
                last_updated=now
            ),
            InventoryItem(
                inventory_id="INV-004",
                material_code="MTL-ANT-006",
                material_name="天线单元",
                available_quantity=0,
                reserved_quantity=0,
                batch_no=None,
                warehouse_location="A-03-01",
                last_updated=now
            ),
            InventoryItem(
                inventory_id="INV-005",
                material_code="MTL-TRA-007",
                material_name="转发器",
                available_quantity=1,
                reserved_quantity=0,
                batch_no="BATCH-004",
                warehouse_location="A-02-01",
                last_updated=now
            ),
        ]

    async def fetch_inventory(self, query: Dict) -> List[InventoryItem]:
        """获取库存数据"""
        material_code = query.get("material_code")
        if material_code:
            return [item for item in self._mock_inventory if item.material_code == material_code]
        return self._mock_inventory

    async def fetch_bom(self, query: Dict) -> Optional[BOMStructure]:
        """WMS适配器不支持BOM查询"""
        return None

    async def fetch_schedule(self, query: Dict) -> Optional[ProjectSchedule]:
        """WMS适配器不支持排程查询"""
        return None

    async def fetch_purchase_orders(self, query: Dict) -> List[PurchaseOrder]:
        """WMS适配器不支持采购订单查询"""
        return []

    async def fetch_suppliers(self, query: Dict) -> List[SupplierInfo]:
        """WMS适配器不支持供应商查询"""
        return []


# ==================== 工厂类 ====================

class MockAdapterFactory:
    """Mock适配器工厂"""

    _adapters = {}

    @classmethod
    def get_adapter(cls, platform_type: PlatformType):
        """获取适配器实例"""
        if platform_type not in cls._adapters:
            if platform_type == PlatformType.PLATFORM1_BOM:
                cls._adapters[platform_type] = MockBOMAdapter()
            elif platform_type == PlatformType.PLATFORM2_SCHEDULE:
                cls._adapters[platform_type] = MockScheduleAdapter()
            elif platform_type == PlatformType.SRM:
                cls._adapters[platform_type] = MockSRMAdapter()
            elif platform_type == PlatformType.WMS:
                cls._adapters[platform_type] = MockWMSAdapter()
        return cls._adapters[platform_type]

    @classmethod
    def get_all_adapters(cls):
        """获取所有适配器"""
        return {
            PlatformType.PLATFORM1_BOM: cls.get_adapter(PlatformType.PLATFORM1_BOM),
            PlatformType.PLATFORM2_SCHEDULE: cls.get_adapter(PlatformType.PLATFORM2_SCHEDULE),
            PlatformType.SRM: cls.get_adapter(PlatformType.SRM),
            PlatformType.WMS: cls.get_adapter(PlatformType.WMS),
        }