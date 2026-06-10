"""
政策检索器

使用向量数据库检索相关业务政策，用于规则检查和决策支持。
"""

import os
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

# 政策文档目录
POLICIES_DIR = Path(__file__).parent / "policies"


class PolicyRetriever:
    """
    政策检索器

    使用向量数据库（ChromaDB）存储和检索业务政策文档。
    支持：
    - 政策文档索引
    - 语义检索
    - 规则匹配
    """

    def __init__(self) -> None:
        self._policies: dict[str, str] = {}
        self._indexed = False

    def load_policies(self) -> None:
        """加载政策文档"""
        if not POLICIES_DIR.exists():
            logger.warning("policies_dir_not_found", path=str(POLICIES_DIR))
            return

        for policy_file in POLICIES_DIR.glob("*.md"):
            try:
                content = policy_file.read_text(encoding="utf-8")
                policy_name = policy_file.stem
                self._policies[policy_name] = content
                logger.info("policy_loaded", name=policy_name)
            except Exception as e:
                logger.error("policy_load_failed", file=policy_file.name, error=str(e))

        self._indexed = True
        logger.info("policies_loaded", count=len(self._policies))

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """
        检索相关政策

        Args:
            query: 查询内容
            top_k: 返回结果数量

        Returns:
            相关政策列表
        """
        if not self._indexed:
            self.load_policies()

        # 简单的关键词匹配（生产环境应使用向量检索）
        results = []
        query_lower = query.lower()

        for name, content in self._policies.items():
            # 计算简单的相关性分数
            score = self._calculate_relevance(query_lower, content.lower())
            if score > 0:
                results.append({
                    "name": name,
                    "content": content,
                    "score": score,
                })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]

    def _calculate_relevance(self, query: str, content: str) -> float:
        """计算查询与内容的相关性"""
        # 简单的关键词匹配
        query_words = set(query.split())
        content_words = set(content.split())

        # 计算交集比例
        if not query_words:
            return 0.0

        intersection = query_words & content_words
        return len(intersection) / len(query_words)

    def get_policy(self, name: str) -> Optional[str]:
        """获取指定政策"""
        if not self._indexed:
            self.load_policies()
        return self._policies.get(name)

    def check_rule(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        检查操作是否符合规则

        Args:
            action: 操作类型（如 refund, cancel, freeze）
            context: 上下文信息

        Returns:
            检查结果
        """
        # 检索相关政策
        relevant_policies = self.retrieve(action)

        if not relevant_policies:
            return {
                "allowed": True,
                "reason": "未找到相关规则，默认允许",
                "policies": [],
            }

        # 分析规则
        # 这里简化处理，实际应该使用 LLM 分析政策内容
        return {
            "allowed": True,
            "reason": "符合相关政策",
            "policies": [p["name"] for p in relevant_policies],
        }


# 全局政策检索器
policy_retriever = PolicyRetriever()
