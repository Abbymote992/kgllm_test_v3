# backend/api/chat_api.py
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging

from models.request import QuestionRequest
from models.response import AnswerResponse
from services.kg_service import KnowledgeGraphService
from services.llm_service import LLMService
from services.cypher_generator import CypherGenerator
from services.task_manager import task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


def get_kg_service():
    from main import kg_service
    return kg_service


def get_llm_service():
    from main import llm_service
    return llm_service


def get_cypher_generator():
    from main import cypher_generator
    return cypher_generator


# ==========================================
# 方案三：流式响应接口
# ==========================================

@router.post("/ask/stream")
async def ask_stream(
        request: QuestionRequest,
        kg: KnowledgeGraphService = Depends(get_kg_service),
        llm: LLMService = Depends(get_llm_service),
        cypher_gen: CypherGenerator = Depends(get_cypher_generator)
):
    """流式问答 - 边生成边返回"""

    async def generate():
        question = request.question
        logger.info(f"流式问答开始: {question}")

        try:
            # 1. 发送开始信号
            yield f"data: {json.dumps({'type': 'start', 'message': '开始处理...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # 2. 获取Schema并生成Cypher
            yield f"data: {json.dumps({'type': 'step', 'step': 'generating_cypher', 'message': '正在理解问题...'}, ensure_ascii=False)}\n\n"

            schema = kg.get_schema()
            cypher = cypher_gen.generate(question, schema)

            if not cypher:
                yield f"data: {json.dumps({'type': 'error', 'message': '无法理解问题，请换个说法'}, ensure_ascii=False)}\n\n"
                return

            # 3. 返回生成的Cypher
            yield f"data: {json.dumps({'type': 'cypher', 'cypher': cypher}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # 4. 执行查询
            yield f"data: {json.dumps({'type': 'step', 'step': 'querying', 'message': '正在查询知识图谱...'}, ensure_ascii=False)}\n\n"

            result = kg.execute_query(cypher)

            if not result["success"]:
                yield f"data: {json.dumps({'type': 'error', 'message': f'查询失败:'})}"
                return

            # 5. 流式生成回答
            yield f"data: {json.dumps({'type': 'step', 'step': 'generating_answer', 'message': '正在生成回答...'}, ensure_ascii=False)}\n\n"

            # 收集完整回答
            full_answer = ""
            for chunk in llm.generate_answer_stream(question, result):
                full_answer += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            # 6. 发送完成信号
            yield f"data: {json.dumps({'type': 'end', 'full_answer': full_answer, 'cypher': cypher}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"流式问答失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ==========================================
# 方案五：异步任务接口
# ==========================================

@router.post("/ask/async")
async def ask_async(
        request: QuestionRequest,
        kg: KnowledgeGraphService = Depends(get_kg_service),
        llm: LLMService = Depends(get_llm_service),
        cypher_gen: CypherGenerator = Depends(get_cypher_generator)
):
    """异步问答 - 立即返回任务ID"""

    # 创建任务
    task_id = task_manager.create_task(request.question)

    # 后台执行
    asyncio.create_task(
        _process_question_async(
            task_id,
            request.question,
            kg, llm, cypher_gen
        )
    )

    return {
        "success": True,
        "task_id": task_id,
        "status": "pending",
        "message": "任务已创建，请轮询获取结果"
    }


@router.get("/ask/result/{task_id}")
async def get_ask_result(task_id: str):
    """获取异步任务结果"""
    task = task_manager.get_task(task_id)

    if not task:
        return {
            "success": False,
            "status": "not_found",
            "message": "任务不存在"
        }

    response = {
        "success": True,
        "task_id": task_id,
        "status": task["status"].value,
        "created_at": task["created_at"].isoformat()
    }

    if task["status"].value == "completed":
        response["answer"] = task["result"]
        response["cypher"] = task.get("cypher")
    elif task["status"].value == "failed":
        response["error"] = task.get("error")
    elif task["status"].value == "timeout":
        response["error"] = task.get("error", "任务执行超时")

    return response


@router.get("/ask/progress/{task_id}")
async def get_ask_progress(task_id: str):
    """获取任务进度"""
    task = task_manager.get_task(task_id)

    if not task:
        return {"success": False, "status": "not_found"}

    return {
        "success": True,
        "task_id": task_id,
        "status": task["status"].value,
        "steps": task.get("steps", []),
        "current_step": task["steps"][-1]["name"] if task.get("steps") else None
    }


async def _process_question_async(task_id: str, question: str, kg, llm, cypher_gen):
    """后台处理问题"""
    try:
        # 更新状态
        task_manager.update_task(task_id, status=task_manager.status.PROCESSING)
        task_manager.add_step(task_id, "开始处理", question)

        # 生成Cypher
        task_manager.add_step(task_id, "生成查询语句")
        schema = kg.get_schema()
        cypher = cypher_gen.generate(question, schema)

        if not cypher:
            task_manager.fail_task(task_id, "无法理解问题，请换个说法")
            return

        task_manager.add_step(task_id, "查询知识图谱", cypher)

        # 执行查询
        result = kg.execute_query(cypher)

        if not result["success"]:
            task_manager.fail_task(task_id, f"查询失败: {result.get('error', '未知错误')}")
            return

        # 生成回答
        task_manager.add_step(task_id, "生成回答", f"找到{result['count']}条结果")
        answer = llm.generate_answer(question, result)

        # 完成任务
        task_manager.complete_task(task_id, answer, cypher)

    except Exception as e:
        logger.error(f"异步处理失败: {e}")
        task_manager.fail_task(task_id, str(e))


# ==========================================
# 保留原有同步接口（带缓存）
# ==========================================

@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
        request: QuestionRequest,
        kg: KnowledgeGraphService = Depends(get_kg_service),
        llm: LLMService = Depends(get_llm_service),
        cypher_gen: CypherGenerator = Depends(get_cypher_generator)
):
    """同步问答（带缓存）"""
    logger.info(f"收到问题: {request.question}")

    schema = kg.get_schema()
    cypher = cypher_gen.generate(request.question, schema)

    if not cypher:
        return AnswerResponse(
            success=False,
            answer="无法理解您的问题，请尝试换个说法。",
            message="Text2Cypher生成失败"
        )

    result = kg.execute_query(cypher)

    if not result["success"]:
        return AnswerResponse(
            success=False,
            answer=f"查询执行失败: {result.get('error', '未知错误')}",
            cypher=cypher,
            message="查询执行失败"
        )

    # 使用带缓存的生成
    answer = llm.generate_answer(request.question, result)

    return AnswerResponse(
        success=True,
        answer=answer,
        cypher=cypher,
        raw_data=result["data"][:10]
    )