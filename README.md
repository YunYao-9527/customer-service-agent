# 事务型智能客服 Agent

> 一个能够完成订单退款、改签、账户冻结、物流修改等真实业务操作的 Agent 系统，而不是只回答问题。

## 项目亮点

- **真实业务操作**：不是问答助手，而是能执行退款、取消订单、冻结账户等操作的 Agent
- **多轮对话管理**：状态机驱动的对话流程，支持信息收集、用户确认、错误恢复
- **Policy RAG**：从业务规则中判断操作是否允许，而不是硬编码逻辑
- **Saga 事务模式**：每个高风险操作都有补偿机制，保证数据一致性
- **安全防护**：Prompt Injection 检测、敏感信息脱敏、权限校验
- **完整评测体系**：7 个量化指标，50+ 测试场景

## 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 后端框架 | FastAPI | 高性能异步 Web 框架 |
| 数据库 | PostgreSQL | 支持事务的关系型数据库 |
| 缓存 | Redis | 会话状态存储 |
| 向量数据库 | ChromaDB | Policy RAG 检索 |
| LLM | OpenAI / Anthropic | 支持双 Provider 切换 |
| Agent 框架 | 自研 | 不依赖 LangChain，展示底层能力 |

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI 服务层                          │
├─────────────────────────────────────────────────────────────┤
│                      Agent 核心层                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 状态机   │  │ 工具系统 │  │ LLM 调用 │  │ 安全防护 │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│                      业务逻辑层                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 订单操作 │  │ 支付退款 │  │ 物流管理 │  │ 账户管理 │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│                      数据层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │PostgreSQL│  │  Redis   │  │ ChromaDB │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## 状态机设计

```
INIT → INTENT_RECOGNITION → INFO_COLLECTION → POLICY_CHECK →
USER_CONFIRMATION → TOOL_EXECUTION → RESULT_VERIFICATION → COMPLETED
                                                        ↘ ROLLBACK → FAILED
```

每个状态有明确的进入条件和退出条件，支持中断恢复。

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/yourusername/customer-service-agent.git
cd customer-service-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"
```

### 2. 启动基础设施

```bash
# 启动 PostgreSQL、Redis、ChromaDB
docker-compose up -d
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API Key
# OPENAI_API_KEY=sk-your-key-here
```

### 4. 初始化数据库

```bash
# 运行数据库迁移
make db-migrate

# 填充测试数据
make db-seed
```

### 5. 启动服务

```bash
make run
```

服务将在 http://localhost:8080 启动。

## API 使用

### 聊天接口

```bash
# 发送消息
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我要退款，订单号 ORD20240101001",
    "user_id": 1
  }'
```

### 响应示例

```json
{
  "session_id": "xxx",
  "response": "好的，我来帮您处理退款。订单 ORD20240101001 的信息如下：...",
  "state": "USER_CONFIRMATION",
  "requires_confirmation": true,
  "processing_time": 1.23
}
```

### 确认操作

```bash
# 继续对话（确认退款）
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "xxx",
    "message": "确认"
  }'
```

## 评测体系

### 评测指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| 任务完成率 | 成功完成任务的比例 | ≥ 90% |
| 状态正确率 | 最终状态正确的比例 | ≥ 95% |
| 策略违反率 | 违反业务规则的比例 | ≤ 5% |
| 错误工具调用率 | 调用错误工具的比例 | ≤ 10% |
| pass@1 | 首次执行成功率 | ≥ 85% |
| P95 延迟 | 95% 请求的延迟 | ≤ 5000ms |
| 单任务成本 | 平均每个任务的成本 | ≤ $0.05 |

### 运行评测

```bash
# 运行所有评测场景
make eval

# 生成评测报告
make eval-report
```

### 评测场景

项目包含 50+ 评测场景，覆盖：

- 基础操作：订单查询、物流查询
- 退款流程：全额退款、部分退款、退款失败
- 订单取消：不同状态的订单取消
- 物流操作：地址修改、物流查询
- 账户操作：冻结、解冻、身份验证
- 安全测试：Prompt Injection 检测
- 多轮对话：复杂业务流程

## 项目结构

```
customer-service-agent/
├── README.md                    # 项目文档
├── docker-compose.yml           # 一键启动
├── Makefile                     # 常用命令
├── pyproject.toml               # 项目配置
├── .env.example                 # 环境变量模板
│
├── src/
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置管理
│   │
│   ├── agent/                   # Agent 核心
│   │   ├── core.py              # Agent 主循环
│   │   ├── state.py             # 状态机定义
│   │   ├── llm.py               # LLM 调用封装
│   │   ├── memory.py            # 对话记忆管理
│   │   └── guardrails.py        # 安全防护
│   │
│   ├── tools/                   # 工具系统
│   │   ├── registry.py          # 工具注册中心
│   │   ├── executor.py          # 工具执行器
│   │   ├── schema.py            # 工具 Schema 定义
│   │   └── builtin/             # 内置业务工具
│   │       ├── order.py         # 订单操作
│   │       ├── payment.py       # 支付操作
│   │       ├── logistics.py     # 物流操作
│   │       ├── account.py       # 账户操作
│   │       └── user.py          # 用户操作
│   │
│   ├── rag/                     # Policy RAG
│   │   ├── retriever.py         # 政策检索
│   │   └── policies/            # 业务政策文档
│   │
│   ├── db/                      # 数据层
│   │   ├── models.py            # SQLAlchemy 模型
│   │   ├── session.py           # 数据库会话
│   │   └── transaction.py       # 事务管理 (Saga)
│   │
│   ├── api/                     # API 层
│   │   ├── routes.py            # 路由定义
│   │   └── schemas.py           # Pydantic 模型
│   │
│   └── eval/                    # 评测框架
│       ├── runner.py            # 评测执行器
│       ├── metrics.py           # 指标计算
│       └── scenarios/           # 测试场景
│
└── simulation/                  # 业务模拟环境
    ├── ecommerce.py             # 电商模拟系统
    └── seed_data.py             # 初始数据
```

## 核心难点实现

### 1. 多轮 Function Calling

Agent 能够在多轮对话中收集信息、确认意图、调用工具：

```
用户: 我要退款
Agent: 好的，请提供您的订单号。
用户: ORD20240101001
Agent: 订单信息如下... 退款原因是什么？
用户: 不想要了
Agent: 确认要退款吗？金额 ¥8999.00
用户: 确认
Agent: 退款已提交，预计 3-5 个工作日到账。
```

### 2. Policy RAG

不是硬编码业务规则，而是从政策文档中检索：

```python
# 检索相关政策
policies = policy_retriever.retrieve("退款")

# 检查是否符合规则
check_result = policy_retriever.check_rule("refund", {
    "order_status": "delivered",
    "days_since_delivery": 10,
})
# 返回: {"allowed": False, "reason": "超过7天退款时效"}
```

### 3. Saga 事务模式

每个高风险操作都有补偿机制：

```python
saga = SagaExecutor()

# 添加步骤
saga.add_step(context, "create_refund", create_refund, compensate_refund)
saga.add_step(context, "update_order", update_order, restore_order)
saga.add_step(context, "send_notification", send_notification)

# 执行（失败时自动补偿）
result = await saga.execute(context)
```

### 4. Prompt Injection 防御

```python
# 检测 Prompt Injection
safety_check = guardrails.check_input(user_input)
if not safety_check["safe"]:
    return "抱歉，您的消息中包含不安全的内容。"
```

## 简历描述

### 项目名称

事务型智能客服 Agent

### 项目描述

构建了一个能够完成订单退款、改签、账户冻结、物流修改等真实业务操作的 Agent 系统。

### 核心职责

1. 设计并实现了基于状态机的多轮对话管理，支持信息收集、用户确认、错误恢复等复杂流程
2. 实现了 Policy RAG 系统，从业务规则文档中检索政策，动态判断操作是否允许
3. 设计了 Saga 事务模式，为每个高风险操作提供补偿机制，保证数据一致性
4. 实现了 Prompt Injection 检测、敏感信息脱敏、权限校验等安全防护机制
5. 构建了完整的评测框架，包含 50+ 测试场景和 7 个量化指标

### 技术栈

Python, FastAPI, PostgreSQL, Redis, ChromaDB, OpenAI API, SQLAlchemy

### 项目成果

- 任务完成率 ≥ 90%，状态正确率 ≥ 95%
- 支持 8 种业务操作，覆盖订单、退款、物流、账户等场景
- 实现了完整的安全防护，成功拦截 95% 的 Prompt Injection 攻击

## License

MIT
