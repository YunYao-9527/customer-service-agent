"""
政策检索器

使用向量数据库检索相关业务政策，用于规则检查和决策支持。
"""

import os
import re
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
        aliases = {"refund": "退款", "cancel": "取消", "shipping": "物流", "freeze": "冻结"}
        query = aliases.get(query, query)
        query_words = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", query))
        content_words = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", content))

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
        relevant_policies = self.retrieve(action)
        reason = "符合当前业务政策"
        allowed = True
        status = context.get("order_status")
        if action == "refund":
            policy = self.get_policy("refund_policy") or ""
            match = re.search(r"签收后\s*(\d+)\s*天", policy)
            limit = int(match.group(1)) if match else 7
            if status not in {"paid", "shipped", "delivered"}:
                allowed, reason = False, "当前订单状态不允许退款"
            elif context.get("amount") is not None and (
                float(context["amount"]) <= 0 or float(context["amount"]) > float(context.get("paid_amount", 0))
            ):
                allowed, reason = False, "退款金额必须大于零且不能超过实付金额"
            elif status == "delivered" and context.get("days_since_delivery") is None:
                allowed, reason = False, "缺少签收时间，需要人工核查退款时效"
            elif status == "delivered" and context.get("days_since_delivery", 0) > limit:
                allowed, reason = False, f"已超过签收后 {limit} 天的普通退款时效，请联系人工核查质量问题"
        elif action in {"cancel", "shipping"} and status not in {"pending", "paid"}:
            allowed, reason = False, "订单已发货或已结束，不能直接取消或修改地址"
        return {"allowed": allowed, "reason": reason,
                "policies": [p["name"] for p in relevant_policies]}


# 全局政策检索器
policy_retriever = PolicyRetriever()
