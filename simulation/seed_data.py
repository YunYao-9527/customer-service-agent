"""
初始数据填充

创建测试用的初始数据，包括用户、订单、支付、物流等。
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import select

from src.db.models import (
    Account,
    AccountStatus,
    Logistics,
    LogisticsStatus,
    LogisticsTrace,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    User,
)
from src.db.session import async_session_factory, init_db

logger = structlog.get_logger()


# 测试用户数据
USERS = [
    {
        "username": "zhangsan",
        "email": "zhangsan@example.com",
        "phone": "13800138001",
        "real_name": "张三",
        "id_card": "110101199001011234",
    },
    {
        "username": "lisi",
        "email": "lisi@example.com",
        "phone": "13800138002",
        "real_name": "李四",
        "id_card": "110101199002021234",
    },
    {
        "username": "wangwu",
        "email": "wangwu@example.com",
        "phone": "13800138003",
        "real_name": "王五",
        "id_card": "110101199003031234",
    },
]

# 测试订单数据
ORDERS = [
    {
        "user_index": 0,
        "order_no": "ORD20240101001",
        "status": OrderStatus.PAID,
        "items": [
            {
                "product_id": 1001,
                "product_name": "iPhone 15 Pro 256GB 深空黑",
                "product_sku": "SKU-IPHONE15P-256-BK",
                "quantity": 1,
                "unit_price": Decimal("8999.00"),
                "total_price": Decimal("8999.00"),
            },
        ],
        "receiver_name": "张三",
        "receiver_phone": "13800138001",
        "receiver_address": "北京市朝阳区建国路100号",
        "payment_method": "alipay",
    },
    {
        "user_index": 0,
        "order_no": "ORD20240115002",
        "status": OrderStatus.DELIVERED,
        "items": [
            {
                "product_id": 2001,
                "product_name": "MacBook Air M3 16GB/512GB",
                "product_sku": "SKU-MBA-M3-16-512",
                "quantity": 1,
                "unit_price": Decimal("10999.00"),
                "total_price": Decimal("10999.00"),
            },
            {
                "product_id": 3001,
                "product_name": "USB-C 转接头",
                "product_sku": "SKU-USBC-ADAPTER",
                "quantity": 2,
                "unit_price": Decimal("99.00"),
                "total_price": Decimal("198.00"),
            },
        ],
        "receiver_name": "张三",
        "receiver_phone": "13800138001",
        "receiver_address": "北京市朝阳区建国路100号",
        "payment_method": "wechat",
    },
    {
        "user_index": 1,
        "order_no": "ORD20240201003",
        "status": OrderStatus.SHIPPED,
        "items": [
            {
                "product_id": 4001,
                "product_name": "AirPods Pro 2",
                "product_sku": "SKU-AIRPODS-PRO2",
                "quantity": 1,
                "unit_price": Decimal("1899.00"),
                "total_price": Decimal("1899.00"),
            },
        ],
        "receiver_name": "李四",
        "receiver_phone": "13800138002",
        "receiver_address": "上海市浦东新区陆家嘴100号",
        "payment_method": "alipay",
    },
    {
        "user_index": 2,
        "order_no": "ORD20240210004",
        "status": OrderStatus.COMPLETED,
        "items": [
            {
                "product_id": 5001,
                "product_name": "iPad Air 64GB",
                "product_sku": "SKU-IPADAIR-64",
                "quantity": 1,
                "unit_price": Decimal("4799.00"),
                "total_price": Decimal("4799.00"),
            },
        ],
        "receiver_name": "王五",
        "receiver_phone": "13800138003",
        "receiver_address": "广州市天河区珠江新城100号",
        "payment_method": "card",
    },
]


async def seed_users(session) -> list[User]:
    """创建测试用户"""
    users = []
    for user_data in USERS:
        user = User(**user_data)
        session.add(user)
        users.append(user)

    await session.flush()
    logger.info("users_created", count=len(users))
    return users


async def seed_accounts(session, users: list[User]) -> list[Account]:
    """创建测试账户"""
    accounts = []
    balance_map = [Decimal("5000.00"), Decimal("10000.00"), Decimal("2000.00")]
    points_map = [500, 1200, 300]
    level_map = ["silver", "gold", "normal"]

    for i, user in enumerate(users):
        account = Account(
            user_id=user.id,
            balance=balance_map[i],
            points=points_map[i],
            status=AccountStatus.ACTIVE,
            member_level=level_map[i],
        )
        session.add(account)
        accounts.append(account)

    await session.flush()
    logger.info("accounts_created", count=len(accounts))
    return accounts


async def seed_orders(session, users: list[User]) -> list[Order]:
    """创建测试订单"""
    orders = []
    base_time = datetime.now() - timedelta(days=30)

    for i, order_data in enumerate(ORDERS):
        user = users[order_data["user_index"]]

        # 计算订单金额
        total_amount = sum(item["total_price"] for item in order_data["items"])
        discount_amount = Decimal("0")
        shipping_fee = Decimal("0") if total_amount > 500 else Decimal("10.00")
        final_amount = total_amount - discount_amount + shipping_fee

        # 创建订单
        order = Order(
            order_no=order_data["order_no"],
            user_id=user.id,
            status=order_data["status"],
            total_amount=total_amount,
            discount_amount=discount_amount,
            shipping_fee=shipping_fee,
            final_amount=final_amount,
            receiver_name=order_data["receiver_name"],
            receiver_phone=order_data["receiver_phone"],
            receiver_address=order_data["receiver_address"],
        )

        # 设置时间
        order.created_at = base_time + timedelta(days=i * 5)
        if order_data["status"] in [
            OrderStatus.PAID,
            OrderStatus.PROCESSING,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        ]:
            order.paid_at = order.created_at + timedelta(hours=1)
        if order_data["status"] in [
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        ]:
            order.shipped_at = order.created_at + timedelta(days=2)
        if order_data["status"] in [OrderStatus.DELIVERED, OrderStatus.COMPLETED]:
            order.delivered_at = order.created_at + timedelta(days=5)
        if order_data["status"] == OrderStatus.COMPLETED:
            order.completed_at = order.created_at + timedelta(days=7)

        session.add(order)
        await session.flush()

        # 创建订单商品
        for item_data in order_data["items"]:
            item = OrderItem(
                order_id=order.id,
                product_id=item_data["product_id"],
                product_name=item_data["product_name"],
                product_sku=item_data["product_sku"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
            )
            session.add(item)

        # 创建支付记录
        if order.paid_at:
            payment = Payment(
                payment_no=f"PAY{order.order_no[3:]}",
                order_id=order.id,
                amount=final_amount,
                method=order_data["payment_method"],
                status=PaymentStatus.SUCCESS,
                paid_at=order.paid_at,
            )
            session.add(payment)

        orders.append(order)

    await session.flush()
    logger.info("orders_created", count=len(orders))
    return orders


async def seed_logistics(session, orders: list[Order]) -> None:
    """创建物流信息"""
    carriers = ["顺丰速运", "中通快递", "圆通速递"]

    for i, order in enumerate(orders):
        if order.status in [
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        ]:
            logistics = Logistics(
                order_id=order.id,
                tracking_no=f"SF{1000000000 + i}",
                carrier=carriers[i % len(carriers)],
                status=(
                    LogisticsStatus.DELIVERED
                    if order.status in [OrderStatus.DELIVERED, OrderStatus.COMPLETED]
                    else LogisticsStatus.IN_TRANSIT
                ),
                sender_name="苹果官方旗舰店",
                sender_phone="400-666-8800",
                sender_address="上海市浦东新区Apple Store",
                picked_at=order.shipped_at,
                delivered_at=order.delivered_at,
            )
            session.add(logistics)
            await session.flush()

            # 创建物流轨迹
            traces = [
                LogisticsTrace(
                    logistics_id=logistics.id,
                    status="picked",
                    location="上海市浦东新区",
                    description="快件已从苹果官方旗舰店取出",
                    trace_time=order.shipped_at,
                ),
                LogisticsTrace(
                    logistics_id=logistics.id,
                    status="in_transit",
                    location="上海市转运中心",
                    description="快件已到达上海市转运中心",
                    trace_time=order.shipped_at + timedelta(hours=6),
                ),
            ]

            if order.delivered_at:
                traces.append(
                    LogisticsTrace(
                        logistics_id=logistics.id,
                        status="delivered",
                        location=order.receiver_address,
                        description="快件已签收，签收人：本人",
                        trace_time=order.delivered_at,
                    )
                )

            for trace in traces:
                session.add(trace)


async def seed_all() -> None:
    """填充所有初始数据"""
    logger.info("seeding_started")

    # 初始化数据库
    await init_db()

    async with async_session_factory() as session:
        # 检查是否已有数据
        result = await session.execute(select(User))
        if result.scalar_one_or_none():
            logger.info("database_already_seeded")
            return

        # 填充数据
        users = await seed_users(session)
        await seed_accounts(session, users)
        orders = await seed_orders(session, users)
        await seed_logistics(session, orders)

        await session.commit()

    logger.info("seeding_completed")


if __name__ == "__main__":
    asyncio.run(seed_all())
