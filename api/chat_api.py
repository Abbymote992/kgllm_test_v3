# backend/api/chat_api.py
from fastapi import APIRouter, HTTPException, Depends
import logging

from models.request import QuestionRequest
from models.response import AnswerResponse
from services.kg_service import KnowledgeGraphService
from services.llm_service import LLMService
from services.cypher_generator import CypherGenerator

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


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
        request: QuestionRequest,
        kg: KnowledgeGraphService = Depends(get_kg_service),
        llm: LLMService = Depends(get_llm_service),
        cypher_gen: CypherGenerator = Depends(get_cypher_generator)
):
    """智能问答"""
    logger.info(f"收到问题: {request.question}")

    # 1. 获取Schema
    schema = kg.get_schema()

    # 2. 生成Cypher
    cypher = cypher_gen.generate(request.question, schema)

    if not cypher:
        return AnswerResponse(
            success=False,
            answer="无法理解您的问题，请尝试换个说法。",
            message="Text2Cypher生成失败"
        )

    # 3. 执行查询
    result = kg.execute_query(cypher)

    if not result["success"]:
        return AnswerResponse(
            success=False,
            answer=f"查询执行失败: {result.get('error', '未知错误')}",
            cypher=cypher,
            message="查询执行失败"
        )

    # 4. 生成自然语言回答
    answer = llm.generate_answer(request.question, result)

    return AnswerResponse(
        success=True,
        answer=answer,
        cypher=cypher,
        raw_data=result["data"][:10]  # 只返回前10条
    )


@router.post("/ask/direct")
async def ask_direct(request: QuestionRequest, **kwargs):
    """直接问答（不返回Cypher）"""
    response = await ask_question(request, **kwargs)
    return {"answer": response.answer}