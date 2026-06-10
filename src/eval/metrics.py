"""
评测指标计算模块

定义和计算 Agent 评测的各项指标。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class EvalResult:
    """单次评测结果"""
    scenario_id: str
    session_id: str
    success: bool
    task_completed: bool
    state_correct: bool
    policy_violated: bool
    wrong_tool_calls: int
    total_tool_calls: int
    turns: int
    latency_ms: float
    cost_usd: float
    errors: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AggregateMetrics:
    """聚合指标"""
    total_scenarios: int = 0
    successful_scenarios: int = 0
    failed_scenarios: int = 0

    # 任务完成率
    task_completion_rate: float = 0.0

    # 状态正确率
    state_correctness_rate: float = 0.0

    # 策略违反率
    policy_violation_rate: float = 0.0

    # 错误工具调用率
    wrong_tool_call_rate: float = 0.0

    # 平均指标
    avg_turns: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost_usd: float = 0.0

    # P95 延迟
    p95_latency_ms: float = 0.0

    # pass@1 稳定性
    pass_at_1: float = 0.0

    # 详细分布
    scenario_results: list[EvalResult] = field(default_factory=list)


class MetricsCalculator:
    """
    指标计算器

    计算各项评测指标：
    - 任务完成率
    - 数据库状态正确率
    - 业务规则违反率
    - 错误工具调用率
    - P95 延迟
    - 单任务成本
    """

    def calculate_single(self, result: EvalResult) -> dict[str, float]:
        """
        计算单次评测的指标

        Args:
            result: 评测结果

        Returns:
            指标字典
        """
        return {
            "success": 1.0 if result.success else 0.0,
            "task_completed": 1.0 if result.task_completed else 0.0,
            "state_correct": 1.0 if result.state_correct else 0.0,
            "policy_violated": 1.0 if result.policy_violated else 0.0,
            "wrong_tool_call_rate": (
                result.wrong_tool_calls / result.total_tool_calls
                if result.total_tool_calls > 0
                else 0.0
            ),
            "turns": result.turns,
            "latency_ms": result.latency_ms,
            "cost_usd": result.cost_usd,
        }

    def calculate_aggregate(self, results: list[EvalResult]) -> AggregateMetrics:
        """
        计算聚合指标

        Args:
            results: 评测结果列表

        Returns:
            聚合指标
        """
        if not results:
            return AggregateMetrics()

        metrics = AggregateMetrics()
        metrics.total_scenarios = len(results)
        metrics.scenario_results = results

        # 统计成功/失败
        metrics.successful_scenarios = sum(1 for r in results if r.success)
        metrics.failed_scenarios = metrics.total_scenarios - metrics.successful_scenarios

        # 任务完成率
        metrics.task_completion_rate = (
            sum(1 for r in results if r.task_completed) / metrics.total_scenarios
        )

        # 状态正确率
        metrics.state_correctness_rate = (
            sum(1 for r in results if r.state_correct) / metrics.total_scenarios
        )

        # 策略违反率
        metrics.policy_violation_rate = (
            sum(1 for r in results if r.policy_violated) / metrics.total_scenarios
        )

        # 错误工具调用率
        total_wrong = sum(r.wrong_tool_calls for r in results)
        total_calls = sum(r.total_tool_calls for r in results)
        metrics.wrong_tool_call_rate = total_wrong / total_calls if total_calls > 0 else 0.0

        # 平均指标
        metrics.avg_turns = sum(r.turns for r in results) / metrics.total_scenarios
        metrics.avg_latency_ms = sum(r.latency_ms for r in results) / metrics.total_scenarios
        metrics.avg_cost_usd = sum(r.cost_usd for r in results) / metrics.total_scenarios

        # P95 延迟
        latencies = sorted([r.latency_ms for r in results])
        p95_index = int(len(latencies) * 0.95)
        metrics.p95_latency_ms = latencies[min(p95_index, len(latencies) - 1)]

        # pass@1（首次执行成功率）
        metrics.pass_at_1 = metrics.successful_scenarios / metrics.total_scenarios

        return metrics

    def format_report(self, metrics: AggregateMetrics) -> str:
        """
        格式化评测报告

        Args:
            metrics: 聚合指标

        Returns:
            格式化的报告
        """
        report = f"""
# Agent 评测报告

## 总体指标

| 指标 | 值 |
|------|-----|
| 总场景数 | {metrics.total_scenarios} |
| 成功场景数 | {metrics.successful_scenarios} |
| 失败场景数 | {metrics.failed_scenarios} |

## 核心指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 任务完成率 | {metrics.task_completion_rate:.2%} | 成功完成任务的比例 |
| 状态正确率 | {metrics.state_correctness_rate:.2%} | 最终状态正确的比例 |
| 策略违反率 | {metrics.policy_violation_rate:.2%} | 违反业务规则的比例 |
| 错误工具调用率 | {metrics.wrong_tool_call_rate:.2%} | 调用错误工具的比例 |
| pass@1 | {metrics.pass_at_1:.2%} | 首次执行成功率 |

## 性能指标

| 指标 | 值 |
|------|-----|
| 平均轮次 | {metrics.avg_turns:.1f} |
| 平均延迟 | {metrics.avg_latency_ms:.0f}ms |
| P95 延迟 | {metrics.p95_latency_ms:.0f}ms |
| 平均成本 | ${metrics.avg_cost_usd:.4f} |

## 失败案例分析

"""
        # 添加失败案例详情
        failed_results = [r for r in metrics.scenario_results if not r.success]
        if failed_results:
            report += f"共 {len(failed_results)} 个失败案例：\n\n"
            for i, result in enumerate(failed_results[:5], 1):
                report += f"### 失败案例 {i}: {result.scenario_id}\n"
                report += f"- 错误: {', '.join(result.errors) if result.errors else '未知错误'}\n"
                report += f"- 轮次: {result.turns}\n"
                report += f"- 工具调用: {result.total_tool_calls}\n\n"
        else:
            report += "无失败案例。\n"

        return report


# 全局指标计算器
metrics_calculator = MetricsCalculator()
