"""
支付和退款操作工具

提供退款申请、审核、处理等功能。
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.registry import tool
from src.tools.schema import RiskLevel
from simulation.ecommerce import EcommerceSimulator


@tool(
    name="request_refund",
    description="申请退款。为指定订单申请退款，需要提供退款原因。只有已支付、已发货、已送达状态的订单可以申请退款。",
    risk_level=RiskLevel.HIGH,
    requires_confirmation=True,
    category="payment",
)
async def request_refund(
    order_no: str,
    reason: str,
    amount: Optional[float] = None,
    db: AsyncSession = None,
) -> dict:
    """
    申请退款

    Args:
        order_no: 订单编号
        reason: 退款原因
        amount: 退款金额（可选，默认为全额退款）
        db: 数据库会话

    Returns:
        退款申请结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.request_refund(order_no, reason, amount)

    return result


@tool(
    name="approve_refund",
    description="批准退款。审核通过退款申请。只有待审核状态的退款可以批准。",
    risk_level=RiskLevel.HIGH,
    requires_confirmation=True,
    requires_verification=True,
    category="payment",
)
async def approve_refund(refund_no: str, db: AsyncSession) -> dict:
    """
    批准退款

    Args:
        refund_no: 退款单号
        db: 数据库会话

    Returns:
        审核结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.approve_refund(refund_no)

    return result


@tool(
    name="process_refund",
    description="处理退款（退款到账）。执行实际的退款操作，将退款金额返还到用户原支付账户。只有已批准的退款可以处理。",
    risk_level=RiskLevel.HIGH,
    requires_confirmation=True,
    requires_verification=True,
    category="payment",
)
async def process_refund(refund_no: str, db: AsyncSession) -> dict:
    """
    处理退款

    Args:
        refund_no: 退款单号
        db: 数据库会话

    Returns:
        退款处理结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.process_refund(refund_no)

    return result
