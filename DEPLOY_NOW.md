# 一键部署指南

## 方案: Railway.app (最简单稳定)

### 步骤 1: 访问 Railway
打开 https://railway.app，使用 GitHub 账号登录

### 步骤 2: 创建项目
1. 点击 "New Project"
2. 选择 "Deploy from GitHub Repo"
3. 选择仓库: `YunYao-9527/customer-service-agent`

### 步骤 3: 配置环境变量
点击服务，进入 "Variables" 选项卡，添加以下变量:

```
APP_ENV=production
APP_DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./customer_service.db
LLM_PROVIDER=openai
OPENAI_API_KEY=tp-ck4amttxbmf3peifg80y1pazrvs3f5dec9uigo0x8xoa25nq
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=4096
ENABLE_GUARDRAILS=true
LOG_LEVEL=INFO
```

### 步骤 4: 配置启动命令
在 "Settings" 选项卡中:
- **Build Command**: `pip install -e .`
- **Start Command**: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`

### 步骤 5: 部署
Railway 会自动部署，等待 2-3 分钟

### 步骤 6: 获取域名
部署成功后，点击 "Settings" → "Networking" → "Generate Domain"

你将获得一个类似这样的链接:
```
https://customer-service-agent-production.up.railway.app
```

---

## 验证部署

访问健康检查接口:
```
https://your-domain.railway.app/health
```

测试聊天接口:
```bash
curl -X POST https://your-domain.railway.app/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "user_id": 1}'
```

---

## 简历链接格式

部署完成后，你的简历可以这样写:

**GitHub**: https://github.com/YunYao-9527/customer-service-agent

**在线演示**: https://customer-service-agent-production.up.railway.app
