"""
分析智能体 (Analysis Agent)

核心职责：
1. 齐套率计算 - 动态计算物料齐备率
2. 缺料识别 - 识别缺失物料及数量
3. 瓶颈分析 - 找出影响齐套的关键物料
4. 健康度评估 - 综合评估供应链健康状态
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, retry_on_failure
from agents.context import AgentContext
from models.agent_models import AgentType, ShortageItem, ShortageStatus


class AnalysisAgent(BaseAgent):
    """分析智能体"""

    def __init__(self, llm_service=None, kg_service=None):
        super().__init__(
            name="AnalysisAgent",
            agent_type=AgentType.ANALYSIS,
            llm_service=llm_service,
            kg_service=kg_service
        )

        self.kit_rate_threshold = 0.8
        self.critical_shortage_days = 7

    @retry_on_failure(max_retries=2, delay=1.0)
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        import time
        start_time = time.time()

        self.logger.info(f"开始分析: {context.question[:50]}...")

        try:
            data_context = context.data_context

            if not data_context:
                self.logger.warning("数据上下文为空，使用空数据")
                data_context = {}

            standardized_view = data_context.get("standardized_view", {})

            # 1. 计算齐套率
            kit_rate_result = await self._calculate_kit_rate(standardized_view)

            # 2. 识别缺料项
            shortages = await self._identify_shortages(standardized_view)

            # 3. 分析瓶颈物料
            bottleneck_materials = await self._analyze_bottlenecks(
                shortages, standardized_view
            )

            # 4. 计算健康度评分
            health_score = self._calculate_health_score(
                kit_rate_result["kit_rate"],
                shortages,
                standardized_view
            )

            # 5. 生成分析摘要
            summary = await self._generate_summary(
                kit_rate_result,
                shortages,
                bottleneck_materials,
                health_score
            )

            self._log_execution(start_time)

            return {
                "kit_rate": kit_rate_result["kit_rate"],
                "total_materials": kit_rate_result["total_materials"],
                "kitted_count": kit_rate_result["kitted_count"],
                "shortages": [s.dict() for s in shortages],
                "bottleneck_materials": bottleneck_materials,
                "health_score": health_score,
                "summary": summary
            }

        except Exception as e:
            self.logger.error(f"分析任务失败: {e}")
            self._log_execution(start_time, success=False)

            return {
                "kit_rate": 0.0,
                "total_materials": 0,
                "kitted_count": 0,
                "shortages": [],
                "bottleneck_materials": [],
                "health_score": 0,
                "summary": f"分析失败: {str(e)}",
                "error": str(e)
            }

    async def _calculate_kit_rate(self, standardized_view: Dict) -> Dict[str, Any]:
        """计算齐套率"""
        materials = standardized_view.get("materials", [])
        inventory = standardized_view.get("inventory", [])
        purchases = standardized_view.get("purchases", [])

        # 修复：没有物料时返回0而不是1
        if not materials:
            return {
                "kit_rate": 0.0,
                "total_materials": 0,
                "kitted_count": 0
            }

        # 构建库存映射
        inventory_map = {}
        for inv in inventory:
            code = inv.get("material_code")
            if code:
                inventory_map[code] = inventory_map.get(code, 0) + inv.get("available_quantity", 0)

        # 构建采购映射
        purchase_map = {}
        for po in purchases:
            code = po.get("material_code")
            if code and po.get("status") in ["ordered", "shipped"]:
                purchase_map[code] = purchase_map.get(code, 0) + po.get("quantity", 0)

        kitted_count = 0
        material_details = []

        for material in materials:
            material_code = material.get("material_code")
            required_qty = material.get("required_quantity", 0)
            available_qty = inventory_map.get(material_code, 0)
            in_transit_qty = purchase_map.get(material_code, 0)

            total_available = available_qty + in_transit_qty
            is_kitted = total_available >= required_qty

            if is_kitted:
                kitted_count += 1

            material_details.append({
                "material_code": material_code,
                "material_name": material.get("material_name"),
                "required_qty": required_qty,
                "available_qty": available_qty,
                "in_transit_qty": in_transit_qty,
                "total_available": total_available,
                "is_kitted": is_kitted
            })

        total_materials = len(materials)
        kit_rate = kitted_count / total_materials if total_materials > 0 else 0.0

        self.logger.info(f"齐套率计算完成: {kit_rate:.1%} ({kitted_count}/{total_materials})")

        return {
            "kit_rate": kit_rate,
            "total_materials": total_materials,
            "kitted_count": kitted_count,
            "material_details": material_details
        }

    async def _identify_shortages(self, standardized_view: Dict) -> List[ShortageItem]:
        """识别缺料项"""
        materials = standardized_view.get("materials", [])
        inventory = standardized_view.get("inventory", [])
        purchases = standardized_view.get("purchases", [])
        suppliers = standardized_view.get("suppliers", [])

        if not materials:
            return []

        supplier_map = {s.get("supplier_id"): s for s in suppliers}

        inventory_map = {}
        for inv in inventory:
            code = inv.get("material_code")
            if code:
                inventory_map[code] = inventory_map.get(code, 0) + inv.get("available_quantity", 0)

        purchase_map = {}
        po_details = {}
        for po in purchases:
            code = po.get("material_code")
            if code:
                qty = po.get("quantity", 0)
                purchase_map[code] = purchase_map.get(code, 0) + qty
                if code not in po_details:
                    po_details[code] = []
                po_details[code].append({
                    "po_id": po.get("po_id"),
                    "quantity": qty,
                    "promised_date": po.get("promised_date"),
                    "supplier_name": po.get("supplier_name")
                })

        shortages = []

        for material in materials:
            material_code = material.get("material_code")
            material_name = material.get("material_name", material_code)
            required_qty = material.get("required_quantity", 0)
            available_qty = inventory_map.get(material_code, 0)
            in_transit_qty = purchase_map.get(material_code, 0)

            total_available = available_qty + in_transit_qty

            if total_available < required_qty:
                shortage_qty = required_qty - total_available

                if shortage_qty == required_qty:
                    status = ShortageStatus.CRITICAL
                elif shortage_qty > required_qty * 0.5:
                    status = ShortageStatus.CRITICAL
                elif shortage_qty > 0:
                    status = ShortageStatus.RISK
                else:
                    status = ShortageStatus.PENDING

                supplier_name = "未知"
                expected_date = None

                if material_code in po_details:
                    for po in po_details[material_code]:
                        if po.get("supplier_name"):
                            supplier_name = po.get("supplier_name")
                        if po.get("promised_date"):
                            expected_date = po.get("promised_date")

                shortage_item = ShortageItem(
                    material_code=material_code,
                    material_name=material_name,
                    required_quantity=required_qty,
                    available_quantity=available_qty,
                    shortage_quantity=shortage_qty,
                    expected_arrival_date=expected_date,
                    supplier_name=supplier_name,
                    status=status,
                    reason=self._determine_shortage_reason(
                        material, available_qty, in_transit_qty, required_qty
                    )
                )
                shortages.append(shortage_item)

        self.logger.info(f"识别到 {len(shortages)} 种缺货物料")
        return shortages

    def _determine_shortage_reason(
        self,
        material: Dict,
        available_qty: float,
        in_transit_qty: float,
        required_qty: float
    ) -> str:
        if available_qty == 0 and in_transit_qty == 0:
            return "无库存且无在途采购"
        elif available_qty == 0 and in_transit_qty > 0:
            return "无库存，在途物料尚未到达"
        elif available_qty > 0 and available_qty < required_qty:
            return f"库存不足，仅剩 {available_qty} 件"
        elif in_transit_qty > 0 and available_qty + in_transit_qty < required_qty:
            return f"在途物料 {in_transit_qty} 件仍不足以满足需求"
        else:
            return "需求超过供应能力"

    async def _analyze_bottlenecks(
        self,
        shortages: List[ShortageItem],
        standardized_view: Dict
    ) -> List[Dict]:
        if not shortages:
            return []

        materials = {m.get("material_code"): m for m in standardized_view.get("materials", [])}

        bottleneck_scores = []

        for shortage in shortages:
            score = 0
            material_info = materials.get(shortage.material_code, {})

            if material_info.get("is_key_material"):
                score += 30

            if material_info.get("grade") == "aerospace":
                score += 20

            shortage_ratio = shortage.shortage_quantity / shortage.required_quantity if shortage.required_quantity > 0 else 0
            if shortage_ratio > 0.8:
                score += 25
            elif shortage_ratio > 0.5:
                score += 15

            if shortage.status == ShortageStatus.CRITICAL:
                score += 25
            elif shortage.status == ShortageStatus.RISK:
                score += 10

            bottleneck_scores.append({
                "material_code": shortage.material_code,
                "material_name": shortage.material_name,
                "shortage_quantity": shortage.shortage_quantity,
                "required_quantity": shortage.required_quantity,
                "status": shortage.status.value,
                "bottleneck_score": score,
                "is_key_material": material_info.get("is_key_material", False),
                "grade": material_info.get("grade", "industrial")
            })

        bottleneck_scores.sort(key=lambda x: x["bottleneck_score"], reverse=True)
        self.logger.info(f"识别到 {len(bottleneck_scores)} 个瓶颈物料")
        return bottleneck_scores

    def _calculate_health_score(
        self,
        kit_rate: float,
        shortages: List[ShortageItem],
        standardized_view: Dict
    ) -> float:
        # 基础分：齐套率贡献（最高50分）
        kit_score = kit_rate * 50

        # 缺料扣分（最高30分）
        shortage_penalty = 0
        for shortage in shortages:
            if shortage.status == ShortageStatus.CRITICAL:
                shortage_penalty += 10
            elif shortage.status == ShortageStatus.RISK:
                shortage_penalty += 5

        shortage_penalty = min(shortage_penalty, 30)

        # 关键物料齐套率（最高20分）
        materials = standardized_view.get("materials", [])
        key_materials = [m for m in materials if m.get("is_key_material")]

        key_kit_score = 0
        if key_materials:
            key_kitted = 0
            for km in key_materials:
                km_code = km.get("material_code")
                is_shortage = any(s.material_code == km_code for s in shortages)
                if not is_shortage:
                    key_kitted += 1
            key_kit_score = (key_kitted / len(key_materials)) * 20

        health_score = kit_score - shortage_penalty + key_kit_score
        health_score = max(0, min(100, health_score))

        self.logger.info(f"健康度评分: {health_score:.1f}")
        return round(health_score, 1)

    async def _generate_summary(
        self,
        kit_rate_result: Dict,
        shortages: List[ShortageItem],
        bottleneck_materials: List[Dict],
        health_score: float
    ) -> str:
        kit_rate = kit_rate_result["kit_rate"]
        total = kit_rate_result["total_materials"]
        kitted = kit_rate_result["kitted_count"]

        if total == 0:
            return "【齐套分析报告】\n\n无物料数据，无法进行分析。"

        if kit_rate >= self.kit_rate_threshold:
            status = "良好"
            status_emoji = "✅"
        elif kit_rate >= 0.6:
            status = "注意"
            status_emoji = "⚠️"
        else:
            status = "紧急"
            status_emoji = "🔴"

        summary_lines = [
            f"【齐套分析报告】",
            f"",
            f"{status_emoji} 整体状态: {status}",
            f"📊 齐套率: {kit_rate:.1%} ({kitted}/{total})",
            f"💚 健康度评分: {health_score:.1f}/100",
        ]

        if shortages:
            critical_count = sum(1 for s in shortages if s.status == ShortageStatus.CRITICAL)
            risk_count = sum(1 for s in shortages if s.status == ShortageStatus.RISK)

            summary_lines.extend([
                f"",
                f"📦 缺料情况:",
                f"   - 严重缺料: {critical_count} 种",
                f"   - 存在风险: {risk_count} 种",
            ])

            top_shortages = shortages[:3]
            if top_shortages:
                summary_lines.append(f"   - 主要缺料:")
                for s in top_shortages:
                    summary_lines.append(
                        f"     • {s.material_name}: 缺 {s.shortage_quantity}/{s.required_quantity}"
                    )

        if bottleneck_materials:
            top_bottlenecks = bottleneck_materials[:3]
            summary_lines.extend([
                f"",
                f"🎯 瓶颈物料 (TOP3):",
            ])
            for b in top_bottlenecks:
                summary_lines.append(
                    f"     • {b['material_name']} (分数: {b['bottleneck_score']})"
                )

        if kit_rate < self.kit_rate_threshold and total > 0:
            summary_lines.extend([
                f"",
                f"💡 建议: 齐套率低于{self.kit_rate_threshold:.0%}，建议优先处理严重缺货物料"
            ])

        return "\n".join(summary_lines)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "healthy": True,
            "kit_rate_threshold": self.kit_rate_threshold,
            "critical_shortage_days": self.critical_shortage_days
        }