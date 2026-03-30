# backend/services/kg_service.py
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """知识图谱服务 - 封装Neo4j操作"""

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
                session.run("RETURN 1")
            logger.info(f"成功连接到Neo4j: {self.uri}")
        except Exception as e:
            logger.error(f"Neo4j连接失败: {e}")
            raise

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j连接已关闭")

    def execute_query(self, cypher: str, parameters: Dict = None) -> Dict[str, Any]:
        """执行Cypher查询"""
        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                records = [record.data() for record in result]
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

    def get_schema(self) -> Dict[str, Any]:
        """获取图谱Schema"""
        # 手动定义Schema（因为Neo4j版本可能不支持自动获取）
        return {
            "nodes": [
                {
                    "labels": ["Project"],
                    "properties": ["id", "name", "delivery_date", "priority", "status"]
                },
                {
                    "labels": ["Material"],
                    "properties": ["id", "name", "category", "criticality", "lead_time_days", "unit", "spec"]
                },
                {
                    "labels": ["Supplier"],
                    "properties": ["id", "name", "rating", "lead_time_avg", "location", "category"]
                },
                {
                    "labels": ["Inventory"],
                    "properties": ["id", "material_id", "project_id", "required_qty", "current_stock", "required_date"]
                },
                {
                    "labels": ["PurchaseOrder"],
                    "properties": ["id", "quantity", "order_date", "expected_date", "status", "tracking_info"]
                }
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

    def get_graph_data(self, limit: int = 50, node_types: List[str] = None) -> Dict:
        """获取图谱可视化数据"""
        # 构建节点类型过滤
        type_filter = ""
        if node_types:
            labels = [f"n:{t}" for t in node_types]
            type_filter = f"WHERE {' OR '.join(labels)}"

        query = f"""
        MATCH (n)-[r]->(m)
        {type_filter}
        RETURN n, r, m
        LIMIT {limit}
        """

        try:
            with self.driver.session() as session:
                result = session.run(query)

                nodes = {}
                edges = []

                for record in result:
                    # 处理源节点
                    source = record["n"]
                    source_id = source.id
                    if source_id not in nodes:
                        labels = list(source.labels)
                        nodes[source_id] = {
                            "id": source_id,
                            "label": labels[0] if labels else "Unknown",
                            "properties": dict(source.items()),
                            "type": labels[0] if labels else "Unknown"
                        }

                    # 处理目标节点
                    target = record["m"]
                    target_id = target.id
                    if target_id not in nodes:
                        labels = list(target.labels)
                        nodes[target_id] = {
                            "id": target_id,
                            "label": labels[0] if labels else "Unknown",
                            "properties": dict(target.items()),
                            "type": labels[0] if labels else "Unknown"
                        }

                    # 添加边
                    rel = record["r"]
                    edges.append({
                        "id": f"{source_id}_{target_id}_{len(edges)}",
                        "source": source_id,
                        "target": target_id,
                        "label": rel.type,
                        "properties": dict(rel.items())
                    })

                return {
                    "success": True,
                    "nodes": list(nodes.values()),
                    "edges": edges,
                    "total": len(nodes)
                }
        except Exception as e:
            logger.error(f"获取图谱数据失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "nodes": [],
                "edges": [],
                "total": 0
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