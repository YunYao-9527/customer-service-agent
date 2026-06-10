"""
用户操作工具

提供用户查询、身份验证等功能。
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.registry import tool
from src.tools.schema import RiskLevel
from simulation.ecommerce import EcommerceSimulator


@tool(
    name="get_user",
    description="查询用户信息。根据用户 ID 获取用户基本信息。",
    risk_level=RiskLevel.LOW,
    category="user",
)
async def get_user(user_id: int, db: AsyncSession) -> dict:
    """
    查询用户信息

    Args:
        user_id: 用户 ID
        db: 数据库会话

    Returns:
        用户信息
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.get_user(user_id)

    if not result:
        return {
            "success": False,
            "error": f"用户 {user_id} 不存在",
        }

    return {
        "success": True,
        "user": result,
    }


@tool(
    name="verify_user_identity",
    description="验证用户身份。用于高风险操作前的身份确认，需要提供姓名、手机号或身份证号中的至少一项。",
    risk_level=RiskLevel.LOW,
    category="user",
)
async def verify_user_identity(
    user_id: int,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    id_card: Optional[str] = None,
    db: AsyncSession = None,
) -> dict:
    """
    验证用户身份

    Args:
        user_id: 用户 ID
        name: 姓名（可选）
        phone: 手机号（可选）
        id_card: 身份证号（可选）
        db: 数据库会话

    Returns:
        验证结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.verify_user_identity(user_id, name, phone, id_card)

    return {
        "success": True,
        "verification": result,
    }
