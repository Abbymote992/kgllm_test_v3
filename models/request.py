# backend/models/request.py
from pydantic import BaseModel, Field
from typing import Optional, List, Any

class QuestionRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., description="用户问题", min_length=1, max_length=500)
    session_id: Optional[str] = Field(None, description="会话ID")


class CypherQueryRequest(BaseModel):
    """Cypher查询请求"""
    cypher: str = Field(..., description="Cypher查询语句")
    limit: Optional[int] = Field(100, description="返回数量限制", ge=1, le=500)


class GraphDataRequest(BaseModel):
    """图谱数据请求"""
    limit: Optional[int] = Field(50, description="返回节点限制", ge=1, le=200)
    node_types: Optional[List[str]] = Field(None, description="节点类型过滤")