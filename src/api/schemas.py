"""
API Schema 定义

定义请求和响应的数据结构。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# 请求 Schema
# =============================================================================

class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: Optional[str] = Field(None, description="会话 ID，首次对话可不传")
    user_id: Optional[int] = Field(None, description="用户 ID")
    message: str = Field(..., description="用户消息")


class ToolCallRequest(BaseModel):
    """工具调用请求"""
    tool_name: str = Field(..., description="工具名称")
    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数")
    user_confirmed: bool = Field(False, description="用户是否已确认")


# =============================================================================
# 响应 Schema
# =============================================================================

class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str = Field(..., description="会话 ID")
    response: str = Field(..., description="助手回复")
    state: str = Field(..., description="当前状态")
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list, description="工具调用记录"
    )
    requires_confirmation: bool = Field(False, description="是否需要用户确认")
    missing_info: list[str] = Field(
        default_factory=list, description="缺失的信息"
    )
    processing_time: float = Field(0, description="处理时间（秒）")


class ToolCallResponse(BaseModel):
    """工具调用响应"""
    success: bool = Field(..., description="是否成功")
    tool_name: str = Field(..., description="工具名称")
    result: Any = Field(None, description="执行结果")
    error: Optional[str] = Field(None, description="错误信息")
    execution_time: float = Field(0, description="执行时间（秒）")


class ConversationSummary(BaseModel):
    """对话摘要"""
    session_id: str
    user_id: Optional[int]
    state: str
    intent: Optional[str]
    turn_count: int
    tool_call_count: int
    started_at: datetime
    last_updated: datetime


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    version: str
    env: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None
    status_code: int
