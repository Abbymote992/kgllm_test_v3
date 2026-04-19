"""
聊天问答接口

提供：
1. 同步问答接口
2. 流式问答接口
3. 异步问答接口
4. 多智能体流式接口
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, AsyncGenerator
import asyncio
import json
import time
from datetime import datetime

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import AGENT_CONFIG

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 全局智能体实例（在main.py中初始化）
_conductor_agent = None
_data_knowledge_agent = None
_analysis_agent = None
_risk_agent = None
_decision_agent = None


def init_agents(conductor, data_knowledge, analysis, risk, decision):
    """初始化智能体实例"""
    global _conductor_agent, _data_knowledge_agent, _analysis_agent, _risk_agent, _decision_agent
    _conductor_agent = conductor
    _data_knowledge_agent = data_knowledge
    _analysis_agent = analysis
    _risk_agent = risk
    _decision_agent = decision


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str = Field(..., description="用户问题")
    session_id: str = Field(default="default", description="会话ID")
    mode: str = Field(default="sync", description="模式: sync/stream/async")
    history: Optional[list] = Field(default=[], description="对话历史")


class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str = Field(..., description="回答")
    session_id: str = Field(..., description="会话ID")
    intent: Optional[str] = Field(default=None, description="识别的意图")
    execution_time_ms: float = Field(default=0, description="执行时间(毫秒)")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细信息")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


@router.post("/sync")
async def sync_chat(request: ChatRequest):
    """同步问答接口"""
    if not _conductor_agent:
        raise HTTPException(status_code=500, detail="智能体未初始化")

    start_time = time.time()

    try:
        from agents.context import AgentContext
        context = AgentContext(
            session_id=request.session_id,
            question=request.question
        )

        result = await _conductor_agent.execute(context)

        execution_time_ms = (time.time() - start_time) * 1000

        response = ChatResponse(
            answer=result.get("answer", "无法生成回答"),
            session_id=request.session_id,
            intent=result.get("intent"),
            execution_time_ms=round(execution_time_ms, 2),
            details=result.get("intermediate_results") if AGENT_CONFIG.get("enable_debug", False) else None
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    """流式问答接口"""
    if not _conductor_agent:
        raise HTTPException(status_code=500, detail="智能体未初始化")

    async def generate() -> AsyncGenerator[str, None]:
        try:
            from agents.context import AgentContext
            context = AgentContext(
                session_id=request.session_id,
                question=request.question
            )

            result = await _conductor_agent.execute(context)
            answer = result.get("answer", "无法生成回答")

            for char in answer:
                yield char
                await asyncio.sleep(0.01)

            yield "\n\n---\n"
            yield f"意图: {result.get('intent', 'unknown')}"

        except Exception as e:
            yield f"错误: {str(e)}"

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/async")
async def async_chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """异步问答接口"""
    import uuid

    task_id = str(uuid.uuid4())

    if not hasattr(async_chat, "tasks"):
        async_chat.tasks = {}

    async_chat.tasks[task_id] = {
        "status": "processing",
        "result": None,
        "created_at": datetime.now().isoformat()
    }

    async def process_task():
        try:
            from agents.context import AgentContext
            context = AgentContext(
                session_id=request.session_id,
                question=request.question
            )

            result = await _conductor_agent.execute(context)
            async_chat.tasks[task_id]["status"] = "completed"
            async_chat.tasks[task_id]["result"] = result

        except Exception as e:
            async_chat.tasks[task_id]["status"] = "failed"
            async_chat.tasks[task_id]["error"] = str(e)

    background_tasks.add_task(process_task)

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "任务已提交，请使用 /api/chat/status/{task_id} 查询结果"
    }


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """查询异步任务状态"""
    if not hasattr(async_chat, "tasks"):
        raise HTTPException(status_code=404, detail="任务不存在")

    task = async_chat.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task_id,
        "status": task["status"],
        "result": task.get("result"),
        "error": task.get("error"),
        "created_at": task.get("created_at")
    }


@router.get("/health")
async def health_check():
    """健康检查"""
    agents_ready = {
        "conductor": _conductor_agent is not None,
        "data_knowledge": _data_knowledge_agent is not None,
        "analysis": _analysis_agent is not None,
        "risk": _risk_agent is not None,
        "decision": _decision_agent is not None
    }

    return {
        "status": "healthy" if all(agents_ready.values()) else "degraded",
        "agents": agents_ready,
        "config": AGENT_CONFIG
    }


@router.post("/agent-stream-testbanben")
async def agent_stream_chat_test_banben(request: ChatRequest):
    """多智能体流式问答 - 模拟版本（不依赖 execute_stream）"""

    async def generate():
        if not _conductor_agent:
            yield f"data: {json.dumps({'type': 'error', 'message': '智能体未初始化'})}\n\n"
            return

        # 模拟智能体执行过程
        agents = [
            ("conductor", "指挥协调器"),
            ("data_knowledge", "数据知识智能体"),
            ("analysis", "分析智能体"),
            ("risk", "风险智能体"),
            ("decision", "决策智能体")
        ]

        for agent, name in agents:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent, 'message': f'{name} 开始执行...'})}\n\n"
            await asyncio.sleep(0.5)

            # 发送完成事件
            yield f"data: {json.dumps({'type': 'agent_complete', 'agent': agent, 'result': f'{name} 执行完成'})}\n\n"
            await asyncio.sleep(0.3)

        # 发送最终答案
        yield f"data: {json.dumps({'type': 'complete', 'answer': f'关于「{request.question}」的模拟回答。多智能体协作完成！', 'details': {}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/agent-stream")
async def agent_stream_chat(request: ChatRequest):
    """多智能体流式问答 - 按执行计划编排"""

    async def generate():
        def sse(payload: Dict[str, Any]) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

        def build_agent_preview(agent_key: str, result: Dict[str, Any]) -> str:
            if not isinstance(result, dict):
                return str(result)[:200]

            if agent_key == "data_knowledge":
                sv = result.get("standardized_view", {}) or {}
                return (
                    f"物料{len(sv.get('materials', []))}种，"
                    f"库存{len(sv.get('inventory', []))}条，"
                    f"供应商{len(sv.get('suppliers', []))}家"
                )
            if agent_key == "analysis":
                return (
                    result.get("analysis")
                    or f"齐套率: {result.get('kit_rate', 0) * 100:.1f}%"
                )[:200]
            if agent_key == "risk":
                return (
                    result.get("risk_summary")
                    or f"风险等级: {result.get('overall_risk_level', 'unknown')}"
                )[:200]
            if agent_key == "decision":
                return (
                    result.get("recommended_action")
                    or result.get("decision")
                    or "已生成决策建议"
                )[:200]
            return str(result)[:200]

        if not _conductor_agent:
            yield sse({"type": "error", "message": "智能体未初始化"})
            return

        try:
            from agents.context import AgentContext
            context = AgentContext(
                session_id=request.session_id,
                question=request.question
            )

            # 1) Conductor: 意图识别
            yield sse({
                "type": "agent_start",
                "agent": "conductor",
                "message": "正在识别用户意图..."
            })
            intent_result = await _conductor_agent._recognize_intent(context)
            intent = intent_result.get("intent")
            context.set_intent(intent, intent_result.get("params", {}))
            yield sse({
                "type": "agent_complete",
                "agent": "conductor",
                "result": f"识别到意图: {context.intent.value}"
            })

            # simple_qa 直接回答
            if context.intent.value == "simple_qa":
                answer = await _conductor_agent._handle_simple_qa(context)
                yield sse({
                    "type": "complete",
                    "answer": answer,
                    "details": {"intent": context.intent.value}
                })
                return

            # 2) 创建执行计划
            plan = await _conductor_agent._create_execution_plan(context)
            results = {}

            # 3) 按计划执行子任务，并实时推送
            for task_id in plan.execution_order:
                subtask = next((st for st in plan.subtasks if st.task_id == task_id), None)
                if not subtask:
                    continue

                agent_key = subtask.target_agent.value
                agent = _conductor_agent._agents.get(subtask.target_agent)
                if not agent:
                    yield sse({
                        "type": "agent_complete",
                        "agent": agent_key,
                        "result": f"智能体未注册: {agent_key}"
                    })
                    continue

                yield sse({
                    "type": "agent_start",
                    "agent": agent_key,
                    "message": f"{agent_key} 正在执行 {subtask.task_type}..."
                })

                try:
                    result = await agent.execute(context)
                    context.set_agent_result(agent_key, result)
                    results[subtask.task_type] = result
                    yield sse({
                        "type": "agent_complete",
                        "agent": agent_key,
                        "result": build_agent_preview(agent_key, result)
                    })
                except Exception as task_err:
                    subtask.error = str(task_err)
                    yield sse({
                        "type": "agent_complete",
                        "agent": agent_key,
                        "result": f"执行失败: {task_err}"
                    })
                    should_continue = await _conductor_agent._handle_subtask_failure(subtask, plan)
                    if not should_continue:
                        raise

            # 4) 汇总最终回答
            final_answer = _conductor_agent._generate_final_answer(context, results)
            yield sse({
                "type": "complete",
                "answer": final_answer,
                "details": {
                    "intent": context.intent.value,
                    "execution_plan": plan.dict(),
                    "intermediate_results": results
                }
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
