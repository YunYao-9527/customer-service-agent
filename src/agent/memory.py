"""
对话记忆管理

管理对话历史、上下文窗口和记忆压缩。
"""

import json
from datetime import datetime
from typing import Any, Optional

import structlog
from redis import asyncio as aioredis

from src.config import get_settings

logger = structlog.get_logger()


class ConversationMemory:
    """
    对话记忆管理器

    管理对话历史，支持：
    - 对话历史存储（Redis）
    - 上下文窗口管理
    - 记忆压缩
    - 会话恢复
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.settings = get_settings()
        self._redis: Optional[aioredis.Redis] = None
        self._local_messages: list[dict[str, Any]] = []

    @property
    def redis(self) -> aioredis.Redis:
        """获取 Redis 连接"""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.settings.redis.url,
                decode_responses=True,
            )
        return self._redis

    @property
    def _redis_key(self) -> str:
        """Redis 键名"""
        return f"conversation:{self.session_id}"

    async def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """
        添加消息到对话历史

        Args:
            role: 消息角色 (user, assistant, system, tool)
            content: 消息内容
            **kwargs: 额外信息
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }

        # 添加到本地缓存
        self._local_messages.append(message)

        # 持久化到 Redis
        try:
            await self.redis.rpush(self._redis_key, json.dumps(message))
            # 设置过期时间（24 小时）
            await self.redis.expire(self._redis_key, 86400)
        except Exception as e:
            logger.warning("redis_save_failed", session_id=self.session_id, error=str(e))

    async def get_messages(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        """
        获取对话历史

        Args:
            limit: 返回的消息数量限制

        Returns:
            消息列表
        """
        try:
            if limit:
                messages = await self.redis.lrange(self._redis_key, -limit, -1)
            else:
                messages = await self.redis.lrange(self._redis_key, 0, -1)

            return [json.loads(msg) for msg in messages]
        except Exception as e:
            logger.warning("redis_get_failed", session_id=self.session_id, error=str(e))
            # 降级到本地缓存
            if limit:
                return self._local_messages[-limit:]
            return self._local_messages.copy()

    async def get_context_messages(self, max_tokens: int = 4000) -> list[dict[str, Any]]:
        """
        获取适合上下文窗口的消息

        根据 token 限制截取消息，保留最近的对话。

        Args:
            max_tokens: 最大 token 数

        Returns:
            截取后的消息列表
        """
        messages = await self.get_messages()

        # 简单的 token 估算（4 字符 ≈ 1 token）
        estimated_tokens = 0
        selected_messages = []

        for msg in reversed(messages):
            msg_tokens = len(msg.get("content", "")) // 4
            if estimated_tokens + msg_tokens > max_tokens:
                break
            selected_messages.insert(0, msg)
            estimated_tokens += msg_tokens

        return selected_messages

    async def clear(self) -> None:
        """清空对话历史"""
        try:
            await self.redis.delete(self._redis_key)
        except Exception as e:
            logger.warning("redis_clear_failed", session_id=self.session_id, error=str(e))

        self._local_messages.clear()

    async def get_summary(self) -> dict[str, Any]:
        """
        获取对话摘要

        Returns:
            对话统计信息
        """
        messages = await self.get_messages()

        user_messages = [m for m in messages if m["role"] == "user"]
        assistant_messages = [m for m in messages if m["role"] == "assistant"]
        tool_messages = [m for m in messages if m["role"] == "tool"]

        return {
            "session_id": self.session_id,
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "tool_messages": len(tool_messages),
            "first_message_at": messages[0]["timestamp"] if messages else None,
            "last_message_at": messages[-1]["timestamp"] if messages else None,
        }


class MemoryManager:
    """
    记忆管理器

    管理多个会话的记忆。
    """

    def __init__(self) -> None:
        self._memories: dict[str, ConversationMemory] = {}

    def get_memory(self, session_id: str) -> ConversationMemory:
        """获取或创建会话记忆"""
        if session_id not in self._memories:
            self._memories[session_id] = ConversationMemory(session_id)
        return self._memories[session_id]

    def remove_memory(self, session_id: str) -> None:
        """移除会话记忆"""
        if session_id in self._memories:
            del self._memories[session_id]

    async def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """清理过期的会话记忆"""
        # 实际实现需要检查 Redis 中的过期键
        return 0


# 全局记忆管理器
memory_manager = MemoryManager()
