"""
事务管理模块

实现 Saga 模式，支持分布式事务、补偿操作和回滚。
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class SagaStepStatus(str, Enum):
    """Saga 步骤状态"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class SagaStatus(str, Enum):
    """Saga 整体状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Saga 步骤定义"""
    name: str
    action: Callable[..., Any]
    compensation: Optional[Callable[..., Any]] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    result: Any = None
    status: SagaStepStatus = SagaStepStatus.PENDING
    error: Optional[str] = None
    executed_at: Optional[datetime] = None


@dataclass
class SagaContext:
    """Saga 执行上下文"""
    saga_id: str
    steps: list[SagaStep] = field(default_factory=list)
    status: SagaStatus = SagaStatus.RUNNING
    current_step_index: int = 0
    metadata: dict = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class SagaExecutor:
    """
    Saga 执行器

    实现 Saga 模式，支持：
    1. 正向执行多个步骤
    2. 失败时自动补偿已完成的步骤
    3. 补偿失败时记录并告警
    """

    def __init__(self) -> None:
        self._sagas: dict[str, SagaContext] = {}

    def create_saga(self, saga_id: Optional[str] = None) -> SagaContext:
        """创建新的 Saga"""
        if saga_id is None:
            saga_id = str(uuid.uuid4())

        context = SagaContext(saga_id=saga_id)
        self._sagas[saga_id] = context
        return context

    def add_step(
        self,
        context: SagaContext,
        name: str,
        action: Callable[..., Any],
        compensation: Optional[Callable[..., Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> SagaContext:
        """添加 Saga 步骤"""
        step = SagaStep(
            name=name,
            action=action,
            compensation=compensation,
            args=args,
            kwargs=kwargs,
        )
        context.steps.append(step)
        return context

    async def execute(self, context: SagaContext) -> SagaContext:
        """执行 Saga"""
        logger.info(
            "saga_started",
            saga_id=context.saga_id,
            step_count=len(context.steps),
        )

        for i, step in enumerate(context.steps):
            context.current_step_index = i

            try:
                logger.info(
                    "saga_step_executing",
                    saga_id=context.saga_id,
                    step_name=step.name,
                    step_index=i,
                )

                # 执行步骤
                if asyncio.iscoroutinefunction(step.action):
                    result = await step.action(*step.args, **step.kwargs)
                else:
                    result = step.action(*step.args, **step.kwargs)

                step.result = result
                step.status = SagaStepStatus.COMPLETED
                step.executed_at = datetime.now()

                logger.info(
                    "saga_step_completed",
                    saga_id=context.saga_id,
                    step_name=step.name,
                )

            except Exception as e:
                step.status = SagaStepStatus.FAILED
                step.error = str(e)
                step.executed_at = datetime.now()

                logger.error(
                    "saga_step_failed",
                    saga_id=context.saga_id,
                    step_name=step.name,
                    error=str(e),
                )

                # 步骤失败，开始补偿
                context.status = SagaStatus.COMPENSATING
                await self._compensate(context, i)
                return context

        # 所有步骤执行成功
        context.status = SagaStatus.COMPLETED
        context.completed_at = datetime.now()

        logger.info(
            "saga_completed",
            saga_id=context.saga_id,
        )

        return context

    async def _compensate(self, context: SagaContext, failed_step_index: int) -> None:
        """补偿已完成的步骤（逆序执行）"""
        logger.info(
            "saga_compensating",
            saga_id=context.saga_id,
            failed_step_index=failed_step_index,
        )

        compensated_count = 0

        # 从失败步骤的前一个步骤开始，逆序补偿
        for i in range(failed_step_index - 1, -1, -1):
            step = context.steps[i]

            if step.status != SagaStepStatus.COMPLETED:
                continue

            if step.compensation is None:
                logger.warning(
                    "saga_step_no_compensation",
                    saga_id=context.saga_id,
                    step_name=step.name,
                )
                continue

            try:
                step.status = SagaStepStatus.COMPENSATING

                logger.info(
                    "saga_step_compensating",
                    saga_id=context.saga_id,
                    step_name=step.name,
                )

                # 执行补偿操作
                if asyncio.iscoroutinefunction(step.compensation):
                    await step.compensation(step.result)
                else:
                    step.compensation(step.result)

                step.status = SagaStepStatus.COMPENSATED
                compensated_count += 1

                logger.info(
                    "saga_step_compensated",
                    saga_id=context.saga_id,
                    step_name=step.name,
                )

            except Exception as e:
                logger.error(
                    "saga_compensation_failed",
                    saga_id=context.saga_id,
                    step_name=step.name,
                    error=str(e),
                )
                # 补偿失败需要人工介入，记录但继续
                # 在生产环境中，这里应该触发告警

        if compensated_count == failed_step_index:
            context.status = SagaStatus.COMPENSATED
        else:
            context.status = SagaStatus.FAILED

        context.completed_at = datetime.now()

        logger.info(
            "saga_compensation_completed",
            saga_id=context.saga_id,
            status=context.status.value,
            compensated_count=compensated_count,
        )

    def get_saga(self, saga_id: str) -> Optional[SagaContext]:
        """获取 Saga 上下文"""
        return self._sagas.get(saga_id)

    def get_saga_status(self, saga_id: str) -> Optional[SagaStatus]:
        """获取 Saga 状态"""
        context = self._sagas.get(saga_id)
        return context.status if context else None


# 全局 Saga 执行器
saga_executor = SagaExecutor()


class TransactionManager:
    """
    事务管理器

    封装数据库事务和 Saga 事务，提供统一的事务管理接口。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.saga = saga_executor

    async def execute_in_transaction(self, operations: list[Callable[..., Any]]) -> list[Any]:
        """在单个数据库事务中执行多个操作"""
        results = []
        try:
            for op in operations:
                if asyncio.iscoroutinefunction(op):
                    result = await op(self.db)
                else:
                    result = op(self.db)
                results.append(result)

            await self.db.commit()
            return results

        except Exception:
            await self.db.rollback()
            raise

    async def execute_saga(
        self,
        steps: list[dict[str, Any]],
        saga_id: Optional[str] = None,
    ) -> SagaContext:
        """执行 Saga 事务"""
        context = self.saga.create_saga(saga_id)

        for step_def in steps:
            self.saga.add_step(
                context=context,
                name=step_def["name"],
                action=step_def["action"],
                compensation=step_def.get("compensation"),
                *step_def.get("args", ()),
                **step_def.get("kwargs", {}),
            )

        return await self.saga.execute(context)
