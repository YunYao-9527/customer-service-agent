"""
Agent 状态机

定义 Agent 的对话状态和状态转换逻辑。
"""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


class AgentState(str, enum.Enum):
    """
    Agent 对话状态

    状态流转：
    INIT → INTENT_RECOGNITION → INFO_COLLECTION → POLICY_CHECK →
    USER_CONFIRMATION → TOOL_EXECUTION → RESULT_VERIFICATION → COMPLETED
                                                            ↘ ROLLBACK → FAILED
    """
    # 初始状态
    INIT = "INIT"

    # 意图识别：理解用户想要做什么
    INTENT_RECOGNITION = "INTENT_RECOGNITION"

    # 信息收集：收集完成任务所需的缺失信息
    INFO_COLLECTION = "INFO_COLLECTION"

    # 策略检查：检查操作是否符合业务规则
    POLICY_CHECK = "POLICY_CHECK"

    # 用户确认：高风险操作前请求用户确认
    USER_CONFIRMATION = "USER_CONFIRMATION"

    # 工具执行：调用工具完成操作
    TOOL_EXECUTION = "TOOL_EXECUTION"

    # 结果验证：验证操作结果是否正确
    RESULT_VERIFICATION = "RESULT_VERIFICATION"

    # 操作完成
    COMPLETED = "COMPLETED"

    # 回滚：操作失败时回滚
    ROLLBACK = "ROLLBACK"

    # 失败
    FAILED = "FAILED"


# 状态转换规则
STATE_TRANSITIONS = {
    AgentState.INIT: [AgentState.INTENT_RECOGNITION],
    AgentState.INTENT_RECOGNITION: [
        AgentState.INFO_COLLECTION,
        AgentState.POLICY_CHECK,
        AgentState.COMPLETED,  # 简单问答不需要后续步骤
    ],
    AgentState.INFO_COLLECTION: [
        AgentState.INFO_COLLECTION,  # 可能需要多轮收集
        AgentState.POLICY_CHECK,
    ],
    AgentState.POLICY_CHECK: [
        AgentState.USER_CONFIRMATION,
        AgentState.TOOL_EXECUTION,
        AgentState.FAILED,  # 策略不允许
    ],
    AgentState.USER_CONFIRMATION: [
        AgentState.TOOL_EXECUTION,
        AgentState.INTENT_RECOGNITION,  # 用户改变主意
    ],
    AgentState.TOOL_EXECUTION: [
        AgentState.RESULT_VERIFICATION,
        AgentState.ROLLBACK,
    ],
    AgentState.RESULT_VERIFICATION: [
        AgentState.COMPLETED,
        AgentState.TOOL_EXECUTION,  # 需要重试
        AgentState.ROLLBACK,
    ],
    AgentState.ROLLBACK: [AgentState.FAILED],
    AgentState.COMPLETED: [],
    AgentState.FAILED: [],
}


@dataclass
class ConversationContext:
    """对话上下文"""
    # 用户信息
    user_id: Optional[int] = None
    user_name: Optional[str] = None

    # 意图信息
    intent: Optional[str] = None
    intent_confidence: float = 0.0

    # 业务信息
    order_no: Optional[str] = None
    refund_reason: Optional[str] = None
    refund_amount: Optional[float] = None
    new_address: Optional[str] = None

    # 收集的信息
    collected_info: dict[str, Any] = field(default_factory=dict)

    # 缺失的信息
    missing_info: list[str] = field(default_factory=list)

    # 策略检查结果
    policy_allowed: bool = True
    policy_reason: Optional[str] = None

    # 用户确认
    user_confirmed: bool = False

    # 工具调用结果
    tool_results: list[dict[str, Any]] = field(default_factory=list)

    # 错误信息
    errors: list[str] = field(default_factory=list)


@dataclass
class AgentStateData:
    """Agent 状态数据"""
    # 会话信息
    session_id: str
    current_state: AgentState = AgentState.INIT
    previous_state: Optional[AgentState] = None

    # 对话上下文
    context: ConversationContext = field(default_factory=ConversationContext)

    # 对话历史
    messages: list[dict[str, Any]] = field(default_factory=list)

    # 工具调用历史
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    # 统计信息
    turn_count: int = 0
    tool_call_count: int = 0
    error_count: int = 0

    # 时间戳
    started_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


class AgentStateMachine:
    """
    Agent 状态机

    管理 Agent 的状态转换，确保状态流转的合法性。
    """

    def __init__(self, session_id: str) -> None:
        self.state_data = AgentStateData(session_id=session_id)

    @property
    def current_state(self) -> AgentState:
        """当前状态"""
        return self.state_data.current_state

    @property
    def context(self) -> ConversationContext:
        """对话上下文"""
        return self.state_data.context

    def can_transition_to(self, new_state: AgentState) -> bool:
        """检查是否可以转换到新状态"""
        allowed_states = STATE_TRANSITIONS.get(self.state_data.current_state, [])
        return new_state in allowed_states

    def transition_to(self, new_state: AgentState) -> bool:
        """
        转换到新状态

        Returns:
            是否转换成功
        """
        if not self.can_transition_to(new_state):
            logger.warning(
                "invalid_state_transition",
                current=self.state_data.current_state.value,
                target=new_state.value,
            )
            return False

        old_state = self.state_data.current_state
        self.state_data.previous_state = old_state
        self.state_data.current_state = new_state
        self.state_data.last_updated = datetime.now()

        logger.info(
            "state_transition",
            session_id=self.state_data.session_id,
            from_state=old_state.value,
            to_state=new_state.value,
        )

        return True

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """添加消息到历史"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.state_data.messages.append(message)
        self.state_data.turn_count += 1
        self.state_data.last_updated = datetime.now()

    def add_tool_call(self, tool_name: str, arguments: dict, result: Any) -> None:
        """记录工具调用"""
        tool_call = {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        self.state_data.tool_calls.append(tool_call)
        self.state_data.tool_call_count += 1
        self.state_data.last_updated = datetime.now()

    def get_state_summary(self) -> dict[str, Any]:
        """获取状态摘要"""
        return {
            "session_id": self.state_data.session_id,
            "current_state": self.current_state.value,
            "intent": self.context.intent,
            "order_no": self.context.order_no,
            "turn_count": self.state_data.turn_count,
            "tool_call_count": self.state_data.tool_call_count,
            "error_count": self.state_data.error_count,
            "collected_info": self.context.collected_info,
            "missing_info": self.context.missing_info,
        }
