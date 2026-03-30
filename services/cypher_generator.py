# backend/services/cypher_generator.py
from openai import OpenAI
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CypherGenerator:
    """Text2Cypher 生成器 - 将自然语言转换为Cypher查询"""

    def __init__(self, api_base: str, api_key: str, model: str):
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.model = model

    def generate(self, question: str, schema: dict) -> Optional[str]:
        """生成Cypher查询"""
        prompt = self._build_prompt(question, schema)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            cypher = response.choices[0].message.content.strip()
            # 清理markdown标记
            cypher = re.sub(r'^```cypher\n?|```$', '', cypher)
            cypher = re.sub(r'^```\n?|```$', '', cypher)
            cypher = cypher.strip()

            logger.info(f"生成的Cypher: {cypher}")
            return cypher
        except Exception as e:
            logger.error(f"Text2Cypher生成失败: {e}")
            return None

    def _build_prompt(self, question: str, schema: dict) -> str:
        """构建Prompt"""
        # 格式化Schema
        schema_text = self._format_schema(schema)

        # 常见问题示例
        examples = self._get_examples()

        prompt = f"""
你是一个Neo4j图数据库专家。根据以下图模式，将用户问题转换为Cypher查询语句。

## 图模式
{schema_text}

## 重要规则
1. 节点类型: Project, Material, Supplier, Inventory, PurchaseOrder
2. 项目名称示例: "通信卫星平台项目", "遥感卫星载荷项目", "空间站实验舱项目"
3. 物料ID格式: MAT-001, MAT-002...
4. 供应商ID格式: SUP-001, SUP-002...
5. 返回结果用中文别名，如: RETURN m.name as 物料名称
6. 只返回Cypher语句，不要其他内容

## 示例
{examples}

## 用户问题
{question}

Cypher:
"""
        return prompt

    def _format_schema(self, schema: dict) -> str:
        """格式化Schema为文本"""
        text = "节点类型:\n"
        for node in schema.get("nodes", []):
            labels = node.get("labels", [])
            props = node.get("properties", [])
            if labels:
                text += f"- {labels[0]}: {', '.join(props)}\n"

        text += "\n关系类型:\n"
        for rel in schema.get("relationships", []):
            props = rel.get("properties", [])
            prop_text = f" {{{', '.join(props)}}}" if props else ""
            text += f"- ({rel['from']})-[:{rel['type']}{prop_text}]->({rel['to']})\n"

        return text

    def _get_examples(self) -> str:
        """获取示例查询"""
        return """
1. 问题: "通信卫星平台项目需要什么物料？"
   Cypher: MATCH (p:Project {name: "通信卫星平台项目"})-[:REQUIRES]->(m:Material) 
           RETURN m.name as 物料名称, m.id as 物料ID

2. 问题: "MAT-001物料由哪个供应商提供？"
   Cypher: MATCH (m:Material {id: "MAT-001"})-[:SUPPLIED_BY]->(s:Supplier) 
           RETURN s.name as 供应商名称, s.location as 供应商地点

3. 问题: "通信卫星平台项目涉及哪些供应商？"
   Cypher: MATCH (p:Project {name: "通信卫星平台项目"})-[:REQUIRES]->(m:Material)-[:SUPPLIED_BY]->(s:Supplier) 
           RETURN DISTINCT s.name as 供应商名称

4. 问题: "当前有哪些物料库存不足？"
   Cypher: MATCH (i:Inventory) WHERE i.current_stock < i.required_qty 
           MATCH (m:Material {id: i.material_id}) 
           RETURN m.name as 物料名称, i.current_stock as 当前库存, i.required_qty as 需求数量

5. 问题: "查询所有延迟的采购订单"
   Cypher: MATCH (po:PurchaseOrder) WHERE po.status CONTAINS "DELAYED" 
           RETURN po.id as 订单号, po.status as 状态, po.expected_date as 预计日期
"""