"""
指挥协调智能体 (Conductor Agent)

核心职责：
1. 意图识别 - 理解用户问题的类型
2. 任务分解 - 将复杂问题拆解为子任务
3. 流程编排 - 调度其他智能体协同工作
4. 异常处理 - 处理执行过程中的错误和重试

这是整个多智能体系统的"大脑"
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, retry_on_failure
from agents.context import AgentContext
from models.agent_models import (
    IntentType, AgentType, SubTask, TaskStatus,
    ExecutionPlan, ConductorOutput
)


class ConductorAgent(BaseAgent):
    """指挥协调智能体"""

    def __init__(self, llm_service, kg_service=None):
        """
        初始化指挥协调智能体

        Args:
            llm_service: LLM服务（用于意图识别和任务分解）
            kg_service: 知识图谱服务（可选）
        """
        super().__init__(
            name="ConductorAgent",
            agent_type=AgentType.CONDUCTOR,
            llm_service=llm_service,
            kg_service=kg_service
        )

        # 定义任务执行流程
        self.execution_flows = {
            IntentType.ANALYSIS: {
                "description": "齐套分析流程",
                "subtasks": [
                    {"type": "data_collection", "agent": AgentType.DATA_KNOWLEDGE},
                    {"type": "analysis", "agent": AgentType.ANALYSIS}
                ],
                "execution_mode": "sequential"  # 串行执行
            },
            IntentType.RISK: {
                "description": "风险评估流程",
                "subtasks": [
                    {"type": "data_collection", "agent": AgentType.DATA_KNOWLEDGE},
                    {"type": "risk_assessment", "agent": AgentType.RISK}
                ],
                "execution_mode": "sequential"
            },
            IntentType.PROCUREMENT: {
                "description": "采购决策流程",
                "subtasks": [
                    {"type": "data_collection", "agent": AgentType.DATA_KNOWLEDGE},
                    {"type": "analysis", "agent": AgentType.ANALYSIS},
                    {"type": "risk_assessment", "agent": AgentType.RISK},
                    {"type": "decision", "agent": AgentType.DECISION}
                ],
                "execution_mode": "sequential"
            },
            IntentType.COMPLEX: {
                "description": "复杂综合流程",
                "subtasks": [
                    {"type": "data_collection", "agent": AgentType.DATA_KNOWLEDGE},
                    {"type": "analysis", "agent": AgentType.ANALYSIS},
                    {"type": "risk_assessment", "agent": AgentType.RISK},
                    {"type": "decision", "agent": AgentType.DECISION}
                ],
                "execution_mode": "sequential"
            },
            IntentType.SIMPLE_QA: {
                "description": "简单问答流程",
                "subtasks": [],
                "execution_mode": "direct"  # 直接回答，不需要子任务
            }
        }

        # 智能体实例（依赖注入）
        self._agents = {}

    async def execute_stream(self, context, send_event):
        """流式执行多智能体协作 - 简化版"""
        import json

        try:
            # 发送开始事件
            await send_event(json.dumps({
                'type': 'agent_start',
                'agent': 'conductor',
                'message': '开始协调智能体...'
            }) + '\n\n')

            # 模拟执行各个智能体
            agents = ['data_knowledge', 'analysis', 'risk', 'decision']
            agent_names = {
                'data_knowledge': '数据知识智能体',
                'analysis': '分析智能体',
                'risk': '风险智能体',
                'decision': '决策智能体'
            }

            for agent in agents:
                # 开始事件
                await send_event(json.dumps({
                    'type': 'agent_start',
                    'agent': agent,
                    'message': f'{agent_names[agent]} 开始执行...'
                }) + '\n\n')

                # 模拟执行（如果有真实的智能体就调用）
                if agent in self._agents:
                    result = await self._agents[agent].execute(context)
                    output = str(
                        result.get('data', result.get('analysis', result.get('risks', result.get('decision', '')))))[
                             :200]
                else:
                    output = f'{agent_names[agent]} 执行完成（模拟）'

                # 完成事件
                await send_event(json.dumps({
                    'type': 'agent_complete',
                    'agent': agent,
                    'result': output
                }) + '\n\n')

            # 生成最终答案
            final_answer = f"关于「{context.question}」的分析已完成。"

            # 发送完成事件
            await send_event(json.dumps({
                'type': 'complete',
                'answer': final_answer,
                'details': {}
            }) + '\n\n')

            return {"answer": final_answer}

        except Exception as e:
            await send_event(json.dumps({
                'type': 'error',
                'message': str(e)
            }) + '\n\n')
            raise

    def register_agent(self, agent_type: AgentType, agent_instance):
        """注册其他智能体实例"""
        self._agents[agent_type] = agent_instance
        self.logger.info(f"已注册智能体: {agent_type.value}")

    @retry_on_failure(max_retries=2, delay=1.0)
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        执行指挥协调任务

        Args:
            context: 智能体上下文

        Returns:
            执行结果字典
        """
        import time
        start_time = time.time()

        self.logger.info(f"开始处理问题: {context.question[:100]}")

        try:
            # 1. 意图识别
            intent_result = await self._recognize_intent(context)
            context.set_intent(intent_result["intent"], intent_result.get("params"))
            self.logger.info(f"意图识别结果: {context.intent.value}")

            # 2. 简单问答直接返回
            if context.intent == IntentType.SIMPLE_QA:
                answer = await self._handle_simple_qa(context)
                self._log_execution(start_time)
                return {
                    "answer": answer,
                    "intent": context.intent.value,
                    "execution_plan": None
                }

            # 3. 创建执行计划
            execution_plan = await self._create_execution_plan(context)
            context._log("execution_plan_created", {
                "plan_id": execution_plan.plan_id,
                "subtask_count": len(execution_plan.subtasks)
            })

            # 4. 执行计划
            results = await self._execute_plan(execution_plan, context)

            # 5. 生成最终答案
            final_answer = await self._generate_final_answer(context, results)

            self._log_execution(start_time)

            return {
                "answer": final_answer,
                "intent": context.intent.value,
                "execution_plan": execution_plan.dict() if execution_plan else None,
                "intermediate_results": results
            }

        except Exception as e:
            self.logger.error(f"执行失败: {e}")
            context.set_error(str(e))
            self._log_execution(start_time, success=False)
            raise

    async def _recognize_intent(self, context: AgentContext) -> Dict[str, Any]:
        """
        识别用户意图
        """
        system_prompt = """你是供应链智能助手，负责识别用户问题的意图类型。

    意图类型说明：
    - analysis: 询问齐套率、缺料情况、物料状态、生产准备情况（如"齐套率"、"缺什么料"、"物料情况"）
    - risk: 询问风险、预警、供应商稳定性、交期风险（如"风险"、"预警"、"供应商问题"）
    - procurement: 询问采购建议、催货、下单、替代方案（如"怎么采购"、"买什么"、"下单"）
    - complex: 同时包含分析、风控、采购需求的综合问题（如"怎么办"、"如何处理"、"分析并建议"）
    - simple_qa: 简单查询（如"什么是XX"、"XX是什么意思"、"介绍一下XX"）

    重要规则：
    1. 如果问题包含"是什么"、"什么是"、"介绍一下"，优先判断为 simple_qa
    2. 如果问题包含"怎么办"、"如何处理"、"分析并建议"，优先判断为 complex
    3. 其他情况根据关键词判断

    请只返回JSON格式的结果，不要有其他内容。"""

        user_prompt = f"""
    用户问题: {context.question}

    请分析意图并提取关键参数，返回JSON格式：
    {{
        "intent": "analysis/risk/procurement/complex/simple_qa",
        "params": {{
            "project_id": "项目编号（如果有）",
            "module_id": "舱段编号（如果有）",
            "material_code": "物料编码（如果有）",
            "time_horizon": "时间范围（如果有）"
        }}
    }}
    """

        try:
            response = await self._call_llm(user_prompt, system_prompt, temperature=0.3)

            # 清理响应，提取JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            result = json.loads(response)

            intent_str = result.get("intent", "simple_qa")

            # 根据问题内容进行二次校验
            question_lower = context.question.lower()

            # 规则：如果问题是"什么是XX"，强制设为 simple_qa
            if "什么是" in question_lower or "是什么" in question_lower or "介绍一下" in question_lower:
                intent_str = "simple_qa"
            # 规则：如果问题包含"怎么办"或"如何处理"，强制设为 complex
            elif "怎么办" in question_lower or "如何处理" in question_lower:
                intent_str = "complex"

            return {
                "intent": IntentType(intent_str),
                "params": result.get("params", {})
            }

        except Exception as e:
            self.logger.warning(f"意图识别失败: {e}，使用默认意图")

            # 根据问题内容简单判断
            question_lower = context.question.lower()
            if "什么是" in question_lower or "是什么" in question_lower:
                return {"intent": IntentType.SIMPLE_QA, "params": {}}
            elif "齐套" in question_lower or "缺料" in question_lower:
                return {"intent": IntentType.ANALYSIS, "params": {}}
            elif "风险" in question_lower:
                return {"intent": IntentType.RISK, "params": {}}
            elif "采购" in question_lower:
                return {"intent": IntentType.PROCUREMENT, "params": {}}
            elif "怎么办" in question_lower:
                return {"intent": IntentType.COMPLEX, "params": {}}
            else:
                return {"intent": IntentType.SIMPLE_QA, "params": {}}

    async def _create_execution_plan(self, context: AgentContext) -> ExecutionPlan:
        """
        创建执行计划

        Args:
            context: 智能体上下文

        Returns:
            执行计划
        """
        flow = self.execution_flows.get(context.intent)
        if not flow:
            flow = self.execution_flows[IntentType.COMPLEX]

        subtasks = []
        execution_order = []

        for i, task_config in enumerate(flow["subtasks"]):
            subtask = SubTask(
                task_id=f"task_{i + 1}",
                task_type=task_config["type"],
                target_agent=task_config["agent"],
                params={
                    "original_question": context.question,
                    "extracted_params": context.extracted_params
                },
                depends_on=[]  # 串行执行，无依赖
            )
            subtasks.append(subtask)
            execution_order.append(subtask.task_id)

        return ExecutionPlan(
            plan_id=f"plan_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            original_question=context.question,
            intent=context.intent,
            subtasks=subtasks,
            execution_order=execution_order
        )

    async def _execute_plan(
            self,
            plan: ExecutionPlan,
            context: AgentContext
    ) -> Dict[str, Any]:
        """
        执行计划

        Args:
            plan: 执行计划
            context: 智能体上下文

        Returns:
            执行结果
        """
        results = {}

        for task_id in plan.execution_order:
            subtask = next((st for st in plan.subtasks if st.task_id == task_id), None)
            if not subtask:
                continue

            # 更新状态为运行中
            subtask.status = TaskStatus.RUNNING

            try:
                # 获取对应的智能体
                agent = self._agents.get(subtask.target_agent)
                if not agent:
                    raise ValueError(f"未找到智能体: {subtask.target_agent}")

                # 执行子任务
                self.logger.info(f"执行子任务: {subtask.task_id} - {subtask.task_type}")
                result = await agent.execute(context)

                # 保存结果
                subtask.result = result
                subtask.status = TaskStatus.SUCCESS
                subtask.completed_at = datetime.now()

                # 更新上下文中的智能体结果
                agent_name = subtask.target_agent.value
                context.set_agent_result(agent_name, result)

                results[subtask.task_type] = result

            except Exception as e:
                subtask.status = TaskStatus.FAILED
                subtask.error = str(e)
                self.logger.error(f"子任务失败: {subtask.task_id} - {e}")

                # 根据失败策略决定是否继续
                if not await self._handle_subtask_failure(subtask, plan):
                    raise

        return results

    async def _handle_subtask_failure(
            self,
            subtask: SubTask,
            plan: ExecutionPlan
    ) -> bool:
        """
        处理子任务失败

        Args:
            subtask: 失败的子任务
            plan: 执行计划

        Returns:
            是否继续执行
        """
        # 简单策略：分析失败时继续风控，其他失败则停止
        if subtask.task_type == "analysis":
            self.logger.warning("分析失败，继续执行后续任务")
            return True
        elif subtask.task_type == "risk_assessment":
            self.logger.warning("风控失败，继续执行决策")
            return True
        else:
            self.logger.error("关键任务失败，停止执行")
            return False

    async def _handle_simple_qa(self, context: AgentContext) -> str:
        """
        处理简单问答（不需要其他智能体）
        """
        system_prompt = """你是供应链知识助手，请根据你的知识回答问题。
    如果问题涉及具体数据（如齐套率、缺料情况），请说明需要查询系统数据。
    回答要简洁、准确。"""

        # 构建知识库上下文（如果有RAG）
        knowledge_context = ""
        if hasattr(self, '_get_knowledge_context'):
            knowledge_context = await self._get_knowledge_context(context.question)

        user_prompt = f"""
    问题: {context.question}

    {knowledge_context}

    请回答：
    """

        try:
            answer = await self._call_llm(user_prompt, system_prompt, temperature=0.5)
            return answer
        except Exception as e:
            self.logger.error(f"简单问答失败: {e}")
            # 返回备用答案
            return f"关于「{context.question}」，我暂时无法给出准确回答。请尝试更具体的问题，或联系管理员。"

#     async def _generate_final_answer(
#             self,
#             context: AgentContext,
#             results: Dict[str, Any]
#     ) -> str:
#         """
#         生成最终答案
#
#         Args:
#             context: 智能体上下文
#             results: 各子任务执行结果
#
#         Returns:
#             最终答案文本
#         """
#         # 如果没有分析结果，返回简单答案
#         if not results:
#             return "抱歉，我无法处理这个问题。请尝试更具体的问题。"
#
#         # 构建提示词
#         system_prompt = """你是供应链智能助手，负责将分析结果转化为清晰、易懂的回答。
#
# 要求：
# 1. 回答要结构化，先给结论，再给细节
# 2. 突出关键信息（齐套率、缺货物料、风险等级、建议行动）
# 3. 使用友好的语气
# 4. 如果数据不足，说明需要补充什么信息
# """
#
#         # 构建上下文信息
#         context_info = {
#             "original_question": context.question,
#             "analysis_result": results.get("analysis", {}),
#             "risk_result": results.get("risk_assessment", {}),
#             "decision_result": results.get("decision", {}),
#             "data_context": context.data_context
#         }
#
#         user_prompt = f"""
# 基于以下分析结果，回答用户问题。
#
# 用户问题: {context.question}
#
# 分析结果:
# {json.dumps(context_info, ensure_ascii=False, default=str, indent=2)}
#
# 请生成最终回答:
# """
#
#         try:
#             answer = await self._call_llm(user_prompt, system_prompt, temperature=0.5)
#             return answer
#         except Exception as e:
#             self.logger.error(f"生成答案失败: {e}")
#             return self._generate_fallback_answer(context, results)

    def _generate_fallback_answer(
            self,
            context: AgentContext,
            results: Dict[str, Any]
    ) -> str:
        """
        生成备用答案（当LLM失败时）

        Args:
            context: 智能体上下文
            results: 执行结果

        Returns:
            备用答案
        """
        # 提取分析结果
        analysis = results.get("analysis", {})

        if analysis:
            kit_rate = analysis.get("kit_rate", 0)
            shortages = analysis.get("shortages", [])

            answer = f"根据分析结果：\n"
            answer += f"- 齐套率: {kit_rate * 100:.1f}%\n"

            if shortages:
                answer += f"- 缺货物料数量: {len(shortages)}种\n"
                answer += f"- 主要缺货物料: {', '.join([s.get('material_name', '') for s in shortages[:3]])}\n"
            else:
                answer += "- 无缺货物料，所有物料已齐套\n"

            # 添加风险信息
            risk = results.get("risk_assessment", {})
            if risk:
                risk_level = risk.get("overall_risk_level", "none")
                answer += f"- 整体风险等级: {risk_level}\n"

            # 添加决策建议
            decision = results.get("decision", {})
            if decision:
                recommended = decision.get("recommended_action", "")
                if recommended:
                    answer += f"- 建议行动: {recommended}\n"

            return answer

        return f"收到您的问题：{context.question}\n\n系统正在处理中，请稍后..."

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查（增强版）

        Returns:
            健康状态
        """
        base_health = await super().health_check()

        registered_agents = {
            agent_type.value: agent is not None
            for agent_type, agent in self._agents.items()
        }

        return {
            "agent": self.name,
            "healthy": base_health,
            "registered_agents": registered_agents,
            "registered_count": len(self._agents),
            "execution_flows": list(self.execution_flows.keys())
        }

    def _generate_final_answer(self, context, results):
        """生成最终答案"""
        analysis = results.get("analysis", {})
        risk = results.get("risk_assessment", {})
        decision = results.get("decision", {})

        # 如果分析结果中有数据，构建答案
        if analysis:
            kit_rate = analysis.get("kit_rate", 0)
            shortages = analysis.get("shortages", [])

            answer = f"根据查询结果：\n"
            if kit_rate > 0:
                answer += f"📊 齐套率: {kit_rate * 100:.1f}%\n"

            if shortages:
                answer += f"⚠️ 缺货物料数量: {len(shortages)}种\n"
                for s in shortages[:3]:
                    answer += f"  - {s.get('material_name', '未知物料')}\n"
            else:
                answer += "✅ 无缺货物料，所有物料已齐套\n"

            if risk:
                risk_level = risk.get("overall_risk_level", "低")
                answer += f"📈 风险等级: {risk_level}\n"

            if decision:
                action = decision.get("recommended_action", "")
                if action:
                    answer += f"💡 建议: {action}\n"

            return answer

        return f"关于「{context.question}」的查询已完成。详细信息请查看各智能体输出。"