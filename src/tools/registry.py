"""
工具注册中心

提供工具注册、发现和管理功能。
使用装饰器简化工具定义。
"""

import functools
from collections.abc import Callable
from typing import Any, Optional

import structlog

from src.tools.schema import RiskLevel, ToolSchema, extract_schema_from_function

logger = structlog.get_logger()


class ToolRegistry:
    """
    工具注册中心

    管理所有可用工具，支持：
    - 装饰器注册
    - 按类别和风险等级筛选
    - Schema 导出（OpenAI/Anthropic 格式）
    """

    _instance: Optional["ToolRegistry"] = None
    _tools: dict[str, tuple[ToolSchema, Callable]] = {}

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(
        self,
        name: str,
        description: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        requires_confirmation: bool = False,
        requires_verification: bool = False,
        category: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> Callable:
        """
        注册工具装饰器

        Args:
            name: 工具名称
            description: 工具描述
            risk_level: 风险等级
            requires_confirmation: 是否需要用户确认
            requires_verification: 是否需要验证
            category: 工具类别
            parameters: 参数 Schema（可选，自动从函数签名提取）

        Returns:
            装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            # 提取或使用提供的参数 Schema
            if parameters is None:
                param_schema = extract_schema_from_function(func)
            else:
                param_schema = parameters

            # 创建工具 Schema
            schema = ToolSchema(
                name=name,
                description=description,
                parameters=param_schema,
                risk_level=risk_level,
                requires_confirmation=requires_confirmation,
                requires_verification=requires_verification,
                category=category,
            )

            # 注册工具
            self._tools[name] = (schema, func)

            logger.info("tool_registered", name=name, risk_level=risk_level.value)

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                return await func(*args, **kwargs)

            # 保留原始函数的引用
            wrapper._tool_schema = schema  # type: ignore
            wrapper._original_func = func  # type: ignore

            return wrapper

        return decorator

    def get_tool(self, name: str) -> Optional[tuple[ToolSchema, Callable]]:
        """获取工具"""
        return self._tools.get(name)

    def get_all_tools(self) -> dict[str, tuple[ToolSchema, Callable]]:
        """获取所有工具"""
        return self._tools.copy()

    def get_tools_by_category(self, category: str) -> list[tuple[ToolSchema, Callable]]:
        """按类别获取工具"""
        return [
            (schema, func)
            for schema, func in self._tools.values()
            if schema.category == category
        ]

    def get_tools_by_risk_level(self, risk_level: RiskLevel) -> list[tuple[ToolSchema, Callable]]:
        """按风险等级获取工具"""
        return [
            (schema, func)
            for schema, func in self._tools.values()
            if schema.risk_level == risk_level
        ]

    def get_schemas(self, risk_level: Optional[RiskLevel] = None) -> list[ToolSchema]:
        """获取工具 Schema 列表"""
        if risk_level:
            return [
                schema
                for schema, _ in self._tools.values()
                if schema.risk_level == risk_level
            ]
        return [schema for schema, _ in self._tools.values()]

    def get_openai_functions(
        self, risk_level: Optional[RiskLevel] = None
    ) -> list[dict[str, Any]]:
        """获取 OpenAI Function Calling 格式的工具定义"""
        schemas = self.get_schemas(risk_level)
        return [schema.to_openai_function() for schema in schemas]

    def get_anthropic_tools(
        self, risk_level: Optional[RiskLevel] = None
    ) -> list[dict[str, Any]]:
        """获取 Anthropic Tool Use 格式的工具定义"""
        schemas = self.get_schemas(risk_level)
        return [schema.to_anthropic_tool() for schema in schemas]

    def clear(self) -> None:
        """清空注册表（测试用）"""
        self._tools.clear()


# 全局工具注册表
tool_registry = ToolRegistry()


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    risk_level: RiskLevel = RiskLevel.LOW,
    requires_confirmation: bool = False,
    requires_verification: bool = False,
    category: Optional[str] = None,
    parameters: Optional[dict[str, Any]] = None,
) -> Callable:
    """
    工具装饰器快捷方式

    用法：
        @tool(description="查询订单详情", risk_level="low")
        async def get_order(order_no: str, db: Session) -> dict:
            ...
    """
    # 处理 risk_level 字符串
    if isinstance(risk_level, str):
        risk_level = RiskLevel(risk_level)

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or f"工具: {tool_name}"

        return tool_registry.register(
            name=tool_name,
            description=tool_desc,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            requires_verification=requires_verification,
            category=category,
            parameters=parameters,
        )(func)

    return decorator
