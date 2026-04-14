"""
智能体管理接口

提供：
1. 智能体状态查询
2. 智能体配置管理
3. 智能体统计信息
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/agent", tags=["agent"])

# 全局智能体实例
_agents = {}


def init_agents(agents_dict: Dict[str, Any]):
    """初始化智能体实例"""
    global _agents
    _agents = agents_dict


@router.get("/status")
async def get_agent_status():
    """获取所有智能体状态"""
    status = {}

    for name, agent in _agents.items():
        if agent and hasattr(agent, 'health_check'):
            try:
                health = await agent.health_check()
                status[name] = health
            except Exception as e:
                status[name] = {"healthy": False, "error": str(e)}
        else:
            status[name] = {"healthy": False, "error": "Agent not available"}

    return {
        "total_agents": len(_agents),
        "agents": status
    }


@router.get("/stats")
async def get_agent_stats():
    """获取智能体统计信息"""
    stats = {}

    for name, agent in _agents.items():
        if agent and hasattr(agent, 'get_stats'):
            try:
                stats[name] = agent.get_stats()
            except Exception as e:
                stats[name] = {"error": str(e)}
        else:
            stats[name] = {"error": "Stats not available"}

    return {
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "stats": stats
    }


@router.post("/reset/{agent_name}")
async def reset_agent(agent_name: str):
    """重置智能体统计"""
    if agent_name not in _agents:
        raise HTTPException(status_code=404, detail=f"智能体 {agent_name} 不存在")

    agent = _agents[agent_name]
    if hasattr(agent, 'reset_stats'):
        agent.reset_stats()
        return {"message": f"智能体 {agent_name} 统计已重置"}

    return {"message": f"智能体 {agent_name} 不支持重置"}


@router.get("/config")
async def get_agent_config():
    """获取智能体配置"""
    from config import AGENT_CONFIG, DATA_SOURCE_CONFIG

    return {
        "agent_config": AGENT_CONFIG,
        "data_source_config": DATA_SOURCE_CONFIG
    }


class ConfigUpdate(BaseModel):
    """配置更新请求"""
    key: str
    value: Any


@router.post("/config")
async def update_agent_config(update: ConfigUpdate):
    """更新智能体配置"""
    from config import AGENT_CONFIG

    if update.key in AGENT_CONFIG:
        AGENT_CONFIG[update.key] = update.value
        return {"message": f"配置 {update.key} 已更新", "value": update.value}

    raise HTTPException(status_code=404, detail=f"配置项 {update.key} 不存在")