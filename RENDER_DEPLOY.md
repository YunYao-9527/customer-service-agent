# Render.com 部署指南

## 步骤 1: 访问 Render.com

打开 https://render.com 并登录（可以使用 GitHub 账号登录）

## 步骤 2: 创建新的 Web Service

1. 点击 "New +" 按钮
2. 选择 "Web Service"
3. 连接你的 GitHub 仓库: `YunYao-9527/customer-service-agent`

## 步骤 3: 配置部署设置

**Name**: `customer-service-agent`

**Region**: 选择离你最近的区域（如 Oregon）

**Branch**: `master`

**Runtime**: `Python`

**Build Command**: `pip install -e .`

**Start Command**: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`

## 步骤 4: 配置环境变量

在 "Environment" 部分添加以下环境变量：

| Key | Value |
|-----|-------|
| APP_ENV | production |
| APP_DEBUG | false |
| DATABASE_URL | sqlite+aiosqlite:///./customer_service.db |
| LLM_PROVIDER | openai |
| OPENAI_API_KEY | tp-ck4amttxbmf3peifg80y1pazrvs3f5dec9uigo0x8xoa25nq |
| OPENAI_MODEL | deepseek-chat |
| OPENAI_BASE_URL | https://api.deepseek.com/v1 |
| OPENAI_TEMPERATURE | 0.1 |
| OPENAI_MAX_TOKENS | 4096 |
| ENABLE_GUARDRAILS | true |
| LOG_LEVEL | INFO |

## 步骤 5: 部署

1. 点击 "Create Web Service"
2. 等待部署完成（通常需要 2-5 分钟）
3. 部署成功后，你会得到一个 URL，如: `https://customer-service-agent.onrender.com`

## 步骤 6: 验证部署

访问你的应用 URL，应该能看到健康检查页面:

```
https://customer-service-agent.onrender.com/health
```

## 步骤 7: 测试 API

使用 curl 测试聊天接口:

```bash
curl -X POST https://customer-service-agent.onrender.com/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "user_id": 1}'
```

## 注意事项

1. **免费计划限制**: Render 免费计划会在 15 分钟无活动后休眠，首次访问可能需要等待 30 秒左右唤醒
2. **数据库**: 使用 SQLite，数据会在服务重启后丢失（生产环境建议使用 PostgreSQL）
3. **API Key**: 确保你的 DeepSeek API Key 有足够的额度

## 获取部署链接

部署成功后，你将获得一个类似以下格式的链接:

```
https://customer-service-agent.onrender.com
```

这个链接可以放在简历中，展示你的项目。
