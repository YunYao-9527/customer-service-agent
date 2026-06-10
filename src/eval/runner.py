"""
评测执行器

执行评测场景，收集指标，生成报告。
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.core import CustomerServiceAgent
from src.config import get_settings
from src.db.session import async_session_factory
from src.eval.metrics import EvalResult, MetricsCalculator, metrics_calculator

logger = structlog.get_logger()


class EvalScenario:
    """评测场景定义"""

    def __init__(self, config: dict[str, Any]):
        self.id: str = config["id"]
        self.name: str = config["name"]
        self.description: str = config.get("description", "")
        self.category: str = config.get("category", "general")

        # 初始状态
        self.initial_state: dict[str, Any] = config.get("initial_state", {})

        # 对话流程
        self.messages: list[dict[str, str]] = config.get("messages", [])

        # 预期结果
        self.expected: dict[str, Any] = config.get("expected", {})

        # 评测配置
        self.max_turns: int = config.get("max_turns", 20)
        self.timeout_seconds: int = config.get("timeout_seconds", 60)


class EvalRunner:
    """
    评测执行器

    执行评测场景，收集指标，生成报告。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.metrics_calculator = metrics_calculator
        self.scenarios: list[EvalScenario] = []
        self.results: list[EvalResult] = []

    def load_scenarios(self, scenarios_dir: str) -> None:
        """
        加载评测场景

        Args:
            scenarios_dir: 场景文件目录
        """
        scenarios_path = Path(scenarios_dir)
        if not scenarios_path.exists():
            logger.warning("scenarios_dir_not_found", path=scenarios_dir)
            return

        for scenario_file in scenarios_path.glob("*.yaml"):
            try:
                with open(scenario_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                if isinstance(config, dict):
                    scenario = EvalScenario(config)
                    self.scenarios.append(scenario)
                    logger.info("scenario_loaded", id=scenario.id, name=scenario.name)
                elif isinstance(config, list):
                    for item in config:
                        scenario = EvalScenario(item)
                        self.scenarios.append(scenario)
                        logger.info("scenario_loaded", id=scenario.id, name=scenario.name)

            except Exception as e:
                logger.error("scenario_load_failed", file=scenario_file.name, error=str(e))

        logger.info("scenarios_loaded", count=len(self.scenarios))

    async def run_scenario(
        self,
        scenario: EvalScenario,
        db: AsyncSession,
    ) -> EvalResult:
        """
        执行单个评测场景

        Args:
            scenario: 评测场景
            db: 数据库会话

        Returns:
            评测结果
        """
        start_time = datetime.now()
        session_id = f"eval_{scenario.id}_{start_time.timestamp()}"

        logger.info("scenario_running", scenario_id=scenario.id)

        # 创建 Agent
        agent = CustomerServiceAgent(session_id=session_id, db=db)

        errors = []
        tool_calls = []
        wrong_tool_calls = 0
        turns = 0

        try:
            # 执行对话
            for i, msg in enumerate(scenario.messages):
                if turns >= scenario.max_turns:
                    errors.append("超过最大轮次限制")
                    break

                user_message = msg.get("content", "")
                if not user_message:
                    continue

                # 处理消息
                result = await agent.process_message(user_message)
                turns += 1

                # 记录工具调用
                if "tool_result" in result:
                    tool_call = result["tool_result"]
                    tool_calls.append(tool_call)

                    # 检查工具调用是否正确
                    expected_tools = scenario.expected.get("expected_tools", [])
                    if expected_tools:
                        tool_name = tool_call.get("tool_name", "")
                        if i < len(expected_tools) and tool_name != expected_tools[i]:
                            wrong_tool_calls += 1

                # 检查是否出错
                if result.get("error"):
                    errors.append(result["error"])

                # 检查是否需要确认
                if result.get("requires_confirmation"):
                    # 自动确认（评测模式）
                    confirm_result = await agent.process_message("确认")
                    turns += 1

            # 检查最终状态
            state_summary = agent.get_state_summary()
            final_state = state_summary.get("current_state", "UNKNOWN")

            # 判断任务是否完成
            task_completed = final_state == "COMPLETED"

            # 检查状态是否正确
            expected_final_state = scenario.expected.get("final_state", "COMPLETED")
            state_correct = final_state == expected_final_state

            # 检查是否有策略违反
            policy_violated = False
            for tool_call in tool_calls:
                if not tool_call.get("success", True):
                    error_msg = tool_call.get("error", "")
                    if "策略" in error_msg or "规则" in error_msg or "不允许" in error_msg:
                        policy_violated = True
                        break

            # 计算延迟
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            # 估算成本（简化处理）
            cost_usd = turns * 0.01  # 假设每轮 $0.01

            return EvalResult(
                scenario_id=scenario.id,
                session_id=session_id,
                success=task_completed and state_correct and not policy_violated,
                task_completed=task_completed,
                state_correct=state_correct,
                policy_violated=policy_violated,
                wrong_tool_calls=wrong_tool_calls,
                total_tool_calls=len(tool_calls),
                turns=turns,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                errors=errors,
                details={
                    "final_state": final_state,
                    "tool_calls": tool_calls,
                    "state_summary": state_summary,
                },
            )

        except Exception as e:
            logger.error(
                "scenario_execution_failed",
                scenario_id=scenario.id,
                error=str(e),
                exc_info=True,
            )

            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            return EvalResult(
                scenario_id=scenario.id,
                session_id=session_id,
                success=False,
                task_completed=False,
                state_correct=False,
                policy_violated=False,
                wrong_tool_calls=0,
                total_tool_calls=0,
                turns=turns,
                latency_ms=latency_ms,
                cost_usd=0,
                errors=[str(e)],
            )

    async def run_all(
        self,
        scenarios: Optional[list[EvalScenario]] = None,
        max_concurrent: Optional[int] = None,
    ) -> list[EvalResult]:
        """
        执行所有评测场景

        Args:
            scenarios: 评测场景列表（默认使用已加载的场景）
            max_concurrent: 最大并发数

        Returns:
            评测结果列表
        """
        if scenarios is None:
            scenarios = self.scenarios

        if max_concurrent is None:
            max_concurrent = self.settings.eval.max_concurrent

        logger.info("eval_started", total_scenarios=len(scenarios))

        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(scenario: EvalScenario) -> EvalResult:
            async with semaphore:
                async with async_session_factory() as db:
                    return await self.run_scenario(scenario, db)

        # 并发执行
        tasks = [run_with_semaphore(s) for s in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "scenario_failed",
                    scenario_id=scenarios[i].id,
                    error=str(result),
                )
                processed_results.append(
                    EvalResult(
                        scenario_id=scenarios[i].id,
                        session_id="",
                        success=False,
                        task_completed=False,
                        state_correct=False,
                        policy_violated=False,
                        wrong_tool_calls=0,
                        total_tool_calls=0,
                        turns=0,
                        latency_ms=0,
                        cost_usd=0,
                        errors=[str(result)],
                    )
                )
            else:
                processed_results.append(result)

        self.results.extend(processed_results)

        logger.info(
            "eval_completed",
            total=len(processed_results),
            successful=sum(1 for r in processed_results if r.success),
        )

        return processed_results

    def generate_report(self, results: Optional[list[EvalResult]] = None) -> str:
        """
        生成评测报告

        Args:
            results: 评测结果列表

        Returns:
            评测报告
        """
        if results is None:
            results = self.results

        metrics = self.metrics_calculator.calculate_aggregate(results)
        return self.metrics_calculator.format_report(metrics)

    def save_results(
        self,
        results: list[EvalResult],
        output_dir: str,
    ) -> str:
        """
        保存评测结果

        Args:
            results: 评测结果列表
            output_dir: 输出目录

        Returns:
            保存的文件路径
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = output_path / f"eval_results_{timestamp}.json"

        # 转换为可序列化格式
        serializable_results = []
        for result in results:
            serializable_results.append({
                "scenario_id": result.scenario_id,
                "session_id": result.session_id,
                "success": result.success,
                "task_completed": result.task_completed,
                "state_correct": result.state_correct,
                "policy_violated": result.policy_violated,
                "wrong_tool_calls": result.wrong_tool_calls,
                "total_tool_calls": result.total_tool_calls,
                "turns": result.turns,
                "latency_ms": result.latency_ms,
                "cost_usd": result.cost_usd,
                "errors": result.errors,
                "timestamp": result.timestamp.isoformat(),
            })

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)

        logger.info("results_saved", path=str(results_file))

        # 保存报告
        report_file = output_path / f"eval_report_{timestamp}.md"
        report = self.generate_report(results)
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info("report_saved", path=str(report_file))

        return str(results_file)


# 全局评测执行器
eval_runner = EvalRunner()


async def main() -> None:
    """主函数（命令行运行）"""
    import argparse

    parser = argparse.ArgumentParser(description="运行 Agent 评测")
    parser.add_argument(
        "--scenarios",
        default="src/eval/scenarios",
        help="场景文件目录",
    )
    parser.add_argument(
        "--output",
        default="./eval_results",
        help="输出目录",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="最大并发数",
    )

    args = parser.parse_args()

    # 加载场景
    eval_runner.load_scenarios(args.scenarios)

    # 执行评测
    results = await eval_runner.run_all(max_concurrent=args.max_concurrent)

    # 保存结果
    eval_runner.save_results(results, args.output)

    # 打印报告
    print(eval_runner.generate_report(results))


if __name__ == "__main__":
    asyncio.run(main())
