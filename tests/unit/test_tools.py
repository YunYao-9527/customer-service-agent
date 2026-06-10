"""
工具系统单元测试
"""

import pytest

from src.tools.registry import ToolRegistry, tool
from src.tools.schema import RiskLevel, ToolSchema


class TestToolRegistry:
    """工具注册表测试"""

    def setup_method(self):
        """测试前准备"""
        self.registry = ToolRegistry()
        self.registry.clear()

    def test_register_tool(self):
        """测试注册工具"""
        @tool(
            name="test_tool",
            description="测试工具",
            risk_level=RiskLevel.LOW,
        )
        async def test_func(param1: str, param2: int = 10) -> dict:
            return {"result": True}

        assert "test_tool" in self.registry.get_all_tools()

    def test_get_tool(self):
        """测试获取工具"""
        @tool(
            name="get_test",
            description="获取测试",
            risk_level=RiskLevel.LOW,
        )
        async def get_test(id: int) -> dict:
            return {"id": id}

        tool_info = self.registry.get_tool("get_test")
        assert tool_info is not None

        schema, func = tool_info
        assert schema.name == "get_test"
        assert schema.risk_level == RiskLevel.LOW

    def test_get_tools_by_category(self):
        """测试按类别获取工具"""
        @tool(
            name="order_tool",
            description="订单工具",
            category="order",
        )
        async def order_func() -> dict:
            return {}

        @tool(
            name="payment_tool",
            description="支付工具",
            category="payment",
        )
        async def payment_func() -> dict:
            return {}

        order_tools = self.registry.get_tools_by_category("order")
        assert len(order_tools) == 1
        assert order_tools[0][0].name == "order_tool"

    def test_get_tools_by_risk_level(self):
        """测试按风险等级获取工具"""
        @tool(
            name="low_risk",
            description="低风险",
            risk_level=RiskLevel.LOW,
        )
        async def low_risk_func() -> dict:
            return {}

        @tool(
            name="high_risk",
            description="高风险",
            risk_level=RiskLevel.HIGH,
        )
        async def high_risk_func() -> dict:
            return {}

        high_risk_tools = self.registry.get_tools_by_risk_level(RiskLevel.HIGH)
        assert len(high_risk_tools) == 1
        assert high_risk_tools[0][0].name == "high_risk"

    def test_openai_functions_format(self):
        """测试 OpenAI Function Calling 格式"""
        @tool(
            name="test_func",
            description="测试函数",
        )
        async def test_func(param1: str, param2: int) -> dict:
            return {}

        functions = self.registry.get_openai_functions()
        assert len(functions) == 1

        func = functions[0]
        assert func["name"] == "test_func"
        assert "parameters" in func

    def test_anthropic_tools_format(self):
        """测试 Anthropic Tool Use 格式"""
        @tool(
            name="test_func",
            description="测试函数",
        )
        async def test_func(param1: str, param2: int) -> dict:
            return {}

        tools = self.registry.get_anthropic_tools()
        assert len(tools) == 1

        t = tools[0]
        assert t["name"] == "test_func"
        assert "input_schema" in t


class TestToolSchema:
    """工具 Schema 测试"""

    def test_schema_creation(self):
        """测试 Schema 创建"""
        schema = ToolSchema(
            name="test",
            description="测试",
            parameters={"type": "object", "properties": {}},
            risk_level=RiskLevel.LOW,
        )

        assert schema.name == "test"
        assert schema.risk_level == RiskLevel.LOW

    def test_to_openai_function(self):
        """测试转换为 OpenAI 格式"""
        schema = ToolSchema(
            name="test",
            description="测试",
            parameters={"type": "object", "properties": {}},
        )

        result = schema.to_openai_function()
        assert result["name"] == "test"
        assert result["description"] == "测试"

    def test_to_anthropic_tool(self):
        """测试转换为 Anthropic 格式"""
        schema = ToolSchema(
            name="test",
            description="测试",
            parameters={"type": "object", "properties": {}},
        )

        result = schema.to_anthropic_tool()
        assert result["name"] == "test"
        assert result["description"] == "测试"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
