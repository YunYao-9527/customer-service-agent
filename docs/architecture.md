# 架构设计文档

## 1. 系统概述

事务型智能客服 Agent 是一个能够完成真实业务操作的智能客服系统。与传统的问答助手不同，本系统能够：

- 理解用户真实意图
- 收集缺失信息
- 遵守复杂业务规则
- 调用多个工具完成操作
- 对高风险操作请求用户确认
- 处理工具失败和用户反悔
- 保证数据库最终状态正确

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│                    (Web/App/API)                                │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                      API 网关层                                  │
│                  (FastAPI + 中间件)                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 认证鉴权 │  │ 限流熔断 │  │ 日志追踪 │  │ CORS     │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Agent 核心层                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    状态机引擎                              │  │
│  │  INIT → INTENT → INFO → POLICY → CONFIRM → EXEC → DONE  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 意图识别 │  │ 信息提取 │  │ 策略检查 │  │ 结果验证 │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      能力层                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 工具系统 │  │ LLM 调用 │  │ Policy   │  │ 安全防护 │       │
│  │          │  │          │  │ RAG      │  │          │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      业务工具层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 订单操作 │  │ 支付退款 │  │ 物流管理 │  │ 账户管理 │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      数据层                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │PostgreSQL│  │  Redis   │  │ ChromaDB │  │ 文件存储 │       │
│  │ (事务)   │  │ (缓存)   │  │ (向量)   │  │ (文档)   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 核心模块设计

### 3.1 状态机引擎

状态机是 Agent 的核心，控制对话流程和状态转换。

#### 状态定义

| 状态 | 说明 | 允许的转换 |
|------|------|-----------|
| INIT | 初始状态 | INTENT_RECOGNITION |
| INTENT_RECOGNITION | 意图识别 | INFO_COLLECTION, POLICY_CHECK, COMPLETED |
| INFO_COLLECTION | 信息收集 | INFO_COLLECTION, POLICY_CHECK |
| POLICY_CHECK | 策略检查 | USER_CONFIRMATION, TOOL_EXECUTION, FAILED |
| USER_CONFIRMATION | 用户确认 | TOOL_EXECUTION, INTENT_RECOGNITION |
| TOOL_EXECUTION | 工具执行 | RESULT_VERIFICATION, ROLLBACK |
| RESULT_VERIFICATION | 结果验证 | COMPLETED, TOOL_EXECUTION, ROLLBACK |
| COMPLETED | 完成 | - |
| ROLLBACK | 回滚 | FAILED |
| FAILED | 失败 | - |

#### 状态转换规则

```python
STATE_TRANSITIONS = {
    AgentState.INIT: [AgentState.INTENT_RECOGNITION],
    AgentState.INTENT_RECOGNITION: [
        AgentState.INFO_COLLECTION,
        AgentState.POLICY_CHECK,
        AgentState.COMPLETED,
    ],
    # ...
}
```

### 3.2 工具系统

#### 工具注册

使用装饰器注册工具，自动提取 Schema：

```python
@tool(
    name="get_order",
    description="查询订单详情",
    risk_level=RiskLevel.LOW,
    category="order",
)
async def get_order(order_no: str, db: AsyncSession) -> dict:
    ...
```

#### 工具执行流程

```
1. 查找工具 → 2. 风险检查 → 3. 参数验证 → 4. 执行工具 → 5. 结果封装
```

#### 风险等级

| 等级 | 说明 | 是否需要确认 |
|------|------|-------------|
| LOW | 只读操作 | 否 |
| MEDIUM | 一般操作 | 视情况 |
| HIGH | 高风险操作 | 是 |

### 3.3 Policy RAG

#### 设计思路

不是硬编码业务规则，而是将政策文档化，使用 RAG 检索相关规则：

```
用户请求 → 检索相关政策 → 分析是否允许 → 返回结果
```

#### 政策文档结构

```markdown
# 退款政策

## 退款条件
- 已支付订单：7 天内可退款
- 已发货订单：需退货后退款
- 已完成订单：不可退款

## 退款流程
1. 申请退款
2. 审核退款
3. 退货寄回
4. 退款到账
```

### 3.4 Saga 事务模式

#### 设计思路

对于跨多个服务的操作，使用 Saga 模式保证数据一致性：

```
正向操作: A → B → C
补偿操作: C' → B' → A' (如果 C 失败)
```

#### 实现示例

```python
saga = SagaExecutor()

# 定义步骤和补偿
saga.add_step(context, "create_refund", create_refund, compensate_refund)
saga.add_step(context, "update_order", update_order, restore_order)
saga.add_step(context, "send_notification", send_notification)

# 执行
result = await saga.execute(context)

# 如果失败，自动执行补偿
if result.status == SagaStatus.COMPENSATED:
    print("操作已回滚")
```

### 3.5 安全防护

#### Prompt Injection 检测

```python
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now",
    r"reveal\s+(your|the)\s+(system|prompt|instructions)",
    # ...
]
```

#### 敏感信息脱敏

```python
# 手机号: 138****8001
# 邮箱: zha***@example.com
# 身份证: 110***********1234
```

## 4. 数据模型

### 4.1 核心实体

```
User (用户)
├── id, username, email, phone
├── real_name, id_card
└── has_many: Orders, Account

Order (订单)
├── id, order_no, status
├── total_amount, discount_amount, final_amount
├── receiver_name, receiver_phone, receiver_address
└── has_many: OrderItems, Payments, Refunds

OrderItem (订单商品)
├── product_id, product_name, product_sku
├── quantity, unit_price, total_price
└── belongs_to: Order

Payment (支付)
├── payment_no, amount, method, status
├── third_party_no
└── belongs_to: Order

Refund (退款)
├── refund_no, amount, reason, status
├── reviewer, review_note
└── belongs_to: Order

Account (账户)
├── balance, points, status, member_level
├── frozen_reason, frozen_at
└── belongs_to: User

Logistics (物流)
├── tracking_no, carrier, status
├── sender_name, sender_phone, sender_address
└── has_many: LogisticsTraces
```

### 4.2 状态枚举

```python
class OrderStatus(str, Enum):
    PENDING = "pending"          # 待支付
    PAID = "paid"                # 已支付
    PROCESSING = "processing"    # 处理中
    SHIPPED = "shipped"          # 已发货
    DELIVERED = "delivered"      # 已送达
    COMPLETED = "completed"      # 已完成
    CANCELLED = "cancelled"      # 已取消
    REFUNDING = "refunding"      # 退款中
    REFUNDED = "refunded"        # 已退款
```

## 5. API 设计

### 5.1 聊天接口

```
POST /api/v1/chat
```

请求：
```json
{
    "session_id": "xxx",
    "user_id": 1,
    "message": "我要退款"
}
```

响应：
```json
{
    "session_id": "xxx",
    "response": "好的，请提供您的订单号。",
    "state": "INFO_COLLECTION",
    "requires_confirmation": false,
    "processing_time": 1.23
}
```

### 5.2 工具调用接口

```
POST /api/v1/tools/call
```

请求：
```json
{
    "tool_name": "get_order",
    "arguments": {"order_no": "ORD20240101001"},
    "user_confirmed": false
}
```

## 6. 评测体系

### 6.1 评测指标

| 指标 | 计算公式 | 目标值 |
|------|----------|--------|
| 任务完成率 | 成功任务数 / 总任务数 | ≥ 90% |
| 状态正确率 | 状态正确数 / 总任务数 | ≥ 95% |
| 策略违反率 | 违反次数 / 总操作数 | ≤ 5% |
| 错误工具调用率 | 错误调用数 / 总调用数 | ≤ 10% |
| pass@1 | 首次成功数 / 总任务数 | ≥ 85% |
| P95 延迟 | 95 分位延迟 | ≤ 5000ms |
| 单任务成本 | 总成本 / 总任务数 | ≤ $0.05 |

### 6.2 评测场景

```
scenarios/
├── refund.yaml      # 退款场景
├── order.yaml       # 订单场景
├── logistics.yaml   # 物流场景
├── account.yaml     # 账户场景
├── security.yaml    # 安全场景
└── multi_turn.yaml  # 多轮对话场景
```

## 7. 部署架构

### 7.1 开发环境

```bash
docker-compose up -d  # 启动基础设施
make run              # 启动应用
```

### 7.2 生产环境

```
                    ┌─────────────┐
                    │   Nginx     │
                    │ (负载均衡)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌────▼────┐ ┌────▼────┐
        │  App 1    │ │ App 2   │ │ App 3   │
        │ (FastAPI) │ │(FastAPI)│ │(FastAPI)│
        └─────┬─────┘ └────┬────┘ └────┬────┘
              │            │            │
              └────────────┼────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │PostgreSQL│       │  Redis  │       │ ChromaDB│
   │ (主从)  │       │ (集群)  │       │         │
   └─────────┘       └─────────┘       └─────────┘
```

## 8. 性能优化

### 8.1 LLM 调用优化

- 使用流式响应减少首字延迟
- 缓存常见意图的识别结果
- 批量处理多个工具调用

### 8.2 数据库优化

- 使用连接池管理数据库连接
- 对常用查询添加索引
- 使用 Redis 缓存热点数据

### 8.3 并发处理

- 使用异步 IO 处理并发请求
- 对工具调用使用超时控制
- 实现限流和熔断机制
