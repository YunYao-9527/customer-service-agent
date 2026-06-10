"""
状态机单元测试
"""

import pytest

from src.agent.state import AgentState, AgentStateMachine


class TestAgentStateMachine:
    """Agent 状态机测试"""

    def test_initial_state(self):
        """测试初始状态"""
        sm = AgentStateMachine("test_session")
        assert sm.current_state == AgentState.INIT

    def test_valid_transition(self):
        """测试有效的状态转换"""
        sm = AgentStateMachine("test_session")

        # INIT -> INTENT_RECOGNITION
        assert sm.can_transition_to(AgentState.INTENT_RECOGNITION)
        assert sm.transition_to(AgentState.INTENT_RECOGNITION)
        assert sm.current_state == AgentState.INTENT_RECOGNITION

    def test_invalid_transition(self):
        """测试无效的状态转换"""
        sm = AgentStateMachine("test_session")

        # INIT -> COMPLETED (不允许)
        assert not sm.can_transition_to(AgentState.COMPLETED)
        assert not sm.transition_to(AgentState.COMPLETED)
        assert sm.current_state == AgentState.INIT

    def test_state_flow(self):
        """测试完整的状态流转"""
        sm = AgentStateMachine("test_session")

        # INIT -> INTENT_RECOGNITION
        sm.transition_to(AgentState.INTENT_RECOGNITION)

        # INTENT_RECOGNITION -> INFO_COLLECTION
        sm.transition_to(AgentState.INFO_COLLECTION)

        # INFO_COLLECTION -> POLICY_CHECK
        sm.transition_to(AgentState.POLICY_CHECK)

        # POLICY_CHECK -> USER_CONFIRMATION
        sm.transition_to(AgentState.USER_CONFIRMATION)

        # USER_CONFIRMATION -> TOOL_EXECUTION
        sm.transition_to(AgentState.TOOL_EXECUTION)

        # TOOL_EXECUTION -> RESULT_VERIFICATION
        sm.transition_to(AgentState.RESULT_VERIFICATION)

        # RESULT_VERIFICATION -> COMPLETED
        sm.transition_to(AgentState.COMPLETED)

        assert sm.current_state == AgentState.COMPLETED

    def test_rollback_flow(self):
        """测试回滚流程"""
        sm = AgentStateMachine("test_session")

        sm.transition_to(AgentState.INTENT_RECOGNITION)
        sm.transition_to(AgentState.POLICY_CHECK)
        sm.transition_to(AgentState.TOOL_EXECUTION)

        # TOOL_EXECUTION -> ROLLBACK
        sm.transition_to(AgentState.ROLLBACK)

        # ROLLBACK -> FAILED
        sm.transition_to(AgentState.FAILED)

        assert sm.current_state == AgentState.FAILED

    def test_add_message(self):
        """测试添加消息"""
        sm = AgentStateMachine("test_session")

        sm.add_message("user", "你好")
        sm.add_message("assistant", "您好！")

        assert sm.state_data.turn_count == 2
        assert len(sm.state_data.messages) == 2

    def test_add_tool_call(self):
        """测试记录工具调用"""
        sm = AgentStateMachine("test_session")

        sm.add_tool_call("get_order", {"order_no": "ORD001"}, {"success": True})

        assert sm.state_data.tool_call_count == 1
        assert len(sm.state_data.tool_calls) == 1

    def test_get_state_summary(self):
        """测试获取状态摘要"""
        sm = AgentStateMachine("test_session")
        sm.context.intent = "query_order"
        sm.context.order_no = "ORD001"

        summary = sm.get_state_summary()

        assert summary["session_id"] == "test_session"
        assert summary["current_state"] == "INIT"
        assert summary["intent"] == "query_order"
        assert summary["order_no"] == "ORD001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
