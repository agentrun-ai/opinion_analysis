# 舆情分析系统

基于 [PydanticAI](https://ai.pydantic.dev/) 和 [AG-UI 协议](https://github.com/ag-ui-protocol/ag-ui) 构建的企业级舆情分析系统。

## ⚠️ 免责声明

**内容由AI生成，仅供参考，您据此所作判断及操作均由您自行承担责任。**

## ✨ 功能特性

- 🔍 **智能数据收集**: 自动从多个平台（微博、知乎、新闻、贴吧等）收集相关数据
- 📊 **深度数据分析**: 关键词提取、情感分析、热度趋势、风险评估
- 📝 **专业报告生成**: 企业级舆情分析报告，达到 C-level 决策标准
- 🎨 **精美 HTML 渲染**: 图文并茂的专业报告展示
- ⚡ **实时状态同步**: 前端实时显示数据收集和分析进度
- 🌐 **浏览器实时预览**: 通过 VNC 实时查看数据收集过程
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
│  │  多 Agent 架构，代码控制流程                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Browser Sandbox                                    │   │
│  │  使用 Playwright 进行网页数据收集                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 📋 系统要求

- **Python**: 3.12+
- **Node.js**: 20+
- **uv**: Python 包管理器

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd opinion_analysis
```

### 2. 安装依赖

```bash
# 后端
cd src/backend
uv sync

# 前端
cd ../frontend
npm install
```

### 3. 配置环境变量

```bash
cd src/backend
cat > .env << EOF
AGENTRUN_MODEL_NAME=your-model-name
AGENTRUN_BROWSER_SANDBOX_NAME=your-sandbox-name
EOF
```

### 4. 启动系统

```bash
# 启动后端（在 src/backend/src 目录）
source ../.venv/bin/activate
python main.py

# 启动前端（在 src/frontend 目录）
npm run dev
```

系统启动后访问: http://localhost:3000

### 5. 使用系统

1. 在输入框中输入关键词（如"新能源汽车"）
2. 设置最大采集数量（默认 20）
3. 点击"开始分析"按钮
4. 观察实时数据收集进度和浏览器预览

## 📁 项目结构

```
opinion_analysis/
├── src/
│   ├── backend/                 # Python 后端
│   │   ├── src/
│   │   │   ├── agent.py        # 主 Agent 逻辑
│   │   │   ├── main.py         # FastAPI 服务
│   │   │   └── analysis_standards.py  # 分析标准
│   │   ├── pyproject.toml      # Python 依赖
│   │   └── .env                # 环境变量配置
│   └── frontend/               # Next.js 前端
│       ├── src/
│       │   ├── app/            # 页面
│       │   ├── components/     # 组件
│       │   └── hooks/          # 自定义 Hooks
│       └── package.json        # Node.js 依赖
├── AGENTS.md                   # 架构文档
└── README.md                   # 本文件
```

## 🏗️ 核心流程

```
阶段 1: 数据收集 (实时同步)
  → 多平台、多角度搜索（微博、知乎、新闻、贴吧等）
  → 严格保证数据量达到目标
  → 每收集一条，前端立即显示
  → VNC 实时预览浏览器活动

阶段 2: 数据分析
  → 关键词提取、情感分析
  → 热度趋势、风险评估
  → 关键观点挖掘

阶段 3: 报告撰写
  → 企业级 7 部分结构化报告
  → 3000-5000 字深度分析
  → 数据驱动、战略视角

阶段 4: HTML 渲染
  → Markdown → HTML 自动转换
  → 精美样式和布局
  → 包含免责声明
```

## ⚙️ 配置选项

### 调整收集数量

在前端界面的配置选项中调整，范围 5-100，默认为 20。

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `AGENTRUN_MODEL_NAME` | LLM 模型名称 |
| `AGENTRUN_BROWSER_SANDBOX_NAME` | Browser Sandbox 模板名称 |

## 🔧 故障排查

### 问题: 数据收集数量不足

系统会自动补充搜索，最多重试 5 次。如果仍然不足，请检查：
1. 网络连接是否正常
2. 搜索关键词是否过于冷门
3. Browser Sandbox 是否正常工作

### 问题: 前端无法看到实时更新

1. 刷新浏览器页面（Ctrl+Shift+R）
2. 检查浏览器控制台是否有错误
3. 确认后端服务正在运行

### 问题: VNC 预览无法连接

1. 确认 Browser Sandbox 已正确配置
2. 检查 `/api/browser/vnc` 接口返回
3. 等待 Sandbox 初始化完成

## 📚 核心依赖

### Python (Backend)

- `pydantic-ai` - PydanticAI 框架
- `ag-ui-core` - AG-UI 协议支持
- `fastapi` - Web 框架
- `uvicorn` - ASGI 服务器
- `playwright` - 浏览器自动化
- `markdown` - Markdown 渲染

### TypeScript (Frontend)

- `next` - Next.js 框架
- `react` - React 库
- `@ag-ui/client` - AG-UI 客户端

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](./LICENSE) 文件。

## 🙏 致谢

本项目基于以下优秀的开源项目构建:

- [PydanticAI](https://ai.pydantic.dev/) - Python Agent 框架
- [AG-UI Protocol](https://github.com/ag-ui-protocol/ag-ui) - Agent UI 通信协议
- [Next.js](https://nextjs.org/) - React 框架
- [Playwright](https://playwright.dev/) - 浏览器自动化

---

**状态**: 生产就绪 ✅  
**最后更新**: 2025-12-07
