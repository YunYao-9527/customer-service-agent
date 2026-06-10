"""
账户操作工具

提供账户查询、冻结、解冻等功能。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.registry import tool
from src.tools.schema import RiskLevel
from simulation.ecommerce import EcommerceSimulator


@tool(
    name="get_account",
    description="查询账户信息。根据用户 ID 获取账户余额、积分、状态等信息。",
    risk_level=RiskLevel.LOW,
    category="account",
)
async def get_account(user_id: int, db: AsyncSession) -> dict:
    """
    查询账户信息

    Args:
        user_id: 用户 ID
        db: 数据库会话

    Returns:
        账户信息
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.get_account(user_id)

    if not result:
        return {
            "success": False,
            "error": f"用户 {user_id} 的账户不存在",
        }

    return {
        "success": True,
        "account": result,
    }


@tool(
    name="freeze_account",
    description="冻结账户。冻结用户账户，冻结后账户余额不可使用。需要提供冻结原因。",
    risk_level=RiskLevel.HIGH,
    requires_confirmation=True,
    requires_verification=True,
    category="account",
)
async def freeze_account(
    user_id: int,
    reason: str,
    db: AsyncSession = None,
) -> dict:
    """
    冻结账户

    Args:
        user_id: 用户 ID
        reason: 冻结原因
        db: 数据库会话

    Returns:
        冻结结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.freeze_account(user_id, reason, operator="agent")

    return result


@tool(
    name="unfreeze_account",
    description="解冻账户。解冻被冻结的用户账户，恢复账户正常使用。",
    risk_level=RiskLevel.HIGH,
    requires_confirmation=True,
    requires_verification=True,
    category="account",
)
async def unfreeze_account(
    user_id: int,
    reason: str,
    db: AsyncSession = None,
) -> dict:
    """
    解冻账户

    Args:
        user_id: 用户 ID
        reason: 解冻原因
        db: 数据库会话

    Returns:
        解冻结果
    """
    simulator = EcommerceSimulator(db)
    result = await simulator.unfreeze_account(user_id, reason, operator="agent")

    return result
