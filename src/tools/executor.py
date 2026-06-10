"""
工具执行器

负责执行工具调用，包括参数校验、权限检查、超时控制和错误处理。
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.tools.registry import tool_registry
from src.tools.schema import RiskLevel, ToolSchema

logger = structlog.get_logger()


class ToolExecutionError(Exception):
    """工具执行错误"""

    def __init__(self, tool_name: str, message: str, original_error: Optional[Exception] = None):
        self.tool_name = tool_name
        self.message = message
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")


class ToolPermissionError(ToolExecutionError):
    """工具权限错误"""
    pass


class ToolTimeoutError(ToolExecutionError):
    """工具超时错误"""
    pass


class ToolValidationError(ToolExecutionError):
    """工具参数校验错误"""
    pass


class ToolExecutor:
    """
    工具执行器

    提供工具执行的核心功能：
    1. 工具查找和 Schema 校验
    2. 参数验证
    3. 风险等级检查
    4. 超时控制
    5. 执行结果封装
    6. 错误处理和重试
    """

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self.db = db
        self.settings = get_settings()

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_confirmed: bool = False,
    ) -> dict[str, Any]:
        """
        执行工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            user_confirmed: 用户是否已确认（高风险操作需要）

        Returns:
            工具执行结果

        Raises:
            ToolExecutionError: 执行失败
            ToolPermissionError: 权限不足
            ToolTimeoutError: 执行超时
            ToolValidationError: 参数校验失败
        """
        start_time = datetime.now()

        # 1. 查找工具
        tool_info = tool_registry.get_tool(tool_name)
        if not tool_info:
            raise ToolExecutionError(tool_name, f"工具 '{tool_name}' 不存在")

        schema, func = tool_info

        # 2. 风险等级检查
        if schema.requires_confirmation and not user_confirmed:
            raise ToolPermissionError(
                tool_name,
                f"工具 '{tool_name}' 需要用户确认才能执行",
            )

        # 3. 参数验证
        validated_args = self._validate_arguments(schema, arguments)

        # 4. 注入数据库会话
        if self.db is not None:
            validated_args["db"] = self.db

        # 5. 执行工具（带超时）
        try:
            result = await asyncio.wait_for(
                func(**validated_args),
                timeout=self.settings.agent.tool_call_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise ToolTimeoutError(
                tool_name,
                f"工具执行超时（{self.settings.agent.tool_call_timeout_seconds}秒）",
            )
        except Exception as e:
            raise ToolExecutionError(
                tool_name,
                f"工具执行异常: {str(e)}",
                original_error=e,
            )

        # 6. 计算执行时间
        execution_time = (datetime.now() - start_time).total_seconds()

        # 7. 封装结果
        return {
            "success": True,
            "tool_name": tool_name,
            "result": result,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat(),
        }

    def _validate_arguments(
        self, schema: ToolSchema, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        验证工具参数

        根据 Schema 验证参数类型和必填项。
        """
        validated = {}
        properties = schema.parameters.get("properties", {})
        required = schema.parameters.get("required", [])

        # 检查必填参数
        for param_name in required:
            if param_name not in arguments:
                raise ToolValidationError(
                    schema.name,
                    f"缺少必填参数: {param_name}",
                )

        # 验证参数类型
        for param_name, param_value in arguments.items():
            if param_name not in properties:
                logger.warning(
                    "unknown_parameter",
                    tool_name=schema.name,
                    param_name=param_name,
                )
                continue

            param_schema = properties[param_name]
            expected_type = param_schema.get("type")

            # 类型检查
            if not self._check_type(param_value, expected_type):
                raise ToolValidationError(
                    schema.name,
                    f"参数 '{param_name}' 类型错误: 期望 {expected_type}, "
                    f"实际 {type(param_value).__name__}",
                )

            # 枚举检查
            if "enum" in param_schema and param_value not in param_schema["enum"]:
                raise ToolValidationError(
                    schema.name,
                    f"参数 '{param_name}' 值无效: {param_value}, "
                    f"允许的值: {param_schema['enum']}",
                )

            validated[param_name] = param_value

        # 填充默认值
        for param_name, param_schema in properties.items():
            if param_name not in validated and "default" in param_schema:
                validated[param_name] = param_schema["default"]

        return validated

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值是否符合预期类型"""
        type_checkers = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int),
            "number": lambda v: isinstance(v, (int, float)),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }

        checker = type_checkers.get(expected_type)
        if checker:
            return checker(value)

        # 未知类型默认通过
        return True

    async def execute_batch(
        self,
        tool_calls: list[dict[str, Any]],
        parallel: bool = False,
    ) -> list[dict[str, Any]]:
        """
        批量执行工具调用

        Args:
            tool_calls: 工具调用列表，每个元素包含 tool_name 和 arguments
            parallel: 是否并行执行

        Returns:
            执行结果列表
        """
        if parallel:
            # 并行执行
            tasks = [
                self.execute(call["tool_name"], call.get("arguments", {}))
                for call in tool_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理异常
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "success": False,
                        "tool_name": tool_calls[i]["tool_name"],
                        "error": str(result),
                        "timestamp": datetime.now().isoformat(),
                    })
                else:
                    processed_results.append(result)

            return processed_results
        else:
            # 串行执行
            results = []
            for call in tool_calls:
                try:
                    result = await self.execute(
                        call["tool_name"],
                        call.get("arguments", {}),
                    )
                    results.append(result)
                except ToolExecutionError as e:
                    results.append({
                        "success": False,
                        "tool_name": call["tool_name"],
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    })

            return results
