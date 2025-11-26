# V3 系统改进方案 - 6大优化

## ✅ 问题 1: 状态实时同步（已完成）

### 问题
状态更新延迟，数据收集结束后才能在页面看到

### 解决方案
- 恢复所有关键工具返回 `StateSnapshotEvent`
- 通过日志（logs）传递进度信息给 LLM
- 前端通过 WebSocket 实时接收状态更新

### 修改文件
- `agent/src/agent_v2.py`:
  - `save_search_result` 返回 `StateSnapshotEvent`
  - `start_collection` 返回 `StateSnapshotEvent`
  - 所有 `finish_*`、`start_*` 工具都返回事件

---

## 🔧 问题 2: 简化UI界面

### 问题
- 右侧聊天页面功能重复
- 用户体验混乱（左侧 vs 右侧输入）
- 聊天界面不提供实际价值

### 解决方案
**方案 A: 移除聊天，使用顶部输入框**
```
┌─────────────────────────────────────────────────────┐
│  舆情分析系统                    [输入框] [分析按钮]  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  左侧面板（配置 + 数据 + 分析 + 报告）                │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**方案 B: 保留聊天但简化**（推荐）
```
┌───────────┬─────────────────────────────────────────┐
│           │                                          │
│  配置面板  │            聊天界面                      │
│  数据列表  │  （仅用于输入关键词和查看报告）           │
│  分析结果  │                                          │
│  报告显示  │                                          │
│           │                                          │
└───────────┴─────────────────────────────────────────┘
```

### 实现
1. 移除左侧 "Target Selection" 表单
2. 简化右侧聊天界面，添加明确提示："请输入关键词开始分析，例如：'分析新能源汽车舆情'"
3. 在 `page.tsx` 中设置默认建议为舆情分析专用

### 修改文件
- `src/components/OpinionDashboard.tsx`
- `src/app/page.tsx`

---

## 🛡️ 问题 3: 错误处理与容错

### 3.1 敏感信息过滤

**需求**: 百度搜索或 LLM 返回可能包含敏感内容

**解决方案**:
```python
# 敏感词列表
SENSITIVE_KEYWORDS = [
    "政治敏感词", "暴力", "色情", "赌博", 
    # ... 根据需要添加
]

async def filter_sensitive_content(text: str) -> str:
    """过滤敏感内容"""
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in text:
            text = text.replace(keyword, "***")
    return text

@opinion_agent.tool
async def save_search_result(...):
    # 过滤敏感内容
    title = await filter_sensitive_content(title)
    snippet = await filter_sensitive_content(snippet)
    ...
```

### 3.2 工具调用重试机制

**需求**: `baidu_search` 可能超时或返回错误

**解决方案**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

async def baidu_search_with_retry(query: str, max_retries=3):
    """带重试的搜索"""
    for attempt in range(max_retries):
        try:
            result = await baidu_search(query)
            return result
        except TimeoutError as e:
            if attempt == max_retries - 1:
                raise
            print(f"⚠️ 搜索超时，重试 {attempt+1}/{max_retries}")
            await asyncio.sleep(2 ** attempt)  # 指数退避
        except Exception as e:
            print(f"❌ 搜索错误: {e}")
            if attempt == max_retries - 1:
                return {"textContent": [], "videoContent": []}
            await asyncio.sleep(1)
    return {"textContent": [], "videoContent": []}
```

### 3.3 LLM 调用容错

**解决方案**:
```python
opinion_agent = Agent(
    name="opinion_agent",
    model=agentrun_model,
    retries=8,  # 增加到 8 次重试
    ...
)
```

### 修改文件
- `agent/src/agent_v2.py` - 添加敏感词过滤和重试逻辑

---

## 📚 问题 4: 报告中添加数据来源

### 需求
报告需要引用具体的数据来源，增强说服力

### 解决方案

#### 4.1 在状态中保存数据来源索引
```python
class AnalysisResult(BaseModel):
    keywords: List[str]
    sentiment_score: float
    sentiment_distribution: Dict[str, int]
    heat_trend: List[int]
    summary: str
    data_sources: List[Dict[str, str]] = []  # 新增：数据来源
```

#### 4.2 在分析时提取关键来源
```python
@opinion_agent.tool
async def save_analysis_result(...):
    # 提取前 5 个最重要的数据来源
    key_sources = [
        {"title": item.title, "url": item.url, "source": item.source}
        for item in ctx.deps.state.raw_data[:5]
    ]
    
    analysis = AnalysisResult(
        ...
        data_sources=key_sources
    )
```

#### 4.3 报告中引用来源
更新 `report_writer` 的提示词：
```python
你必须在报告中引用数据来源，格式如下：

## 数据来源

本报告基于以下数据源（共 {total_count} 条）：

1. [{source_title}]({url}) - {platform}
2. ...

在报告正文中，重要结论后添加来源引用，例如：
"新能源汽车销量同比增长40% [1]"
```

### 修改文件
- `agent/src/agent_v2.py` - 更新数据模型和提示词
- `agent/src/analysis_standards.py` - 更新分析标准

---

## 📊 问题 5: 统一量化计算标准

### 需求
热度、情感倾向等指标需要有明确、统一的计算标准

### 解决方案

#### 5.1 创建量化标准文档（已存在）
`agent/src/analysis_standards.py` 已经定义了标准，需要增强：

```python
class AnalysisStandards:
    """企业级舆情分析量化标准"""
    
    @staticmethod
    def calculate_sentiment_score(positive: int, neutral: int, negative: int) -> float:
        """
        计算情感得分（-1 到 1）
        
        公式: (正面 - 负面) / 总数
        标准:
        - 0.5 ~ 1.0: 非常正面
        - 0.2 ~ 0.5: 正面
        - -0.2 ~ 0.2: 中性
        - -0.5 ~ -0.2: 负面
        - -1.0 ~ -0.5: 非常负面
        """
        total = positive + neutral + negative
        if total == 0:
            return 0.0
        return (positive - negative) / total
    
    @staticmethod
    def calculate_heat_level(sample_size: int, engagement_avg: int) -> str:
        """
        计算热度等级
        
        参数:
        - sample_size: 样本数量
        - engagement_avg: 平均互动数（点赞+评论+转发）
        
        标准:
        - 极热: engagement_avg >= 10000
        - 很热: engagement_avg >= 1000
        - 较热: engagement_avg >= 100
        - 一般: engagement_avg >= 10
        - 冷门: engagement_avg < 10
        """
        if engagement_avg >= 10000:
            return "极热 ★★★★★"
        elif engagement_avg >= 1000:
            return "很热 ★★★★☆"
        elif engagement_avg >= 100:
            return "较热 ★★★☆☆"
        elif engagement_avg >= 10:
            return "一般 ★★☆☆☆"
        else:
            return "冷门 ★☆☆☆☆"
    
    @staticmethod
    def calculate_sentiment_distribution(texts: List[str]) -> Dict[str, int]:
        """
        计算情感分布
        
        方法：基于关键词匹配（简化版，实际应使用情感分析模型）
        """
        positive_keywords = ["好", "优秀", "喜欢", "支持", "赞", "棒"]
        negative_keywords = ["差", "糟", "讨厌", "反对", "烂", "垃圾"]
        
        positive = neutral = negative = 0
        
        for text in texts:
            has_positive = any(kw in text for kw in positive_keywords)
            has_negative = any(kw in text for kw in negative_keywords)
            
            if has_positive and not has_negative:
                positive += 1
            elif has_negative and not has_positive:
                negative += 1
            else:
                neutral += 1
        
        return {
            "positive": positive,
            "neutral": neutral,
            "negative": negative
        }
```

#### 5.2 在分析工具中强制使用标准
```python
@opinion_agent.tool
async def save_analysis_result(...):
    """使用统一标准计算各项指标"""
    from analysis_standards import AnalysisStandards
    
    # 使用标准计算情感得分
    sentiment_dist = AnalysisStandards.calculate_sentiment_distribution(
        [item.snippet for item in ctx.deps.state.raw_data]
    )
    sentiment_score = AnalysisStandards.calculate_sentiment_score(
        sentiment_dist["positive"],
        sentiment_dist["neutral"],
        sentiment_dist["negative"]
    )
    
    # 使用标准计算热度
    heat_level = AnalysisStandards.calculate_heat_level(
        sample_size=len(ctx.deps.state.raw_data),
        engagement_avg=100  # 从数据中提取
    )
    
    analysis = AnalysisResult(
        sentiment_score=sentiment_score,
        sentiment_distribution=sentiment_dist,
        heat_level=heat_level,
        ...
    )
```

### 修改文件
- `agent/src/analysis_standards.py` - 增强量化标准
- `agent/src/agent_v2.py` - 使用标准计算指标

---

## 🌊 问题 6: 流式输出渲染

### 需求
分析和报告撰写阶段支持流式输出，实时显示进度

### 挑战
- PydanticAI Agent 的 `run` 方法不直接支持流式输出
- 需要在分析和报告阶段显示"正在思考中..."

### 解决方案 A: 使用进度状态字段（简单）

```python
class OpinionState(BaseModel):
    ...
    # 新增字段
    analysis_progress: str = ""  # "正在分析第 1/5 批数据..."
    report_progress: str = ""    # "正在撰写第 3/7 部分..."
```

```python
@opinion_agent.tool
async def save_batch_analysis(...):
    # 更新进度
    ctx.deps.state.analysis_progress = f"正在分析第 {batch_index+1}/{total_batches} 批数据..."
    await log_and_update(ctx, "analyzing", ctx.deps.state.analysis_progress)
    return StateSnapshotEvent(...)

@opinion_agent.tool
async def update_report_progress(...):
    """报告撰写进度更新工具（新增）"""
    ctx.deps.state.report_progress = section_name
    await log_and_update(ctx, "writing", f"正在撰写: {section_name}")
    return StateSnapshotEvent(...)
```

### 解决方案 B: 使用真实的流式输出（复杂）

需要修改 Agent 的调用方式，使用 `run_stream`:

```python
async for event in opinion_agent.run_stream(...):
    if isinstance(event, ModelResponsePart):
        # 流式输出的文本片段
        current_text += event.content
        # 更新状态
        ctx.deps.state.report_progress = current_text[:100] + "..."
        # 触发前端更新
```

**推荐**: 使用方案 A（进度字段），因为更简单且符合当前架构

### 修改文件
- `agent/src/agent_v2.py` - 添加进度字段和更新逻辑
- `src/components/OpinionDashboard.tsx` - 显示进度信息

---

## 📝 总结

### 优先级
1. ✅ **P0（已完成）**: 状态实时同步
2. **P1（高）**: 简化 UI、错误处理
3. **P2（中）**: 数据来源引用、量化标准
4. **P3（低）**: 流式输出

### 实施计划
1. ✅ 问题 1 - 完成
2. ⏳ 问题 2 - 简化 UI（前端修改）
3. ⏳ 问题 3 - 添加错误处理（后端修改）
4. ⏳ 问题 4 - 数据来源（后端 + 提示词）
5. ⏳ 问题 5 - 量化标准（后端逻辑）
6. ⏳ 问题 6 - 流式输出（后端 + 前端）

### 预计工作量
- **后端修改**: 2-3 小时
- **前端修改**: 1-2 小时
- **测试验证**: 1 小时
- **总计**: 4-6 小时

