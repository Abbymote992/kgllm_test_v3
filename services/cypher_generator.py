# backend/services/cypher_generator.py
from openai import OpenAI
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CypherGenerator:
    """Text2Cypher 生成器"""

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

            # 清理 Cypher
            cypher = self._clean_cypher(cypher)

            if cypher:
                logger.info(f"生成的Cypher: {cypher}")
            return cypher
        except Exception as e:
            logger.error(f"Text2Cypher生成失败: {e}")
            return None

    def _clean_cypher(self, cypher: str) -> str:
        """清理 Cypher 语句"""
        if not cypher:
            return cypher

        # 移除 markdown 代码块标记
        cypher = re.sub(r'^```cypher\n?', '', cypher)
        cypher = re.sub(r'^```\n?', '', cypher)
        cypher = re.sub(r'\n?```$', '', cypher)

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

    def _build_prompt(self, question: str, schema: dict) -> str:
        """构建Prompt"""
        schema_text = self._format_schema(schema)

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
6. **只返回Cypher语句，不要任何解释、说明或额外文字**
7. **Cypher语句必须以 RETURN 结尾**

## 示例
问题: "通信卫星平台项目需要什么物料？"
Cypher: MATCH (p:Project {{name: "通信卫星平台项目"}})-[:REQUIRES]->(m:Material) RETURN m.name as 物料名称, m.id as 物料ID

问题: "MAT-001物料由哪个供应商提供？"
Cypher: MATCH (m:Material {{id: "MAT-001"}})-[:SUPPLIED_BY]->(s:Supplier) RETURN s.name as 供应商名称

问题: "通信卫星平台项目涉及哪些供应商？"
Cypher: MATCH (p:Project {{name: "通信卫星平台项目"}})-[:REQUIRES]->(m:Material)-[:SUPPLIED_BY]->(s:Supplier) RETURN DISTINCT s.name as 供应商名称

## 用户问题
{question}

Cypher:"""
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