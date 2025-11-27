# 舆情分析系统

基于 [PydanticAI](https://ai.pydantic.dev/) 和 [AG-UI 协议](https://github.com/ag-ui-protocol/ag-ui) 构建的企业级舆情分析系统。

## ✨ 功能特性

- 🔍 **智能数据收集**: 自动从多个平台（微博、知乎、新闻等）收集相关数据
- 📊 **深度数据分析**: 关键词提取、情感分析、热度趋势、时间线分析
- 📝 **专业报告生成**: 企业级舆情分析报告，达到 C-level 决策标准
- 🎨 **精美 HTML 渲染**: 图文并茂的专业报告展示
- ⚡ **实时状态同步**: 前端实时显示数据收集和分析进度
- 🔗 **AG-UI 协议**: 使用 HTTP SSE 直接通信，无需 GraphQL

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Next.js 静态导出)                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  @ag-ui/client (HttpAgent)                          │   │
│  │  直接通过 HTTP SSE 与后端通信                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP SSE (AG-UI 协议)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    后端 (Python/FastAPI)                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PydanticAI Agent                                   │   │
│  │  .to_ag_ui() → 自动生成 AG-UI 兼容端点               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  静态文件服务                                        │   │
│  │  提供前端构建产物                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**关键特点**:
- 单进程 Python 服务，同时提供 API 和静态文件
- 使用 AG-UI 协议通过 HTTP SSE 通信
- 无需 GraphQL，架构更简洁

## 📋 系统要求

- **Python**: 3.12+
- **Node.js**: 20+
- **uv**: Python 包管理器
- **Make**: 构建工具

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd opinion_analysis
```

### 2. 安装依赖

```bash
make install
```

### 3. 配置 API Key

```bash
cd agent
cat > .env << EOF
OPENAI_API_KEY=sk-your-key-here
EOF
cd ..
```

### 4. 启动系统

```bash
make dev
```

系统启动后访问: http://localhost:8000

### 5. 使用系统

在聊天框中输入：

```
分析"新能源汽车"的舆情
```

观察实时更新的数据收集进度！

## 📦 Make 命令

### 开发环境

| 命令 | 说明 |
|------|------|
| `make` 或 `make help` | 显示帮助信息 |
| `make install` | 安装所有依赖（Python + Node.js） |
| `make dev` | **一键启动开发环境** |
| `make build` | 构建生产版本到 dist/ 目录 |
| `make verify` | 验证环境配置 |
| `make lint` | 运行代码检查 |
| `make clean` | 清理所有构建文件 |

### 生产环境（在 dist/ 目录中）

| 命令 | 说明 |
|------|------|
| `make install` | 安装 Python 依赖 |
| `make start` | **一键启动生产环境（端口 8000）** |

## 📁 项目结构

```
opinion_analysis/
├── agent/                    # Python 后端
│   ├── src/
│   │   ├── agent.py         # 主 Agent 逻辑
│   │   ├── main.py          # FastAPI 服务
│   │   └── analysis_standards.py  # 分析标准
│   ├── pyproject.toml       # Python 依赖
│   └── .env                 # API Key 配置
├── src/                     # Next.js 前端源码
│   ├── app/
│   │   ├── layout.tsx       # 布局
│   │   └── page.tsx         # 主页面
│   ├── components/
│   │   ├── OpinionDashboard.tsx  # 主界面组件
│   │   └── ChatPanel.tsx    # 聊天面板
│   └── hooks/
│       └── useAgentState.ts # AG-UI 状态 Hook
├── Makefile                 # 构建和启动命令
├── package.json             # Node.js 依赖
├── AGENTS.md                # 架构文档（详细）
└── README.md                # 本文件
```

## 🏗️ 核心流程

```
阶段 1: 数据收集 (实时同步)
  → 多角度搜索关键词
  → 每收集一条，前端立即显示 +1
  → 达到目标数量后完成

阶段 2: 数据分析
  → 使用统一标准进行量化分析
  → 关键词提取、情感分析、热度趋势
  → 支持批次处理大量数据

阶段 3: 报告撰写
  → 企业级 7 部分结构化报告
  → Markdown 格式，1500-2500 字
  → 数据驱动、战略视角

阶段 4: HTML 渲染
  → Markdown → HTML 自动转换
  → 精美样式和布局
```

详细架构说明请参考 [AGENTS.md](./AGENTS.md)。

## ⚙️ 配置选项

### 调整收集数量

在前端左侧面板的配置选项中调整，默认为 5（测试）。

### 切换大模型

编辑 `agent/src/agent.py`:

```python
agentrun_model = model("your-model-name", config=model_config)
```

### 调整端口

编辑 `agent/src/main.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 🔧 故障排查

### 问题: 前端无法看到实时更新

**解决方案**:
1. 确认启动的是最新版本的代码
2. 刷新浏览器页面（Ctrl+Shift+R）
3. 检查浏览器控制台是否有错误

### 问题: 数据收集失败

**解决方案**:
1. 检查网络连接
2. 确认搜索工具正常工作
3. 查看后端日志排查具体错误

### 问题: Agent 无法启动

**解决方案**:
1. 确认 `.env` 文件存在且包含有效的 API Key
2. 运行 `make install` 重新安装依赖
3. 确认 Python 版本 >= 3.12

## 🚀 生产环境部署

### 构建

```bash
make build
```

构建产物位于 `dist/` 目录，包含所有运行所需的文件。

### 部署到服务器

```bash
# 1. 复制 dist 到服务器
scp -r dist/ user@server:/opt/opinion-analysis/

# 2. SSH 到服务器并配置
ssh user@server
cd /opt/opinion-analysis
cd agent
echo "OPENAI_API_KEY=sk-your-key" > .env
cd ..

# 3. 安装依赖并启动
make install
make start
```

**就这么简单！** `dist/` 目录是完全独立的，只需 Python 和 uv 即可运行。

## 📚 核心依赖

### Python (Backend)

- `pydantic-ai-slim[ag-ui]` - PydanticAI 框架 + AG-UI 支持
- `pydantic-ai-slim[openai]` - OpenAI 集成
- `fastapi` - Web 框架
- `uvicorn` - ASGI 服务器
- `markdown` - Markdown 渲染
- `pandas` - 数据分析

### TypeScript (Frontend)

- `next` - Next.js 框架（静态导出）
- `react` - React 库
- `@ag-ui/client` - AG-UI 客户端（直接 SSE 通信）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](./LICENSE) 文件。

## 🙏 致谢

本项目基于以下优秀的开源项目构建:

- [PydanticAI](https://ai.pydantic.dev/) - Python Agent 框架
- [AG-UI Protocol](https://github.com/ag-ui-protocol/ag-ui) - Agent UI 通信协议
- [Next.js](https://nextjs.org/) - React 框架

## 📖 相关文档

- [AGENTS.md](./AGENTS.md) - 详细的架构设计和开发历程文档
- [PydanticAI 文档](https://ai.pydantic.dev/)
- [AG-UI 协议](https://github.com/ag-ui-protocol/ag-ui)

---

**版本**: 3.0.0  
**状态**: 生产就绪 ✅  
**最后更新**: 2025-11-26
