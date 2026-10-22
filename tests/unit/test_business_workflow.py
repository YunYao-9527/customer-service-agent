from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.agent.core import CustomerServiceAgent
from src.db.models import Base, Order, OrderStatus, Refund
from src.rag.retriever import PolicyRetriever
from simulation.ecommerce import EcommerceSimulator


@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    import simulation.seed_data as seed
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'business.db').as_posix()}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async def initialized():
        return None
    monkeypatch.setattr(seed, "init_db", initialized)
    monkeypatch.setattr(seed, "async_session_factory", factory)
    await seed.seed_all()
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_refund_uses_confirmation_and_reaches_completed(db):
    agent = CustomerServiceAgent(db=db)
    async def recognize(message):
        return {'intent': 'request_refund', 'entities': {'order_no': 'ORD20240101001', 'reason': '不需要'}, 'missing_info': [], 'requires_confirmation': False}
    async def confirm(message):
        return True
    async def describe(intent, result):
        return '退款申请已提交'
    agent._recognize_intent = recognize
    agent._check_confirmation = confirm
    agent._generate_tool_response = describe
    first = await agent.process_message('申请退款')
    assert first['state'] == 'USER_CONFIRMATION'
    second = await agent.process_message('确认')
    assert second['state'] == 'COMPLETED', second
    assert second['tool_result']['result']['saga_status'] == 'completed'


@pytest.mark.asyncio
async def test_refund_compensates_a_post_commit_verification_failure(db, monkeypatch):
    simulator = EcommerceSimulator(db)
    before = await simulator.get_order('ORD20240101001')
    async def failed_verification(*args):
        raise RuntimeError('injected verification failure')
    monkeypatch.setattr(simulator, '_verify_refund', failed_verification)
    result = await simulator.request_refund('ORD20240101001', '不需要')
    assert result['success'] is False
    assert result['saga_status'] == 'compensated'
    after = await simulator.get_order('ORD20240101001')
    assert before['status'] == after['status']
    assert (await db.execute(select(Refund))).scalars().all() == []


@pytest.mark.asyncio
async def test_direct_refund_tool_cannot_bypass_policy(db):
    simulator = EcommerceSimulator(db)
    order = (await db.execute(select(Order).where(Order.order_no == 'ORD20240101001'))).scalar_one()
    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now() - timedelta(days=10)
    await db.commit()
    assert (await simulator.request_refund(order.order_no, '不需要'))['success'] is False
    assert (await simulator.request_refund(order.order_no, '不需要', -1))['success'] is False


def test_policy_search_and_expired_refund_are_not_allow_all():
    policy = PolicyRetriever()
    assert policy.retrieve('退款')
    assert not policy.check_rule('refund', {'order_status': 'delivered', 'days_since_delivery': 10})['allowed']
    assert policy.check_rule('refund', {'order_status': 'paid', 'amount': 5, 'paid_amount': 10})['allowed']
