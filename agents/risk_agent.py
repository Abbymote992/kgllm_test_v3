"""
风控智能体 (Risk Agent)

核心职责：
1. 缺料风险评估 - 评估缺料事件的严重程度
2. 供应商风险评估 - 评估供应商的稳定性和可靠性
3. 进度风险评估 - 评估交期延误风险
4. 分级预警 - 生成分级预警信息并推送

这是系统的"监控专家"
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, retry_on_failure
from agents.context import AgentContext
from models.agent_models import AgentType, RiskLevel, RiskEvent


class RiskAgent(BaseAgent):
    """风控智能体"""

    def __init__(self, llm_service=None, kg_service=None):
        """
        初始化风控智能体

        Args:
            llm_service: LLM服务（用于生成风险报告）
            kg_service: 知识图谱服务（用于查询历史风险）
        """
        super().__init__(
            name="RiskAgent",
            agent_type=AgentType.RISK,
            llm_service=llm_service,
            kg_service=kg_service
        )

        # 风险阈值配置
        self.risk_thresholds = {
            "shortage_days": {
                "high": 7,  # 延期超过7天为高风险
                "medium": 3,  # 延期3-7天为中风险
                "low": 1  # 延期1-3天为低风险
            },
            "supplier_rating": {
                "high": "D",  # D级供应商高风险
                "medium": "C",  # C级供应商中风险
                "low": "B"  # B级供应商低风险
            },
            "delivery_rate": {
                "high": 0.7,  # 准时交付率<70%高风险
                "medium": 0.85,  # 准时交付率70-85%中风险
                "low": 0.95  # 准时交付率85-95%低风险
            }
        }

        # 预警接收人配置（模拟）
        self.alert_recipients = {
            "high": ["项目经理", "采购总监", "生产主管"],
            "medium": ["项目经理", "采购专员"],
            "low": ["采购专员"]
        }

    @retry_on_failure(max_retries=2, delay=1.0)
    # agents/risk_agent.py

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """执行风险评估"""

        # 从上下文获取数据
        data_context = context.data_context
        analysis_result = context.analysis_result

        shortages = []
        if analysis_result:
            shortages = analysis_result.get("shortages", [])
        total_materials = analysis_result.get("total_materials", 0) if analysis_result else 0

        # 评估风险
        risks = []
        risk_level = "低"

        if total_materials == 0 and not shortages:
            return {
                "risks": [],
                "overall_risk_level": "none",
                "risk_count": 0,
                "risk_summary": "数据不足，暂无法完成风险评估"
            }

        if shortages:
            high_risk_materials = [s for s in shortages if s.get("shortage", 0) > 100]
            if high_risk_materials:
                risk_level = "高"
                risks.append({
                    "type": "缺料风险",
                    "level": "高",
                    "description": f"{len(high_risk_materials)}种物料严重缺货",
                    "materials": high_risk_materials[:3]
                })
            elif len(shortages) > 0:
                risk_level = "中"
                risks.append({
                    "type": "缺料风险",
                    "level": "中",
                    "description": f"{len(shortages)}种物料库存不足",
                    "materials": shortages[:3]
                })

        # 检查供应商风险
        suppliers = data_context.get("suppliers", []) if data_context else []
        for supplier in suppliers:
            if supplier.get("risk_level") == "高":
                risks.append({
                    "type": "供应商风险",
                    "level": "高",
                    "description": f"供应商{supplier.get('supplier_name')}存在高风险",
                    "supplier": supplier.get("supplier_name")
                })

        return {
            "risks": risks,
            "overall_risk_level": risk_level,
            "risk_count": len(risks),
            "risk_summary": f"整体风险等级：{risk_level}，共发现{len(risks)}个风险点"
        }

    async def _assess_shortage_risk(
            self,
            shortages: List[Dict],
            standardized_view: Dict
    ) -> tuple:
        """
        评估缺料风险

        Args:
            shortages: 缺料列表
            standardized_view: 标准化数据视图

        Returns:
            (风险等级, 风险事件列表)
        """
        if not shortages:
            return RiskLevel.NONE, []

        risk_events = []
        risk_scores = []

        for shortage in shortages:
            # 获取物料信息
            material_code = shortage.get("material_code")
            material_name = shortage.get("material_name", material_code)
            shortage_qty = shortage.get("shortage_quantity", 0)
            required_qty = shortage.get("required_quantity", 1)
            expected_date = shortage.get("expected_arrival_date")

            # 计算缺料比例
            shortage_ratio = shortage_qty / required_qty if required_qty > 0 else 1

            # 计算延期天数
            delay_days = 0
            if expected_date:
                try:
                    if isinstance(expected_date, str):
                        expected_date = datetime.fromisoformat(expected_date)
                    today = datetime.now()
                    if expected_date < today:
                        delay_days = (today - expected_date).days
                except:
                    pass

            # 确定风险等级
            if shortage_ratio > 0.8 or delay_days >= self.risk_thresholds["shortage_days"]["high"]:
                level = RiskLevel.HIGH
            elif shortage_ratio > 0.5 or delay_days >= self.risk_thresholds["shortage_days"]["medium"]:
                level = RiskLevel.MEDIUM
            elif shortage_ratio > 0:
                level = RiskLevel.LOW
            else:
                level = RiskLevel.NONE

            if level != RiskLevel.NONE:
                risk_events.append(RiskEvent(
                    event_type="shortage",
                    level=level,
                    description=f"物料 {material_name} 缺货 {shortage_qty}/{required_qty}",
                    affected_materials=[material_code],
                    estimated_impact_days=delay_days,
                    suggestion=self._get_shortage_suggestion(level, material_name)
                ))
                risk_scores.append(self._risk_level_to_score(level))

        # 计算综合缺料风险
        if risk_scores:
            avg_score = sum(risk_scores) / len(risk_scores)
            overall_risk = self._score_to_risk_level(avg_score)
        else:
            overall_risk = RiskLevel.NONE

        return overall_risk, risk_events

    async def _assess_supplier_risk(
            self,
            shortages: List[Dict],
            standardized_view: Dict
    ) -> tuple:
        """
        评估供应商风险

        Args:
            shortages: 缺料列表
            standardized_view: 标准化数据视图

        Returns:
            (供应商风险映射, 风险事件列表)
        """
        suppliers = standardized_view.get("suppliers", [])
        purchases = standardized_view.get("purchases", [])

        if not suppliers:
            return {}, []

        supplier_risk_map = {}
        risk_events = []

        # 构建供应商采购统计
        supplier_purchases = {}
        for po in purchases:
            supplier_name = po.get("supplier_name")
            if supplier_name:
                if supplier_name not in supplier_purchases:
                    supplier_purchases[supplier_name] = {
                        "total_orders": 0,
                        "delayed_orders": 0,
                        "total_amount": 0
                    }
                supplier_purchases[supplier_name]["total_orders"] += 1
                supplier_purchases[supplier_name]["total_amount"] += po.get("quantity", 0) * po.get("unit_price", 0)
                if po.get("status") == "delayed":
                    supplier_purchases[supplier_name]["delayed_orders"] += 1

        for supplier in suppliers:
            supplier_name = supplier.get("supplier_name")
            rating = supplier.get("rating", "C")
            delivery_rate = supplier.get("on_time_delivery_rate", 0.8)
            aerospace_qualified = supplier.get("aerospace_qualified", False)

            # 确定风险等级
            if rating >= self.risk_thresholds["supplier_rating"]["high"]:
                level = RiskLevel.HIGH
            elif rating >= self.risk_thresholds["supplier_rating"]["medium"]:
                level = RiskLevel.MEDIUM
            elif rating >= self.risk_thresholds["supplier_rating"]["low"]:
                level = RiskLevel.LOW
            else:
                level = RiskLevel.NONE

            # 准时交付率调整
            if delivery_rate < self.risk_thresholds["delivery_rate"]["high"]:
                level = RiskLevel.HIGH
            elif delivery_rate < self.risk_thresholds["delivery_rate"]["medium"]:
                if level == RiskLevel.LOW:
                    level = RiskLevel.MEDIUM

            supplier_risk_map[supplier_name] = level.value

            # 生成风险事件
            if level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
                # 检查是否有缺料与该供应商相关
                related_shortages = [
                    s for s in shortages
                    if s.get("supplier_name") == supplier_name
                ]

                if related_shortages or level == RiskLevel.HIGH:
                    risk_events.append(RiskEvent(
                        event_type="supplier",
                        level=level,
                        description=f"供应商 {supplier_name} 风险评估为{level.value}级",
                        affected_materials=[s.get("material_code") for s in related_shortages],
                        estimated_impact_days=0,
                        suggestion=self._get_supplier_suggestion(level, supplier_name)
                    ))

        return supplier_risk_map, risk_events

    async def _assess_schedule_risk(
            self,
            shortages: List[Dict],
            standardized_view: Dict
    ) -> tuple:
        """
        评估进度风险

        Args:
            shortages: 缺料列表
            standardized_view: 标准化数据视图

        Returns:
            (风险等级, 风险事件列表)
        """
        schedule = standardized_view.get("schedule")

        if not schedule or not shortages:
            return RiskLevel.NONE, []

        work_orders = schedule.get("work_orders", [])

        if not work_orders:
            return RiskLevel.NONE, []

        risk_events = []
        max_delay = 0

        for wo in work_orders:
            planned_start = wo.get("planned_start")
            if planned_start:
                try:
                    if isinstance(planned_start, str):
                        planned_start = datetime.fromisoformat(planned_start)

                    today = datetime.now()
                    if planned_start < today:
                        delay = (today - planned_start).days
                        max_delay = max(max_delay, delay)

                        if delay > 0:
                            risk_events.append(RiskEvent(
                                event_type="schedule",
                                level=RiskLevel.HIGH if delay > 7 else RiskLevel.MEDIUM,
                                description=f"工单 {wo.get('wo_id')} 已延期 {delay} 天",
                                affected_materials=[s.get("material_code") for s in shortages],
                                estimated_impact_days=delay,
                                suggestion="建议调整生产计划，优先处理缺货物料"
                            ))
                except:
                    pass

        # 确定进度风险等级
        if max_delay >= self.risk_thresholds["shortage_days"]["high"]:
            overall_risk = RiskLevel.HIGH
        elif max_delay >= self.risk_thresholds["shortage_days"]["medium"]:
            overall_risk = RiskLevel.MEDIUM
        elif max_delay > 0:
            overall_risk = RiskLevel.LOW
        else:
            overall_risk = RiskLevel.NONE

        return overall_risk, risk_events


    def _risk_level_to_score(self, level: RiskLevel) -> int:
        """风险等级转分数"""
        scores = {
            RiskLevel.HIGH: 100,
            RiskLevel.MEDIUM: 70,  # 修改：从60改为70
            RiskLevel.LOW: 40,  # 修改：从30改为40
            RiskLevel.NONE: 0
        }
        return scores.get(level, 0)

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """分数转风险等级"""
        if score >= 70:  # 修改：从80改为70
            return RiskLevel.HIGH
        elif score >= 50:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.NONE

    def _calculate_overall_risk(
            self,
            shortage_risk: RiskLevel,
            supplier_risk: Dict,
            schedule_risk: RiskLevel
    ) -> RiskLevel:
        """计算综合风险等级"""
        risk_scores = []

        risk_scores.append(self._risk_level_to_score(shortage_risk))
        risk_scores.append(self._risk_level_to_score(schedule_risk))

        # 供应商风险取最高分
        supplier_scores = []
        for v in supplier_risk.values():
            if v in ["high", "medium", "low", "none"]:
                try:
                    supplier_scores.append(self._risk_level_to_score(RiskLevel(v)))
                except ValueError:
                    pass

        if supplier_scores:
            risk_scores.append(max(supplier_scores))

        if not risk_scores:
            return RiskLevel.NONE

        avg_score = sum(risk_scores) / len(risk_scores)

        # 调试日志
        self.logger.debug(f"风险分数: {risk_scores}, 平均值: {avg_score:.1f}")

        result = self._score_to_risk_level(avg_score)
        self.logger.debug(f"综合风险等级: {result.value}")

        return result

    def _get_shortage_suggestion(self, level: RiskLevel, material_name: str) -> str:
        """获取缺料建议"""
        suggestions = {
            RiskLevel.HIGH: f"立即处理 {material_name} 缺料问题，联系供应商确认紧急交货",
            RiskLevel.MEDIUM: f"密切关注 {material_name} 供应情况，准备备选方案",
            RiskLevel.LOW: f"跟踪 {material_name} 到货进度，确保按时交付",
            RiskLevel.NONE: ""
        }
        return suggestions.get(level, "")

    def _get_supplier_suggestion(self, level: RiskLevel, supplier_name: str) -> str:
        """获取供应商建议"""
        suggestions = {
            RiskLevel.HIGH: f"启动供应商替换流程，降低对 {supplier_name} 的依赖",
            RiskLevel.MEDIUM: f"加强与 {supplier_name} 的沟通，定期跟踪订单状态",
            RiskLevel.LOW: f"持续监控 {supplier_name} 交付表现",
            RiskLevel.NONE: ""
        }
        return suggestions.get(level, "")

    def _generate_alerts(
            self,
            overall_risk: RiskLevel,
            risk_events: List[RiskEvent],
            standardized_view: Dict
    ) -> List[Dict]:
        """生成预警信息"""
        alerts = []

        if overall_risk == RiskLevel.NONE:
            return alerts

        # 生成综合预警
        recipients = self.alert_recipients.get(overall_risk.value, [])

        alert = {
            "level": overall_risk.value,
            "title": f"供应链风险预警 - {overall_risk.value.upper()}级",
            "message": self._get_alert_message(overall_risk, risk_events),
            "recipients": recipients,
            "timestamp": datetime.now().isoformat(),
            "risk_events_count": len(risk_events)
        }
        alerts.append(alert)

        # 为高风险事件生成单独预警
        for event in risk_events:
            if event.level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
                event_recipients = self.alert_recipients.get(event.level.value, [])
                alerts.append({
                    "level": event.level.value,
                    "title": f"{event.event_type} 风险预警",
                    "message": event.description,
                    "recipients": event_recipients,
                    "timestamp": datetime.now().isoformat(),
                    "suggestion": event.suggestion
                })

        self.logger.info(f"生成 {len(alerts)} 条预警信息")
        return alerts

    def _get_alert_message(self, overall_risk: RiskLevel, risk_events: List[RiskEvent]) -> str:
        """获取预警消息"""
        if overall_risk == RiskLevel.HIGH:
            return "⚠️ 供应链存在高风险，建议立即采取行动！"
        elif overall_risk == RiskLevel.MEDIUM:
            return "⚡ 供应链存在中等风险，请关注并准备应对措施。"
        else:
            return "ℹ️ 供应链存在低风险，建议持续监控。"

    async def _generate_risk_summary(
            self,
            overall_risk: RiskLevel,
            shortage_risk: RiskLevel,
            supplier_risk: Dict,
            schedule_risk: RiskLevel,
            alerts: List[Dict]
    ) -> str:
        """生成风险摘要"""
        summary_lines = [
            "【风险评估报告】",
            "",
            f"📊 综合风险等级: {overall_risk.value.upper()}",
            "",
            "分项风险:",
            f"  - 缺料风险: {shortage_risk.value}",
            f"  - 进度风险: {schedule_risk.value}",
        ]

        if supplier_risk:
            high_risk_suppliers = [name for name, level in supplier_risk.items() if level == "high"]
            if high_risk_suppliers:
                summary_lines.append(f"  - 供应商风险: 高风险供应商 {len(high_risk_suppliers)} 家")
                summary_lines.append(f"    • {', '.join(high_risk_suppliers[:3])}")

        if alerts:
            high_alerts = [a for a in alerts if a.get("level") == "high"]
            medium_alerts = [a for a in alerts if a.get("level") == "medium"]
            summary_lines.extend([
                "",
                f"🚨 预警信息:",
                f"  - 高风险预警: {len(high_alerts)} 条",
                f"  - 中风险预警: {len(medium_alerts)} 条",
            ])

            if high_alerts:
                summary_lines.append(f"  - 建议: {high_alerts[0].get('message', '立即处理')}")

        return "\n".join(summary_lines)

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent": self.name,
            "healthy": True,
            "risk_thresholds": self.risk_thresholds,
            "alert_levels": list(self.alert_recipients.keys())
        }
