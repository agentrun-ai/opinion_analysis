# 舆情分析系统 - 架构文档

## 📋 目录
1. [系统概述](#系统概述)
2. [核心架构](#核心架构)
3. [数据模型](#数据模型)
4. [流程设计](#流程设计)
5. [技术实现](#技术实现)
6. [配置说明](#配置说明)

---

## 系统概述

### 功能定位
企业级舆情分析系统，提供：
- **数据收集**: 多平台数据抓取（微博、知乎、新闻、贴吧等）
- **数据分析**: 关键词提取、情感分析、热度趋势、风险评估
- **报告生成**: 专业、客观的舆情分析报告
- **可视化**: 图文并茂的 HTML 报告

### 质量标准
- **专业性**: 达到企业级标准，可提交给 C-level 高管
- **可靠性**: 基于真实数据，不编造内容
- **实时性**: 前端实时显示收集和分析进度

---

## 核心架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                   用户输入关键词                             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Opinion Agent                             │
│                   代码控制流程流转                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  阶段 1: 数据收集 (collect_data)                            │
│  ┌──────────────────────────────────────┐                  │
│  │ - 多平台搜索（微博、知乎、新闻等）      │                  │
│  │ - 严格保证数据量                      │                  │
│  │ - 实时更新前端                        │                  │
│  │ - VNC 浏览器预览                      │                  │
│  └──────────────────────────────────────┘                  │
│                                                             │
│  阶段 2: 数据分析 (analyze_data)                            │
│  ┌──────────────────────────────────────┐                  │
│  │ - 关键词提取                          │                  │
│  │ - 情感分析                            │                  │
│  │ - 风险评估                            │                  │
│  └──────────────────────────────────────┘                  │
│                                                             │
│  阶段 3: 报告撰写 (write_report)                            │
│  ┌──────────────────────────────────────┐                  │
│  │ - 3000-5000 字深度报告                │                  │
│  │ - 7 部分结构化内容                    │                  │
│  │ - 企业级专业标准                      │                  │
│  └──────────────────────────────────────┘                  │
│                                                             │
│  阶段 4: HTML 渲染 (render_html)                            │
│  ┌──────────────────────────────────────┐                  │
│  │ - Markdown → HTML                    │                  │
│  │ - 精美样式                            │                  │
│  │ - 免责声明                            │                  │
│  └──────────────────────────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   前端实时显示         │
            │  - 数据列表 (逐条)     │
            │  - 进度条 (实时)       │
            │  - VNC 预览           │
            │  - 最终 HTML 报告      │
            └───────────────────────┘
```

### 设计原则

1. **代码控制流程**: 不依赖 LLM 自主决策，通过代码严格控制每个阶段
2. **严格数据收集**: 必须收集到目标数量，不足时自动补充搜索
3. **实时状态同步**: 每个工具返回 StateSnapshotEvent，前端立即更新
4. **多 Sandbox 支持**: 支持多个浏览器沙箱并行工作

---

## 数据模型

### SearchResult
```python
class SearchResult(BaseModel):
    title: str          # 标题
    url: str            # 链接
    snippet: str        # 摘要
    source: str         # 来源（微博/知乎/新闻等）
    date: str           # 日期
    platform: str       # 搜索平台
```

### AnalysisResult
```python
class AnalysisResult(BaseModel):
    keywords: List[str]                    # 关键词列表
    sentiment_score: float                 # 情感得分 (-1到1)
    sentiment_distribution: Dict[str, int] # 情感分布
    heat_trend: List[int]                  # 热度趋势
    summary: str                           # 分析摘要
    key_opinions: List[Dict[str, str]]     # 关键观点
    risk_assessment: Dict[str, str]        # 风险评估
```

### OpinionState
```python
class OpinionState(BaseModel):
    keyword: str = ""                      # 分析关键词
    status: str = "idle"                   # 当前状态
    logs: List[str] = []                   # 日志列表
    max_results: int = 20                  # 最大收集数量
    
    raw_data: List[SearchResult] = []      # 原始数据
    collected_data_summary: List[Dict] = [] # 前端摘要
    analysis: Optional[AnalysisResult]     # 分析结果
    report_text: str = ""                  # Markdown 报告
    final_html: str = ""                   # 最终 HTML
    
    collection_progress: int = 0           # 收集进度
    current_phase: str = ""                # 当前阶段
    sandboxes: List[SandboxInfo] = []      # Sandbox 列表
    active_sandbox_id: str = ""            # 当前活动 Sandbox
```

---

## 流程设计

### 数据收集策略

多平台搜索查询模板：
```python
SEARCH_TEMPLATES = {
    "general": ["{keyword}", "{keyword} 最新消息"],
    "weibo": ["site:weibo.com {keyword}"],
    "zhihu": ["site:zhihu.com {keyword}"],
    "news": ["{keyword} 新闻报道"],
    "tieba": ["site:tieba.baidu.com {keyword}"],
    "comments": ["{keyword} 用户评价"],
}
```

### 数据收集保证

```python
# 持续搜索直到达到目标数量
while len(collected) < target_count:
    # 执行搜索...
    
    # 如果用完预定义查询，生成补充查询
    if query_index >= len(queries):
        if retry_count >= max_retries:
            break
        retry_count += 1
        # 生成补充查询...
```

### 报告结构

6 部分企业级报告（围绕四个核心要点）：

**核心要点**：
1. 近期舆情背景、时间线
2. 网络上的主流观点
3. 未来舆情的发展趋势
4. 后续建议

**报告章节**：
1. **舆情背景与时间线**: 数据基础 + 近期背景 + 时间线梳理 + 热度趋势
2. **网络主流观点分析**: 各平台观点 + 代表性声音 + 意见领袖影响
3. **成因与驱动因素分析**: 直接诱因 + 深层原因 + 情感驱动
4. **未来发展趋势预测**: 短期预测 + 中长期预测 + 风险评估
5. **应对建议与行动方案**: 即时响应 + 中期策略 + 长期策略
6. **结论与核心要点**: 核心结论 + 关键行动建议 + 后续跟踪

---

## 技术实现

### 后端 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agent` | POST | AG-UI 主端点 |
| `/api/browser/vnc` | GET | 获取 VNC URL |
| `/api/browser/sandboxes` | GET | 获取所有 Sandbox |
| `/api/browser/screenshot` | GET | 获取浏览器截图 |

### 状态同步机制

每个工具返回 `StateSnapshotEvent`，确保前端实时更新：

```python
@opinion_agent.tool
async def collect_data(ctx, keyword):
    # ... 收集逻辑 ...
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT, 
        snapshot=state
    )
```

### 前端状态管理

使用 `useAgentState` Hook 管理状态：

```typescript
const { state, running, sendMessage } = useAgentState<AgentState>({
    name: 'opinion_agent',
    agentUrl: 'http://localhost:8000/api/agent',
    initialState: { ... }
});
```

---

## 配置说明

### 环境变量

```bash
# 必需
AGENTRUN_MODEL_NAME=your-model-name
AGENTRUN_BROWSER_SANDBOX_NAME=your-sandbox-name
```

### 前端配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 最大采集数量 | 20 | 范围 5-100 |

### 超时设置

```python
config = Config(timeout=180)  # 3分钟超时
```

---

## 免责声明

**内容由AI生成，仅供参考，您据此所作判断及操作均由您自行承担责任。**

---

**文档版本**: 1.0  
**最后更新**: 2025-12-07
