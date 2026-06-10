# 评测体系文档

## 1. 评测目标

评测体系的目标是量化评估 Agent 的能力，包括：

- **任务完成能力**：Agent 能否正确完成用户请求的任务
- **状态管理能力**：Agent 能否维护正确的业务状态
- **规则遵守能力**：Agent 能否遵守业务规则
- **工具使用能力**：Agent 能否正确选择和使用工具
- **安全防护能力**：Agent 能否防御恶意攻击
- **性能表现**：Agent 的延迟和成本

## 2. 评测指标

### 2.1 核心指标

| 指标 | 英文名 | 计算公式 | 目标值 | 说明 |
|------|--------|----------|--------|------|
| 任务完成率 | Task Completion Rate | 成功任务数 / 总任务数 | ≥ 90% | Agent 能否完成用户请求的任务 |
| 状态正确率 | State Correctness Rate | 状态正确数 / 总任务数 | ≥ 95% | 最终业务状态是否正确 |
| 策略违反率 | Policy Violation Rate | 违反次数 / 总操作数 | ≤ 5% | 是否违反业务规则 |
| 错误工具调用率 | Wrong Tool Call Rate | 错误调用数 / 总调用数 | ≤ 10% | 是否选择了正确的工具 |
| pass@1 | Pass at 1 | 首次成功数 / 总任务数 | ≥ 85% | 首次执行成功率 |
| P95 延迟 | P95 Latency | 95 分位延迟 | ≤ 5000ms | 响应速度 |
| 单任务成本 | Cost per Task | 总成本 / 总任务数 | ≤ $0.05 | API 调用成本 |

### 2.2 辅助指标

| 指标 | 说明 |
|------|------|
| 平均对话轮次 | 完成任务所需的平均对话轮次 |
| 工具调用次数 | 每个任务的平均工具调用次数 |
| 信息收集效率 | 收集必要信息所需的轮次 |
| 错误恢复率 | 从错误中恢复的成功率 |
| 安全拦截率 | 成功拦截恶意攻击的比例 |

## 3. 评测场景

### 3.1 场景分类

```
scenarios/
├── refund.yaml          # 退款场景 (10+ 场景)
├── order.yaml           # 订单场景 (10+ 场景)
├── logistics.yaml       # 物流场景 (10+ 场景)
├── account.yaml         # 账户场景 (10+ 场景)
├── security.yaml        # 安全场景 (10+ 场景)
└── multi_turn.yaml      # 多轮对话场景 (10+ 场景)
```

### 3.2 场景结构

```yaml
- id: "refund_001"
  name: "简单退款 - 已支付订单"
  description: "用户申请退款已支付的订单"
  category: "refund"
  messages:
    - role: "user"
      content: "我要退款，订单号 ORD20240101001"
    - role: "user"
      content: "不想要了"
    - role: "user"
      content: "确认"
  expected:
    final_state: "COMPLETED"
    expected_tools: ["get_order", "request_refund"]
  max_turns: 10
```

### 3.3 场景示例

#### 退款场景

| ID | 名称 | 描述 | 预期结果 |
|----|------|------|----------|
| refund_001 | 简单退款 | 已支付订单退款 | 成功 |
| refund_002 | 缺少信息退款 | 未提供订单号 | 成功（收集信息后） |
| refund_003 | 退款被拒绝 | 已完成订单退款 | 失败 |
| refund_004 | 部分退款 | 部分金额退款 | 成功 |

#### 安全场景

| ID | 名称 | 描述 | 预期结果 |
|----|------|------|----------|
| security_001 | Prompt Injection | 尝试覆盖系统提示词 | 拦截 |
| security_002 | 角色劫持 | 尝试劫持 Agent 角色 | 拦截 |
| security_003 | 信息泄露 | 尝试获取系统提示词 | 拦截 |
| security_004 | 越狱尝试 | 尝试绕过安全限制 | 拦截 |

## 4. 评测流程

### 4.1 评测执行流程

```
1. 加载评测场景
2. 初始化评测环境（数据库、缓存）
3. 对每个场景：
   a. 创建 Agent 实例
   b. 依次发送消息
   c. 收集 Agent 响应
   d. 记录工具调用
   e. 检查最终状态
4. 计算评测指标
5. 生成评测报告
```

### 4.2 并发控制

```python
# 最大并发数
max_concurrent = 5

# 使用信号量控制并发
semaphore = asyncio.Semaphore(max_concurrent)

async def run_with_semaphore(scenario):
    async with semaphore:
        return await run_scenario(scenario)
```

## 5. 评测报告

### 5.1 报告格式

```markdown
# Agent 评测报告

## 总体指标

| 指标 | 值 |
|------|-----|
| 总场景数 | 50 |
| 成功场景数 | 45 |
| 失败场景数 | 5 |

## 核心指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 任务完成率 | 90.00% | 成功完成任务的比例 |
| 状态正确率 | 95.00% | 最终状态正确的比例 |
| 策略违反率 | 3.00% | 违反业务规则的比例 |
| 错误工具调用率 | 8.00% | 调用错误工具的比例 |
| pass@1 | 88.00% | 首次执行成功率 |

## 性能指标

| 指标 | 值 |
|------|-----|
| 平均轮次 | 4.5 |
| 平均延迟 | 2500ms |
| P95 延迟 | 4500ms |
| 平均成本 | $0.03 |

## 失败案例分析

### 失败案例 1: refund_003
- 错误: 退款被拒绝
- 原因: 已完成订单不允许退款
```

### 5.2 报告存储

```
eval_results/
├── eval_results_20240101_120000.json
├── eval_report_20240101_120000.md
├── eval_results_20240102_120000.json
└── eval_report_20240102_120000.md
```

## 6. 持续集成

### 6.1 CI 配置

```yaml
# .github/workflows/eval.yml
name: Agent Evaluation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run evaluation
        run: make eval
      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: eval-report
          path: eval_results/
```

### 6.2 发布门禁

```yaml
# 发布前必须通过评测
release:
  needs: eval
  if: success()
  steps:
    - name: Deploy
      run: make deploy
```

## 7. 最佳实践

### 7.1 场景设计原则

1. **覆盖全面**：覆盖所有业务场景和边界情况
2. **独立可测**：每个场景独立运行，不依赖其他场景
3. **预期明确**：明确预期结果，便于自动判断
4. **可复现**：使用固定数据，保证结果可复现

### 7.2 指标分析

1. **关注趋势**：关注指标的变化趋势，而非单次数值
2. **分析失败**：深入分析失败案例，找出根本原因
3. **对比基线**：与基线版本对比，量化改进效果
4. **分场景分析**：按场景类别分析，找出薄弱环节

### 7.3 持续改进

1. **定期评测**：每次代码变更后运行评测
2. **扩充场景**：根据实际问题扩充评测场景
3. **优化模型**：根据评测结果优化 Prompt 和模型
4. **监控告警**：设置指标告警，及时发现问题
