"""
RAG检索服务

负责向量知识库的检索和管理
"""

from typing import List, Dict, Any, Optional
import json
import hashlib


class RAGService:
    """RAG知识检索服务"""

    def __init__(self, embedding_model=None, vector_store=None):
        """
        初始化RAG服务

        Args:
            embedding_model: 嵌入模型（可选，用于实验）
            vector_store: 向量数据库（可选）
        """
        self.embedding_model = embedding_model
        self.vector_store = vector_store

        # 内存知识库（实验用）
        self._knowledge_base = self._init_knowledge_base()

    def _init_knowledge_base(self) -> List[Dict]:
        """初始化内存知识库"""
        return [
            {
                "id": "kb_001",
                "title": "宇航级元器件定义",
                "content": "宇航级元器件是指经过特殊筛选、测试和认证，能够在太空环境中可靠工作的电子元器件。其特点是高可靠性、抗辐射、宽温工作范围。",
                "category": "terminology",
                "keywords": ["宇航级", "元器件", "航天", "可靠性"]
            },
            {
                "id": "kb_002",
                "title": "齐套率计算公式",
                "content": "齐套率 = (已齐套物料种类数 / 总物料种类数) × 100%。其中，已齐套指该物料的可用库存 + 在途采购 ≥ 需求数量。",
                "category": "business_rule",
                "keywords": ["齐套率", "计算公式", "物料", "库存"]
            },
            {
                "id": "kb_003",
                "title": "缺料预警规则",
                "content": "缺料预警分为三个等级：高（缺货或延期超过7天）、中（延期3-7天或库存不足）、低（延期小于3天）。预警需提前至少5天通知项目经理。",
                "category": "business_rule",
                "keywords": ["预警", "缺料", "风险", "等级"]
            },
            {
                "id": "kb_004",
                "title": "航天供应商资质要求",
                "content": "航天供应商必须通过ISO9001认证，具备宇航级生产资质，且连续三年交付合格率不低于98%。新供应商需经过3个月的试用期评估。",
                "category": "sop",
                "keywords": ["供应商", "资质", "航天", "认证"]
            },
            {
                "id": "kb_005",
                "title": "采购建议生成规则",
                "content": "当物料齐套率低于80%时，系统应自动生成采购建议：1) 优先催货在途订单；2) 评估备选供应商；3) 考虑替代物料；4) 紧急情况下申请特批。",
                "category": "sop",
                "keywords": ["采购", "建议", "催货", "备选"]
            },
            {
                "id": "kb_006",
                "title": "BOM变更管理流程",
                "content": "BOM变更需经过变更申请、技术评审、采购评估、库存确认、生产确认五个步骤。紧急变更可在24小时内完成，但需事后补录审批。",
                "category": "sop",
                "keywords": ["BOM", "变更", "流程", "管理"]
            }
        ]

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        检索相关知识

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            相关知识列表
        """
        # 简单关键词匹配（实验用）
        # 生产环境应使用向量检索

        query_lower = query.lower()
        scored_results = []

        for kb_item in self._knowledge_base:
            score = 0

            # 标题匹配
            if any(kw in query_lower for kw in kb_item.get("keywords", [])):
                score += 3

            # 内容匹配
            content_lower = kb_item["content"].lower()
            if any(kw in query_lower for kw in kb_item.get("keywords", [])):
                score += 2

            # 关键词匹配
            for keyword in kb_item.get("keywords", []):
                if keyword in query_lower:
                    score += 1

            if score > 0:
                scored_results.append({
                    **kb_item,
                    "relevance_score": score
                })

        # 按相关度排序
        scored_results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return scored_results[:top_k]

    async def add_knowledge(self, knowledge: Dict) -> str:
        """
        添加知识到知识库

        Args:
            knowledge: 知识条目

        Returns:
            知识ID
        """
        knowledge_id = hashlib.md5(
            knowledge.get("title", "").encode()
        ).hexdigest()[:8]

        knowledge["id"] = knowledge_id
        self._knowledge_base.append(knowledge)

        return knowledge_id

    async def search_by_category(self, category: str) -> List[Dict]:
        """按类别搜索知识"""
        return [
            item for item in self._knowledge_base
            if item.get("category") == category
        ]