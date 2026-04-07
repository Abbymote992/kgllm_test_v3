# backend/services/kg_service.py
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging
import re
from datetime import date, datetime

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    def __init__(self, uri: str, user: str, password: str):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self._connect()

    def _connect(self):
        """连接Neo4j数据库"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 测试连接
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                test = result.single()["test"]
                logger.info(f"Neo4j连接成功: {self.uri}")
        except Exception as e:
            logger.error(f"Neo4j连接失败: {e}")
            raise

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j连接已关闭")

    def _convert_value(self, value):
        """
        转换 Neo4j 特殊类型为 Python 可序列化类型
        """
        if value is None:
            return None

        # 处理 Neo4j 日期类型
        type_name = str(type(value))
        if 'neo4j.time.Date' in type_name:
            return str(value)
        if 'neo4j.time.DateTime' in type_name:
            return str(value)
        if 'neo4j.time.Time' in type_name:
            return str(value)

        # 处理 Python datetime
        if isinstance(value, (date, datetime)):
            return value.isoformat()

        # 处理列表
        if isinstance(value, list):
            return [self._convert_value(v) for v in value]

        # 处理字典
        if isinstance(value, dict):
            return {k: self._convert_value(v) for k, v in value.items()}

        # 其他类型直接返回
        return value

    def _clean_cypher(self, cypher: str) -> str:
        """执行前清理 Cypher 语句"""
        if not cypher:
            return cypher

        # 只取第一个分号之前的内容
        if ';' in cypher:
            cypher = cypher.split(';')[0]

        # 按行处理，移除多余的中文说明
        lines = cypher.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过包含中文提示的行
            if any(keyword in line for keyword in ['请告诉我', '帮助', '需要', '如有', '如果', '有任何', '问题']):
                continue

            # 如果行包含中文但不是 Cypher 关键字，跳过
            if re.search(r'[\u4e00-\u9fff]', line):
                if not any(kw in line.upper() for kw in
                           ['MATCH', 'RETURN', 'WHERE', 'WITH', 'CREATE', 'MERGE', 'OPTIONAL']):
                    continue

            cleaned_lines.append(line)

        cypher = ' '.join(cleaned_lines).strip()

        # 确保有 RETURN 子句
        if cypher and 'RETURN' not in cypher.upper():
            cypher += ' RETURN 1'

        return cypher

    def execute_query(self, cypher: str, parameters: Dict = None) -> Dict[str, Any]:
        """执行Cypher查询"""
        try:
            # 清理 Cypher
            cypher = self._clean_cypher(cypher)

            if not cypher:
                return {
                    "success": False,
                    "error": "Cypher语句为空",
                    "data": [],
                    "count": 0,
                    "cypher": cypher
                }

            logger.debug(f"执行Cypher: {cypher}")

            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                records = []
                for record in result:
                    # 转换每个记录中的值
                    converted = {}
                    for key, value in record.items():
                        converted[key] = self._convert_value(value)
                    records.append(converted)

                return {
                    "success": True,
                    "data": records,
                    "count": len(records),
                    "cypher": cypher
                }
        except Exception as e:
            logger.error(f"查询执行失败: {e}\nCypher: {cypher}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "count": 0,
                "cypher": cypher
            }

    def get_graph_data(self, limit: int = 50, node_types: List[str] = None) -> Dict:
        """获取图谱可视化数据 - 包含节点和关系"""

        try:
            with self.driver.session() as session:
                # 使用路径查询获取节点和关系
                path_query = """
                MATCH path = (n)-[r]->(m)
                WHERE (n:Project OR n:Material OR n:Supplier OR n:Inventory OR n:PurchaseOrder)
                  AND (m:Project OR m:Material OR m:Supplier OR m:Inventory OR m:PurchaseOrder)
                RETURN n, r, m
                LIMIT $limit
                """

                result = session.run(path_query, limit=limit)

                nodes_dict = {}
                edges = []

                for record in result:
                    # 处理源节点
                    source = record["n"]
                    if source and source.id not in nodes_dict:
                        labels = list(source.labels)
                        node_type = labels[0] if labels else "Unknown"
                        properties = {}
                        for key, value in source.items():
                            properties[key] = self._convert_value(value)
                        nodes_dict[source.id] = {
                            "id": source.id,
                            "label": node_type,
                            "properties": properties,
                            "type": node_type
                        }

                    # 处理目标节点
                    target = record["m"]
                    if target and target.id not in nodes_dict:
                        labels = list(target.labels)
                        node_type = labels[0] if labels else "Unknown"
                        properties = {}
                        for key, value in target.items():
                            properties[key] = self._convert_value(value)
                        nodes_dict[target.id] = {
                            "id": target.id,
                            "label": node_type,
                            "properties": properties,
                            "type": node_type
                        }

                    # 处理关系
                    rel = record["r"]
                    if rel:
                        rel_props = {}
                        for key, value in rel.items():
                            rel_props[key] = self._convert_value(value)

                        edges.append({
                            "id": f"{rel.id}",
                            "source": rel.start_node.id,
                            "target": rel.end_node.id,
                            "label": rel.type,
                            "properties": rel_props
                        })

                # 如果没有关系数据，尝试获取孤立节点
                if len(nodes_dict) == 0:
                    node_query = """
                    MATCH (n)
                    WHERE (n:Project OR n:Material OR n:Supplier OR n:Inventory OR n:PurchaseOrder)
                    RETURN n
                    LIMIT $limit
                    """
                    node_result = session.run(node_query, limit=limit)

                    for record in node_result:
                        node = record["n"]
                        if node.id not in nodes_dict:
                            labels = list(node.labels)
                            node_type = labels[0] if labels else "Unknown"
                            properties = {}
                            for key, value in node.items():
                                properties[key] = self._convert_value(value)
                            nodes_dict[node.id] = {
                                "id": node.id,
                                "label": node_type,
                                "properties": properties,
                                "type": node_type
                            }

                nodes = list(nodes_dict.values())

                logger.info(f"图谱数据: {len(nodes)} 个节点, {len(edges)} 条关系")

                return {
                    "success": True,
                    "nodes": nodes,
                    "edges": edges,
                    "total": len(nodes)
                }

        except Exception as e:
            logger.error(f"获取图谱数据失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "nodes": [],
                "edges": [],
                "total": 0
            }

    def get_schema(self) -> Dict[str, Any]:
        """获取图谱Schema"""
        return {
            "nodes": [
                {"labels": ["Project"], "properties": ["id", "name", "delivery_date", "priority", "status"]},
                {"labels": ["Material"],
                 "properties": ["id", "name", "category", "criticality", "lead_time_days", "unit", "spec"]},
                {"labels": ["Supplier"],
                 "properties": ["id", "name", "rating", "lead_time_avg", "location", "category"]},
                {"labels": ["Inventory"],
                 "properties": ["id", "material_id", "project_id", "required_qty", "current_stock", "required_date"]},
                {"labels": ["PurchaseOrder"],
                 "properties": ["id", "quantity", "order_date", "expected_date", "status", "tracking_info"]}
            ],
            "relationships": [
                {"type": "REQUIRES", "from": "Project", "to": "Material",
                 "properties": ["required_qty", "required_date", "current_stock"]},
                {"type": "HAS_INVENTORY", "from": "Material", "to": "Inventory", "properties": ["current_stock"]},
                {"type": "TRIGGERED_BY", "from": "Inventory", "to": "PurchaseOrder",
                 "properties": ["quantity", "order_date"]},
                {"type": "PLACED_WITH", "from": "PurchaseOrder", "to": "Supplier", "properties": ["expected_date"]},
                {"type": "SUPPLIED_BY", "from": "Material", "to": "Supplier", "properties": ["lead_time_days"]}
            ]
        }

    def get_node_count(self) -> Dict[str, int]:
        """获取各类型节点数量"""
        query = """
        MATCH (n)
        RETURN labels(n)[0] as type, count(n) as count
        """
        result = self.execute_query(query)
        if result["success"]:
            return {item["type"]: item["count"] for item in result["data"]}
        return {}

    def get_relationship_count(self) -> Dict[str, int]:
        """获取各类型关系数量"""
        query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        """
        result = self.execute_query(query)
        if result["success"]:
            return {item["type"]: item["count"] for item in result["data"]}
        return {}

    def health_check(self) -> bool:
        """健康检查"""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except:
            return False