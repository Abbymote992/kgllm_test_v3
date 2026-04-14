"""
数据知识智能体 (Data Knowledge Agent)

核心职责：
1. 数据汇聚 - 从4个平台（BOM、排程、SRM、WMS）获取数据
2. 知识检索 - RAG向量库检索（SOP、业务规则、历史案例）
3. 图谱查询 - Neo4j知识图谱查询
4. 数据标准化 - 统一格式输出给下游智能体
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, retry_on_failure
from agents.context import AgentContext
from models.agent_models import AgentType


class DataKnowledgeAgent(BaseAgent):
    """数据知识智能体"""

    def __init__(self, llm_service=None, kg_service=None):
        """
        初始化数据知识智能体

        Args:
            llm_service: LLM服务
            kg_service: 知识图谱服务（Neo4j）
        """
        super().__init__(
            name="DataKnowledgeAgent",
            agent_type=AgentType.DATA_KNOWLEDGE,
            llm_service=llm_service,
            kg_service=kg_service
        )

        # 添加属性别名，保持代码可读性
        self.kg_service = self.kg  # kg_service 是 kg 的别名
        self.llm_service = self.llm

        # 平台适配器
        self._adapters = {}

        # RAG服务（可选）
        self.rag_service = None

        # 数据缓存
        self._cache = {}
        self._cache_ttl = 300

    def register_adapter(self, platform_type, adapter):
        """注册平台适配器"""
        self._adapters[platform_type] = adapter
        self.logger.info(f"已注册适配器: {platform_type.value}")

    def set_rag_service(self, rag_service):
        """设置RAG服务"""
        self.rag_service = rag_service
        self.logger.info("RAG服务已注册")

    @retry_on_failure(max_retries=3, delay=1.0)
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """执行数据知识任务"""
        import time
        start_time = time.time()

        self.logger.info(f"开始数据汇聚: {context.question[:50]}...")

        try:
            # 并行执行三个任务
            tasks = [
                self._collect_platform_data(context),
                self._retrieve_knowledge(context),
                self._query_graph(context)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            platform_data = results[0] if not isinstance(results[0], Exception) else {}
            knowledge_context = results[1] if not isinstance(results[1], Exception) else []
            graph_data = results[2] if not isinstance(results[2], Exception) else {}

            if isinstance(results[0], Exception):
                self.logger.error(f"平台数据采集失败: {results[0]}")
            if isinstance(results[1], Exception):
                self.logger.error(f"知识检索失败: {results[1]}")
            if isinstance(results[2], Exception):
                self.logger.error(f"图谱查询失败: {results[2]}")

            # 数据标准化
            standardized_view = self._standardize_data(platform_data)

            # 获取业务规则
            business_rules = self._get_business_rules(context)

            # 数据质量报告
            data_quality = self._assess_data_quality(platform_data)

            self._log_execution(start_time)

            return {
                "graph_data": graph_data,
                "knowledge_context": knowledge_context,
                "business_rules": business_rules,
                "data_quality": data_quality,
                "standardized_view": standardized_view
            }

        except Exception as e:
            self.logger.error(f"数据知识任务失败: {e}")
            self._log_execution(start_time, success=False)

            return {
                "graph_data": {},
                "knowledge_context": [],
                "business_rules": {},
                "data_quality": {"error": str(e)},
                "standardized_view": {}
            }

    async def _collect_platform_data(self, context: AgentContext) -> Dict[str, Any]:
        """从4个平台采集数据"""
        from models.platform_models import PlatformType

        params = context.extracted_params
        project_id = params.get("project_id")
        module_id = params.get("module_id")
        material_code = params.get("material_code")

        result = {}

        # 并行采集各平台数据
        tasks = {}

        # 1. BOM数据（平台1）
        if PlatformType.PLATFORM1_BOM in self._adapters:
            tasks["bom"] = self._adapters[PlatformType.PLATFORM1_BOM].fetch_bom({
                "project_id": project_id,
                "module_id": module_id
            })

        # 2. 排程数据（平台2）
        if PlatformType.PLATFORM2_SCHEDULE in self._adapters:
            tasks["schedule"] = self._adapters[PlatformType.PLATFORM2_SCHEDULE].fetch_schedule({
                "project_id": project_id
            })

        # 3. 采购订单（SRM）
        if PlatformType.SRM in self._adapters:
            query = {}
            if material_code:
                query["material_code"] = material_code
            tasks["purchase_orders"] = self._adapters[PlatformType.SRM].fetch_purchase_orders(query)
            tasks["suppliers"] = self._adapters[PlatformType.SRM].fetch_suppliers({})

        # 4. 库存数据（WMS）
        if PlatformType.WMS in self._adapters:
            query = {}
            if material_code:
                query["material_code"] = material_code
            tasks["inventory"] = self._adapters[PlatformType.WMS].fetch_inventory(query)

        # 执行所有任务
        for key, task in tasks.items():
            try:
                result[key] = await task
                self.logger.debug(f"采集到 {key} 数据")
            except Exception as e:
                self.logger.warning(f"采集 {key} 数据失败: {e}")
                result[key] = None

        return result

    async def _retrieve_knowledge(self, context: AgentContext) -> List[Dict]:
        """检索RAG知识库"""
        if not self.rag_service:
            return []

        try:
            query = context.question
            if context.intent:
                query = f"[{context.intent.value}] {context.question}"

            results = await self.rag_service.retrieve(query, top_k=5)
            return results
        except Exception as e:
            self.logger.warning(f"RAG检索失败: {e}")
            return []

    async def _query_graph(self, context: AgentContext) -> Dict[str, Any]:
        """查询知识图谱"""
        if not self.kg_service:
            return {"nodes": [], "relationships": []}

        try:
            params = context.extracted_params
            project_id = params.get("project_id")
            material_code = params.get("material_code")

            if project_id:
                query = """
                MATCH (p:Project {project_id: $project_id})
                OPTIONAL MATCH (p)-[:HAS_WO]->(wo:WorkOrder)
                OPTIONAL MATCH (wo)-[:REQUIRES]->(m:Material)
                OPTIONAL MATCH (m)-[:SUPPLIES]-(s:Supplier)
                RETURN p, wo, m, s
                LIMIT 100
                """
                result = await self.kg_service.query(query, {"project_id": project_id})
                return result
            elif material_code:
                query = """
                MATCH (m:Material {material_code: $material_code})
                OPTIONAL MATCH (m)-[:SUPPLIES]-(s:Supplier)
                OPTIONAL MATCH (wo:WorkOrder)-[:REQUIRES]->(m)
                RETURN m, s, wo
                LIMIT 50
                """
                result = await self.kg_service.query(query, {"material_code": material_code})
                return result

            return {"nodes": [], "relationships": []}
        except Exception as e:
            self.logger.warning(f"图谱查询失败: {e}")
            return {"nodes": [], "relationships": [], "error": str(e)}

    def _standardize_data(self, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化数据"""
        standardized = {
            "materials": [],
            "inventory": [],
            "purchases": [],
            "suppliers": [],
            "schedule": None
        }

        # 处理BOM数据
        bom = platform_data.get("bom")
        if bom:
            try:
                from models.platform_models import BOMStructure
                if isinstance(bom, BOMStructure):
                    for item in bom.items:
                        standardized["materials"].append({
                            "material_code": item.material_code,
                            "material_name": item.material_name,
                            "required_quantity": item.quantity,
                            "unit": item.unit,
                            "grade": item.grade,
                            "is_key_material": item.is_key_material,
                            "lead_time": item.lead_time,
                            "source": "bom"
                        })
            except ImportError:
                # 如果无法导入，尝试字典方式
                if isinstance(bom, dict) and "items" in bom:
                    for item in bom.get("items", []):
                        standardized["materials"].append(item)

        # 处理库存数据
        inventory_list = platform_data.get("inventory", [])
        if inventory_list:
            for inv in inventory_list:
                if hasattr(inv, 'material_code'):
                    standardized["inventory"].append({
                        "material_code": inv.material_code,
                        "material_name": inv.material_name,
                        "available_quantity": inv.available_quantity,
                        "reserved_quantity": inv.reserved_quantity,
                        "warehouse_location": inv.warehouse_location,
                        "source": "wms"
                    })
                elif isinstance(inv, dict):
                    standardized["inventory"].append(inv)

        # 处理采购订单
        po_list = platform_data.get("purchase_orders", [])
        if po_list:
            for po in po_list:
                if hasattr(po, 'items'):
                    for item in po.items:
                        standardized["purchases"].append({
                            "po_id": po.po_id,
                            "material_code": item.material_code,
                            "material_name": item.material_name,
                            "quantity": item.quantity,
                            "promised_date": item.promised_date.isoformat() if item.promised_date else None,
                            "status": po.status,
                            "supplier_name": po.supplier_name,
                            "source": "srm"
                        })

        # 处理供应商数据
        supplier_list = platform_data.get("suppliers", [])
        if supplier_list:
            for sup in supplier_list:
                if hasattr(sup, 'supplier_id'):
                    standardized["suppliers"].append({
                        "supplier_id": sup.supplier_id,
                        "supplier_name": sup.supplier_name,
                        "rating": sup.rating,
                        "aerospace_qualified": sup.aerospace_qualified,
                        "on_time_delivery_rate": sup.on_time_delivery_rate,
                        "source": "srm"
                    })

        # 处理排程数据
        schedule = platform_data.get("schedule")
        if schedule:
            if hasattr(schedule, 'project_id'):
                standardized["schedule"] = {
                    "project_id": schedule.project_id,
                    "project_name": schedule.project_name,
                    "work_orders": [
                        {
                            "wo_id": wo.wo_id,
                            "planned_start": wo.planned_start.isoformat() if wo.planned_start else None,
                            "planned_end": wo.planned_end.isoformat() if wo.planned_end else None,
                            "priority": wo.priority
                        }
                        for wo in schedule.work_orders
                    ] if hasattr(schedule, 'work_orders') else []
                }

        return standardized

    def _get_business_rules(self, context: AgentContext) -> Dict[str, Any]:
        """获取业务规则"""
        rules = {
            "kit_rate_formula": "kit_rate = kitted_materials / total_materials",
            "risk_levels": {
                "high": "缺货或延期超过7天",
                "medium": "延期3-7天或库存不足",
                "low": "延期小于3天"
            },
            "priority_mapping": {
                "high": "关键物料或宇航级物料",
                "medium": "重要物料",
                "low": "一般物料"
            }
        }

        if context.intent:
            if context.intent.value == "analysis":
                rules["analysis_threshold"] = 0.8
            elif context.intent.value == "risk":
                rules["risk_alert_days"] = 7

        return rules

    def _assess_data_quality(self, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """评估数据质量"""
        quality = {
            "overall_score": 100,
            "issues": [],
            "missing_data": []
        }

        if not platform_data.get("bom"):
            quality["missing_data"].append("BOM数据")
            quality["overall_score"] -= 20

        if not platform_data.get("inventory"):
            quality["missing_data"].append("库存数据")
            quality["overall_score"] -= 15

        if not platform_data.get("purchase_orders"):
            quality["missing_data"].append("采购订单数据")
            quality["overall_score"] -= 15

        if not platform_data.get("suppliers"):
            quality["missing_data"].append("供应商数据")
            quality["overall_score"] -= 10

        if not platform_data.get("schedule"):
            quality["missing_data"].append("排程数据")
            quality["overall_score"] -= 20

        quality["overall_score"] = max(0, quality["overall_score"])

        if quality["overall_score"] < 60:
            quality["issues"].append("数据完整度不足，可能影响分析准确性")

        return quality

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        adapters_status = {
            pt.value: adapter is not None
            for pt, adapter in self._adapters.items()
        }

        return {
            "agent": self.name,
            "healthy": True,
            "adapters": adapters_status,
            "adapter_count": len(self._adapters),
            "rag_enabled": self.rag_service is not None,
            "kg_enabled": self.kg_service is not None  # 使用 kg_service
        }