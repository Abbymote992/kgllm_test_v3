# backend/api/kg_api.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from models.request import GraphDataRequest, CypherQueryRequest
from models.response import GraphDataResponse, SchemaResponse, QueryResponse
from services.kg_service import KnowledgeGraphService

# backend/api/kg_api.py
from utils.serializer import to_json_serializable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["knowledge-graph"])


# 依赖注入
def get_kg_service():
    """获取知识图谱服务实例（将在main.py中注入）"""
    from main import kg_service
    return kg_service


@router.get("/schema", response_model=SchemaResponse)
async def get_schema(kg: KnowledgeGraphService = Depends(get_kg_service)):
    """获取图谱Schema"""
    schema = kg.get_schema()
    return SchemaResponse(
        success=True,
        nodes=schema["nodes"],
        relationships=schema["relationships"]
    )


@router.get("/graph", response_model=GraphDataResponse)
async def get_graph_data(
        limit: int = 50,
        node_types: Optional[str] = None,
        kg: KnowledgeGraphService = Depends(get_kg_service)
):
    """获取图谱可视化数据"""
    types = node_types.split(",") if node_types else None
    result = kg.get_graph_data(limit, types)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "获取图谱数据失败"))

    return GraphDataResponse(
        success=True,
        nodes=result["nodes"],
        edges=result["edges"],
        total=result["total"]
    )


@router.post("/query", response_model=QueryResponse)
async def execute_query(
        request: CypherQueryRequest,
        kg: KnowledgeGraphService = Depends(get_kg_service)
):
    """执行Cypher查询"""
    result = kg.execute_query(request.cypher)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "查询执行失败"))

    return QueryResponse(
        success=True,
        data=result["data"],
        count=result["count"],
        cypher=result["cypher"]
    )


@router.get("/stats")
async def get_stats(kg: KnowledgeGraphService = Depends(get_kg_service)):
    """获取统计信息"""
    return {
        "success": True,
        "node_counts": kg.get_node_count(),
        "relationship_counts": kg.get_relationship_count(),
        "health": kg.health_check()
    }


@router.post("/query")
async def execute_query(
        request: dict,
        kg: KnowledgeGraphService = Depends(get_kg_service)
):
    """执行Cypher查询"""
    cypher = request.get("cypher")
    if not cypher:
        return {"success": False, "error": "缺少cypher参数"}

    result = kg.execute_query(cypher)
    return result



@router.get("/graph", response_model=GraphDataResponse)
async def get_graph_data(
        limit: int = 50,
        node_types: Optional[str] = None,
        kg: KnowledgeGraphService = Depends(get_kg_service)
):
    """获取图谱可视化数据"""
    types = node_types.split(",") if node_types else None
    result = kg.get_graph_data(limit, types)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "获取图谱数据失败"))

    # 转换所有数据为可序列化格式
    nodes = [to_json_serializable(node) for node in result["nodes"]]
    edges = [to_json_serializable(edge) for edge in result["edges"]]

    return GraphDataResponse(
        success=True,
        nodes=nodes,
        edges=edges,
        total=result["total"]
    )