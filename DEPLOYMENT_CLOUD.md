# 云端运行事务型客服 Agent

本仓库提供真实 FastAPI 后端和模拟电商业务。GitHub Pages 是项目介绍页。

## Render 配置

- 运行环境：Python 3.12（也可使用仓库根目录 Dockerfile）
- 构建命令：`pip install -e .`
- 启动命令：`uvicorn src.main:app --host 0.0.0.0 --port $PORT`
- 健康检查：`/health`
- 预览实例：Free
- `DATABASE_URL=sqlite+aiosqlite:///./customer_service.db`
- `SEED_DEMO_DATA=1`：首次启动填充模拟用户和订单；已有数据时不重复填充。

服务根路径会跳转到 `/docs`。`GET /api/v1/tools` 列出工具。可通过 `POST /api/v1/tools/call` 调用 `get_order`，参数为 `{"order_no":"ORD20240101001"}`。

## 对话模型

在 Render 的 Environment 页面设置密钥，勿将密钥提交到仓库：

- OpenAI 兼容接口：`LLM_PROVIDER=openai`、`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。
- 使用仓库 Blueprint 默认 DeepSeek 配置时，填写相应 DeepSeek 密钥；也可以同时修改 Base URL 和模型名称。
- Anthropic：`LLM_PROVIDER=anthropic`、`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`。

没有密钥时，健康检查和业务工具仍可运行，聊天接口返回明确的 503 配置提示。`/health` 的 `llm_configured` 仅表示是否填入密钥，不表示上游密钥已验证。

当前政策检索器使用仓库现有的关键词检索实现。ChromaDB 与 sentence-transformers 已归入可选依赖 `pip install -e '.[vector-rag]'`，默认部署不下载未使用的向量模型。

## 数据与验证

公开服务仅用于模拟业务，不连接真实订单系统。Free 实例的 SQLite 数据在重启、休眠或重新部署时会丢失；长期保存需使用外部数据库或持久磁盘。

已验证：后端启动、模拟数据填充与重复启动、13 个已注册工具、订单读取、缺少模型密钥时的配置提示、意图提示词解析，以及现有 28 项单元测试。真实 LLM 对话需在配置密钥后另行验证。
