"""
物流操作工具

提供物流查询、地址修改等功能。
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.registry import tool
from src.tools.schema import RiskLevel
from simulation.ecommerce import EcommerceSimulator


@tool(
    name="get_logistics",
    description="查询物流信息。根据订单号获取物流状态和物流轨迹。",
    risk_level=RiskLevel.LOW,
    category="logistics",
)
async def get_logistics(order_no: str, db: AsyncSession) -> dict:
    """
    查询物流信息

    Args:
        order_no: 订单编号
        db: 数据库会话

    Returns:
        物流信息
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.get_logistics(order_no)

    if not result:
        return {
            "success": False,
            "error": f"订单 {order_no} 的物流信息不存在",
        }

    return {
        "success": True,
        "logistics": result,
    }


@tool(
    name="update_logistics_address",
    description="修改物流地址。修改订单的收货地址，只有未签收的订单可以修改地址。",
    risk_level=RiskLevel.MEDIUM,
    requires_confirmation=True,
    category="logistics",
)
async def update_logistics_address(
    order_no: str,
    new_address: str,
    new_phone: Optional[str] = None,
    new_name: Optional[str] = None,
    db: AsyncSession = None,
) -> dict:
    """
    修改物流地址

    Args:
        order_no: 订单编号
        new_address: 新的收货地址
        new_phone: 新的联系电话（可选）
        new_name: 新的收件人姓名（可选）
        db: 数据库会话

    Returns:
        地址修改结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.update_logistics_address(
        order_no, new_address, new_phone, new_name
    )

    return result
