"""
智能体核心数据模型

定义智能体系统中的核心数据结构，包括：
- 任务定义与状态
- 智能体执行上下文
- 意图识别结果
- 各智能体的输入输出结构
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import uuid4


# ==================== 枚举类型定义 ====================

class IntentType(str, Enum):
    """意图类型 - 指挥协调智能体识别结果"""
    ANALYSIS = "analysis"  # 需要齐套分析
    RISK = "risk"  # 需要风险评估
    PROCUREMENT = "procurement"  # 需要采购建议
    COMPLEX = "complex"  # 复杂综合任务
    SIMPLE_QA = "simple_qa"  # 简单问答（不需要业务智能体）


class TaskStatus(str, Enum):
    """任务执行状态"""
    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    RETRYING = "retrying"  # 重试中
    SKIPPED = "skipped"  # 已跳过


class AgentType(str, Enum):
    """智能体类型"""
    CONDUCTOR = "conductor"  # 指挥协调智能体
    DATA_KNOWLEDGE = "data_knowledge"  # 数据知识智能体
    ANALYSIS = "analysis"  # 分析智能体
    RISK = "risk"  # 风控智能体
    DECISION = "decision"  # 决策智能体


class RiskLevel(str, Enum):
    """风险等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ShortageStatus(str, Enum):
    """缺料状态"""
    KITTED = "kitted"  # 已齐套
    CRITICAL = "critical"  # 严重缺料
    RISK = "risk"  # 存在风险
    PENDING = "pending"  # 待确认


# ==================== 任务相关模型 ====================

class SubTask(BaseModel):
    """子任务定义 - 任务分解的结果"""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    task_type: str  # 任务类型：query_bom, query_inventory, calculate_kit_rate, assess_risk, generate_advice
    target_agent: AgentType  # 目标智能体
    params: Dict[str, Any] = Field(default_factory=dict)  # 任务参数
    depends_on: List[str] = Field(default_factory=list)  # 依赖的任务ID列表
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ExecutionPlan(BaseModel):
    """执行计划 - 指挥协调智能体输出"""
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    original_question: str
    intent: IntentType
    subtasks: List[SubTask] = Field(default_factory=list)
    execution_order: List[str] = Field(default_factory=list)  # 任务ID执行顺序
    created_at: datetime = Field(default_factory=datetime.now)


# ==================== 智能体上下文 ====================

class AgentContext(BaseModel):
    """智能体执行上下文 - 在智能体间传递"""
    session_id: str
    question: str
    intent: Optional[IntentType] = None
    params: Dict[str, Any] = Field(default_factory=dict)  # 提取的参数（项目号、时间等）

    # 各智能体产生的中间结果
    data_context: Optional[Dict[str, Any]] = None  # 数据知识智能体产出
    analysis_result: Optional[Dict[str, Any]] = None  # 分析智能体产出
    risk_result: Optional[Dict[str, Any]] = None  # 风控智能体产出
    decision_result: Optional[Dict[str, Any]] = None  # 决策智能体产出

    # 执行元数据
    execution_log: List[Dict] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


# ==================== 各智能体输入/输出模型 ====================

# ----- 指挥协调智能体 -----
class ConductorInput(BaseModel):
    """指挥协调智能体输入"""
    question: str
    session_id: str
    history: List[Dict] = Field(default_factory=list)  # 对话历史


class ConductorOutput(BaseModel):
    """指挥协调智能体输出"""
    intent: IntentType
    execution_plan: ExecutionPlan
    direct_answer: Optional[str] = None  # 当intent为SIMPLE_QA时使用
    extracted_params: Dict[str, Any] = Field(default_factory=dict)


# ----- 数据知识智能体 -----
class DataKnowledgeInput(BaseModel):
    """数据知识智能体输入"""
    subtask: SubTask
    context: AgentContext
    query_type: str  # bom_query, inventory_query, purchase_query, schedule_query, knowledge_retrieval


class DataKnowledgeOutput(BaseModel):
    """数据知识智能体输出"""
    graph_data: Dict[str, Any] = Field(default_factory=dict)  # 图谱查询结果
    knowledge_context: List[Dict] = Field(default_factory=list)  # RAG检索结果
    business_rules: Dict[str, Any] = Field(default_factory=dict)  # 业务规则
    data_quality: Dict[str, Any] = Field(default_factory=dict)  # 数据质量报告
    standardized_view: Dict[str, Any] = Field(default_factory=dict)  # 标准化视图


# ----- 分析智能体 -----
class AnalysisInput(BaseModel):
    """分析智能体输入"""
    data_context: DataKnowledgeOutput
    project_id: Optional[str] = None
    work_order_id: Optional[str] = None
    time_window: Optional[Dict[str, datetime]] = None


class ShortageItem(BaseModel):
    """缺料项"""
    material_code: str
    material_name: str
    required_quantity: float
    available_quantity: float
    shortage_quantity: float
    expected_arrival_date: Optional[datetime]
    supplier_name: str
    status: ShortageStatus
    reason: Optional[str] = None


class AnalysisOutput(BaseModel):
    """分析智能体输出"""
    kit_rate: float = 0.0  # 齐套率（0-1）
    total_materials: int = 0  # 总物料种类数
    kitted_count: int = 0  # 已齐套数量
    shortages: List[ShortageItem] = Field(default_factory=list)  # 缺料清单
    bottleneck_materials: List[Dict] = Field(default_factory=list)  # 瓶颈物料
    health_score: float = 0.0  # 健康度评分（0-100）
    summary: str = ""  # 分析摘要


# ----- 风控智能体 -----
class RiskInput(BaseModel):
    """风控智能体输入"""
    analysis_result: AnalysisOutput
    data_context: DataKnowledgeOutput


class RiskEvent(BaseModel):
    """风险事件"""
    event_type: str  # shortage_delay, supplier_risk, logistics_risk
    level: RiskLevel
    description: str
    affected_materials: List[str]
    estimated_impact_days: int
    suggestion: str


class RiskOutput(BaseModel):
    """风控智能体输出"""
    overall_risk_level: RiskLevel = RiskLevel.NONE
    shortage_risk: RiskLevel = RiskLevel.NONE
    supplier_risk: Dict[str, RiskLevel] = Field(default_factory=dict)  # 供应商->风险等级
    risk_events: List[RiskEvent] = Field(default_factory=list)
    alerts: List[Dict] = Field(default_factory=list)  # 预警信息（含接收人）
    summary: str = ""


# ----- 决策智能体 -----
class DecisionInput(BaseModel):
    """决策智能体输入"""
    analysis_result: AnalysisOutput
    risk_result: RiskOutput
    data_context: DataKnowledgeOutput


class ProcurementAction(BaseModel):
    """采购行动建议"""
    material_code: str
    material_name: str
    action: str  # 立即催货 / 启动备选供应商 / 调整采购批量 / 接受替代料
    priority: str  # 高 / 中 / 低
    reason: str
    estimated_cost_impact: Optional[float]
    suggested_deadline: Optional[datetime]


class DecisionOutput(BaseModel):
    """决策智能体输出"""
    urgency: str = ""  # 紧急 / 常规 / 可延迟
    strategy_summary: str = ""  # 策略摘要
    procurement_actions: List[ProcurementAction] = Field(default_factory=list)
    alternative_suggestions: List[str] = Field(default_factory=list)
    recommended_action: str = ""  # 最重要的推荐行动
    cost_analysis: Dict[str, float] = Field(default_factory=dict)


# ==================== 最终响应模型 ====================

class AgentFinalResponse(BaseModel):
    """智能体系统最终响应"""
    session_id: str
    question: str
    answer: str  # 自然语言答案
    intent: IntentType
    execution_time_ms: int = 0

    # 详细结果（可选，用于前端展示调试信息）
    details: Optional[Dict[str, Any]] = None

    # 用于可视化的图谱数据
    graph_data: Optional[Dict[str, Any]] = None

    success: bool = True
    error: Optional[str] = None