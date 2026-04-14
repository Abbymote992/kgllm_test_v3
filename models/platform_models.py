"""
4平台数据模型

定义从不同平台获取数据的标准化结构
每个平台的适配器都会将原始数据转换为这些标准模型
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


# ==================== 平台类型 ====================

class PlatformType(str, Enum):
    """数据平台类型"""
    PLATFORM1_BOM = "platform1_bom"
    PLATFORM2_SCHEDULE = "platform2_schedule"
    SRM = "srm"
    WMS = "wms"


# ==================== 平台1：BOM系统模型 ====================

class BOMItem(BaseModel):
    """BOM物料项"""
    material_code: str
    material_name: str
    specification: Optional[str] = None
    grade: str = "industrial"
    quantity: float = 1.0
    unit: str = "件"
    parent_material_code: Optional[str] = None  # 上层物料，用于树形结构
    level: int = 0  # BOM层级
    is_key_material: bool = False
    lead_time: int = 0
    source_platform: str = "platform1_bom"


class BOMStructure(BaseModel):
    """BOM结构"""
    project_id: str
    project_name: str
    module_id: str
    module_name: str
    items: List[BOMItem] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ==================== 平台2：排程系统模型 ====================

class WorkOrderSchedule(BaseModel):
    """工单排程"""
    wo_id: str
    project_id: str
    module_id: str
    planned_start: datetime
    planned_end: datetime
    status: str = "pending"  # pending/running/completed
    priority: str = "medium"  # high/medium/low
    source_platform: str = "platform2_schedule"


class ProjectSchedule(BaseModel):
    """项目排程"""
    project_id: str
    project_name: str
    work_orders: List[WorkOrderSchedule] = Field(default_factory=list)
    overall_start: Optional[datetime] = None
    overall_end: Optional[datetime] = None


# ==================== SRM模型 ====================

class SupplierInfo(BaseModel):
    """供应商信息"""
    supplier_id: str
    supplier_name: str
    rating: str = "C"  # A/B/C/D
    aerospace_qualified: bool = False
    on_time_delivery_rate: float = 0.0
    risk_level: str = "low"
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    source_platform: str = "srm"


class PurchaseOrderItem(BaseModel):
    """采购订单明细"""
    po_id: str
    material_code: str
    material_name: str
    quantity: float
    unit_price: float
    order_date: datetime
    promised_date: datetime
    actual_arrival_date: Optional[datetime] = None
    status: str = "ordered"  # ordered/shipped/received/closed
    supplier_id: str
    supplier_name: str
    tracking_no: Optional[str] = None
    source_platform: str = "srm"


class PurchaseOrder(BaseModel):
    """采购订单（聚合）"""
    po_id: str
    supplier_id: str
    supplier_name: str
    order_date: datetime
    items: List[PurchaseOrderItem] = Field(default_factory=list)
    total_amount: float = 0.0
    status: str = "ordered"


# ==================== WMS模型 ====================

class InventoryItem(BaseModel):
    """库存项"""
    inventory_id: str
    material_code: str
    material_name: str
    available_quantity: float
    reserved_quantity: float = 0.0
    batch_no: Optional[str] = None
    warehouse_location: str
    last_updated: datetime
    source_platform: str = "wms"


class InboundRecord(BaseModel):
    """入库记录"""
    record_id: str
    po_id: str
    material_code: str
    quantity: float
    arrival_date: datetime
    batch_no: Optional[str] = None
    quality_status: str = "passed"  # passed/failed/pending
    source_platform: str = "wms"


class OutboundRecord(BaseModel):
    """出库记录"""
    record_id: str
    wo_id: str
    material_code: str
    quantity: float
    issue_date: datetime
    batch_no: Optional[str] = None
    destination: Optional[str] = None
    source_platform: str = "wms"


# ==================== 统一视图模型 ====================

class MaterialDemandView(BaseModel):
    """物料需求视图 - 对齐套分析使用"""
    project_id: str
    project_name: str
    work_order_id: str
    material_code: str
    material_name: str
    required_quantity: float
    required_date: datetime  # 需求日期（投产时间）
    priority: str = "medium"
    source: str = "bom"  # 数据来源


class MaterialSupplyView(BaseModel):
    """物料供应视图 - 对齐套分析使用"""
    material_code: str
    material_name: str
    supply_quantity: float
    supply_type: str  # inventory / purchase_order / in_transit
    available_date: datetime  # 可供使用日期
    source_id: str  # 库存ID或PO号
    supplier_name: Optional[str] = None
    source_platform: str


class UnifiedMaterialView(BaseModel):
    """统一物料视图 - 汇聚需求和供应"""
    project_id: str
    work_order_id: str
    material_code: str
    material_name: str
    required_quantity: float
    required_date: datetime
    supplied_quantity: float = 0.0
    shortage_quantity: float = 0.0
    kit_status: str = "pending"  # kitted / partial / missing
    supply_sources: List[MaterialSupplyView] = Field(default_factory=list)
    data_quality_flags: List[str] = Field(default_factory=list)  # 数据质量问题标记


# 修改后
from abc import ABC, abstractmethod


class IPlatformAdapter(ABC):
    """平台适配器接口（抽象定义，实际实现在services中）"""

    def __init__(self):
        self.platform_type = None

    @abstractmethod
    async def fetch_bom(self, query: Dict) -> Optional[BOMStructure]:
        """获取BOM数据（平台1）"""
        pass

    @abstractmethod
    async def fetch_schedule(self, query: Dict) -> Optional[ProjectSchedule]:
        """获取排程数据（平台2）"""
        pass

    @abstractmethod
    async def fetch_purchase_orders(self, query: Dict) -> List[PurchaseOrder]:
        """获取采购订单（SRM）"""
        pass

    @abstractmethod
    async def fetch_inventory(self, query: Dict) -> List[InventoryItem]:
        """获取库存数据（WMS）"""
        pass

    @abstractmethod
    async def fetch_suppliers(self, query: Dict) -> List[SupplierInfo]:
        """获取供应商信息（SRM）"""
        pass