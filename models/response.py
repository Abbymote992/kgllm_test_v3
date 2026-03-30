# backend/models/response.py
"""
响应模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class BaseResponse(BaseModel):
    """基础响应模型，所有响应都继承此类"""
    success: bool = Field(..., description="是否成功")
    message: Optional[str] = Field(None, description="消息")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="时间戳"
    )


class AnswerResponse(BaseResponse):
    """问答响应模型"""
    answer: str = Field(..., description="回答内容")
    cypher: Optional[str] = Field(None, description="生成的Cypher查询")
    raw_data: Optional[List[Dict[str, Any]]] = Field(None, description="原始查询结果")


class GraphDataResponse(BaseResponse):
    """图谱数据响应模型"""
    nodes: List[Dict[str, Any]] = Field(..., description="节点列表")
    edges: List[Dict[str, Any]] = Field(..., description="边列表")
    total: int = Field(..., description="节点总数")


class SchemaResponse(BaseResponse):
    """Schema响应模型"""
    nodes: List[Dict[str, Any]] = Field(..., description="节点类型列表")
    relationships: List[Dict[str, Any]] = Field(..., description="关系类型列表")


class QueryResponse(BaseResponse):
    """Cypher查询响应模型"""
    data: List[Dict[str, Any]] = Field(..., description="查询结果数据")
    count: int = Field(..., description="结果数量")
    cypher: str = Field(..., description="执行的Cypher语句")


class StatsResponse(BaseResponse):
    """统计信息响应模型"""
    node_counts: Dict[str, int] = Field(..., description="节点数量统计")
    relationship_counts: Dict[str, int] = Field(..., description="关系数量统计")
    health: bool = Field(..., description="健康状态")