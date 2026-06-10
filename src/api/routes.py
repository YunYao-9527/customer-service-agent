"""
API 路由定义

提供聊天、工具调用、对话管理等接口。
"""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.core import CustomerServiceAgent
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationSummary,
    ToolCallRequest,
    ToolCallResponse,
)
from src.db.session import get_db

logger = structlog.get_logger()

router = APIRouter()

# 会话存储（生产环境应使用 Redis）
sessions: dict[str, CustomerServiceAgent] = {}


def get_or_create_agent(
    session_id: str | None,
    db: AsyncSession,
) -> tuple[str, CustomerServiceAgent]:
    """获取或创建 Agent 实例"""
    if session_id and session_id in sessions:
        agent = sessions[session_id]
        # 更新数据库会话
        agent.db = db
        agent.tool_executor.db = db
        return session_id, agent

    # 创建新的 Agent
    new_session_id = session_id or str(uuid.uuid4())
    agent = CustomerServiceAgent(session_id=new_session_id, db=db)
    sessions[new_session_id] = agent

    return new_session_id, agent


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    处理聊天消息

    接收用户消息，返回助手回复。
    支持多轮对话，通过 session_id 维持会话状态。
    """
    try:
        session_id, agent = get_or_create_agent(request.session_id, db)

        # 设置用户 ID
        if request.user_id:
            agent._user_id = request.user_id
            agent.state_machine.context.user_id = request.user_id

        # 处理消息
        result = await agent.process_message(request.message)

        return ChatResponse(
            session_id=session_id,
            response=result.get("response", ""),
            state=result.get("state", "UNKNOWN"),
            tool_calls=result.get("tool_calls", []),
            requires_confirmation=result.get("requires_confirmation", False),
            missing_info=result.get("missing_info", []),
            processing_time=result.get("processing_time", 0),
        )

    except Exception as e:
        logger.error("chat_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(
    request: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
) -> ToolCallResponse:
    """
    直接调用工具

    用于测试或外部系统直接调用工具。
    """
    from src.tools.executor import ToolExecutor

    executor = ToolExecutor(db)

    try:
        result = await executor.execute(
            tool_name=request.tool_name,
            arguments=request.arguments,
            user_confirmed=request.user_confirmed,
        )

        return ToolCallResponse(
            success=result.get("success", False),
            tool_name=request.tool_name,
            result=result.get("result"),
            execution_time=result.get("execution_time", 0),
        )

    except Exception as e:
        logger.error("tool_call_error", tool_name=request.tool_name, error=str(e))
        return ToolCallResponse(
            success=False,
            tool_name=request.tool_name,
            error=str(e),
        )


@router.get("/sessions/{session_id}", response_model=ConversationSummary)
async def get_session(
    session_id: str,
) -> ConversationSummary:
    """获取会话信息"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    agent = sessions[session_id]
    summary = agent.get_state_summary()

    return ConversationSummary(
        session_id=session_id,
        user_id=agent._user_id,
        state=summary.get("current_state", "UNKNOWN"),
        intent=summary.get("intent"),
        turn_count=summary.get("turn_count", 0),
        tool_call_count=summary.get("tool_call_count", 0),
        started_at=agent.state_machine.state_data.started_at,
        last_updated=agent.state_machine.state_data.last_updated,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
) -> dict[str, str]:
    """删除会话"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    agent = sessions[session_id]
    await agent.memory.clear()
    del sessions[session_id]

    return {"message": "会话已删除"}


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    """列出所有会话"""
    result = []
    for session_id, agent in sessions.items():
        summary = agent.get_state_summary()
        result.append({
            "session_id": session_id,
            "user_id": agent._user_id,
            "state": summary.get("current_state"),
            "turn_count": summary.get("turn_count", 0),
        })

    return result


@router.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    """列出所有可用工具"""
    from src.tools.registry import tool_registry

    tools = tool_registry.get_schemas()
    return [
        {
            "name": t.name,
            "description": t.description,
            "risk_level": t.risk_level.value,
            "requires_confirmation": t.requires_confirmation,
            "category": t.category,
        }
        for t in tools
    ]
