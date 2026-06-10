"""
工具 Schema 定义

定义工具的 Schema 结构，用于 LLM Function Calling。
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """工具风险等级"""
    LOW = "low"          # 只读操作，如查询
    MEDIUM = "medium"    # 一般操作，如修改地址
    HIGH = "high"        # 高风险操作，如退款、冻结账户


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[list[str]] = None
    default: Any = None


class ToolSchema(BaseModel):
    """工具 Schema 定义"""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema 格式
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    requires_verification: bool = False
    category: Optional[str] = None

    def to_openai_function(self) -> dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_anthropic_tool(self) -> dict[str, Any]:
        """转换为 Anthropic Tool Use 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


def extract_schema_from_function(func: Any) -> dict[str, Any]:
    """
    从函数签名提取 JSON Schema

    支持类型注解和 docstring 解析。
    """
    import inspect
    from typing import get_type_hints

    sig = inspect.signature(func)
    hints = get_type_hints(func)

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls", "db"):
            continue

        param_type = hints.get(param_name, str)
        param_info = _type_to_schema(param_type)

        # 从 docstring 获取描述
        param_info["description"] = _get_param_description(func, param_name)

        # 检查是否有默认值
        if param.default is not inspect.Parameter.empty:
            param_info["default"] = param.default
        else:
            required.append(param_name)

        properties[param_name] = param_info

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _type_to_schema(type_hint: Any) -> dict[str, Any]:
    """将 Python 类型转换为 JSON Schema 类型"""
    type_mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    # 处理基本类型
    if type_hint in type_mapping:
        return type_mapping[type_hint].copy()

    # 处理 Optional 类型
    origin = getattr(type_hint, "__origin__", None)
    if origin is type(None) or (hasattr(type_hint, "__args__") and type(None) in type_hint.__args__):
        # Optional[X] -> X 的 schema，但不是 required
        args = [a for a in type_hint.__args__ if a is not type(None)]
        if args:
            return _type_to_schema(args[0])

    # 处理 list[X]
    if origin is list:
        args = getattr(type_hint, "__args__", [])
        if args:
            return {
                "type": "array",
                "items": _type_to_schema(args[0]),
            }
        return {"type": "array"}

    # 处理 dict[K, V]
    if origin is dict:
        return {"type": "object"}

    # 默认返回 string
    return {"type": "string"}


def _get_param_description(func: Any, param_name: str) -> str:
    """从 docstring 获取参数描述"""
    import inspect
    import re

    doc = inspect.getdoc(func) or ""

    # 尝试解析 Google 风格 docstring
    args_match = re.search(r"(?:Args|Parameters):(.*?)(?:\n\n|\Z)", doc, re.DOTALL)
    if args_match:
        args_section = args_match.group(1)
        param_match = re.search(
            rf"{param_name}\s*(?:\(.*?\))?\s*:\s*(.*?)(?:\n\s+\w|\Z)",
            args_section,
            re.DOTALL,
        )
        if param_match:
            return param_match.group(1).strip()

    # 尝试解析 Args: 风格
    param_match = re.search(
        rf"{param_name}\s*[:\-]\s*(.*?)(?:\n|\Z)", doc
    )
    if param_match:
        return param_match.group(1).strip()

    return f"参数 {param_name}"
