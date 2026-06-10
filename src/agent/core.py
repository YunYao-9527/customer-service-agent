"""
Agent 核心模块

集成状态机、工具系统、LLM 调用、记忆管理和安全防护，
提供完整的智能客服对话能力。
"""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.guardrails import guardrails
from src.agent.llm import LLMClient, LLMResponse, llm_client
from src.agent.memory import ConversationMemory, memory_manager
from src.agent.state import AgentState, AgentStateMachine, ConversationContext
from src.config import get_settings
from src.tools.builtin import (
    cancel_order,
    freeze_account,
    get_account,
    get_logistics,
    get_order,
    get_user,
    get_user_orders,
    process_refund,
    request_refund,
    unfreeze_account,
    update_logistics_address,
    approve_refund,
    verify_user_identity,
)
from src.tools.executor import ToolExecutor
from src.tools.registry import tool_registry

logger = structlog.get_logger()

# 系统提示词
SYSTEM_PROMPT = """你是一个专业的电商客服助手。你的职责是帮助用户解决订单、退款、物流、账户等相关问题。

## 你的能力

1. **订单管理**：查询订单详情、取消订单
2. **退款服务**：申请退款、处理退款
3. **物流查询**：查询物流状态、修改收货地址
4. **账户服务**：查询账户信息、冻结/解冻账户

## 工作原则

1. **准确理解意图**：仔细分析用户需求，确认理解正确
2. **收集必要信息**：在执行操作前，确保收集到所有必要信息
3. **遵守业务规则**：严格按照业务规则执行操作
4. **风险操作确认**：高风险操作（如退款、冻结账户）前必须请求用户确认
5. **友好专业**：保持友好、专业的态度
6. **保护隐私**：不泄露用户的敏感信息

## 状态说明

- 当你在收集信息时，直接询问用户缺少的信息
- 当你需要用户确认时，明确说明操作内容和后果
- 当操作完成时，清晰地告知用户结果
- 当操作失败时，解释原因并提供替代方案

## 重要提示

- 不要编造信息，如果不确定请询问用户
- 高风险操作前必须获得用户明确确认
- 如果检测到异常行为，立即停止操作并报告
"""

# 意图识别提示词
INTENT_PROMPT = """请分析用户的消息，识别用户意图和提取关键信息。

用户消息：{user_message}

请以 JSON 格式返回：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0,
    "entities": {
        "order_no": "订单号（如有）",
        "user_id": "用户ID（如有）",
        "reason": "原因（如有）",
        "amount": "金额（如有）",
        "address": "地址（如有）"
    },
    "missing_info": ["缺失的必要信息列表"],
    "requires_confirmation": true/false
}

意图类型包括：
- query_order: 查询订单
- cancel_order: 取消订单
- request_refund: 申请退款
- query_logistics: 查询物流
- update_address: 修改地址
- query_account: 查询账户
- freeze_account: 冻结账户
- unfreeze_account: 解冻账户
- general_inquiry: 一般咨询
- greeting: 问候
- complaint: 投诉
"""


class CustomerServiceAgent:
    """
    智能客服 Agent

    核心功能：
    1. 多轮对话管理
    2. 意图识别和信息收集
    3. 业务规则检查
    4. 工具调用执行
    5. 安全防护
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.db = db
        self.settings = get_settings()

        # 初始化组件
        self.state_machine = AgentStateMachine(self.session_id)
        self.memory = memory_manager.get_memory(self.session_id)
        self.llm = llm_client
        self.tool_executor = ToolExecutor(db) if db else None

        # 当前用户 ID
        self._user_id: Optional[int] = None

    async def process_message(self, user_message: str) -> dict[str, Any]:
        """
        处理用户消息

        Args:
            user_message: 用户消息

        Returns:
            处理结果，包含回复内容和操作结果
        """
        start_time = datetime.now()

        # 1. 安全检查
        safety_check = guardrails.check_input(user_message)
        if not safety_check["safe"]:
            logger.warning(
                "unsafe_input_detected",
                session_id=self.session_id,
                injection=safety_check["injection"],
            )
            return {
                "response": "抱歉，您的消息中包含不安全的内容，请重新描述您的需求。",
                "state": self.state_machine.current_state.value,
                "safety_blocked": True,
            }

        # 2. 记录用户消息
        await self.memory.add_message("user", user_message)
        self.state_machine.add_message("user", user_message)

        # 3. 根据当前状态处理消息
        try:
            if self.state_machine.current_state == AgentState.INIT:
                response = await self._handle_init(user_message)
            elif self.state_machine.current_state == AgentState.INTENT_RECOGNITION:
                response = await self._handle_intent_recognition(user_message)
            elif self.state_machine.current_state == AgentState.INFO_COLLECTION:
                response = await self._handle_info_collection(user_message)
            elif self.state_machine.current_state == AgentState.USER_CONFIRMATION:
                response = await self._handle_user_confirmation(user_message)
            else:
                response = await self._handle_general(user_message)
        except Exception as e:
            logger.error(
                "message_processing_error",
                session_id=self.session_id,
                error=str(e),
                exc_info=True,
            )
            response = {
                "response": "抱歉，处理您的消息时出现了错误，请稍后重试或联系人工客服。",
                "state": self.state_machine.current_state.value,
                "error": str(e),
            }

        # 4. 记录助手回复
        await self.memory.add_message("assistant", response.get("response", ""))
        self.state_machine.add_message("assistant", response.get("response", ""))

        # 5. 计算处理时间
        processing_time = (datetime.now() - start_time).total_seconds()
        response["processing_time"] = processing_time

        return response

    async def _handle_init(self, user_message: str) -> dict[str, Any]:
        """处理初始状态"""
        # 转换到意图识别状态
        self.state_machine.transition_to(AgentState.INTENT_RECOGNITION)

        # 识别意图
        return await self._handle_intent_recognition(user_message)

    async def _handle_intent_recognition(self, user_message: str) -> dict[str, Any]:
        """处理意图识别状态"""
        # 使用 LLM 识别意图
        intent_result = await self._recognize_intent(user_message)

        intent = intent_result.get("intent", "general_inquiry")
        entities = intent_result.get("entities", {})
        missing_info = intent_result.get("missing_info", [])
        requires_confirmation = intent_result.get("requires_confirmation", False)

        # 更新上下文
        self.state_machine.context.intent = intent
        self.state_machine.context.collected_info.update(entities)
        self.state_machine.context.missing_info = missing_info

        # 根据意图处理
        if intent == "greeting":
            return {
                "response": "您好！我是电商客服助手，请问有什么可以帮您的？",
                "state": self.state_machine.current_state.value,
            }

        if intent == "general_inquiry":
            # 使用 LLM 生成回复
            response = await self._generate_response(user_message)
            return {
                "response": response,
                "state": self.state_machine.current_state.value,
            }

        # 业务意图处理
        if missing_info:
            # 需要收集更多信息
            self.state_machine.transition_to(AgentState.INFO_COLLECTION)
            return await self._ask_for_info(missing_info)

        if requires_confirmation:
            # 需要用户确认
            self.state_machine.transition_to(AgentState.USER_CONFIRMATION)
            return await self._ask_for_confirmation(intent, entities)

        # 直接执行
        self.state_machine.transition_to(AgentState.TOOL_EXECUTION)
        return await self._execute_intent(intent, entities)

    async def _handle_info_collection(self, user_message: str) -> dict[str, Any]:
        """处理信息收集状态"""
        # 从用户消息中提取信息
        extracted = await self._extract_info(user_message)

        # 更新已收集的信息
        for key, value in extracted.items():
            if value:
                self.state_machine.context.collected_info[key] = value

        # 更新缺失信息列表
        remaining_missing = []
        for info in self.state_machine.context.missing_info:
            if info not in self.state_machine.context.collected_info:
                remaining_missing.append(info)

        self.state_machine.context.missing_info = remaining_missing

        if remaining_missing:
            # 继续收集
            return await self._ask_for_info(remaining_missing)

        # 信息收集完成，检查是否需要确认
        intent = self.state_machine.context.intent
        if intent in ["cancel_order", "request_refund", "freeze_account"]:
            self.state_machine.transition_to(AgentState.USER_CONFIRMATION)
            return await self._ask_for_confirmation(
                intent,
                self.state_machine.context.collected_info,
            )

        # 直接执行
        self.state_machine.transition_to(AgentState.TOOL_EXECUTION)
        return await self._execute_intent(
            intent,
            self.state_machine.context.collected_info,
        )

    async def _handle_user_confirmation(self, user_message: str) -> dict[str, Any]:
        """处理用户确认状态"""
        # 判断用户是否确认
        confirmed = await self._check_confirmation(user_message)

        if confirmed:
            self.state_machine.context.user_confirmed = True
            self.state_machine.transition_to(AgentState.TOOL_EXECUTION)
            return await self._execute_intent(
                self.state_machine.context.intent,
                self.state_machine.context.collected_info,
            )
        else:
            # 用户取消，回到初始状态
            self.state_machine.transition_to(AgentState.INIT)
            return {
                "response": "好的，已取消操作。请问还有其他可以帮您的吗？",
                "state": self.state_machine.current_state.value,
            }

    async def _handle_general(self, user_message: str) -> dict[str, Any]:
        """处理其他状态"""
        response = await self._generate_response(user_message)
        return {
            "response": response,
            "state": self.state_machine.current_state.value,
        }

    async def _recognize_intent(self, user_message: str) -> dict[str, Any]:
        """使用 LLM 识别用户意图"""
        prompt = INTENT_PROMPT.format(user_message=user_message)

        messages = [
            {"role": "system", "content": "你是一个意图识别助手，请准确分析用户意图。"},
            {"role": "user", "content": prompt},
        ]

        response = await self.llm.chat(messages)

        try:
            # 解析 JSON 响应
            result = json.loads(response.content)
            return result
        except json.JSONDecodeError:
            # 默认返回一般咨询
            return {
                "intent": "general_inquiry",
                "confidence": 0.5,
                "entities": {},
                "missing_info": [],
                "requires_confirmation": False,
            }

    async def _extract_info(self, user_message: str) -> dict[str, Any]:
        """从用户消息中提取信息"""
        prompt = f"""请从用户消息中提取以下信息（如果有的话）：
- order_no: 订单号
- user_id: 用户ID
- reason: 原因
- amount: 金额
- address: 地址
- phone: 电话
- name: 姓名

用户消息：{user_message}

请以 JSON 格式返回提取到的信息，没有的字段返回 null。"""

        messages = [
            {"role": "system", "content": "你是一个信息提取助手，请准确提取用户提供的信息。"},
            {"role": "user", "content": prompt},
        ]

        response = await self.llm.chat(messages)

        try:
            result = json.loads(response.content)
            return {k: v for k, v in result.items() if v is not None}
        except json.JSONDecodeError:
            return {}

    async def _check_confirmation(self, user_message: str) -> bool:
        """检查用户是否确认"""
        prompt = f"""判断用户是否确认执行操作。

用户消息：{user_message}

如果用户确认（如"确认"、"是的"、"好的"、"同意"等），返回 true。
如果用户取消（如"取消"、"不要"、"算了"等），返回 false。

请只返回 true 或 false。"""

        messages = [
            {"role": "system", "content": "你是一个确认判断助手。"},
            {"role": "user", "content": prompt},
        ]

        response = await self.llm.chat(messages)

        return response.content.strip().lower() == "true"

    async def _ask_for_info(self, missing_info: list[str]) -> dict[str, Any]:
        """请求用户提供缺失信息"""
        info_mapping = {
            "order_no": "订单号",
            "user_id": "用户ID",
            "reason": "原因",
            "amount": "退款金额",
            "address": "收货地址",
            "phone": "联系电话",
            "name": "收件人姓名",
        }

        info_list = [info_mapping.get(info, info) for info in missing_info]
        info_str = "、".join(info_list)

        response = f"为了帮您处理，请提供以下信息：{info_str}"

        return {
            "response": response,
            "state": self.state_machine.current_state.value,
            "missing_info": missing_info,
        }

    async def _ask_for_confirmation(
        self, intent: str, entities: dict[str, Any]
    ) -> dict[str, Any]:
        """请求用户确认操作"""
        intent_descriptions = {
            "cancel_order": f"取消订单 {entities.get('order_no', '')}",
            "request_refund": f"为订单 {entities.get('order_no', '')} 申请退款",
            "freeze_account": f"冻结用户 {entities.get('user_id', '')} 的账户",
            "unfreeze_account": f"解冻用户 {entities.get('user_id', '')} 的账户",
        }

        description = intent_descriptions.get(intent, intent)

        response = f"确认要执行以下操作吗？\n\n**{description}**\n\n请回复"确认"执行，或"取消"放弃。"

        return {
            "response": response,
            "state": self.state_machine.current_state.value,
            "requires_confirmation": True,
            "pending_action": intent,
        }

    async def _execute_intent(
        self, intent: str, entities: dict[str, Any]
    ) -> dict[str, Any]:
        """执行意图对应的操作"""
        self.state_machine.transition_to(AgentState.TOOL_EXECUTION)

        try:
            # 根据意图调用对应的工具
            tool_name, tool_args = self._map_intent_to_tool(intent, entities)

            if not tool_name:
                return {
                    "response": "抱歉，我无法处理这个请求。",
                    "state": self.state_machine.current_state.value,
                }

            # 执行工具
            if self.tool_executor:
                result = await self.tool_executor.execute(
                    tool_name=tool_name,
                    arguments=tool_args,
                    user_confirmed=self.state_machine.context.user_confirmed,
                )

                # 记录工具调用
                self.state_machine.add_tool_call(tool_name, tool_args, result)

                # 生成回复
                response = await self._generate_tool_response(intent, result)

                # 转换到完成状态
                self.state_machine.transition_to(AgentState.COMPLETED)

                return {
                    "response": response,
                    "state": self.state_machine.current_state.value,
                    "tool_result": result,
                }
            else:
                return {
                    "response": "系统错误：工具执行器未初始化",
                    "state": self.state_machine.current_state.value,
                    "error": "tool_executor_not_initialized",
                }

        except Exception as e:
            logger.error(
                "intent_execution_failed",
                session_id=self.session_id,
                intent=intent,
                error=str(e),
            )

            self.state_machine.transition_to(AgentState.FAILED)

            return {
                "response": f"抱歉，执行操作时出现错误：{str(e)}",
                "state": self.state_machine.current_state.value,
                "error": str(e),
            }

    def _map_intent_to_tool(
        self, intent: str, entities: dict[str, Any]
    ) -> tuple[Optional[str], dict[str, Any]]:
        """将意图映射到工具调用"""
        mappings = {
            "query_order": ("get_order", {"order_no": entities.get("order_no")}),
            "cancel_order": (
                "cancel_order",
                {
                    "order_no": entities.get("order_no"),
                    "reason": entities.get("reason", "用户请求取消"),
                },
            ),
            "request_refund": (
                "request_refund",
                {
                    "order_no": entities.get("order_no"),
                    "reason": entities.get("reason", "用户申请退款"),
                    "amount": entities.get("amount"),
                },
            ),
            "query_logistics": (
                "get_logistics",
                {"order_no": entities.get("order_no")},
            ),
            "update_address": (
                "update_logistics_address",
                {
                    "order_no": entities.get("order_no"),
                    "new_address": entities.get("address"),
                },
            ),
            "query_account": (
                "get_account",
                {"user_id": entities.get("user_id")},
            ),
            "freeze_account": (
                "freeze_account",
                {
                    "user_id": entities.get("user_id"),
                    "reason": entities.get("reason", "系统冻结"),
                },
            ),
            "unfreeze_account": (
                "unfreeze_account",
                {
                    "user_id": entities.get("user_id"),
                    "reason": entities.get("reason", "用户申请解冻"),
                },
            ),
        }

        mapping = mappings.get(intent)
        if mapping:
            tool_name, tool_args = mapping
            # 过滤掉 None 值
            tool_args = {k: v for k, v in tool_args.items() if v is not None}
            return tool_name, tool_args

        return None, {}

    async def _generate_response(self, user_message: str) -> str:
        """使用 LLM 生成回复"""
        # 获取对话历史
        history = await self.memory.get_context_messages(max_tokens=3000)

        # 构建消息
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)

        response = await self.llm.chat(messages)

        # 脱敏处理
        return guardrails.mask_output(response.content)

    async def _generate_tool_response(
        self, intent: str, tool_result: dict[str, Any]
    ) -> str:
        """根据工具结果生成回复"""
        # 获取对话历史
        history = await self.memory.get_context_messages(max_tokens=3000)

        # 构建提示
        prompt = f"""根据工具执行结果，生成用户友好的回复。

用户意图：{intent}
工具执行结果：{json.dumps(tool_result, ensure_ascii=False)}

请生成回复，要求：
1. 简洁明了
2. 包含关键信息
3. 友好专业
4. 如果有错误，解释原因并提供替代方案"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": prompt},
        ]

        response = await self.llm.chat(messages)

        # 脱敏处理
        return guardrails.mask_output(response.content)

    def get_state_summary(self) -> dict[str, Any]:
        """获取 Agent 状态摘要"""
        return self.state_machine.get_state_summary()
