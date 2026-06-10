.PHONY: help install dev test lint format run docker-up docker-down db-migrate db-seed eval

# 默认目标
help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# 开发环境
# =============================================================================

install: ## 安装依赖
	pip install -e ".[dev]"

dev: ## 安装开发依赖
	pip install -e ".[dev]"
	pre-commit install

# =============================================================================
# 代码质量
# =============================================================================

lint: ## 运行代码检查
	ruff check src/ tests/
	mypy src/

format: ## 格式化代码
	ruff format src/ tests/
	ruff check --fix src/ tests/

# =============================================================================
# 测试
# =============================================================================

test: ## 运行所有测试
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit: ## 运行单元测试
	pytest tests/unit/ -v

test-integration: ## 运行集成测试
	pytest tests/integration/ -v

test-e2e: ## 运行端到端测试
	pytest tests/e2e/ -v

# =============================================================================
# 数据库
# =============================================================================

db-migrate: ## 运行数据库迁移
	alembic upgrade head

db-migrate-new: ## 创建新的迁移
	alembic revision --autogenerate -m "$(msg)"

db-seed: ## 填充初始数据
	python -m simulation.seed_data

db-reset: ## 重置数据库
	alembic downgrade base
	alembic upgrade head
	python -m simulation.seed_data

# =============================================================================
# 运行
# =============================================================================

run: ## 启动应用
	uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

run-prod: ## 生产模式启动
	uvicorn src.main:app --host 0.0.0.0 --port 8080 --workers 4

# =============================================================================
# Docker
# =============================================================================

docker-up: ## 启动所有服务
	docker-compose up -d

docker-down: ## 停止所有服务
	docker-compose down

docker-build: ## 构建镜像
	docker-compose build

docker-logs: ## 查看日志
	docker-compose logs -f

# =============================================================================
# 评测
# =============================================================================

eval: ## 运行评测
	python -m src.eval.runner --config eval_config.yaml

eval-report: ## 生成评测报告
	python -m src.eval.report --input eval_results/ --output report.html

# =============================================================================
# 初始化
# =============================================================================

init: install docker-up db-migrate db-seed ## 完整初始化项目
	@echo "✅ 项目初始化完成！运行 make run 启动服务"
