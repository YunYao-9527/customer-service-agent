"""
LLM 调用封装

封装 OpenAI 和 Anthropic API，提供统一的调用接口。
"""

import json
from typing import Any, Optional

import structlog
from anthropic import Anthropic
from openai import AsyncOpenAI

from src.config import LLMProvider, get_settings

logger = structlog.get_logger()


class LLMResponse:
    """LLM 响应封装"""

    def __init__(
        self,
        content: str,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        usage: Optional[dict[str, int]] = None,
        model: Optional[str] = None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage = usage or {}
        self.model = model

    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return len(self.tool_calls) > 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "model": self.model,
        }


class LLMClient:
    """
    LLM 客户端

    统一封装 OpenAI 和 Anthropic API，支持：
    - 多轮对话
    - Function Calling / Tool Use
    - 流式响应（预留）
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._openai_client: Optional[AsyncOpenAI] = None
        self._anthropic_client: Optional[Anthropic] = None

    @property
    def openai_client(self) -> AsyncOpenAI:
        """获取 OpenAI 客户端"""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.llm.openai_api_key,
                base_url=self.settings.llm.openai_base_url,
            )
        return self._openai_client

    @property
    def anthropic_client(self) -> Anthropic:
        """获取 Anthropic 客户端"""
        if self._anthropic_client is None:
            self._anthropic_client = Anthropic(
                api_key=self.settings.llm.anthropic_api_key,
            )
        return self._anthropic_client

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """
        发送对话请求

        Args:
            messages: 对话历史
            tools: 工具定义列表
            tool_choice: 工具选择策略 ("auto", "none", "required")

        Returns:
            LLM 响应
        """
        provider = self.settings.llm.provider

        if provider == LLMProvider.OPENAI:
            return await self._chat_openai(messages, tools, tool_choice)
        elif provider == LLMProvider.ANTHROPIC:
            return await self._chat_anthropic(messages, tools, tool_choice)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    async def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """OpenAI API 调用"""
        kwargs: dict[str, Any] = {
            "model": self.settings.llm.openai_model,
            "messages": messages,
            "temperature": self.settings.llm.openai_temperature,
            "max_tokens": self.settings.llm.openai_max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        response = await self.openai_client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        message = choice.message

        # 解析工具调用
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        # 构建响应
        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            model=response.model,
        )

    async def _chat_anthropic(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """Anthropic API 调用"""
        # 转换消息格式
        system_message = ""
        claude_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        kwargs: dict[str, Any] = {
            "model": self.settings.llm.anthropic_model,
            "max_tokens": self.settings.llm.openai_max_tokens,
            "messages": claude_messages,
        }

        if system_message:
            kwargs["system"] = system_message

        if tools:
            kwargs["tools"] = tools

        response = self.anthropic_client.messages.create(**kwargs)

        # 解析响应
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            model=response.model,
        )


# 全局 LLM 客户端
llm_client = LLMClient()
