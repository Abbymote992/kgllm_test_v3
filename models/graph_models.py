"""
知识图谱数据模型

定义Neo4j中存储的节点和关系结构
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


# ==================== 节点类型枚举 ====================

class NodeLabel(str, Enum):
    """节点标签"""
    PROJECT = "Project"
    MODULE = "Module"
    WORK_ORDER = "WorkOrder"
    MATERIAL = "Material"
    SUPPLIER = "Supplier"
    PURCHASE_ORDER = "PurchaseOrder"
    INVENTORY = "Inventory"
    RISK_EVENT = "RiskEvent"


class RelationshipType(str, Enum):
    """关系类型"""
    BELONGS_TO = "BELONGS_TO"      # Module -> Project
    HAS_WO = "HAS_WO"              # Project -> WorkOrder
    REQUIRES = "REQUIRES"          # WorkOrder -> Material
    SUPPLIES = "SUPPLIES"          # Supplier -> Material
    HAS_PO = "HAS_PO"              # PurchaseOrder -> Material
    RECORDS = "RECORDS"            # Inventory -> Material
    FULFILLS = "FULFILLS"          # PurchaseOrder -> WorkOrder
    AFFECTS = "AFFECTS"            # RiskEvent -> WorkOrder


# ==================== 节点模型 ====================

class ProjectNode(BaseModel):
    """项目/型号节点"""
    project_id: str
    name: str
    series: Optional[str] = None
    status: str = "active"          # active/completed/cancelled
    source_platform: str = "platform2"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ModuleNode(BaseModel):
    """舱段/模块节点"""
    module_id: str
    name: str
    position: Optional[str] = None
    importance: str = "P2"          # P1(核心)/P2(重要)/P3(一般)
    source_platform: str = "platform1"
    created_at: Optional[datetime] = None


class WorkOrderNode(BaseModel):
    """工单节点"""
    wo_id: str
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    status: str = "pending"         # pending/running/completed
    priority: str = "medium"        # high/medium/low
    source_platform: str = "platform2"
    created_at: Optional[datetime] = None


class MaterialNode(BaseModel):
    """物料节点"""
    material_code: str
    name: str
    specification: Optional[str] = None
    grade: str = "industrial"       # aerospace/industrial
    lead_time: int = 0              # 采购提前期（天）
    unit: str = "件"
    is_key_material: bool = False
    source_platform: str = "platform1"
    created_at: Optional[datetime] = None


class SupplierNode(BaseModel):
    """供应商节点"""
    supplier_id: str
    name: str
    rating: str = "C"               # A/B/C/D
    aerospace_qualified: bool = False
    on_time_delivery_rate: float = 0.0
    risk_level: str = "low"         # high/medium/low
    source_platform: str = "srm"
    created_at: Optional[datetime] = None


class PurchaseOrderNode(BaseModel):
    """采购订单节点"""
    po_id: str
    order_date: Optional[datetime] = None
    quantity: float = 0.0
    promised_date: Optional[datetime] = None
    actual_arrival_date: Optional[datetime] = None
    status: str = "ordered"         # ordered/shipped/received/closed
    unit_price: float = 0.0
    source_platform: str = "srm"
    created_at: Optional[datetime] = None


class InventoryNode(BaseModel):
    """库存记录节点"""
    inventory_id: str
    available_quantity: float = 0.0
    reserved_quantity: float = 0.0
    batch_no: Optional[str] = None
    warehouse_location: Optional[str] = None
    last_updated: Optional[datetime] = None
    source_platform: str = "wms"


# ==================== 关系模型 ====================

class Relationship(BaseModel):
    """关系基类"""
    source_id: str
    target_id: str
    rel_type: RelationshipType
    properties: Dict[str, Any] = Field(default_factory=dict)


class RequiresRelation(Relationship):
    """工单需要物料关系"""
    rel_type: RelationshipType = RelationshipType.REQUIRES
    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "quantity": 0.0,
        "required_date": None
    })


class SuppliesRelation(Relationship):
    """供应商供应物料关系"""
    rel_type: RelationshipType = RelationshipType.SUPPLIES
    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "price": 0.0,
        "lead_time": 0
    })


class HasPORelation(Relationship):
    """采购单包含物料关系"""
    rel_type: RelationshipType = RelationshipType.HAS_PO
    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "quantity": 0.0,
        "unit_price": 0.0
    })


# ==================== 查询结果模型 ====================

class GraphQueryResult(BaseModel):
    """图谱查询结果"""
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    query_time_ms: int = 0


class PathResult(BaseModel):
    """路径查询结果"""
    nodes: List[Dict]
    relationships: List[Dict]
    length: int = 0