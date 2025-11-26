"""
重构版舆情分析系统 - 实时状态同步优化
所有工具直接注册到主 Agent，确保 StateSnapshotEvent 实时传播
"""
from textwrap import dedent
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.ag_ui import StateDeps
from ag_ui.core import EventType, StateSnapshotEvent
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()

from agentrun.integration.pydantic_ai import model, toolset
from agentrun.utils.config import Config
from analysis_standards import AnalysisStandards

# =====
# Models
# =====

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    date: str

class AnalysisResult(BaseModel):
    keywords: List[str]
    sentiment_score: float
    sentiment_distribution: Dict[str, int]
    heat_trend: List[int]
    summary: str

class OpinionState(BaseModel):
    """State for the Opinion Analysis System."""
    keyword: str = Field(default="", description="The keyword being analyzed")
    status: str = Field(default="idle", description="Current status")
    logs: List[str] = Field(default_factory=list, description="Process logs")
    max_results: int = Field(default=100, description="Maximum number of results to collect")
    batch_size: int = Field(default=20, description="Batch size for analysis")
    
    raw_data: List[SearchResult] = Field(default_factory=list)
    collected_data_summary: List[Dict[str, str]] = Field(default_factory=list, description="Summary for frontend")
    batch_analyses: List[str] = Field(default_factory=list, description="Batch analysis summaries")
    analysis: Optional[AnalysisResult] = None
    report_text: str = Field(default="")
    final_html: str = Field(default="")

# =====
# Tool Setup
# =====

agentrun_model = model("sdk-test-model-service")
search_config = Config(timeout=120)  # 增加超时到120秒，避免搜索超时
search_tools = toolset("web-search-baidu-8baa", config=search_config)

print("=" * 80)
print("🚀 V2: 实时同步优化版舆情分析系统")
print("=" * 80)
print(f"✓ Model: sdk-test-model-service")
print(f"✓ Search Tools: {len(search_tools)} loaded")
print(f"✓ Architecture: Single-Agent (实时同步)")
print("=" * 80 + "\n")

# =====
# Helper Functions
# =====

async def log_and_update(ctx: RunContext[StateDeps[OpinionState]], status: str, message: str):
    """内部辅助函数：更新状态和日志"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = f"[{timestamp}] {message}"
    ctx.deps.state.status = status
    ctx.deps.state.logs.append(log_entry)
    print(f"📊 {log_entry}")

# =====
# Main Opinion Agent - 所有工具都在这里
# =====

opinion_agent = Agent(
    name="opinion_agent",
    model=agentrun_model,
    deps_type=StateDeps[OpinionState],
    retries=5,
    tools=[*search_tools],  # 直接包含搜索工具
    system_prompt=dedent(f"""
        你是具有 10 年以上经验的企业级舆情分析专家，曾服务于多家上市公司和政府机构。
        当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        
        你的分析报告需要达到可直接提交给 C-level 高管和董事会的标准。
        
        ═══════════════════════════════════════════════════════════
        阶段 1: 数据收集 (实时同步到前端)
        ═══════════════════════════════════════════════════════════
        1. 调用 start_collection(keyword) 进入收集模式
           → 系统会告诉你需要收集多少条（max_results）
        
        2. **持续搜索直到达到目标数量**:
           循环执行以下步骤，直到收集满 max_results 条：
           
           a. 使用 baidu_search 搜索（多角度）:
              - "{{keyword}} 最新动态"
              - "{{keyword}} 用户评价"  
              - "{{keyword}} 新闻报道"
              - "{{keyword}} 行业分析"
           
           b. 从搜索结果中提取有价值的信息
              - 过滤广告和无关内容
              - **跳过包含敏感信息的内容**（政治敏感、暴力、色情等）
              - 优先权威来源（官媒、知名平台）
              - 时效性优先（最新信息）
              - 观点多样性（正反中立）
           
           c. 对每条有价值的结果，**立即**调用 save_search_result
              ⚡ 关键：每调用一次，前端实时显示+1！
           
           d. 检查进度：
              - 如果已达到 max_results → 调用 finish_collection
              - 如果未达到 → 继续搜索（回到步骤 a）
        
        ⚠️ 重要：不要提前停止！必须收集满 max_results 条数据！
        
        ═══════════════════════════════════════════════════════════
        阶段 2: 专业数据分析（使用统一标准 + 批次处理）
        ═══════════════════════════════════════════════════════════
        6. 调用 start_analysis 进入分析模式
        
        7. **首先调用 run_standard_analysis 获取基础量化指标**:
           - 这会返回标准化的关键词、情感得分、热度趋势
           - 计算方法统一，跨场景可比
           - 包含数据来源统计
        
        8. **然后进行深度分析**（可选，数据量大时使用批次处理）:
           a. 调用 get_data_overview 获取批次规划
           b. 对每个批次:
              - get_batch_data(batch_index)
              - 分析该批次的深层观点和论据
              - save_batch_analysis(batch_index, summary)
           c. 调用 merge_batch_analyses 综合
        
        9. 深度解读（基于标准化指标 + 批次分析）:
           
           关键词提取标准:
           - 使用词频分析、TF-IDF 等方法
           - 识别核心话题而非泛泛词汇
           - 5-10 个最具代表性的关键词
           
           情感分析标准:
           - 基于实际用词和语气判断
           - 不要过度简化为正负面
           - 考虑中性/客观报道的比例
           - sentiment_score: -1（极负面）到 1（极正面）
           - sentiment_distribution: 必须加起来 100%
           
           热度趋势:
           - 基于时间分布推测
           - 符合传播规律（爆发-高峰-衰减）
           - 7-10 个时间点数据
           
           分析摘要:
           - 100-200字精炼总结
           - 突出核心发现和异常点
           - 数据驱动，不空洞
           
        11. 调用 save_analysis_result(...) 保存最终结果
        12. 调用 finish_analysis
        
        ═══════════════════════════════════════════════════════════
        阶段 3: 企业级报告撰写 (Markdown)
        ═══════════════════════════════════════════════════════════
        13. 调用 start_writing
        14. 调用 get_analysis_data 获取分析数据
        15. 撰写报告（严格遵循以下结构）:
        
        # [关键词] 舆情分析报告
        
        > **报告摘要**: 2-3句话概括核心发现
        
        ## 一、舆情概况
        ### 1.1 数据基础
        - 监测时间：YYYY-MM-DD 至 YYYY-MM-DD
        - 数据来源：微博、知乎、新闻等 X 个平台
        - 样本量：共 X 条有效数据
        - **数据来源分布**：微博 XX%、知乎 XX%、新闻 XX%
        
        ### 1.2 整体态势  
        - 情感分布（基于统一标准）：正面 XX%、中性 XX%、负面 XX%
        - 舆情指数：X.XX（-1到1，基于情感得分）
        - 传播特征：热度趋势呈现 [上升/下降/平稳] 态势
        
        ## 二、舆情演进分析
        ### 2.1 时间脉络
        - 起始期 → 发酵期 → 高峰期 → 衰减期
        
        ### 2.2 核心议题
        - 基于关键词，识别 3-5 个主要话题
        
        ## 三、成因与驱动因素
        ### 3.1 直接诱因
        ### 3.2 深层原因
        - 社会背景、利益相关、传播机制
        
        ### 3.3 情感驱动
        
        ## 四、多维度观点透视
        ### 4.1 主流观点阵营
        - 支持方（XX%）：主要观点和论据
          - 引用示例："..." [来源：平台名]
        - 质疑方（XX%）：主要观点和论据
          - 引用示例："..." [来源：平台名]
        - 中立方（XX%）：观察视角
        
        ### 4.2 意见领袖影响
        - 关键发声及其影响范围
        
        ## 五、风险评估与趋势研判
        ### 5.1 短期预测（1-2周）
        ### 5.2 中长期影响
        ### 5.3 风险等级
        - 传播风险: ★★★☆☆
        - 声誉风险: ★★★★☆
        
        ## 六、应对建议
        ### 6.1 即时响应策略
        ### 6.2 中长期策略
        
        ## 七、结论与建议
        
        ---
        **报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}  
        **数据样本量**: X 条  
        **数据来源**: [列出主要来源及链接示例]
        
        ### 附录：重要数据来源
        列出 3-5 个最具代表性的数据来源：
        - [标题] - [来源平台] - [日期] - [链接]
        
        写作标准:
        1. 数据驱动：每个结论必须有数据支撑
        2. 深度洞察：挖掘深层原因，不满足表面
        3. 专业术语：使用舆情分析专业词汇
        4. 战略视角：站在决策者角度
        5. 客观中立：第三方专业立场
        6. 结构严谨：逻辑清晰，层次分明
        7. 语言精炼：1500-2500字，无废话
        8. 风险意识：明确指出潜在风险
        
        16. 调用 save_report(report_content)
        17. 调用 finish_writing
        
        ═══════════════════════════════════════════════════════════
        阶段 4: HTML 渲染
        ═══════════════════════════════════════════════════════════
        18. 调用 render_html
        19. 调用 mark_complete
        
        ═══════════════════════════════════════════════════════════
        错误处理与容错
        ═══════════════════════════════════════════════════════════
        1. **工具超时**: 系统会自动重试（最多5次），无需担心
        2. **敏感信息**: 跳过包含敏感内容的数据，继续处理
        3. **数据不足**: 尽力收集，基于现有数据分析
        4. **部分失败**: 不要停止，完成可完成的部分
        
        ═══════════════════════════════════════════════════════════
        关键原则
        ═══════════════════════════════════════════════════════════
        ✅ 每次调用工具后，前端实时更新（StateSnapshotEvent）
        ✅ 数据收集：多样性、权威性、时效性、过滤敏感信息
        ✅ 数据分析：使用统一标准（run_standard_analysis）、科学方法、量化支撑
        ✅ 报告撰写：战略高度、专业深度、数据来源引用、可执行性
        ✅ 容错优先：遇到错误继续前进，不要放弃任务
        ✅ 全程透明：用户实时看到每一步进展
    """).strip()
)

# =====
# 数据收集工具 (直接注册到 opinion_agent)
# =====

@opinion_agent.tool
async def start_collection(ctx: RunContext[StateDeps[OpinionState]], keyword: str) -> str:
    """开始数据收集流程
    
    返回: 收集目标说明
    """
    ctx.deps.state.keyword = keyword
    max_results = ctx.deps.state.max_results
    
    await log_and_update(
        ctx, 
        "collecting", 
        f"开始收集关键词 '{keyword}' 的相关数据，目标: {max_results} 条"
    )
    
    print(f"\n{'='*60}")
    print(f"🔍 数据收集阶段")
    print(f"🎯 目标: 收集 {max_results} 条数据")
    print(f"{'='*60}\n")
    
    return f"""
数据收集已启动！

目标关键词: {keyword}
目标数量: {max_results} 条

重要提醒:
- 必须收集满 {max_results} 条数据
- 每条数据调用 save_search_result 保存
- 当前进度: 0/{max_results}
- 达到 {max_results} 条后调用 finish_collection

请开始搜索并保存数据！
"""

@opinion_agent.tool
async def save_search_result(
    ctx: RunContext[StateDeps[OpinionState]],
    title: str,
    url: str,
    snippet: str,
    source: str,
    date: str,
) -> str:
    """保存一条搜索结果 - 前端实时更新！
    
    返回: 当前进度和下一步行动建议
    """
    # 检查是否已达到最大数量
    current_count = len(ctx.deps.state.raw_data)
    max_count = ctx.deps.state.max_results
    
    if current_count >= max_count:
        msg = f"⚠️ 已达到目标数量 {max_count}/{max_count}，请立即调用 finish_collection！"
        print(msg)
        return msg
    
    # 保存完整数据
    result = SearchResult(title=title, url=url, snippet=snippet, source=source, date=date)
    ctx.deps.state.raw_data.append(result)
    
    # 同步更新前端摘要
    ctx.deps.state.collected_data_summary.append({
        "title": title,
        "url": url,
        "source": source,
    })
    
    current_count = len(ctx.deps.state.raw_data)
    max_count = ctx.deps.state.max_results
    
    await log_and_update(
        ctx, 
        "collecting", 
        f"收集数据 [{current_count}/{max_count}]: {source} - {title[:30]}..."
    )
    
    remaining = max_count - current_count
    
    print(f"💾 [SAVED {current_count}/{max_count}] {source}: {title[:50]}...")
    print(f"📊 [进度] 已完成 {current_count}/{max_count}，还需 {remaining} 条")
    
    # 同时返回进度提示和状态事件
    # 注意：我们需要先触发状态同步，然后返回消息给 LLM
    # 但 PydanticAI 不支持同时返回多个值
    # 解决方案：通过 tool 的 description 中的特殊标记来触发事件
    
    # 构建进度消息
    if remaining == 0:
        progress_msg = f"✅ 数据保存成功！进度: {current_count}/{max_count} (100%) - 已达到目标，立即调用 finish_collection！"
    else:
        progress_msg = f"✅ 数据保存成功！进度: {current_count}/{max_count} ({int(current_count/max_count*100)}%) - 还需 {remaining} 条，继续搜索！"
    
    # 注意：这里我们返回字符串给 LLM，状态已经通过 log_and_update 更新
    # 前端会通过 WebSocket 收到 logs 的更新
    return progress_msg

@opinion_agent.tool
async def finish_collection(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """完成数据收集"""
    count = len(ctx.deps.state.raw_data)
    await log_and_update(ctx, "collected", f"数据收集完成，共 {count} 条")
    print(f"✅ [收集完成] 共 {count} 条数据")
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

# =====
# 数据分析工具
# =====

@opinion_agent.tool
async def start_analysis(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """开始数据分析"""
    await log_and_update(ctx, "analyzing", "开始分析收集到的数据...")
    print(f"\n{'='*60}\n📊 数据分析阶段\n{'='*60}")
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

@opinion_agent.tool
async def get_batch_data(
    ctx: RunContext[StateDeps[OpinionState]], 
    batch_index: int
) -> str:
    """获取指定批次的数据用于分析
    
    参数:
    - batch_index: 批次索引（从0开始）
    
    返回:
    - 该批次的数据详情，或错误信息
    """
    raw_data = ctx.deps.state.raw_data
    if not raw_data:
        return "错误：没有收集到数据"
    
    batch_size = ctx.deps.state.batch_size
    start_idx = batch_index * batch_size
    end_idx = min(start_idx + batch_size, len(raw_data))
    
    if start_idx >= len(raw_data):
        return f"错误：批次 {batch_index} 超出范围（总数据: {len(raw_data)}条，批次大小: {batch_size}）"
    
    batch_data = raw_data[start_idx:end_idx]
    
    data_text = f"批次 {batch_index + 1} 数据（{start_idx + 1}-{end_idx}/{len(raw_data)}）：\n\n"
    for i, item in enumerate(batch_data, start_idx + 1):
        data_text += f"{i}. **{item.title}**\n"
        data_text += f"   来源: {item.source}\n"
        data_text += f"   摘要: {item.snippet[:150]}...\n"
        data_text += f"   日期: {item.date}\n\n"
    
    return data_text

@opinion_agent.tool
async def run_standard_analysis(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """
    使用统一标准对数据进行量化分析
    
    这个工具会自动计算：
    - 关键词（基于词频统计，过滤停用词）
    - 情感得分和分布（基于情感词典，-1到1）
    - 热度趋势（7个时间点，模拟舆情曲线）
    
    返回: 标准化分析结果的 JSON 字符串
    """
    data_list = [
        {
            "title": item.title,
            "snippet": item.snippet,
            "source": item.source,
            "date": item.date
        }
        for item in ctx.deps.state.raw_data
    ]
    
    # 使用标准化分析
    result = AnalysisStandards.analyze_data(data_list)
    
    print(f"🔬 [标准化分析] Keywords={result['keywords'][:5]}, Sentiment={result['sentiment_score']}")
    
    import json
    return json.dumps(result, ensure_ascii=False, indent=2)

@opinion_agent.tool
async def get_data_overview(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """获取数据概览，用于规划分批分析"""
    raw_data = ctx.deps.state.raw_data
    if not raw_data:
        return "错误：没有收集到数据"
    
    batch_size = ctx.deps.state.batch_size
    total_count = len(raw_data)
    batch_count = (total_count + batch_size - 1) // batch_size  # 向上取整
    
    overview = f"""
数据概览：
- 总数据量: {total_count} 条
- 批次大小: {batch_size} 条/批
- 总批次数: {batch_count} 批

建议流程:
1. 对每个批次（batch_index 0 到 {batch_count - 1}）调用 get_batch_data 获取数据
2. 分析每个批次并调用 save_batch_analysis 保存摘要
3. 所有批次完成后，调用 merge_batch_analyses 合并结果
4. 调用 save_analysis_result 保存最终分析

数据来源分布：
"""
    
    # 统计来源分布
    source_counts = {}
    for item in raw_data:
        source_counts[item.source] = source_counts.get(item.source, 0) + 1
    
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        overview += f"- {source}: {count} 条\n"
    
    return overview

@opinion_agent.tool
async def save_batch_analysis(
    ctx: RunContext[StateDeps[OpinionState]],
    batch_index: int,
    analysis_summary: str
) -> StateSnapshotEvent:
    """保存单个批次的分析摘要
    
    参数:
    - batch_index: 批次索引
    - analysis_summary: 该批次的分析摘要（关键词、情感、主要观点等）
    """
    # 确保列表足够长
    while len(ctx.deps.state.batch_analyses) <= batch_index:
        ctx.deps.state.batch_analyses.append("")
    
    ctx.deps.state.batch_analyses[batch_index] = analysis_summary
    
    completed = sum(1 for s in ctx.deps.state.batch_analyses if s)
    total = len(ctx.deps.state.batch_analyses)
    
    await log_and_update(
        ctx,
        "analyzing",
        f"批次分析进度: {completed}/{total} 完成"
    )
    
    print(f"📊 [批次 {batch_index + 1}] 分析完成: {analysis_summary[:100]}...")
    
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

@opinion_agent.tool
async def merge_batch_analyses(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """合并所有批次的分析摘要，返回综合视图"""
    if not ctx.deps.state.batch_analyses:
        return "错误：没有批次分析结果"
    
    merged = f"批次分析汇总（共 {len(ctx.deps.state.batch_analyses)} 批）：\n\n"
    
    for i, summary in enumerate(ctx.deps.state.batch_analyses):
        if summary:
            merged += f"批次 {i + 1}:\n{summary}\n\n"
    
    merged += "\n请基于以上批次分析，提取整体的关键词、情感倾向、热度趋势等。"
    
    return merged

@opinion_agent.tool
async def save_analysis_result(
    ctx: RunContext[StateDeps[OpinionState]],
    keywords: List[str],
    sentiment_score: float,
    sentiment_distribution: Dict[str, int],
    heat_trend: List[int],
    summary: str,
) -> StateSnapshotEvent:
    """保存分析结果 - 前端实时更新！"""
    result = AnalysisResult(
        keywords=keywords,
        sentiment_score=sentiment_score,
        sentiment_distribution=sentiment_distribution,
        heat_trend=heat_trend,
        summary=summary,
    )
    ctx.deps.state.analysis = result
    
    await log_and_update(
        ctx,
        "analyzed",
        f"分析完成 - 情感得分: {sentiment_score:.2f}, 正面占比: {sentiment_distribution.get('正面', 0)}%"
    )
    
    print(f"📊 [分析完成] Keywords={keywords}, Sentiment={sentiment_score}")
    
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

@opinion_agent.tool
async def finish_analysis(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """完成数据分析"""
    await log_and_update(ctx, "analyzed", "数据分析完成")
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

# =====
# 报告撰写工具
# =====

@opinion_agent.tool
async def start_writing(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """开始撰写报告"""
    await log_and_update(ctx, "writing", "开始撰写舆情报告...")
    print(f"\n{'='*60}\n📝 报告撰写阶段\n{'='*60}")
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

@opinion_agent.tool
async def get_analysis_data(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """获取分析数据用于撰写报告"""
    if not ctx.deps.state.analysis:
        return "错误：没有分析结果"
    
    analysis = ctx.deps.state.analysis
    raw_data = ctx.deps.state.raw_data
    
    data_text = f"""
分析数据摘要：

关键词: {', '.join(analysis.keywords)}
情感得分: {analysis.sentiment_score:.2f} (-1到1)
情感分布:
  - 正面: {analysis.sentiment_distribution.get('正面', 0)}%
  - 中性: {analysis.sentiment_distribution.get('中性', 0)}%
  - 负面: {analysis.sentiment_distribution.get('负面', 0)}%

热度趋势: {analysis.heat_trend}
分析摘要: {analysis.summary}

数据样本 (前5条):
"""
    for i, item in enumerate(raw_data[:5], 1):
        data_text += f"\n{i}. {item.title}\n   来源: {item.source} | {item.date}\n   {item.snippet[:150]}...\n"
    
    data_text += f"\n总数据量: {len(raw_data)} 条"
    
    return data_text

@opinion_agent.tool
async def save_report(ctx: RunContext[StateDeps[OpinionState]], report_content: str) -> StateSnapshotEvent:
    """保存报告内容 - 前端实时更新！"""
    ctx.deps.state.report_text = report_content
    
    await log_and_update(ctx, "written", f"报告撰写完成 ({len(report_content)} 字符)")
    
    print(f"✅ [报告完成] {len(report_content)} 字符")
    
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

@opinion_agent.tool
async def finish_writing(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """完成报告撰写"""
    await log_and_update(ctx, "written", "报告撰写完成")
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

# =====
# HTML 渲染工具
# =====

@opinion_agent.tool
async def render_html(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """渲染 HTML 报告"""
    await log_and_update(ctx, "rendering", "正在将 Markdown 渲染为 HTML...")
    
    if not ctx.deps.state.report_text or not ctx.deps.state.analysis:
        raise ValueError("缺少报告内容或分析结果")
    
    report_text = ctx.deps.state.report_text
    analysis = ctx.deps.state.analysis
    keyword = ctx.deps.state.keyword or "关键词"
    
    # Markdown 转 HTML
    try:
        import markdown
        report_html = markdown.markdown(
            report_text,
            extensions=['extra', 'codehilite', 'tables', 'toc']
        )
    except ImportError:
        report_html = report_text.replace('\n\n', '</p><p>').replace('\n', '<br>')
        report_html = f"<p>{report_html}</p>"
    
    # 生成完整 HTML (简化版，可以后续扩展)
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{keyword} - 舆情分析报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 20px;
            line-height: 1.8;
        }}
        .container {{ 
            max-width: 900px; 
            margin: 0 auto; 
            background: white; 
            padding: 50px; 
            border-radius: 16px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{ 
            color: #1a202c; 
            border-bottom: 3px solid #667eea; 
            padding-bottom: 15px; 
            margin-bottom: 30px;
        }}
        .report-body {{ color: #4a5568; }}
        .report-body h2 {{ color: #2d3748; margin-top: 32px; margin-bottom: 16px; }}
        .report-body h3 {{ color: #4a5568; margin-top: 24px; margin-bottom: 12px; }}
        .report-body p {{ margin-bottom: 16px; }}
        .report-body ul, .report-body ol {{ margin-left: 24px; margin-bottom: 16px; }}
        .report-body strong {{ color: #2d3748; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {keyword} 舆情分析报告</h1>
        <div class="report-body">{report_html}</div>
    </div>
</body>
</html>"""
    
    ctx.deps.state.final_html = html_content
    
    await log_and_update(ctx, "rendering", "HTML 渲染完成")
    
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

@opinion_agent.tool
async def mark_complete(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """标记任务完成"""
    await log_and_update(ctx, "complete", "✨ 舆情分析报告已生成！")
    print(f"\n{'='*60}\n✅ 任务完成！\n{'='*60}\n")
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)

