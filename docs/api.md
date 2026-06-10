# API 文档

## 1. 概述

事务型智能客服 Agent 提供 RESTful API 接口，支持多轮对话和工具调用。

### 基础信息

- **Base URL**: `http://localhost:8080/api/v1`
- **Content-Type**: `application/json`
- **认证方式**: 无（开发环境）

### 通用响应格式

**成功响应**:
```json
{
    "session_id": "xxx",
    "response": "助手回复",
    "state": "COMPLETED",
    "processing_time": 1.23
}
```

**错误响应**:
```json
{
    "error": "错误信息",
    "detail": "详细错误描述",
    "status_code": 500
}
```

## 2. 聊天接口

### 2.1 发送消息

处理用户消息，返回助手回复。

**请求**:
```
POST /api/v1/chat
```

**请求体**:
```json
{
    "session_id": "可选，会话ID",
    "user_id": 1,
    "message": "用户消息"
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 否 | 会话 ID，首次对话可不传 |
| user_id | int | 否 | 用户 ID |
| message | string | 是 | 用户消息 |

**响应**:
```json
{
    "session_id": "xxx",
    "response": "好的，请提供您的订单号。",
    "state": "INFO_COLLECTION",
    "tool_calls": [],
    "requires_confirmation": false,
    "missing_info": ["order_no"],
    "processing_time": 1.23
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |
| response | string | 助手回复 |
| state | string | 当前状态 |
| tool_calls | array | 工具调用记录 |
| requires_confirmation | bool | 是否需要用户确认 |
| missing_info | array | 缺失的信息 |
| processing_time | float | 处理时间（秒） |

**示例**:

```bash
# 首次对话
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我要退款",
    "user_id": 1
  }'

# 继续对话
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "xxx",
    "message": "订单号是 ORD20240101001"
  }'
```

## 3. 工具调用接口

### 3.1 直接调用工具

直接调用指定工具，用于测试或外部系统集成。

**请求**:
```
POST /api/v1/tools/call
```

**请求体**:
```json
{
    "tool_name": "get_order",
    "arguments": {
        "order_no": "ORD20240101001"
    },
    "user_confirmed": false
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tool_name | string | 是 | 工具名称 |
| arguments | object | 否 | 工具参数 |
| user_confirmed | bool | 否 | 用户是否已确认 |

**响应**:
```json
{
    "success": true,
    "tool_name": "get_order",
    "result": {
        "order_no": "ORD20240101001",
        "status": "paid",
        "total_amount": 8999.00
    },
    "execution_time": 0.05
}
```

**示例**:

```bash
# 查询订单
curl -X POST http://localhost:8080/api/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_order",
    "arguments": {"order_no": "ORD20240101001"}
  }'

# 取消订单（需要确认）
curl -X POST http://localhost:8080/api/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "cancel_order",
    "arguments": {
      "order_no": "ORD20240101001",
      "reason": "不想要了"
    },
    "user_confirmed": true
  }'
```

## 4. 会话管理接口

### 4.1 获取会话信息

**请求**:
```
GET /api/v1/sessions/{session_id}
```

**响应**:
```json
{
    "session_id": "xxx",
    "user_id": 1,
    "state": "COMPLETED",
    "intent": "request_refund",
    "turn_count": 5,
    "tool_call_count": 2,
    "started_at": "2024-01-01T12:00:00",
    "last_updated": "2024-01-01T12:01:30"
}
```

### 4.2 删除会话

**请求**:
```
DELETE /api/v1/sessions/{session_id}
```

**响应**:
```json
{
    "message": "会话已删除"
}
```

### 4.3 列出所有会话

**请求**:
```
GET /api/v1/sessions
```

**响应**:
```json
[
    {
        "session_id": "xxx",
        "user_id": 1,
        "state": "COMPLETED",
        "turn_count": 5
    },
    {
        "session_id": "yyy",
        "user_id": 2,
        "state": "INFO_COLLECTION",
        "turn_count": 3
    }
]
```

## 5. 工具列表接口

### 5.1 获取所有工具

**请求**:
```
GET /api/v1/tools
```

**响应**:
```json
[
    {
        "name": "get_order",
        "description": "查询订单详情",
        "risk_level": "low",
        "requires_confirmation": false,
        "category": "order"
    },
    {
        "name": "cancel_order",
        "description": "取消订单",
        "risk_level": "high",
        "requires_confirmation": true,
        "category": "order"
    }
]
```

## 6. 健康检查接口

### 6.1 健康检查

**请求**:
```
GET /health
```

**响应**:
```json
{
    "status": "healthy",
    "version": "0.1.0",
    "env": "development"
}
```

## 7. 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 8. 错误处理

### 8.1 错误响应格式

```json
{
    "error": "错误类型",
    "detail": "详细错误信息",
    "status_code": 500
}
```

### 8.2 常见错误

| 错误 | 说明 | 处理方式 |
|------|------|----------|
| 会话不存在 | session_id 无效 | 创建新会话 |
| 工具不存在 | tool_name 无效 | 检查工具名称 |
| 参数错误 | arguments 格式错误 | 检查参数格式 |
| 执行超时 | 工具执行超时 | 重试或联系管理员 |

## 9. 最佳实践

### 9.1 会话管理

- 首次对话不传 session_id，系统会自动创建
- 后续对话传入 session_id 维持会话状态
- 长时间未使用的会话会自动过期

### 9.2 错误处理

- 捕获 HTTP 状态码，处理不同类型的错误
- 对于 500 错误，可以重试
- 对于 400 错误，检查请求参数

### 9.3 性能优化

- 使用连接池复用 HTTP 连接
- 对于长时间操作，使用异步调用
- 合理设置超时时间
