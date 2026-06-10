"""
订单操作工具

提供订单查询、取消等功能。
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.registry import tool
from src.tools.schema import RiskLevel
from simulation.ecommerce import EcommerceSimulator


@tool(
    name="get_order",
    description="查询订单详情。根据订单号获取订单的完整信息，包括商品、支付、物流状态等。",
    risk_level=RiskLevel.LOW,
    category="order",
)
async def get_order(order_no: str, db: AsyncSession) -> dict:
    """
    查询订单详情

    Args:
        order_no: 订单编号，如 ORD20240101001
        db: 数据库会话

    Returns:
        订单详情信息
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.get_order(order_no)

    if not result:
        return {
            "success": False,
            "error": f"订单 {order_no} 不存在",
        }

    return {
        "success": True,
        "order": result,
    }


@tool(
    name="get_user_orders",
    description="查询用户的订单列表。根据用户 ID 获取该用户的最近订单。",
    risk_level=RiskLevel.LOW,
    category="order",
)
async def get_user_orders(user_id: int, limit: int = 10, db: AsyncSession = None) -> dict:
    """
    查询用户的订单列表

    Args:
        user_id: 用户 ID
        limit: 返回的订单数量限制，默认 10
        db: 数据库会话

    Returns:
        用户的订单列表
    """
    simulator = EcommerceSimulator(db)
    orders = await simulator.get_user_orders(user_id, limit)

    return {
        "success": True,
        "user_id": user_id,
        "orders": orders,
        "count": len(orders),
    }


@tool(
    name="cancel_order",
    description="取消订单。取消指定的订单，如果已支付会自动触发退款。只有待支付和已支付状态的订单可以取消。",
    risk_level=RiskLevel.HIGH,
    requires_confirmation=True,
    category="order",
)
async def cancel_order(order_no: str, reason: str, db: AsyncSession) -> dict:
    """
    取消订单

    Args:
        order_no: 订单编号
        reason: 取消原因
        db: 数据库会话

    Returns:
        取消结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.cancel_order(order_no, reason)

    return result
