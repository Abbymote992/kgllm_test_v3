"""
决策智能体 (Decision Agent)

核心职责：
1. 采购建议生成 - 基于缺料和风险生成具体采购行动
2. 替代方案推荐 - 推荐备选供应商或替代物料
3. 成本分析 - 评估不同方案的紧急采购成本
4. 优先级排序 - 确定最紧急的采购行动

这是系统的"行动专家"
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, retry_on_failure
from agents.context import AgentContext
from models.agent_models import AgentType, ProcurementAction


class DecisionAgent(BaseAgent):
    """决策智能体"""

    def __init__(self, llm_service=None, kg_service=None):
        """
        初始化决策智能体

        Args:
            llm_service: LLM服务（用于生成决策建议）
            kg_service: 知识图谱服务（用于查询替代关系）
        """
        super().__init__(
            name="DecisionAgent",
            agent_type=AgentType.DECISION,
            llm_service=llm_service,
            kg_service=kg_service
        )

        # 决策配置
        self.config = {
            "urgent_threshold_days": 7,  # 紧急阈值（天）
            "high_priority_score": 70,  # 高优先级分数阈值
            "medium_priority_score": 50,  # 中优先级分数阈值
            "cost_multiplier_urgent": 1.5,  # 紧急采购成本倍数
            "cost_multiplier_air": 2.0  # 空运成本倍数
        }

        # 预定义采购行动模板
        self.action_templates = {
            "expedite": {
                "action": "立即催货",
                "description": "联系供应商确认最新交期，要求加急处理",
                "estimated_lead_time_reduction": 3
            },
            "alternative_supplier": {
                "action": "启动备选供应商",
                "description": "评估备选供应商资质，启动紧急采购流程",
                "estimated_lead_time_reduction": 5
            },
            "substitute_material": {
                "action": "使用替代物料",
                "description": "评估替代物料的技术可行性，申请工程变更",
                "estimated_lead_time_reduction": 2
            },
            "stock_transfer": {
                "action": "库存调拨",
                "description": "从其他项目或仓库调拨库存",
                "estimated_lead_time_reduction": 1
            },
            "air_freight": {
                "action": "改为空运",
                "description": "将海运/陆运改为空运，缩短运输时间",
                "estimated_lead_time_reduction": 10
            }
        }

    @retry_on_failure(max_retries=2, delay=1.0)
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        执行决策任务

        Args:
            context: 智能体上下文

        Returns:
            决策结果
        """
        import time
        start_time = time.time()

        self.logger.info(f"开始决策分析: {context.question[:50]}...")

        try:
            # 获取分析结果和风控结果
            analysis_result = context.analysis_result
            risk_result = context.risk_result
            data_context = context.data_context

            if not analysis_result:
                analysis_result = {}
            if not risk_result:
                risk_result = {}
            if not data_context:
                data_context = {}

            shortages = analysis_result.get("shortages", [])
            kit_rate = analysis_result.get("kit_rate", 0)
            overall_risk = risk_result.get("overall_risk_level", "none")

            # 1. 判断紧急程度
            urgency = self._determine_urgency(kit_rate, overall_risk, shortages)

            # 2. 生成采购行动建议
            procurement_actions = await self._generate_procurement_actions(
                shortages, overall_risk, urgency, data_context
            )

            # 3. 生成替代方案
            alternatives = await self._generate_alternatives(
                shortages, data_context
            )

            # 4. 成本分析
            cost_analysis = await self._analyze_costs(
                procurement_actions, alternatives, shortages
            )

            # 5. 确定推荐行动
            recommended_action = self._get_recommended_action(
                procurement_actions, urgency
            )

            # 6. 生成决策摘要
            summary = await self._generate_decision_summary(
                urgency,
                procurement_actions,
                recommended_action,
                cost_analysis
            )

            self._log_execution(start_time)

            return {
                "urgency": urgency,
                "procurement_actions": [p.dict() for p in procurement_actions],
                "alternative_suggestions": alternatives,
                "recommended_action": recommended_action,
                "cost_analysis": cost_analysis,
                "summary": summary
            }

        except Exception as e:
            self.logger.error(f"决策任务失败: {e}")
            self._log_execution(start_time, success=False)

            return {
                "urgency": "unknown",
                "procurement_actions": [],
                "alternative_suggestions": [],
                "recommended_action": f"决策失败: {str(e)}",
                "cost_analysis": {},
                "summary": f"决策分析失败: {str(e)}",
                "error": str(e)
            }

    def _determine_urgency(self, kit_rate: float, overall_risk: str, shortages: List) -> str:
        """
        判断紧急程度

        Args:
            kit_rate: 齐套率
            overall_risk: 综合风险等级
            shortages: 缺料列表

        Returns:
            紧急程度: urgent / normal / low
        """
        if kit_rate < 0.6 or overall_risk == "high":
            return "urgent"
        elif kit_rate < 0.8 or overall_risk == "medium" or len(shortages) > 3:
            return "normal"
        else:
            return "low"

    async def _generate_procurement_actions(
            self,
            shortages: List[Dict],
            overall_risk: str,
            urgency: str,
            data_context: Dict
    ) -> List[ProcurementAction]:
        """
        生成采购行动建议

        Args:
            shortages: 缺料列表
            overall_risk: 综合风险等级
            urgency: 紧急程度
            data_context: 数据上下文

        Returns:
            采购行动列表
        """
        if not shortages:
            return []

        actions = []
        standardized_view = data_context.get("standardized_view", {})
        purchases = standardized_view.get("purchases", [])

        for shortage in shortages:
            material_code = shortage.get("material_code")
            material_name = shortage.get("material_name", material_code)
            shortage_qty = shortage.get("shortage_quantity", 0)
            required_qty = shortage.get("required_quantity", 0)
            expected_date = shortage.get("expected_arrival_date")
            supplier_name = shortage.get("supplier_name", "未知")

            # 计算优先级分数
            priority_score = self._calculate_priority_score(
                shortage, overall_risk, urgency
            )

            # 确定优先级
            if priority_score >= self.config["high_priority_score"]:
                priority = "高"
            elif priority_score >= self.config["medium_priority_score"]:
                priority = "中"
            else:
                priority = "低"

            # 判断是否有在途订单
            has_in_transit = any(
                p.get("material_code") == material_code
                for p in purchases
            )

            # 选择合适的行动类型
            if has_in_transit and expected_date:
                # 有在途订单，建议催货
                action_type = "expedite"
                action_desc = f"订单 {material_code} 预计 {expected_date} 到货，建议立即催货"
            elif urgency == "urgent" and priority == "高":
                # 紧急且高优先级，建议多渠道采购
                action_type = "alternative_supplier"
                action_desc = f"{material_name} 严重缺货，建议启动备选供应商"
            elif shortage_qty / required_qty > 0.8:
                # 缺货比例高，建议多种方案
                action_type = "air_freight"
                action_desc = f"{material_name} 缺货严重，建议改为空运"
            else:
                action_type = "expedite"
                action_desc = f"跟踪 {material_name} 采购进度，确保按时交付"

            template = self.action_templates.get(action_type, self.action_templates["expedite"])

            action = ProcurementAction(
                material_code=material_code,
                material_name=material_name,
                action=template["action"],
                priority=priority,
                reason=action_desc,
                estimated_cost_impact=self._estimate_cost_impact(action_type, shortage_qty),
                suggested_deadline=self._calculate_suggested_deadline(urgency, priority)
            )
            actions.append(action)

        # 按优先级排序
        priority_order = {"高": 0, "中": 1, "低": 2}
        actions.sort(key=lambda x: priority_order.get(x.priority, 3))

        self.logger.info(f"生成 {len(actions)} 条采购行动建议")
        return actions

    def _calculate_priority_score(
            self,
            shortage: Dict,
            overall_risk: str,
            urgency: str
    ) -> float:
        """计算优先级分数"""
        score = 0

        # 缺货比例加分
        shortage_qty = shortage.get("shortage_quantity", 0)
        required_qty = shortage.get("required_quantity", 1)
        shortage_ratio = shortage_qty / required_qty if required_qty > 0 else 1
        score += shortage_ratio * 30

        # 风险等级加分
        risk_level = shortage.get("status", "risk")
        if risk_level == "critical":
            score += 30
        elif risk_level == "risk":
            score += 15

        # 关键物料加分
        if shortage.get("is_key_material"):
            score += 20

        # 紧急程度加分
        if urgency == "urgent":
            score += 20
        elif urgency == "normal":
            score += 10

        # 综合风险加分
        if overall_risk == "high":
            score += 15
        elif overall_risk == "medium":
            score += 8

        return min(score, 100)

    def _estimate_cost_impact(self, action_type: str, quantity: float) -> float:
        """估算成本影响"""
        base_cost = quantity * 1000  # 假设单价1000元

        multipliers = {
            "expedite": 1.0,
            "alternative_supplier": 1.2,
            "substitute_material": 0.9,
            "stock_transfer": 0.5,
            "air_freight": self.config["cost_multiplier_air"]
        }

        multiplier = multipliers.get(action_type, 1.0)
        return round(base_cost * multiplier, 2)

    def _calculate_suggested_deadline(self, urgency: str, priority: str) -> Optional[str]:
        """计算建议截止日期"""
        today = datetime.now()

        if urgency == "urgent" and priority == "高":
            deadline = today + timedelta(days=1)
        elif urgency == "urgent" or priority == "高":
            deadline = today + timedelta(days=3)
        elif priority == "中":
            deadline = today + timedelta(days=7)
        else:
            return None

        return deadline.isoformat()

    async def _generate_alternatives(
            self,
            shortages: List[Dict],
            data_context: Dict
    ) -> List[str]:
        """
        生成替代方案建议

        Args:
            shortages: 缺料列表
            data_context: 数据上下文

        Returns:
            替代方案列表
        """
        alternatives = []

        if not shortages:
            return alternatives

        standardized_view = data_context.get("standardized_view", {})
        suppliers = standardized_view.get("suppliers", [])

        # 获取高风险供应商
        high_risk_suppliers = [
            s for s in suppliers
            if s.get("rating") in ["C", "D"] or s.get("on_time_delivery_rate", 1) < 0.7
        ]

        for shortage in shortages[:3]:  # 只处理前3个缺料
            material_name = shortage.get("material_name", "")
            supplier_name = shortage.get("supplier_name", "")

            # 如果有高风险供应商，建议备选
            if high_risk_suppliers:
                alt_suppliers = [s.get("supplier_name") for s in high_risk_suppliers[:2]]
                if alt_suppliers:
                    alternatives.append(
                        f"{material_name}: 考虑备选供应商 {'、'.join(alt_suppliers)}"
                    )

            # 通用建议
            alternatives.append(
                f"{material_name}: 建议建立安全库存，设置最小库存预警线"
            )

        # 去重
        alternatives = list(dict.fromkeys(alternatives))

        self.logger.info(f"生成 {len(alternatives)} 条替代方案")
        return alternatives[:5]

    async def _analyze_costs(
            self,
            actions: List[ProcurementAction],
            alternatives: List[str],
            shortages: List[Dict]
    ) -> Dict[str, Any]:
        """
        成本分析

        Args:
            actions: 采购行动列表
            alternatives: 替代方案列表
            shortages: 缺料列表

        Returns:
            成本分析结果
        """
        total_estimated_cost = sum(a.estimated_cost_impact or 0 for a in actions)

        # 估算紧急采购额外成本
        urgent_actions = [a for a in actions if a.priority == "高"]
        urgent_extra_cost = sum(
            a.estimated_cost_impact * (self.config["cost_multiplier_urgent"] - 1)
            for a in urgent_actions
        )

        # 估算停工损失（假设每天损失10000元）
        downtime_cost = len(shortages) * 10000

        cost_analysis = {
            "total_estimated_cost": round(total_estimated_cost, 2),
            "urgent_extra_cost": round(urgent_extra_cost, 2),
            "estimated_downtime_cost": downtime_cost,
            "total_risk_cost": round(total_estimated_cost + urgent_extra_cost + downtime_cost, 2),
            "recommendation": self._get_cost_recommendation(
                total_estimated_cost, urgent_extra_cost, downtime_cost
            )
        }

        return cost_analysis

    def _get_cost_recommendation(self, total_cost: float, urgent_cost: float, downtime_cost: float) -> str:
        """获取成本建议"""
        if urgent_cost > downtime_cost:
            return "紧急采购成本高于停工损失，建议评估是否可以接受延期"
        elif total_cost > 100000:
            return "总成本较高，建议优先处理高优先级缺料，其他可适当延期"
        else:
            return "建议按计划执行采购行动，确保生产顺利进行"

    def _get_recommended_action(
            self,
            actions: List[ProcurementAction],
            urgency: str
    ) -> str:
        """获取推荐行动"""
        if not actions:
            return "暂无缺料，无需采购行动"

        # 优先处理高优先级行动
        high_priority_actions = [a for a in actions if a.priority == "高"]

        if high_priority_actions:
            action = high_priority_actions[0]
            return f"立即处理 {action.material_name}: {action.action}"

        # 紧急情况处理中优先级
        if urgency == "urgent":
            medium_actions = [a for a in actions if a.priority == "中"]
            if medium_actions:
                action = medium_actions[0]
                return f"优先处理 {action.material_name}: {action.action}"

        # 常规建议
        if actions:
            action = actions[0]
            return f"按计划处理 {action.material_name}: {action.action}"

        return "所有物料供应正常，保持监控即可"

    async def _generate_decision_summary(
            self,
            urgency: str,
            actions: List[ProcurementAction],
            recommended_action: str,
            cost_analysis: Dict
    ) -> str:
        """生成决策摘要"""
        urgency_text = {
            "urgent": "🔴 紧急",
            "normal": "🟡 常规",
            "low": "🟢 低优先级"
        }.get(urgency, "⚪ 未知")

        summary_lines = [
            "【采购决策报告】",
            "",
            f"📋 紧急程度: {urgency_text}",
            "",
            "📦 采购行动建议:",
        ]

        for action in actions[:5]:
            summary_lines.append(
                f"  - [{action.priority}] {action.material_name}: {action.action}"
            )

        if not actions:
            summary_lines.append("  - 暂无缺料，无需采购行动")

        summary_lines.extend([
            "",
            f"💡 推荐行动: {recommended_action}",
            "",
            "💰 成本分析:",
            f"  - 预计总成本: ¥{cost_analysis.get('total_estimated_cost', 0):,.2f}",
            f"  - 紧急采购额外成本: ¥{cost_analysis.get('urgent_extra_cost', 0):,.2f}",
            f"  - 建议: {cost_analysis.get('recommendation', '按计划执行')}"
        ])

        return "\n".join(summary_lines)

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent": self.name,
            "healthy": True,
            "config": self.config,
            "action_templates": list(self.action_templates.keys())
        }