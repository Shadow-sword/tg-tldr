.PHONY: help install run summary lint format typecheck ci clean purge search reindex test \
	docker-build docker-run docker-up docker-down docker-restart docker-logs \
	docker-summary docker-summary-date docker-search docker-reindex docker-purge docker-db-shell

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## 安装依赖
	uv sync

run:  ## 启动守护进程（监听消息 + 定时总结）
	uv run python -m tg_tldr

summary:  ## 生成昨日总结
	uv run python -m tg_tldr summary

summary-date:  ## 生成指定日期总结（用法: make summary-date DATE=2026-01-30）
	uv run python -m tg_tldr summary -d $(DATE)

lint:  ## 代码检查
	uv run ruff check src/

format:  ## 代码格式化
	uv run ruff format src/
	uv run ruff check --fix src/

typecheck:  ## 类型检查
	uv run pyright src/

ci:  ## 运行完整 CI 检查（lint + typecheck）
	uv run ruff check src/
	uv run ruff format --check src/
	uv run pyright src/

clean:  ## 清理缓存文件
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

db-shell:  ## 打开 SQLite 数据库
	sqlite3 data/messages.db

purge:  ## 清理早于指定日期的消息（用法: make purge BEFORE=2026-01-01）
	uv run python -m tg_tldr purge $(BEFORE)

search:  ## 搜索消息（用法: make search KEYWORD="Python" GROUP="技术群"）
	uv run python -m tg_tldr search "$(KEYWORD)" $(if $(GROUP),-g "$(GROUP)",) $(if $(LIMIT),-n $(LIMIT),)

reindex:  ## 重建全文搜索索引
	uv run python -m tg_tldr reindex

test:  ## 运行测试
	uv run pytest tests/ -v

# Docker 相关命令
docker-build:  ## 构建 Docker 镜像
	docker compose build

docker-run:  ## 首次运行（交互式登录 Telegram）
	docker compose run --rm tg-tldr

docker-up:  ## 后台启动容器
	docker compose up -d

docker-down:  ## 停止容器
	docker compose down

docker-restart:  ## 重启容器（配置修改后使用）
	docker compose restart

docker-logs:  ## 查看容器日志
	docker compose logs -f

# Docker 容器内运维命令（容器运行时使用）
DOCKER_EXEC = docker compose exec tg-tldr python -m tg_tldr

docker-summary:  ## [Docker] 生成昨日总结
	$(DOCKER_EXEC) summary

docker-summary-date:  ## [Docker] 生成指定日期总结（用法: make docker-summary-date DATE=2026-01-30）
	$(DOCKER_EXEC) summary -d $(DATE)

docker-search:  ## [Docker] 搜索消息（用法: make docker-search KEYWORD="Python" GROUP="技术群"）
	$(DOCKER_EXEC) search "$(KEYWORD)" $(if $(GROUP),-g "$(GROUP)",) $(if $(LIMIT),-n $(LIMIT),)

docker-reindex:  ## [Docker] 重建全文搜索索引
	$(DOCKER_EXEC) reindex

docker-purge:  ## [Docker] 清理早于指定日期的消息（用法: make docker-purge BEFORE=2026-01-01）
	$(DOCKER_EXEC) purge $(BEFORE)

docker-db-shell:  ## [Docker] 打开 SQLite 数据库
	docker compose exec tg-tldr sqlite3 data/messages.db
