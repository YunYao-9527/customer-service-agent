"""
数据库模型定义

定义电商系统的核心数据模型，包括订单、支付、退款、账户等。
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


# =============================================================================
# 枚举类型
# =============================================================================

class OrderStatus(str, enum.Enum):
    """订单状态"""
    PENDING = "pending"              # 待支付
    PAID = "paid"                    # 已支付
    PROCESSING = "processing"        # 处理中
    SHIPPED = "shipped"              # 已发货
    DELIVERED = "delivered"          # 已送达
    COMPLETED = "completed"          # 已完成
    CANCELLED = "cancelled"          # 已取消
    REFUNDING = "refunding"          # 退款中
    REFUNDED = "refunded"            # 已退款
    EXCHANGING = "exchanging"        # 换货中
    EXCHANGED = "exchanged"          # 已换货


class PaymentStatus(str, enum.Enum):
    """支付状态"""
    PENDING = "pending"              # 待支付
    SUCCESS = "success"              # 支付成功
    FAILED = "failed"                # 支付失败
    REFUNDED = "refunded"            # 已退款
    PARTIAL_REFUNDED = "partial_refunded"  # 部分退款


class RefundStatus(str, enum.Enum):
    """退款状态"""
    PENDING = "pending"              # 待审核
    APPROVED = "approved"            # 已批准
    PROCESSING = "processing"        # 处理中
    COMPLETED = "completed"          # 已完成
    REJECTED = "rejected"            # 已拒绝
    CANCELLED = "cancelled"          # 已取消


class AccountStatus(str, enum.Enum):
    """账户状态"""
    ACTIVE = "active"                # 正常
    FROZEN = "frozen"                # 冻结
    SUSPENDED = "suspended"          # 暂停
    CLOSED = "closed"                # 已关闭


class LogisticsStatus(str, enum.Enum):
    """物流状态"""
    PENDING = "pending"              # 待发货
    PICKED = "picked"                # 已取件
    IN_TRANSIT = "in_transit"        # 运输中
    OUT_FOR_DELIVERY = "out_for_delivery"  # 派送中
    DELIVERED = "delivered"          # 已签收
    RETURNED = "returned"            # 已退回


# =============================================================================
# 用户模型
# =============================================================================

class User(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    real_name: Mapped[Optional[str]] = mapped_column(String(50))
    id_card: Mapped[Optional[str]] = mapped_column(String(18))

    # 关系
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    account: Mapped[Optional["Account"]] = relationship(back_populates="user")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# =============================================================================
# 订单模型
# =============================================================================

class Order(Base):
    """订单表"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # 订单信息
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # 收货信息
    receiver_name: Mapped[str] = mapped_column(String(50), nullable=False)
    receiver_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    receiver_address: Mapped[str] = mapped_column(Text, nullable=False)

    # 备注
    remark: Mapped[Optional[str]] = mapped_column(Text)

    # 时间
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 关系
    user: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    payment: Mapped[Optional["Payment"]] = relationship(back_populates="order")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="order")
    logistics: Mapped[Optional["Logistics"]] = relationship(back_populates="order")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class OrderItem(Base):
    """订单商品项"""
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)

    # 商品信息
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # 关系
    order: Mapped["Order"] = relationship(back_populates="items")


# =============================================================================
# 支付模型
# =============================================================================

class Payment(Base):
    """支付表"""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)

    # 支付信息
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # alipay, wechat, card
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False
    )

    # 第三方支付信息
    third_party_no: Mapped[Optional[str]] = mapped_column(String(64))

    # 时间
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 关系
    order: Mapped["Order"] = relationship(back_populates="payment")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# =============================================================================
# 退款模型
# =============================================================================

class Refund(Base):
    """退款表"""
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    refund_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)

    # 退款信息
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus), default=RefundStatus.PENDING, nullable=False
    )

    # 审核信息
    reviewer: Mapped[Optional[str]] = mapped_column(String(50))
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 退款到账信息
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 关系
    order: Mapped["Order"] = relationship(back_populates="refunds")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# =============================================================================
# 账户模型
# =============================================================================

class Account(Base):
    """账户表"""
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # 账户信息
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False
    )
    member_level: Mapped[str] = mapped_column(String(20), default="normal")  # normal, silver, gold, platinum

    # 冻结信息
    frozen_reason: Mapped[Optional[str]] = mapped_column(Text)
    frozen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    frozen_by: Mapped[Optional[str]] = mapped_column(String(50))

    # 关系
    user: Mapped["User"] = relationship(back_populates="account")
    logs: Mapped[list["AccountLog"]] = relationship(back_populates="account")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AccountLog(Base):
    """账户操作日志"""
    __tablename__ = "account_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)

    # 操作信息
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # freeze, unfreeze, deduct, recharge
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str] = mapped_column(String(50), nullable=False)  # system, agent, admin

    # 关系
    account: Mapped["Account"] = relationship(back_populates="logs")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# =============================================================================
# 物流模型
# =============================================================================

class Logistics(Base):
    """物流表"""
    __tablename__ = "logistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), unique=True, nullable=False)

    # 物流信息
    tracking_no: Mapped[Optional[str]] = mapped_column(String(50))
    carrier: Mapped[Optional[str]] = mapped_column(String(50))  # sf, yd, zto, etc.
    status: Mapped[LogisticsStatus] = mapped_column(
        Enum(LogisticsStatus), default=LogisticsStatus.PENDING, nullable=False
    )

    # 地址信息
    sender_name: Mapped[str] = mapped_column(String(50), nullable=False)
    sender_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_address: Mapped[str] = mapped_column(Text, nullable=False)

    # 时间
    picked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 关系
    order: Mapped["Order"] = relationship(back_populates="logistics")
    traces: Mapped[list["LogisticsTrace"]] = relationship(back_populates="logistics")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class LogisticsTrace(Base):
    """物流轨迹"""
    __tablename__ = "logistics_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logistics_id: Mapped[int] = mapped_column(Integer, ForeignKey("logistics.id"), nullable=False)

    # 轨迹信息
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    trace_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 关系
    logistics: Mapped["Logistics"] = relationship(back_populates="traces")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# =============================================================================
# 对话历史模型
# =============================================================================

class Conversation(Base):
    """对话表"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))

    # 对话状态
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, abandoned
    current_state: Mapped[str] = mapped_column(String(50), default="INIT")
    intent: Mapped[Optional[str]] = mapped_column(String(100))

    # 关联信息
    related_order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orders.id"))

    # 统计
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)

    # 时间
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    # 消息信息
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 工具调用信息
    tool_calls: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Token 统计
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
