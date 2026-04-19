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
import re
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
        print("[DataKnowledgeAgent] 被调用", flush=True)
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

            # data_knowledge_agent.py 的 execute 方法末尾，return 之前添加
            self.logger.info(f"=== DataKnowledgeAgent 返回数据 ===")
            self.logger.info(f"graph_data nodes数量: {len(graph_data.get('nodes', []))}")
            self.logger.info(f"standardized_view materials数量: {len(standardized_view.get('materials', []))}")
            self.logger.info(f"standardized_view inventory数量: {len(standardized_view.get('inventory', []))}")
            import json
            with open("c:/temp/kg_debug.json", "w", encoding="utf-8") as f:
                json.dump({
                    "graph_data": graph_data,
                    "standardized_view": standardized_view
                }, f, ensure_ascii=False, indent=2)
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

            # data_knowledge_agent.py 的 execute 方法末尾，return 之前添加
            self.logger.info(f"=== DataKnowledgeAgent 返回数据 ===")
            self.logger.info(f"graph_data nodes数量: {len(graph_data.get('nodes', []))}")
            self.logger.info(f"standardized_view materials数量: {len(standardized_view.get('materials', []))}")
            self.logger.info(f"standardized_view inventory数量: {len(standardized_view.get('inventory', []))}")
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

    # ============================================
    # 图谱查询 - 动态Cypher生成
    # ============================================

    async def _query_graph(self, context: AgentContext) -> Dict[str, Any]:
        """查询知识图谱 - 使用 LLM 动态生成 Cypher"""
        if not self.kg_service:
            self.logger.warning("kg_service 未初始化")
            return {"nodes": [], "relationships": [], "materials": [], "inventory": []}

        try:
            # 1. 获取 schema
            schema = await self._get_graph_schema()

            # 2. 使用 LLM 生成 Cypher
            cypher = await self._generate_cypher_from_question(context.question, schema)

            if not cypher:
                self.logger.warning("无法生成 Cypher，使用降级查询")
                return await self._fallback_query(context.question)

            self.logger.info(f"生成的 Cypher: {cypher}")

            # 3. 执行查询
            result = await self.kg_service.query(cypher)

            if not result.get("success") or not result.get("data"):
                self.logger.warning("查询无结果，尝试简化查询")
                simplified = await self._simplify_cypher_query(cypher, context.question)
                if simplified and simplified != cypher:
                    result = await self.kg_service.query(simplified)
                    cypher = simplified

            # 4. 转换为标准化格式
            materials, inventory = self._extract_materials_and_inventory(result.get("data", []))

            return {
                "nodes": result.get("data", []),
                "relationships": [],
                "materials": materials,
                "inventory": inventory,
                "cypher": cypher,
                "query_type": "dynamic"
            }

        except Exception as e:
            self.logger.error(f"图谱查询失败: {e}")
            import traceback
            traceback.print_exc()
            return {"nodes": [], "relationships": [], "materials": [], "inventory": []}

    def _extract_materials_and_inventory(self, data: List[Dict]) -> tuple:
        """从查询结果中提取物料和库存数据"""
        materials = []
        inventory = []
        seen_materials = set()

        for record in data:
            # 提取物料信息
            material_code = record.get("material_code") or record.get("m.material_code")
            material_name = record.get("material_name") or record.get("m.name") or record.get("name")

            if material_code and material_code not in seen_materials:
                seen_materials.add(material_code)
                materials.append({
                    "material_code": material_code,
                    "material_name": material_name,
                    "required_quantity": record.get("required_quantity") or record.get("r.quantity", 0),
                    "grade": record.get("grade") or record.get("m.grade"),
                    "is_key_material": record.get("is_key_material") or record.get("m.is_key_material", False)
                })

            # 提取库存信息
            available_qty = record.get("available_quantity") or record.get("i.available_quantity")
            if material_code and available_qty is not None:
                inventory.append({
                    "material_code": material_code,
                    "available_quantity": available_qty,
                    "warehouse_location": record.get("warehouse_location") or record.get("i.warehouse_location")
                })

        # 去重库存（按物料代码合并）
        inv_dict = {}
        for inv in inventory:
            code = inv["material_code"]
            if code not in inv_dict:
                inv_dict[code] = inv
            else:
                inv_dict[code]["available_quantity"] += inv["available_quantity"]

        return materials, list(inv_dict.values())

    async def _smart_graph_query(self, context: AgentContext) -> Dict[str, Any]:
        """智能图谱查询 - 使用LLM动态生成Cypher"""
        # 1. 获取图谱schema
        schema = await self._get_graph_schema()

        # 2. 让LLM生成Cypher查询
        cypher = await self._generate_cypher_from_question(context.question, schema)

        if not cypher:
            # 降级：返回通用查询
            return await self._fallback_query(context.question)

        # 3. 执行查询
        result = await self.kg_service.query(cypher)

        # 4. 如果查询结果为空，尝试简化查询
        if not result.get("data") or len(result.get("data", [])) == 0:
            simplified_cypher = await self._simplify_cypher_query(cypher, context.question)
            if simplified_cypher and simplified_cypher != cypher:
                result = await self.kg_service.query(simplified_cypher)
                cypher = simplified_cypher

        return {
            "nodes": result.get("data", []),
            "relationships": [],
            "cypher": cypher,
            "query_type": "dynamic"
        }

    async def _get_graph_schema(self) -> str:
        """获取图谱 schema（供 LLM 使用）"""
        schema = """
    节点类型及属性：
    - Project: project_id, name, series, status
    - WorkOrder: wo_id, planned_start, planned_end, status, priority
    - Material: material_code, name, specification, grade, lead_time, is_key_material
    - Supplier: supplier_id, name, rating, aerospace_qualified, on_time_delivery_rate, risk_level
    - Inventory: inventory_id, available_quantity, reserved_quantity, warehouse_location
    - PurchaseOrder: po_id, order_date, quantity, promised_date, status, unit_price
    - RiskEvent: event_id, name, type, severity, status

    关系类型：
    - (Project)-[:HAS_WO]->(WorkOrder)
    - (WorkOrder)-[:REQUIRES {quantity}]->(Material)
    - (Supplier)-[:SUPPLIES]->(Material)
    - (Inventory)-[:RECORDS]->(Material)
    - (PurchaseOrder)-[:HAS_PO]->(Material)
    - (RiskEvent)-[:AFFECTS]->(WorkOrder)

    注意：属性名使用下划线命名，如 material_code, available_quantity。
    """
        return schema

    async def _generate_cypher_from_question(self, question: str, schema: str) -> Optional[str]:
        """根据问题生成 Cypher 查询"""

        system_prompt = """你是 Neo4j Cypher 查询专家。根据用户问题生成准确的 Cypher 语句。

    重要规则：
    1. 只返回 Cypher 语句，不要有任何解释、注释或 markdown 格式
    2. 使用正确的节点标签和属性名（参考 schema）
    3. 始终添加 LIMIT 50
    4. 对于自然语言中的项目名称、物料名称，使用 WHERE 子句进行匹配
    5. 如果问题涉及“需要什么物料”，应查询工单与物料的关系

    示例：
    问题："东四平台项目需要什么物料？"
    Cypher: MATCH (p:Project {name: '东四平台'})-[:HAS_WO]->(w:WorkOrder)-[:REQUIRES]->(m:Material) RETURN m.material_code, m.name, r.quantity LIMIT 50

    问题："物料MAT-001的库存有多少？"
    Cypher: MATCH (i:Inventory)-[:RECORDS]->(m:Material {material_code: 'MAT-001'}) RETURN i.available_quantity LIMIT 10

    问题："查询所有宇航级物料"
    Cypher: MATCH (m:Material {grade: '宇航级'}) RETURN m.material_code, m.name LIMIT 50

    问题："哪些供应商存在高风险？"
    Cypher: MATCH (s:Supplier {risk_level: '高'}) RETURN s.supplier_id, s.name LIMIT 50

    请严格按此格式输出。"""

        user_prompt = f"""
    知识图谱结构：
    {schema}

    用户问题：{question}

    请生成 Cypher 查询语句：
    """
        try:
            response = await self._call_llm(user_prompt, system_prompt, temperature=0.2)
            cypher = self._extract_cypher_from_response(response)
            if cypher and self._validate_cypher(cypher):
                return cypher
            return None
        except Exception as e:
            self.logger.error(f"生成Cypher失败: {e}")
            return None

    def _extract_cypher_from_response(self, response: str) -> str:
        """从LLM响应中提取Cypher语句"""
        response = re.sub(r'```cypher\n?', '', response)
        response = re.sub(r'```\n?', '', response)
        response = re.sub(r'`', '', response)

        lines = response.strip().split('\n')
        cypher_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(keyword in line.upper() for keyword in ['MATCH', 'RETURN', 'WITH', 'WHERE', 'OPTIONAL']):
                cypher_parts.append(line)
            elif cypher_parts and line and not line.startswith('//'):
                cypher_parts.append(line)

        if cypher_parts:
            cypher = ' '.join(cypher_parts)
            if 'LIMIT' not in cypher.upper():
                cypher += ' LIMIT 50'
            return cypher
        return response

    def _validate_cypher(self, cypher: str) -> bool:
        """验证Cypher语句基本格式"""
        cypher_upper = cypher.upper()
        return ('MATCH' in cypher_upper or 'RETURN' in cypher_upper)

    async def _simplify_cypher_query(self, original_cypher: str, question: str) -> Optional[str]:
        """简化Cypher查询（当原查询无结果时）"""
        system_prompt = "生成简化版的Cypher查询，使用更通用的匹配条件。"
        user_prompt = f"原查询无结果：{original_cypher}\n用户问题：{question}\n请生成简化版查询："

        try:
            response = await self._call_llm(user_prompt, system_prompt, temperature=0.3)
            return self._extract_cypher_from_response(response)
        except Exception as e:
            self.logger.error(f"简化查询失败: {e}")
            return None

    async def _query_by_project(self, project_id: str) -> Dict[str, Any]:
        """按项目ID查询"""
        query = """
        MATCH (p:Project {project_id: $project_id})
        OPTIONAL MATCH (p)-[:HAS_WO]->(w:WorkOrder)
        OPTIONAL MATCH (w)-[:REQUIRES]->(m:Material)
        OPTIONAL MATCH (m)-[:SUPPLIES]-(s:Supplier)
        OPTIONAL MATCH (i:Inventory)-[:RECORDS]->(m)
        RETURN p, collect(DISTINCT w) as work_orders, 
               collect(DISTINCT m) as materials,
               collect(DISTINCT s) as suppliers,
               collect(DISTINCT i) as inventories
        LIMIT 100
        """
        result = await self.kg_service.query(query, {"project_id": project_id})
        return {"nodes": result.get("data", []), "relationships": [], "cypher": query, "query_type": "exact"}

    async def _query_by_material(self, material_code: str) -> Dict[str, Any]:
        """按物料编码查询"""
        query = """
        MATCH (m:Material {material_code: $material_code})
        OPTIONAL MATCH (m)-[:SUPPLIES]-(s:Supplier)
        OPTIONAL MATCH (w:WorkOrder)-[:REQUIRES]->(m)
        OPTIONAL MATCH (i:Inventory)-[:RECORDS]->(m)
        RETURN m, collect(DISTINCT s) as suppliers, 
               collect(DISTINCT w) as work_orders,
               collect(DISTINCT i) as inventories
        LIMIT 50
        """
        result = await self.kg_service.query(query, {"material_code": material_code})
        return {"nodes": result.get("data", []), "relationships": [], "cypher": query, "query_type": "exact"}

    async def _query_by_module(self, module_id: str) -> Dict[str, Any]:
        """按舱段ID查询"""
        query = """
        MATCH (m:Module {module_id: $module_id})
        OPTIONAL MATCH (m)-[:BELONGS_TO]->(p:Project)
        OPTIONAL MATCH (p)-[:HAS_WO]->(w:WorkOrder)
        OPTIONAL MATCH (w)-[:REQUIRES]->(mat:Material)
        RETURN m, p, collect(DISTINCT w) as work_orders, collect(DISTINCT mat) as materials
        LIMIT 100
        """
        result = await self.kg_service.query(query, {"module_id": module_id})
        return {"nodes": result.get("data", []), "relationships": [], "cypher": query, "query_type": "exact"}

    async def _fallback_query(self, question: str) -> Dict[str, Any]:
        """降级查询 - 返回项目概览"""
        question_lower = question.lower()

        if "风险" in question_lower:
            query = "MATCH (r:RiskEvent) RETURN r LIMIT 20"
        elif "供应商" in question_lower:
            query = "MATCH (s:Supplier) RETURN s LIMIT 20"
        elif "物料" in question_lower:
            query = "MATCH (m:Material) RETURN m LIMIT 20"
        else:
            query = "MATCH (p:Project) RETURN p LIMIT 20"

        result = await self.kg_service.query(query)
        return {"nodes": result.get("data", []), "relationships": [], "cypher": query, "query_type": "fallback"}

    # ============================================
    # 数据标准化和其他辅助方法
    # ============================================

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
            "kg_enabled": self.kg_service is not None
        }