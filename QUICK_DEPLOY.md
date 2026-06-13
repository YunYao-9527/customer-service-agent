# 🚀 一键部署指南 (3 分钟完成)

## Railway.app 部署

### 步骤 1: 打开 Railway
访问: https://railway.app
使用 GitHub 账号登录

### 步骤 2: 一键部署
1. 点击 **"New Project"**
2. 选择 **"Deploy from GitHub Repo"**
3. 选择仓库: **`YunYao-9527/customer-service-agent`**
4. 点击 **"Deploy Now"**

### 步骤 3: 添加环境变量
部署后，点击服务 → **"Variables"** 选项卡 → 添加以下变量:

```env
APP_ENV=production
APP_DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./customer_service.db
LLM_PROVIDER=openai
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=4096
ENABLE_GUARDRAILS=true
LOG_LEVEL=INFO
```

### 步骤 4: 获取域名
1. 点击 **"Settings"** 选项卡
2. 找到 **"Networking"** 部分
3. 点击 **"Generate Domain"**

你会获得类似这样的链接:
```
https://customer-service-agent-production.up.railway.app
```

### 步骤 5: 验证部署
访问健康检查接口:
```
https://your-domain.railway.app/health
```

---

## 📝 简历写法

```
事务型智能客服 Agent
GitHub: https://github.com/YunYao-9527/customer-service-agent
在线演示: https://your-domain.railway.app
```

---

## ⚠️ 注意事项

1. **免费计划限制**: Railway 免费计划每月有 500 小时使用时间
2. **休眠机制**: 无活动时会休眠，首次访问需要等待几秒唤醒
3. **数据持久化**: 使用 SQLite，数据在服务重启后会丢失（生产环境建议使用 PostgreSQL）
