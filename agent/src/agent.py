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

from agentrun.integration.pydantic_ai import model, sandbox_toolset, toolset
from agentrun.sandbox import TemplateType
from agentrun.utils.config import Config

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
    
    raw_data: List[SearchResult] = Field(default_factory=list)
    collected_data_summary: List[Dict[str, str]] = Field(default_factory=list, description="Summary of collected data for frontend display")
    analysis: Optional[AnalysisResult] = None
    report_text: str = Field(default="")
    final_html: str = Field(default="")

# =====
# Tool Setup
# =====

agentrun_model = model("sdk-test-model-service")
# agentrun_code_interpreter = sandbox_toolset(
#     "sdk-test-code-interpreter",
#     template_type=TemplateType.CODE_INTERPRETER,
# )

# 配置超时时间（60秒），避免搜索请求超时
search_config = Config(timeout=60)
agentrun_code_interpreter = toolset("web-search-baidu-8baa", config=search_config)
agentrun_browser = [] 
# sandbox_toolset(
#     "sdk-test-browser",
#     template_type=TemplateType.BROWSER,
# )

print("=" * 80)
print("🚀 INITIALIZING MULTI-AGENT OPINION ANALYSIS SYSTEM")
print("=" * 80)
print(f"✓ Model: sdk-test-model-service")
print(f"✓ Code Interpreter Tools: {len(agentrun_code_interpreter)} loaded")
print(f"  → Data Analyzer 模式: {'Python 执行环境' if len(agentrun_code_interpreter) > 0 else 'LLM 推理分析'}")
print(f"✓ Browser/Collection Tools: {len(agentrun_browser)} loaded")
print(f"  → Data Collector 模式: 自动选择可用工具")
print("=" * 80 + "\n")

# =====
# Sub-Agents (专业 Agents)
# =====

# 1. 数据收集 Agent
# 自动使用所有可用的工具（包括但不限于 browser 工具）
collection_tools = [*agentrun_code_interpreter] if len(agentrun_code_interpreter) > 0 else []

data_collector = Agent(
    name="data_collector",
    model=agentrun_model,
    deps_type=StateDeps[OpinionState],
    tools=collection_tools,
    retries=3,  # 增加重试次数
    system_prompt=dedent(f"""
        你是数据收集专家。你的任务是收集关键词相关的舆情信息。
        
        {'=' * 60}
        当前时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}
        可用工具: {len(collection_tools)} 个数据收集工具
        {'=' * 60}
        
        工作目标：
        - 收集多条高质量的相关信息（具体数量见 max_results）
        - 确保来源多样化（新闻、社交媒体、官方报道等）
        - 信息要真实、准确、时效性强
        - **优先收集最新的信息**（距离当前时间越近越好）
        
        搜索策略（重要）：
        - **每次搜索使用不同的关键词组合**，避免重复
        - 建议的搜索角度：
          * 基础搜索："关键词"
          * 新闻搜索："关键词 新闻"、"关键词 最新动态"
          * 社交媒体："关键词 微博"、"关键词 知乎"
          * 深度分析："关键词 分析"、"关键词 评论"
          * 时间限定："关键词 2024"、"关键词 近期"
        - 每次搜索后，从结果中提取不同的条目
        - 确保不要重复保存相同的信息
        
        工作流程：
        
        1. 使用搜索工具收集数据：
           {'- 你有搜索工具可以使用（如 baidu_search）' if len(collection_tools) > 0 else '- 当前没有外部搜索工具'}
           - 每次搜索使用不同的关键词组合，避免重复
           - 仔细阅读搜索返回的 JSON 结果
        
        2. 从搜索结果中提取有价值信息：
           - 百度搜索返回格式: {{"textContent": [...], "videoContent": [...]}}
           - textContent 中每个条目包含: title, text, link, coverImage
           - **你需要阅读返回结果，判断哪些信息有价值**
           - 过滤掉广告、推广、无关信息
           - 优先选择权威来源、最新信息
        
        3. 保存每条有价值的信息：
           - 对每条信息调用 save_search_result
           - 参数: title, url, snippet, source, date
           - title: 使用 textContent 中的 title
           - url: 使用 textContent 中的 link
           - snippet: 使用 textContent 中的 text（摘要）
           - source: 填写"百度搜索"或具体来源
           - date: 使用当前日期 (YYYY-MM-DD 格式)
        
        4. 完成收集：
           - 达到足够数量后，调用 finish_collection
        
        重要规则：
        - **每找到一条有价值信息，立即调用 save_search_result**
        - 不要保存广告、推广、重复的信息
        - 最后必须调用 finish_collection
        - 优先保存最新的、权威的信息
    """).strip()
)

# 2. 数据分析 Agent
# 根据是否有 code interpreter 工具来决定分析策略
has_code_interpreter = len(agentrun_code_interpreter) > 0

data_analyzer = Agent(
    name="data_analyzer",
    model=agentrun_model,
    deps_type=StateDeps[OpinionState],
    retries=5,
    tools=[*agentrun_code_interpreter] if has_code_interpreter else [],
    system_prompt=dedent(f"""
        你是数据分析专家。你的任务是分析收集到的舆情数据。
        
        {'=' * 60}
        可用工具: {'Code Interpreter (Python 执行环境)' if has_code_interpreter else '无外部工具 (使用 LLM 推理)'}
        {'=' * 60}
        
        工作流程：
        
        第一步：获取数据
        - 调用 get_raw_data 获取已收集的原始数据
        - 仔细阅读每条数据的标题、摘要、来源和时间
        
        第二步：执行分析
        {'如果有 Code Interpreter 工具:' if has_code_interpreter else '使用你的分析能力:'}
        {'''- 使用 sandbox_write_file 将数据写入 JSON 文件
        - 使用 sandbox_execute_code 编写并执行 Python 分析代码
        - Python 代码应包括:
          * 关键词提取 (词频分析、TF-IDF 等)
          * 情感分析 (基于关键词和上下文判断正面/负面/中性)
          * 热度趋势模拟 (基于时间分布)
        - 确保代码缩进正确，使用 try-except 处理错误''' if has_code_interpreter else '''- 仔细阅读所有数据的内容和摘要
        - 提取高频关键词 (技术、产品、战略等)
        - 分析情感倾向:
          * 正面: 赞扬、支持、看好、创新等词汇
          * 负面: 批评、质疑、担忧等词汇
          * 中性: 客观描述、中立报道
        - 估算情感分布比例
        - 根据发布时间推断热度趋势
        - 生成数据驱动的分析摘要'''}
        
        第三步：保存结果
        - 使用 save_analysis_result 保存分析结果，包括:
          * keywords: 关键词列表 (5-10个)
          * sentiment_score: 情感得分 (-1到1, 负面到正面)
          * sentiment_distribution: {{'正面': X, '中性': Y, '负面': Z}} (加起来100)
          * heat_trend: 热度趋势列表 (模拟或推测的数值)
          * summary: 100-200字的分析摘要
        - 调用 finish_analysis 标记完成
        
        重要原则：
        - 分析必须基于真实收集的数据，不得编造
        - 结论要有数据支撑，标注样本量和置信度
        - 保持客观、专业的分析视角
        - 深入挖掘数据背后的模式和趋势
        - 识别异常值和特殊案例
        - 考虑时间维度和空间维度的差异
        {'- 确保 Python 代码格式正确，使用科学的分析方法' if has_code_interpreter else '- 发挥 LLM 的语义理解优势，进行深度文本分析'}
        
        质量标准：
        - 关键词提取：必须反映数据的核心主题，不要泛泛而谈
        - 情感分析：基于实际用词和语气，避免过度简化
        - 热度趋势：合理推测，符合传播规律
        - 分析摘要：简洁有力，突出关键发现和异常点
    """).strip()
)

# 3. 报告撰写 Agent
report_writer = Agent(
    name="report_writer",
    model=agentrun_model,
    deps_type=StateDeps[OpinionState],
    tools=[],  # 工具会在下面通过装饰器注册
    system_prompt=dedent("""
        你是具有 10 年以上经验的企业级舆情分析专家，曾服务于多家上市公司和政府机构。
        你的报告需要达到可直接提交给 C-level 高管和董事会的标准。
        
        工作流程：
        1. 使用 get_analysis_data 获取完整的分析数据
        2. 深入研读数据，识别深层模式和隐含风险
        3. 撰写一份具有战略洞察力的专业报告
        4. 使用 save_report 保存报告
        
        ═══════════════════════════════════════════════════════════
        报告结构（严格使用 Markdown 格式）
        ═══════════════════════════════════════════════════════════
        
        # [关键词] 舆情分析报告
        
        > **报告摘要**: 用 2-3 句话概括核心发现和关键风险/机会
        
        ## 一、舆情概况
        
        ### 1.1 数据基础
        - 监测时间范围：[具体日期]
        - 数据来源：[列出主要来源渠道]
        - 样本规模：共采集 X 条有效数据
        - 覆盖平台：[微博/知乎/新闻媒体等]
        
        ### 1.2 整体态势
        - 情感倾向：正面 X%、中性 Y%、负面 Z%（必须使用真实数据）
        - 舆情指数：[根据热度趋势判断] 高/中/低
        - 传播特征：[病毒式传播/线性增长/快速消退等]
        
        ## 二、舆情演进分析
        
        ### 2.1 时间脉络
        - **起始期**：描述舆情最初如何产生、首发平台、初始影响力
        - **发酵期**：分析话题如何扩散、关键节点、媒体介入情况
        - **高峰期**：识别舆情峰值时间、最大传播范围、核心议题
        - **衰减期**：说明舆情如何降温、残留影响
        
        ### 2.2 核心议题
        基于关键词分析，识别 3-5 个核心讨论话题：
        1. **[话题1]**: 占比 X%，主要观点...
        2. **[话题2]**: 占比 Y%，主要观点...
        3. ...
        
        ## 三、成因与驱动因素
        
        ### 3.1 直接诱因
        分析舆情爆发的直接触发事件，引用具体案例和数据
        
        ### 3.2 深层原因
        - **社会背景**：相关社会现象、政策环境
        - **利益相关**：涉及哪些利益主体，各方诉求
        - **传播机制**：信息如何被放大，有无组织化推动
        
        ### 3.3 情感驱动
        - 正面情感来源：[基于数据分析]
        - 负面情感来源：[基于数据分析]
        - 中性讨论特征：[基于数据分析]
        
        ## 四、多维度观点透视
        
        ### 4.1 主流观点阵营
        **支持方** (约 X%)
        - 核心论据：...
        - 代表性评论：引用数据中的实例
        - 人群特征：...
        
        **质疑方** (约 Y%)
        - 核心论据：...
        - 代表性评论：引用数据中的实例
        - 人群特征：...
        
        **中立方** (约 Z%)
        - 观点特征：...
        
        ### 4.2 意见领袖影响
        识别关键意见领袖的立场和影响力（如果数据中有）
        
        ## 五、风险评估与趋势研判
        
        ### 5.1 短期预测（1-2周）
        基于热度趋势数据，预测：
        - 舆情走向：[上升/平稳/下降]
        - 可能的新话题点
        - 需要重点关注的风险
        
        ### 5.2 中长期影响
        - 对品牌/产品/政策的持续影响
        - 可能的演化方向
        - 历史相似案例参考
        
        ### 5.3 风险等级
        综合评估：**[高风险/中等风险/低风险]**
        
        风险维度分析：
        - 传播风险：★★★☆☆
        - 声誉风险：★★★★☆  
        - 法律风险：★☆☆☆☆
        - 经济风险：★★☆☆☆
        
        ## 六、应对建议
        
        ### 6.1 即时响应策略
        1. **官方声明**：建议发布时机、核心内容、传播渠道
        2. **舆论引导**：关键话术、目标人群、预期效果
        3. **危机公关**：应急预案、协调机制
        
        ### 6.2 中长期策略
        1. 品牌修复路径
        2. 用户信任重建
        3. 监测预警机制
        
        ## 七、结论与建议
        
        用 3-5 个要点总结核心发现和最重要的行动建议。
        
        ---
        
        **报告生成时间**: {current_time}  
        **数据样本量**: {data_count} 条  
        **分析师签名**: AI 舆情分析系统  
        **报告编号**: {report_id}
        
        ═══════════════════════════════════════════════════════════
        写作标准
        ═══════════════════════════════════════════════════════════
        
        1. **数据驱动**: 每个结论必须有数据支撑，明确标注百分比和数量
        2. **深度洞察**: 不满足于表面现象，挖掘深层原因和隐含风险
        3. **专业术语**: 使用舆情分析专业术语（传播矩阵、情感指数等）
        4. **战略视角**: 站在决策者角度，提供可执行的战略建议
        5. **客观中立**: 保持第三方专业立场，避免价值判断
        6. **结构严谨**: 逻辑清晰，层次分明，便于快速阅读
        7. **语言精炼**: 避免冗余，信息密度高，字字珠玑
        8. **风险意识**: 明确指出潜在风险，不回避敏感问题
        
        报告长度要求：1500-2500 字，信息量充实，避免空话套话。
    """).strip()
  )

# =====
# Main Orchestrator Agent (编排 Agent)
# =====

opinion_agent = Agent(
    name="opinion_agent",
    model=agentrun_model,
    deps_type=StateDeps[OpinionState],
  system_prompt=dedent("""
        你是舆情分析系统的总指挥。你负责协调三个专业团队完成舆情分析。
        
        严格按照以下流程执行：
        
        阶段 1: 数据收集
        - 调用 update_status 设置状态为 "collecting"
        - 调用 start_data_collection 启动数据收集
        - 等待收集完成
        
        阶段 2: 数据分析
        - 调用 update_status 设置状态为 "analyzing"
        - 调用 start_data_analysis 启动数据分析
        - 等待分析完成
        
        阶段 3: 报告撰写
        - 调用 update_status 设置状态为 "writing"
        - 调用 start_report_writing 启动报告撰写
        - 等待撰写完成
        
        阶段 4: HTML 渲染
        - 调用 update_status 设置状态为 "rendering"
        - 调用 render_html 生成最终 HTML
        
        阶段 5: 完成
        - 调用 update_status 设置状态为 "complete"
        - 向用户报告完成情况
        
        重要规则：
        - 必须严格按顺序执行
        - 每个阶段完成后才能进入下一阶段
        - 随时更新状态让用户了解进度
        - 如果某阶段失败，报告错误并停止
  """).strip()
)

# =====
# Shared State Management Tools
# =====

async def log_and_update(ctx: RunContext[StateDeps[OpinionState]], status: str, message: str):
    """内部辅助函数：更新状态和日志"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = f"[{timestamp}] {message}"
    ctx.deps.state.status = status
    ctx.deps.state.logs.append(log_entry)
    print(f"📊 {log_entry}")

@opinion_agent.tool
async def update_status(
    ctx: RunContext[StateDeps[OpinionState]], status: str, log: str
) -> StateSnapshotEvent:
    """更新系统状态并添加日志（前端实时可见）"""
    await log_and_update(ctx, status, log)
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state,
    )

# =====
# Data Collection Tools
# =====

@data_collector.tool
async def save_search_result(
    ctx: RunContext[StateDeps[OpinionState]],
    title: str,
    url: str,
    snippet: str,
    source: str,
    date: str,
) -> StateSnapshotEvent:
    """保存一条搜索结果"""
    # 检查是否已达到最大数量
    if len(ctx.deps.state.raw_data) >= ctx.deps.state.max_results:
        print(f"⚠️ 已达到最大结果数 {ctx.deps.state.max_results}，跳过保存")
        return StateSnapshotEvent(
            type=EventType.STATE_SNAPSHOT,
            snapshot=ctx.deps.state,
        )
    
    result = SearchResult(
        title=title, url=url, snippet=snippet, source=source, date=date
    )
    ctx.deps.state.raw_data.append(result)
    
    # 同步更新前端展示的摘要
    summary_item = {
        "title": title,
        "url": url,
        "source": source,
    }
    ctx.deps.state.collected_data_summary.append(summary_item)
    
    current_count = len(ctx.deps.state.raw_data)
    summary_count = len(ctx.deps.state.collected_data_summary)
    max_count = ctx.deps.state.max_results
    
    await log_and_update(
        ctx, 
        "collecting", 
        f"收集数据 [{current_count}/{max_count}]: {source} - {title[:30]}..."
    )
    
    print(f"💾 [SAVED {current_count}/{max_count}] {source}: {title[:50]}...")
    print(f"📊 [DEBUG] collected_data_summary count: {summary_count}, last item: {summary_item}")
    print(f"📊 [DEBUG] Returning StateSnapshotEvent with {summary_count} items in collected_data_summary")
    
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state,
    )

@data_collector.tool
async def finish_collection(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """标记数据收集完成"""
    count = len(ctx.deps.state.raw_data)
    await log_and_update(ctx, "collected", f"数据收集完成，共 {count} 条")
    return f"收集完成：{count} 条数据"

@opinion_agent.tool
async def start_data_collection(ctx: RunContext[StateDeps[OpinionState]], keyword: str) -> StateSnapshotEvent:
    """启动数据收集子 Agent - 返回 StateSnapshotEvent 确保前端实时更新"""
    print(f"\n{'='*60}\n🔍 启动数据收集 Agent\n{'='*60}")
    
    ctx.deps.state.keyword = keyword
    await log_and_update(ctx, "collecting", f"开始收集关键词 '{keyword}' 的相关数据...")
    
    # 检查是否有收集工具
    if len(collection_tools) == 0:
        error_msg = "错误：没有配置数据收集工具。请提供搜索工具或浏览器工具。"
        print(f"❌ {error_msg}")
        await log_and_update(ctx, "idle", error_msg)
        raise ValueError(error_msg)
    
    # 运行数据收集 Agent（带超时和错误处理）
    try:
        result = await data_collector.run(
            f"""请收集关于 '{keyword}' 的舆情数据。

步骤：
1. 使用 baidu_search 搜索不同角度的关键词
2. 阅读返回的 JSON 结果（格式: {{"textContent": [...], "videoContent": [...]}}）
3. 从 textContent 中挑选有价值的信息
4. 对每条有价值信息调用 save_search_result(title, url, snippet, source, date)
5. 重复步骤 1-4，直到达到目标数量（{ctx.deps.state.max_results}条）
6. 调用 finish_collection()

示例：
- baidu_search(search_input="{keyword} 最新")
  → 从返回的 textContent 中选择 3-5 条
  → 每条调用 save_search_result(...)
- baidu_search(search_input="{keyword} 新闻")
  → 从返回的 textContent 中选择 3-5 条
  → 每条调用 save_search_result(...)
- finish_collection()

注意：
- **你需要判断哪些信息有价值，过滤广告和无关内容**
- 如果搜索超时，继续尝试其他关键词
- 完成后必须调用 finish_collection""",
            deps=ctx.deps
        )
    except Exception as e:
        error_msg = f"数据收集过程出错: {str(e)}"
        print(f"❌ {error_msg}")
        
        # 如果已经收集到一些数据，可以继续
        collected_count = len(ctx.deps.state.raw_data)
        if collected_count > 0:
            print(f"⚠️ 虽然出现错误，但已收集到 {collected_count} 条数据，继续流程")
            await log_and_update(ctx, "collected", f"收集完成（部分成功）: {collected_count} 条")
            return StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot=ctx.deps.state,
            )
        else:
            await log_and_update(ctx, "idle", error_msg)
            raise ValueError(error_msg)
    
    collected_count = len(ctx.deps.state.raw_data)
    if collected_count == 0:
        error_msg = "错误：未能收集到任何数据。请检查搜索工具是否正常工作。"
        print(f"❌ {error_msg}")
        await log_and_update(ctx, "idle", error_msg)
        raise ValueError(error_msg)
    
    # 返回 StateSnapshotEvent 确保前端立即看到收集结果
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state,
    )

# =====
# Data Analysis Tools
# =====

@data_analyzer.tool
async def get_raw_data(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """获取已收集的原始数据用于分析"""
    raw_data = ctx.deps.state.raw_data
    
    if not raw_data:
        return "错误：没有收集到数据"
    
    # 返回格式化的数据供 LLM 分析
    data_text = f"共收集到 {len(raw_data)} 条数据：\n\n"
    
    for i, item in enumerate(raw_data, 1):
        data_text += f"""
数据 {i}:
- 标题: {item.title}
- 来源: {item.source}
- 时间: {item.date}
- 摘要: {item.snippet}
- 链接: {item.url}
{'='*60}
"""
    
    return data_text

@data_analyzer.tool
async def save_analysis_result(
    ctx: RunContext[StateDeps[OpinionState]],
    keywords: List[str],
    sentiment_score: float,
    sentiment_distribution: Dict[str, int],
    heat_trend: List[int],
    summary: str,
) -> StateSnapshotEvent:
    """保存数据分析结果"""
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
    
    print(f"📊 [SAVED] Analysis: Sentiment={sentiment_score}, Keywords={keywords}")
    
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state,
    )

@data_analyzer.tool
async def finish_analysis(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """标记数据分析完成"""
    await log_and_update(ctx, "analyzed", "数据分析完成")
    return "分析完成"

@opinion_agent.tool
async def start_data_analysis(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """启动数据分析子 Agent"""
    print(f"\n{'='*60}\n📈 启动数据分析 Agent\n{'='*60}")
    
    if not ctx.deps.state.raw_data:
        return "错误：没有数据可供分析"
    
    await log_and_update(ctx, "analyzing", "开始分析收集到的数据...")
    
    # 准备数据给分析 Agent
    data_count = len(ctx.deps.state.raw_data)
    
    analysis_prompt = f"""请分析关键词 '{ctx.deps.state.keyword}' 的 {data_count} 条舆情数据。

步骤：
1. 使用 get_raw_data 获取所有收集到的数据
2. 仔细阅读每条数据的内容、来源和时间
3. 执行深度分析：
   - 提取关键主题词（5-10个）
   - 分析整体情感倾向（正面/中性/负面的比例）
   - 计算情感得分（-1 到 1）
   - 推断或模拟热度趋势
   - 撰写分析摘要（100-200字）
4. 使用 save_analysis_result 保存你的分析结果
5. 调用 finish_analysis 标记完成

要求：
- 分析必须基于真实数据内容
- 结论要有数据支撑
- 保持客观、专业的分析视角
"""

    if has_code_interpreter:
        analysis_prompt += """
- 优先使用 Code Interpreter 进行量化分析
- 确保 Python 代码格式正确（特别注意缩进）
"""
    else:
        analysis_prompt += """
- 使用你的语言理解和推理能力进行深度分析
- 基于数据内容推断情感和趋势
"""
    
    result = await data_analyzer.run(analysis_prompt, deps=ctx.deps)
    
    # 检查分析是否完成
    if ctx.deps.state.analysis:
        return f"数据分析完成"
    else:
        return "数据分析执行完毕，请检查是否调用了 save_analysis_result"

# =====
# Report Writing Tools
# =====

@report_writer.tool
async def get_analysis_data(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """获取分析数据用于报告撰写"""
    analysis = ctx.deps.state.analysis
    keyword = ctx.deps.state.keyword
    raw_data = ctx.deps.state.raw_data
    
    if not analysis:
        return "错误：没有分析结果"
    
    # 返回结构化的分析数据供 LLM 使用
    data_summary = f"""
关键词: {keyword}
数据源数量: {len(raw_data)}
    
分析结果：
- 关键词: {', '.join(analysis.keywords)}
- 情感得分: {analysis.sentiment_score:.2f} (范围 -1 到 1)
- 情感分布: 正面 {analysis.sentiment_distribution.get('正面', 0)}%, 中性 {analysis.sentiment_distribution.get('中性', 0)}%, 负面 {analysis.sentiment_distribution.get('负面', 0)}%
- 热度趋势: {analysis.heat_trend}
- 分析摘要: {analysis.summary}

原始数据样本:
"""
    # 添加几条原始数据作为参考
    for i, item in enumerate(raw_data[:3], 1):
        data_summary += f"\n{i}. [{item.source}] {item.title}\n   摘要: {item.snippet}\n   时间: {item.date}"
    
    return data_summary

@report_writer.tool
async def save_report(ctx: RunContext[StateDeps[OpinionState]], report_content: str) -> StateSnapshotEvent:
    """保存生成的报告内容"""
    ctx.deps.state.report_text = report_content
    
    await log_and_update(ctx, "written", f"报告撰写完成 ({len(report_content)} 字符)")
    
    print(f"✅ [REPORT] Saved ({len(report_content)} chars)")
    
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state,
    )

@opinion_agent.tool
async def start_report_writing(ctx: RunContext[StateDeps[OpinionState]]) -> str:
    """启动报告撰写子 Agent"""
    print(f"\n{'='*60}\n📝 启动报告撰写 Agent\n{'='*60}")
    
    if not ctx.deps.state.analysis:
        return "错误：没有分析结果"
    
    await log_and_update(ctx, "writing", "开始撰写舆情报告...")
    
    result = await report_writer.run(
        f"""请为关键词 '{ctx.deps.state.keyword}' 撰写一份企业级的舆情分析报告。

步骤：
1. 首先使用 get_analysis_data 工具获取分析数据
2. 仔细阅读分析结果和原始数据样本
3. 基于这些数据撰写一份专业、客观的舆情报告
4. 使用 save_report 工具保存你撰写的报告

要求：
- 报告必须基于真实数据，不要编造
- 使用具体的数字和百分比
- 保持专业、客观的语气
- 结构清晰，逻辑严密""",
        deps=ctx.deps
    )
    
    # 检查报告是否完成
    if ctx.deps.state.report_text:
        return f"报告撰写完成 ({len(ctx.deps.state.report_text)} 字符)"
    else:
        return "报告撰写执行完毕，请检查是否调用了 save_report"

# =====
# HTML Rendering Tool
# =====

@opinion_agent.tool
async def render_html(ctx: RunContext[StateDeps[OpinionState]]) -> StateSnapshotEvent:
    """渲染最终的 HTML 报告 - 支持 Markdown"""
    print(f"\n{'='*60}\n🎨 开始渲染 HTML（Markdown → HTML）\n{'='*60}")
    
    if not ctx.deps.state.report_text or not ctx.deps.state.analysis:
        raise ValueError("缺少报告内容或分析结果")
    
    await log_and_update(ctx, "rendering", "正在将 Markdown 渲染为精美的 HTML...")
    
    report_text = ctx.deps.state.report_text
    analysis = ctx.deps.state.analysis
    keyword = ctx.deps.state.keyword or "关键词"
    
    # 将 Markdown 转换为 HTML
    try:
        import markdown
        report_html = markdown.markdown(
            report_text,
            extensions=['extra', 'codehilite', 'tables', 'toc']
        )
    except ImportError:
        # 如果没有 markdown 库，使用简单的文本转换
        print("⚠️ markdown 库未安装，使用简单文本转换")
        report_html = report_text.replace('\n\n', '</p><p>').replace('\n', '<br>')
        report_html = f"<p>{report_html}</p>"

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{keyword} - 企业级舆情分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
            font-size: 28px;
        }}
        h2 {{ 
            color: #2d3748; 
            margin-top: 40px; 
            margin-bottom: 20px;
            font-size: 22px;
            display: flex;
            align-items: center;
        }}
        h2::before {{
            content: '';
            width: 4px;
            height: 24px;
            background: #667eea;
            margin-right: 12px;
            border-radius: 2px;
        }}
        .metric-box {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin: 30px 0; 
        }}
        .metric {{ 
            text-align: center; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%); 
            border-radius: 12px;
            transition: transform 0.2s;
        }}
        .metric:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 16px rgba(102, 126, 234, 0.2);
        }}
        .metric-value {{ 
            font-size: 36px; 
            font-weight: bold; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .metric-label {{ 
            font-size: 14px; 
            color: #718096; 
            margin-top: 8px;
        }}
        .chart-container {{ 
            height: 350px; 
            margin: 30px 0; 
            background: #f7fafc;
            padding: 20px;
            border-radius: 12px;
        }}
        .report-body {{ 
            color: #4a5568; 
            line-height: 1.8;
        }}
        .report-body h2 {{
            color: #2d3748;
            margin-top: 32px;
            margin-bottom: 16px;
            font-size: 20px;
        }}
        .report-body h3 {{
            color: #4a5568;
            margin-top: 24px;
            margin-bottom: 12px;
            font-size: 18px;
        }}
        .report-body p {{
            margin-bottom: 16px;
        }}
        .report-body ul, .report-body ol {{
            margin-left: 24px;
            margin-bottom: 16px;
        }}
        .report-body li {{
            margin-bottom: 8px;
        }}
        .report-body strong {{
            color: #2d3748;
            font-weight: 600;
        }}
        .report-body code {{
            background: #f7fafc;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            text-align: center;
            color: #a0aec0;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="report-body">{report_html}</div>
        
        <h2>📊 数据洞察</h2>
        <div class="metric-box">
            <div class="metric">
                <div class="metric-value">{analysis.sentiment_score:.2f}</div>
                <div class="metric-label">情感指数</div>
            </div>
            <div class="metric">
                <div class="metric-value">{analysis.sentiment_distribution.get('正面', 0)}%</div>
                <div class="metric-label">正面占比</div>
            </div>
            <div class="metric">
                <div class="metric-value">{len(ctx.deps.state.raw_data)}</div>
                <div class="metric-label">数据源数量</div>
            </div>
        </div>
        
        <h2>📈 热度趋势分析</h2>
        <div class="chart-container">
            <canvas id="trendChart"></canvas>
        </div>
        
        <div class="footer">
            <p>本报告由 AI 驱动的企业级舆情分析系统自动生成</p>
            <p>© 2024 Opinion Analysis System | Powered by Multi-Agent Architecture</p>
        </div>
    </div>

    <script>
        new Chart(document.getElementById('trendChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps([f'Day {i+1}' for i in range(len(analysis.heat_trend))])},
                datasets: [{{
                    label: '舆情热度',
                    data: {analysis.heat_trend},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointBackgroundColor: '#667eea',
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 12,
                        titleFont: {{ size: 14 }},
                        bodyFont: {{ size: 13 }}
                    }}
                }},
                scales: {{
                    y: {{ 
                        beginAtZero: true,
                        grid: {{ color: 'rgba(0,0,0,0.05)' }}
                    }},
                    x: {{
                        grid: {{ color: 'rgba(0,0,0,0.05)' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    ctx.deps.state.final_html = html_content
    ctx.deps.state.status = "complete"
    
    await log_and_update(ctx, "complete", "✨ 舆情分析报告已生成！")
    
    print(f"✅ [RENDER] Complete\n{'='*60}\n")
    
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state,
    )
