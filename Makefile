.PHONY: help install dev build clean verify lint

# 默认目标
help:
	@echo "=========================================="
	@echo "舆情分析系统 - AG-UI 协议版"
	@echo "=========================================="
	@echo ""
	@echo "  make install    - 安装所有依赖"
	@echo "  make dev        - 启动开发环境"
	@echo "  make build      - 构建生产版本到 dist/"
	@echo "  make verify     - 验证环境配置"
	@echo "  make lint       - 运行代码检查"
	@echo "  make clean      - 清理构建文件"
	@echo ""
	@echo "架构说明:"
	@echo "  - 前端: Next.js 静态导出"
	@echo "  - 后端: Python (FastAPI + PydanticAI)"
	@echo "  - 通信: AG-UI 协议 (HTTP SSE)"
	@echo ""
	@echo "快速开始:"
	@echo "  1. make install"
	@echo "  2. 配置 agent/.env 文件"
	@echo "  3. make dev"
	@echo ""

# 安装所有依赖
install:
	cd src/frontend && npm i
	cd src/backend && uv sync

# 启动开发环境
dev:
	@echo "🚀 启动开发环境..."
	@echo "   构建前端静态文件..."
	@npm run build
	@cp -r out agent/
	@echo "   启动服务: http://localhost:8000"
	@cd agent && uv run src/main.py

src/frontend/out/index.html: $(wildcard src/frontend/src/*)
	cd src/frontend && npm run build

src/frontend/out/index.js: src/frontend/index.js
	rm src/frontend/out/index.js  2>/dev/null || true
	cp src/frontend/index.js src/frontend/out/index.js

build-frontend: src/frontend/out/index.html src/frontend/out/index.js
	
build-backend:
	

# 构建生产版本
build: build-frontend build-backend

# 验证环境
verify:
	@echo "🔍 验证环境配置..."
	@echo ""
	@command -v python3 >/dev/null 2>&1 && echo "✅ Python: $$(python3 --version)" || echo "❌ Python 未安装"
	@command -v uv >/dev/null 2>&1 && echo "✅ uv: $$(uv --version)" || echo "❌ uv 未安装"
	@command -v node >/dev/null 2>&1 && echo "✅ Node.js: $$(node --version)" || echo "❌ Node.js 未安装"
	@command -v npm >/dev/null 2>&1 && echo "✅ npm: $$(npm --version)" || echo "❌ npm 未安装"
	@echo ""
	@test -f agent/.env && echo "✅ agent/.env 已配置" || echo "⚠️  agent/.env 未找到"
	@test -d node_modules && echo "✅ Node.js 依赖已安装" || echo "⚠️  运行 make install 安装依赖"
	@test -d agent/.venv && echo "✅ Python 依赖已安装" || echo "⚠️  运行 make install 安装依赖"
	@echo ""
	@echo "✅ 验证完成"

# 运行代码检查
lint:
	@echo "🔍 运行代码检查..."
	@npm run lint
	@echo "✅ 代码检查完成"

# 清理构建文件
clean:
	@echo "🧹 清理构建文件..."
	@rm -rf .next
	@rm -rf out
	@rm -rf dist
	@rm -rf agent/.venv
	@rm -rf agent/out
	@rm -rf node_modules
	@echo "✅ 清理完成"

publish: build
	s registry publish -f