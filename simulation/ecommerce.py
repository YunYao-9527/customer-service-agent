"""
电商模拟系统

模拟真实的电商业务逻辑，包括订单、支付、退款、物流等操作。
用于 Agent 测试和评测，不依赖真实外部服务。
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    Account,
    AccountLog,
    AccountStatus,
    Logistics,
    LogisticsStatus,
    LogisticsTrace,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    User,
)

logger = structlog.get_logger()


def generate_no(prefix: str) -> str:
    """生成业务编号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = uuid.uuid4().hex[:8].upper()
    return f"{prefix}{timestamp}{random_suffix}"


class EcommerceSimulator:
    """
    电商模拟器

    提供完整的电商业务操作，包括：
    - 订单管理：查询、取消
    - 支付管理：支付、退款
    - 物流管理：查询、修改地址
    - 账户管理：查询、冻结、解冻
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # 订单操作
    # =========================================================================

    async def get_order(self, order_no: str) -> Optional[dict]:
        """查询订单详情"""
        result = await self.db.execute(
            select(Order).where(Order.order_no == order_no)
        )
        order = result.scalar_one_or_none()

        if not order:
            return None

        # 查询订单商品
        items_result = await self.db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()

        # 查询支付信息
        payment_result = await self.db.execute(
            select(Payment).where(Payment.order_id == order.id)
        )
        payment = payment_result.scalar_one_or_none()

        return {
            "order_no": order.order_no,
            "status": order.status.value,
            "total_amount": float(order.total_amount),
            "discount_amount": float(order.discount_amount),
            "shipping_fee": float(order.shipping_fee),
            "final_amount": float(order.final_amount),
            "receiver_name": order.receiver_name,
            "receiver_phone": order.receiver_phone,
            "receiver_address": order.receiver_address,
            "remark": order.remark,
            "items": [
                {
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "total_price": float(item.total_price),
                }
                for item in items
            ],
            "payment": {
                "method": payment.method,
                "status": payment.status.value,
                "amount": float(payment.amount),
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            } if payment else None,
            "created_at": order.created_at.isoformat(),
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
        }

    async def get_user_orders(self, user_id: int, limit: int = 10) -> list[dict]:
        """查询用户的订单列表"""
        result = await self.db.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        orders = result.scalars().all()

        return [
            {
                "order_no": order.order_no,
                "status": order.status.value,
                "final_amount": float(order.final_amount),
                "created_at": order.created_at.isoformat(),
            }
            for order in orders
        ]

    async def cancel_order(self, order_no: str, reason: str) -> dict:
        """
        取消订单

        规则：
        1. 只有待支付和已支付状态的订单可以取消
        2. 已支付的订单取消后自动触发退款
        """
        result = await self.db.execute(
            select(Order).where(Order.order_no == order_no)
        )
        order = result.scalar_one_or_none()

        if not order:
            return {"success": False, "error": "订单不存在"}

        if order.status not in [OrderStatus.PENDING, OrderStatus.PAID]:
            return {
                "success": False,
                "error": f"当前订单状态({order.status.value})不允许取消",
            }

        # 更新订单状态
        old_status = order.status
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now()
        order.remark = f"取消原因: {reason}"

        # 如果已支付，创建退款单
        refund_result = None
        if old_status == OrderStatus.PAID:
            payment_result = await self.db.execute(
                select(Payment).where(Payment.order_id == order.id)
            )
            payment = payment_result.scalar_one_or_none()

            if payment:
                refund = Refund(
                    refund_no=generate_no("RF"),
                    order_id=order.id,
                    amount=payment.amount,
                    reason=f"订单取消: {reason}",
                    status=RefundStatus.APPROVED,
                )
                self.db.add(refund)

                # 更新支付状态
                payment.status = PaymentStatus.REFUNDED

                refund_result = {
                    "refund_no": refund.refund_no,
                    "amount": float(refund.amount),
                }

        await self.db.commit()

        logger.info("order_cancelled", order_no=order_no, reason=reason)

        return {
            "success": True,
            "order_no": order_no,
            "previous_status": old_status.value,
            "refund": refund_result,
        }

    # =========================================================================
    # 退款操作
    # =========================================================================

    async def request_refund(
        self,
        order_no: str,
        reason: str,
        amount: Optional[float] = None,
    ) -> dict:
        """
        申请退款

        规则：
        1. 只有已支付、已发货、已送达状态的订单可以申请退款
        2. 退款金额不能超过订单金额
        3. 已发货的订单需要退货后才能退款
        """
        result = await self.db.execute(
            select(Order).where(Order.order_no == order_no)
        )
        order = result.scalar_one_or_none()

        if not order:
            return {"success": False, "error": "订单不存在"}

        if order.status not in [
            OrderStatus.PAID,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
        ]:
            return {
                "success": False,
                "error": f"当前订单状态({order.status.value})不允许退款",
            }

        # 查询支付信息
        payment_result = await self.db.execute(
            select(Payment).where(Payment.order_id == order.id)
        )
        payment = payment_result.scalar_one_or_none()

        if not payment:
            return {"success": False, "error": "未找到支付记录"}

        # 确定退款金额
        refund_amount = Decimal(str(amount)) if amount else payment.amount

        if refund_amount > payment.amount:
            return {
                "success": False,
                "error": f"退款金额({refund_amount})不能超过支付金额({payment.amount})",
            }

        # 检查是否已有退款
        existing_refund_result = await self.db.execute(
            select(Refund).where(
                Refund.order_id == order.id,
                Refund.status.in_([RefundStatus.PENDING, RefundStatus.APPROVED, RefundStatus.PROCESSING]),
            )
        )
        existing_refund = existing_refund_result.scalar_one_or_none()

        if existing_refund:
            return {
                "success": False,
                "error": f"已存在进行中的退款({existing_refund.refund_no})",
            }

        # 创建退款单
        refund = Refund(
            refund_no=generate_no("RF"),
            order_id=order.id,
            amount=refund_amount,
            reason=reason,
            status=RefundStatus.PENDING,
        )
        self.db.add(refund)

        # 更新订单状态
        order.status = OrderStatus.REFUNDING

        await self.db.commit()

        logger.info("refund_requested", order_no=order_no, refund_no=refund.refund_no)

        return {
            "success": True,
            "refund_no": refund.refund_no,
            "amount": float(refund_amount),
            "status": refund.status.value,
        }

    async def approve_refund(self, refund_no: str) -> dict:
        """批准退款"""
        result = await self.db.execute(
            select(Refund).where(Refund.refund_no == refund_no)
        )
        refund = result.scalar_one_or_none()

        if not refund:
            return {"success": False, "error": "退款单不存在"}

        if refund.status != RefundStatus.PENDING:
            return {
                "success": False,
                "error": f"当前退款状态({refund.status.value})不允许批准",
            }

        # 更新退款状态
        refund.status = RefundStatus.APPROVED
        refund.reviewed_at = datetime.now()
        refund.reviewer = "system"

        await self.db.commit()

        return {
            "success": True,
            "refund_no": refund_no,
            "status": refund.status.value,
        }

    async def process_refund(self, refund_no: str) -> dict:
        """
        处理退款（模拟退款到账）

        这个操作模拟实际的退款到账过程。
        """
        result = await self.db.execute(
            select(Refund).where(Refund.refund_no == refund_no)
        )
        refund = result.scalar_one_or_none()

        if not refund:
            return {"success": False, "error": "退款单不存在"}

        if refund.status != RefundStatus.APPROVED:
            return {
                "success": False,
                "error": f"当前退款状态({refund.status.value})不允许处理",
            }

        # 更新退款状态
        refund.status = RefundStatus.COMPLETED
        refund.refunded_at = datetime.now()

        # 查询订单
        order_result = await self.db.execute(
            select(Order).where(Order.id == refund.order_id)
        )
        order = order_result.scalar_one_or_none()

        if order:
            # 检查是否全额退款
            payment_result = await self.db.execute(
                select(Payment).where(Payment.order_id == order.id)
            )
            payment = payment_result.scalar_one_or_none()

            if payment and refund.amount >= payment.amount:
                order.status = OrderStatus.REFUNDED
            else:
                order.status = OrderStatus.REFUNDED  # 简化处理

        await self.db.commit()

        logger.info("refund_processed", refund_no=refund_no)

        return {
            "success": True,
            "refund_no": refund_no,
            "amount": float(refund.amount),
            "status": refund.status.value,
            "refunded_at": refund.refunded_at.isoformat(),
        }

    # =========================================================================
    # 物流操作
    # =========================================================================

    async def get_logistics(self, order_no: str) -> Optional[dict]:
        """查询物流信息"""
        order_result = await self.db.execute(
            select(Order).where(Order.order_no == order_no)
        )
        order = order_result.scalar_one_or_none()

        if not order:
            return None

        logistics_result = await self.db.execute(
            select(Logistics).where(Logistics.order_id == order.id)
        )
        logistics = logistics_result.scalar_one_or_none()

        if not logistics:
            return None

        # 查询物流轨迹
        traces_result = await self.db.execute(
            select(LogisticsTrace)
            .where(LogisticsTrace.logistics_id == logistics.id)
            .order_by(LogisticsTrace.trace_time.desc())
        )
        traces = traces_result.scalars().all()

        return {
            "tracking_no": logistics.tracking_no,
            "carrier": logistics.carrier,
            "status": logistics.status.value,
            "sender_name": logistics.sender_name,
            "sender_phone": logistics.sender_phone,
            "sender_address": logistics.sender_address,
            "traces": [
                {
                    "status": trace.status,
                    "location": trace.location,
                    "description": trace.description,
                    "time": trace.trace_time.isoformat(),
                }
                for trace in traces
            ],
            "picked_at": logistics.picked_at.isoformat() if logistics.picked_at else None,
            "delivered_at": logistics.delivered_at.isoformat() if logistics.delivered_at else None,
        }

    async def update_logistics_address(
        self,
        order_no: str,
        new_address: str,
        new_phone: Optional[str] = None,
        new_name: Optional[str] = None,
    ) -> dict:
        """
        修改物流地址

        规则：
        1. 只有未签收的订单可以修改地址
        2. 已派送中的订单修改地址可能产生额外费用
        """
        order_result = await self.db.execute(
            select(Order).where(Order.order_no == order_no)
        )
        order = order_result.scalar_one_or_none()

        if not order:
            return {"success": False, "error": "订单不存在"}

        logistics_result = await self.db.execute(
            select(Logistics).where(Logistics.order_id == order.id)
        )
        logistics = logistics_result.scalar_one_or_none()

        if not logistics:
            return {"success": False, "error": "物流信息不存在"}

        if logistics.status in [LogisticsStatus.DELIVERED, LogisticsStatus.RETURNED]:
            return {
                "success": False,
                "error": f"当前物流状态({logistics.status.value})不允许修改地址",
            }

        # 更新收货地址
        old_address = order.receiver_address
        order.receiver_address = new_address
        if new_phone:
            order.receiver_phone = new_phone
        if new_name:
            order.receiver_name = new_name

        # 添加物流轨迹
        trace = LogisticsTrace(
            logistics_id=logistics.id,
            status="address_updated",
            description=f"收货地址已更新: {old_address} -> {new_address}",
            trace_time=datetime.now(),
        )
        self.db.add(trace)

        await self.db.commit()

        logger.info("logistics_address_updated", order_no=order_no)

        return {
            "success": True,
            "order_no": order_no,
            "old_address": old_address,
            "new_address": new_address,
        }

    # =========================================================================
    # 账户操作
    # =========================================================================

    async def get_account(self, user_id: int) -> Optional[dict]:
        """查询账户信息"""
        result = await self.db.execute(
            select(Account).where(Account.user_id == user_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            return None

        return {
            "user_id": account.user_id,
            "balance": float(account.balance),
            "points": account.points,
            "status": account.status.value,
            "member_level": account.member_level,
            "frozen_reason": account.frozen_reason,
            "frozen_at": account.frozen_at.isoformat() if account.frozen_at else None,
        }

    async def freeze_account(
        self,
        user_id: int,
        reason: str,
        operator: str = "system",
    ) -> dict:
        """
        冻结账户

        规则：
        1. 只有正常状态的账户可以冻结
        2. 冻结后账户余额不可使用
        """
        result = await self.db.execute(
            select(Account).where(Account.user_id == user_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            return {"success": False, "error": "账户不存在"}

        if account.status != AccountStatus.ACTIVE:
            return {
                "success": False,
                "error": f"当前账户状态({account.status.value})不允许冻结",
            }

        # 更新账户状态
        account.status = AccountStatus.FROZEN
        account.frozen_reason = reason
        account.frozen_at = datetime.now()
        account.frozen_by = operator

        # 记录操作日志
        log = AccountLog(
            account_id=account.id,
            action="freeze",
            reason=reason,
            operator=operator,
        )
        self.db.add(log)

        await self.db.commit()

        logger.info("account_frozen", user_id=user_id, reason=reason)

        return {
            "success": True,
            "user_id": user_id,
            "status": account.status.value,
            "frozen_reason": reason,
        }

    async def unfreeze_account(
        self,
        user_id: int,
        reason: str,
        operator: str = "system",
    ) -> dict:
        """解冻账户"""
        result = await self.db.execute(
            select(Account).where(Account.user_id == user_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            return {"success": False, "error": "账户不存在"}

        if account.status != AccountStatus.FROZEN:
            return {
                "success": False,
                "error": f"当前账户状态({account.status.value})不需要解冻",
            }

        # 更新账户状态
        account.status = AccountStatus.ACTIVE
        account.frozen_reason = None
        account.frozen_at = None
        account.frozen_by = None

        # 记录操作日志
        log = AccountLog(
            account_id=account.id,
            action="unfreeze",
            reason=reason,
            operator=operator,
        )
        self.db.add(log)

        await self.db.commit()

        logger.info("account_unfrozen", user_id=user_id)

        return {
            "success": True,
            "user_id": user_id,
            "status": account.status.value,
        }

    # =========================================================================
    # 用户操作
    # =========================================================================

    async def get_user(self, user_id: int) -> Optional[dict]:
        """查询用户信息"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "real_name": user.real_name,
        }

    async def verify_user_identity(
        self,
        user_id: int,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        id_card: Optional[str] = None,
    ) -> dict:
        """
        验证用户身份

        用于高风险操作前的身份确认。
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"verified": False, "error": "用户不存在"}

        # 验证信息
        checks = []
        if name:
            checks.append(("姓名", user.real_name == name))
        if phone:
            checks.append(("手机号", user.phone == phone))
        if id_card:
            checks.append(("身份证", user.id_card == id_card))

        if not checks:
            return {"verified": False, "error": "请提供至少一项验证信息"}

        all_passed = all(passed for _, passed in checks)

        return {
            "verified": all_passed,
            "checks": [
                {"field": field, "passed": passed}
                for field, passed in checks
            ],
        }
