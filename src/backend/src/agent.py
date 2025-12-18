"""
舆情分析系统 - 流式输出架构

核心设计原则：
1. 代码控制流程流转，不依赖 LLM 自主决策
2. 严格执行每个阶段的要求（如必须收集足够数据）
3. 真正的流式输出：搜索、分析、撰写都实时更新
4. 数据质量筛选：相关性、时效性、贡献度
5. 多平台、多角度搜索
6. 深度分析，符合商业标准
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from ag_ui.core import EventType, StateSnapshotEvent
from dataclasses import dataclass, field
from dotenv import load_dotenv
from datetime import datetime
from playwright.async_api import async_playwright

import os
import asyncio
import json
import re

load_dotenv()

from agentrun.integration.pydantic_ai import model
from agentrun.utils.config import Config
from agentrun.sandbox import TemplateType, Sandbox, BrowserSandbox


# =============================================================================
# 自定义 Deps 类（包含 state 和 run_id）
# =============================================================================

@dataclass
class StateDeps:
    """Agent 依赖，包含状态和运行 ID"""
    state: "OpinionState"
    run_id: str = ""


# =============================================================================
# 全局状态存储（用于独立的状态流式更新）
# =============================================================================

global_state_store: Dict[str, "OpinionState"] = {}


# =============================================================================
# 数据模型
# =============================================================================

class SearchResult(BaseModel):
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str
    date: str
    platform: str = "bing"
    relevance_score: float = 0.0  # 相关性得分
    detailed_content: str = ""  # 深入抓取的详细内容


class AnalysisResult(BaseModel):
    """分析结果"""
    keywords: List[str] = Field(default_factory=list)
    sentiment_score: float = 0.0
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict)
    heat_trend: List[int] = Field(default_factory=list)
    summary: str = ""
    key_opinions: List[Dict[str, str]] = Field(default_factory=list)
    risk_assessment: Dict[str, str] = Field(default_factory=dict)


class SandboxInfo(BaseModel):
    """Sandbox 信息"""
    sandbox_id: str
    vnc_url: str
    livestream_url: str
    active: bool = True
    created_at: str = ""


class OpinionState(BaseModel):
    """系统状态"""
    keyword: str = ""
    status: str = "idle"
    logs: List[str] = Field(default_factory=list)
    max_results: int = 50

    raw_data: List[SearchResult] = Field(default_factory=list)
    collected_data_summary: List[Dict[str, str]] = Field(default_factory=list)
    
    analysis: Optional[AnalysisResult] = None
    analysis_progress: str = ""  # 分析进度文本（流式）
    
    report_text: str = ""
    final_html: str = ""
    
    collection_progress: int = 0
    current_phase: str = ""
    
    # Sandbox 管理
    sandboxes: List[SandboxInfo] = Field(default_factory=list)
    active_sandbox_id: str = ""


# =============================================================================
# 配置
# =============================================================================

agentrun_model_name = os.getenv("AGENTRUN_MODEL_NAME", "")
model_name = os.getenv("MODEL_NAME")
agentrun_browser_sandbox_name = os.getenv("AGENTRUN_BROWSER_SANDBOX_NAME", "")

if not agentrun_model_name:
    raise ValueError("AGENTRUN_MODEL_NAME is not set")

config = Config(timeout=180)
agentrun_model = model(agentrun_model_name, model=model_name, config=config)


# =============================================================================
# Browser Sandbox 管理 - 支持多 Sandbox
# =============================================================================

_sandboxes: Dict[str, BrowserSandbox] = {}
_sandbox_lock = asyncio.Lock()


class SandboxTemplateNotFoundError(Exception):
    """Sandbox 模板不存在错误"""
    pass


class SandboxCreationError(Exception):
    """Sandbox 创建错误"""
    pass


async def create_browser_sandbox() -> Optional[BrowserSandbox]:
    """创建新的 Browser Sandbox 实例
    
    Raises:
        SandboxTemplateNotFoundError: 模板不存在时抛出
        SandboxCreationError: 其他创建错误时抛出
    """
    if not agentrun_browser_sandbox_name:
        return None
    
    async with _sandbox_lock:
        print("🌐 正在创建新的 Browser Sandbox...")
        try:
            sandbox = await Sandbox.create_async(
                template_type=TemplateType.BROWSER,
                template_name=agentrun_browser_sandbox_name,
            )
            _sandboxes[sandbox.sandbox_id] = sandbox
            print(f"✅ Browser Sandbox 创建成功: {sandbox.sandbox_id}")
            return sandbox
        except Exception as e:
            error_msg = str(e).lower()
            # 检测模板不存在的错误
            template_not_found_patterns = [
                "template not found",
                "template does not exist",
                "no such template",
                "template_not_found",
                "not found",
                "无法找到模板",
            ]
            if any(pattern in error_msg for pattern in template_not_found_patterns):
                print(f"❌ Sandbox 模板不存在: {agentrun_browser_sandbox_name}")
                raise SandboxTemplateNotFoundError(
                    f"Sandbox 模板 '{agentrun_browser_sandbox_name}' 不存在，请检查 AGENTRUN_BROWSER_SANDBOX_NAME 配置"
                )
            else:
                print(f"❌ 创建 Sandbox 失败: {e}")
                raise SandboxCreationError(f"创建 Sandbox 失败: {e}")


async def get_browser_sandbox(sandbox_id: str = None) -> Optional[BrowserSandbox]:
    """获取指定或任意可用的 Browser Sandbox
    
    Raises:
        SandboxTemplateNotFoundError: 模板不存在时抛出
        SandboxCreationError: 其他创建错误时抛出
    """
    async with _sandbox_lock:
        if sandbox_id and sandbox_id in _sandboxes:
            return _sandboxes[sandbox_id]
        
        for sid, sandbox in _sandboxes.items():
            return sandbox
        
        if agentrun_browser_sandbox_name:
            try:
                sandbox = await Sandbox.create_async(
                    template_type=TemplateType.BROWSER,
                    template_name=agentrun_browser_sandbox_name,
                )
                _sandboxes[sandbox.sandbox_id] = sandbox
                return sandbox
            except Exception as e:
                error_msg = str(e).lower()
                # 检测模板不存在的错误
                template_not_found_patterns = [
                    "template not found",
                    "template does not exist",
                    "no such template",
                    "template_not_found",
                    "not found",
                    "无法找到模板",
                ]
                if any(pattern in error_msg for pattern in template_not_found_patterns):
                    raise SandboxTemplateNotFoundError(
                        f"Sandbox 模板 '{agentrun_browser_sandbox_name}' 不存在，请检查 AGENTRUN_BROWSER_SANDBOX_NAME 配置"
                    )
                else:
                    raise SandboxCreationError(f"创建 Sandbox 失败: {e}")
        
        return None


async def remove_sandbox(sandbox_id: str) -> None:
    """从管理列表中移除指定的 Sandbox"""
    async with _sandbox_lock:
        if sandbox_id in _sandboxes:
            del _sandboxes[sandbox_id]
            print(f"🗑️ Sandbox 已从管理列表中移除: {sandbox_id[:8]}...")


async def recreate_sandbox_if_closed(sandbox_id: str, error_message: str) -> Optional[BrowserSandbox]:
    """检测 sandbox 是否已关闭，如果关闭则重新创建
    
    Args:
        sandbox_id: 当前使用的 sandbox ID
        error_message: 错误信息
    
    Returns:
        新创建的 sandbox 实例，如果不需要重建则返回 None
    """
    # 检测 sandbox 关闭相关的错误
    closed_error_patterns = [
        "Target page, context or browser has been closed",
        "Browser has been closed",
        "Target closed",
        "Connection closed",
        "Session closed",
        "Page closed",
        "Context closed",
    ]
    
    is_closed_error = any(pattern.lower() in error_message.lower() for pattern in closed_error_patterns)
    
    if is_closed_error:
        print(f"⚠️ 检测到 Sandbox 已关闭: {error_message[:100]}")
        print(f"🔄 正在重新创建 Sandbox...")
        
        # 从管理列表中移除旧的 sandbox
        await remove_sandbox(sandbox_id)
        
        # 创建新的 sandbox
        new_sandbox = await create_browser_sandbox()
        if new_sandbox:
            print(f"✅ 新 Sandbox 创建成功: {new_sandbox.sandbox_id[:8]}...")
            return new_sandbox
        else:
            print(f"❌ 创建新 Sandbox 失败")
            return None
    
    return None


async def get_all_sandboxes() -> List[Dict[str, Any]]:
    """获取所有 Sandbox 信息"""
    from urllib.parse import urlparse, parse_qs, urlencode
    
    result = []
    async with _sandbox_lock:
        for sandbox_id, sandbox in _sandboxes.items():
            try:
                vnc_url = sandbox.get_vnc_url()
                access_token = sandbox.data_api.access_token
                
                parsed = urlparse(vnc_url)
                query_dict = parse_qs(parsed.query)
                query_dict["recording"] = ["false"]
                if access_token:
                    query_dict["Authorization"] = [access_token]
                
                new_path = parsed.path.replace("/ws/liveview", "/ws/livestream")
                new_query = urlencode(query_dict, doseq=True)
                livestream_url = f"{parsed.scheme}://{parsed.netloc}{new_path}?{new_query}"
                
                result.append({
                    "sandbox_id": sandbox_id,
                    "vnc_url": vnc_url,
                    "livestream_url": livestream_url,
                    "active": True,
                })
            except Exception as e:
                print(f"⚠️ 获取 Sandbox {sandbox_id} 信息失败: {e}")
                result.append({
                    "sandbox_id": sandbox_id,
                    "vnc_url": "",
                    "livestream_url": "",
                    "active": False,
                })
    
    return result


# =============================================================================
# 数据质量筛选
# =============================================================================

async def evaluate_relevance(keyword: str, title: str, snippet: str) -> float:
    """
    评估搜索结果的相关性（严格版）
    
    返回 0-1 的得分：
    - 1.0: 高度相关（关键词完全出现）
    - 0.5: 中等相关
    - 0.0: 不相关
    
    核心原则：关键词必须在标题或摘要中出现，否则视为不相关
    """
    # 合并标题和摘要
    text = f"{title} {snippet}"
    text_lower = text.lower()
    
    # 检测关键词是否为中文
    has_chinese_keyword = any('\u4e00' <= char <= '\u9fff' for char in keyword)
    result_has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
    
    # 核心规则：中文关键词必须在结果中有中文内容
    if has_chinese_keyword and not result_has_chinese:
        return 0.0  # 直接返回 0，不相关
    
    # 排除明显的无关网站（在计算分数前先检查）
    irrelevant_patterns = [
        "calculator", "deepseek", "chegg", "stackoverflow", "github.com", 
        "npmjs", "pypi", "pizza", "wordreference", "cambridge", "yahoo字典",
        "翻译", "dictionary", "词典"
    ]
    if any(pattern in text_lower for pattern in irrelevant_patterns):
        return 0.0  # 直接返回 0
    
    score = 0.0
    
    # 1. 关键词完全匹配（最重要，必须条件）
    keyword_in_text = keyword in text
    if keyword_in_text:
        score += 0.6  # 基础分
    else:
        # 关键词不在文本中，检查是否有部分匹配
        if has_chinese_keyword:
            keyword_chars = list(keyword)
            matched_chars = sum(1 for char in keyword_chars if char in text)
            char_match_ratio = matched_chars / len(keyword_chars) if keyword_chars else 0
            
            # 如果匹配率低于 50%，直接返回 0
            if char_match_ratio < 0.5:
                return 0.0
            
            score += 0.4 * char_match_ratio
        else:
            # 英文关键词，检查单词匹配
            keyword_words = keyword.lower().split()
            matched_words = sum(1 for word in keyword_words if word in text_lower)
            word_match_ratio = matched_words / len(keyword_words) if keyword_words else 0
            
            if word_match_ratio < 0.5:
                return 0.0
            
            score += 0.4 * word_match_ratio
    
    # 2. 时效性加分
    time_keywords = ["最新", "今日", "近日", "昨日", "本周", "2024", "2025", "刚刚", "最近", "12月", "11月", "10月"]
    if any(tk in text for tk in time_keywords):
        score += 0.1
    
    # 3. 舆情相关性加分
    opinion_keywords = ["评价", "评论", "看法", "观点", "讨论", "热议", "争议", "反响", "舆论", "如何看待", "怎么看", "网友"]
    if any(ok in text for ok in opinion_keywords):
        score += 0.1
    
    # 4. 平台来源加分（知乎、微博等）
    platform_keywords = ["知乎", "微博", "豆瓣", "B站", "bilibili", "抖音", "小红书", "新浪", "网易", "搜狐", "腾讯"]
    if any(pk in text for pk in platform_keywords):
        score += 0.1
    
    # 5. 排除广告和无关内容
    ad_keywords = ["广告", "推广", "优惠", "折扣", "促销", "点击立即", "免费下载", "立即购买", "官方旗舰店", "购物"]
    if any(ak in text for ak in ad_keywords):
        score -= 0.3
    
    return max(0.0, min(1.0, score))


def is_valid_result(result: SearchResult, keyword: str) -> bool:
    """判断搜索结果是否有效"""
    # 基本检查
    if not result.title or not result.url:
        return False
    
    # URL 有效性
    if not result.url.startswith("http"):
        return False
    
    # 排除明显的广告或无关页面
    exclude_domains = ["ad.", "ads.", "click.", "track."]
    if any(ed in result.url.lower() for ed in exclude_domains):
        return False
    
    return True


# =============================================================================
# 搜索查询生成器
# =============================================================================

def generate_search_queries(keyword: str) -> List[Dict[str, str]]:
    """生成多平台搜索查询
    
    注意：不使用 site: 操作符，因为 cn.bing.com 对其支持不稳定
    改用关键词 + 平台名称的方式搜索
    """
    queries = []
    
    # 基础搜索（最高优先级）
    queries.extend([
        {"query": f"{keyword}", "category": "general"},
        {"query": f"{keyword} 最新消息", "category": "general"},
        {"query": f"{keyword} 2024", "category": "general"},
        {"query": f"{keyword} 2025", "category": "general"},
    ])
    
    # 知乎搜索（知乎内容质量较高）
    queries.extend([
        {"query": f"{keyword} 知乎", "category": "zhihu"},
        {"query": f"{keyword} 如何评价 知乎", "category": "zhihu"},
        {"query": f"{keyword} 怎么看 知乎", "category": "zhihu"},
    ])
    
    # 微博搜索
    queries.extend([
        {"query": f"{keyword} 微博", "category": "weibo"},
        {"query": f"{keyword} 微博热搜", "category": "weibo"},
        {"query": f"{keyword} 微博超话", "category": "weibo"},
    ])
    
    # 新闻搜索
    queries.extend([
        {"query": f"{keyword} 新闻", "category": "news"},
        {"query": f"{keyword} 新闻报道", "category": "news"},
        {"query": f"{keyword} 最新新闻", "category": "news"},
    ])
    
    # 评论和观点
    queries.extend([
        {"query": f"{keyword} 评价", "category": "comments"},
        {"query": f"{keyword} 网友评论", "category": "comments"},
        {"query": f"{keyword} 舆论", "category": "comments"},
        {"query": f"{keyword} 争议", "category": "comments"},
    ])
    
    # 深度分析
    queries.extend([
        {"query": f"{keyword} 分析", "category": "analysis"},
        {"query": f"{keyword} 事件", "category": "analysis"},
        {"query": f"{keyword} 影响", "category": "analysis"},
    ])
    
    # B站（哔哩哔哩）- 年轻用户群体的重要舆论场
    queries.extend([
        {"query": f"{keyword} B站", "category": "bilibili"},
        {"query": f"{keyword} 哔哩哔哩", "category": "bilibili"},
        {"query": f"{keyword} bilibili", "category": "bilibili"},
        {"query": f"{keyword} B站评论", "category": "bilibili"},
        {"query": f"{keyword} B站弹幕", "category": "bilibili"},
    ])
    
    # 抖音
    queries.extend([
        {"query": f"{keyword} 抖音", "category": "douyin"},
    ])
    
    return queries


# =============================================================================
# 主 Agent
# =============================================================================

opinion_agent = Agent(
    agentrun_model,
    deps_type=StateDeps,
    system_prompt="""你是舆情分析系统的执行者。

你的任务是按照以下严格流程执行舆情分析：

【流程】
1. 收到关键词后，调用 collect_data 工具收集数据
2. 数据收集完成后，调用 analyze_data 工具分析数据
3. 分析完成后，调用 write_report 工具撰写报告
4. 报告完成后，调用 render_html 工具生成 HTML

【重要规则】
- 必须按顺序调用工具
- 每个工具只调用一次
- 不要跳过任何步骤
- 不要编造数据

当用户输入关键词时，立即开始执行流程。
""",
    retries=3,
)


# =============================================================================
# 工具：数据收集（流式输出）
# =============================================================================

async def push_state_event(run_id: str, state: OpinionState):
    """推送状态更新事件到事件队列
    
    Args:
        run_id: 运行 ID，用于找到对应的事件队列
        state: 当前状态
    """
    import time
    from event_queue import event_manager
    
    # 创建 STATE_SNAPSHOT 事件，确保 timestamp 是数字
    event = StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=state.model_dump(),
        timestamp=int(time.time() * 1000)  # 毫秒时间戳
    )
    
    # 推送到队列
    await event_manager.push_event(run_id, event)


async def llm_decide_exploration(
    keyword: str,
    page_url: str,
    page_content: str,
    source: str,
    available_actions: List[Dict[str, str]]
) -> Dict:
    """让 LLM 决定是否需要进一步探索页面
    
    Args:
        keyword: 搜索关键词
        page_url: 当前页面 URL
        page_content: 当前页面已提取的内容
        source: 来源平台
        available_actions: 可用的操作列表，如 [{"action": "click_comments", "description": "点击查看评论区"}]
    
    Returns:
        {"should_explore": bool, "action": str, "reason": str}
    """
    if not available_actions:
        return {"should_explore": False, "action": None, "reason": "没有可用的操作"}
    
    prompt = f"""你是舆情分析助手。请根据以下信息决定是否需要进一步探索页面获取更多舆情数据。

【搜索关键词】{keyword}

【当前页面】{page_url}

【来源平台】{source}

【已获取内容预览】（前500字）
{page_content[:500]}

【可用操作】
{json.dumps(available_actions, ensure_ascii=False, indent=2)}

【决策标准】
1. 如果当前内容已经足够丰富（超过300字有效内容），可能不需要进一步探索
2. 如果是微博/B站等平台，评论区通常包含重要的舆情信息，值得探索
3. 如果页面需要登录才能查看更多内容，则不探索
4. 如果相关推荐可能包含更多相关舆情，可以考虑探索
5. 权衡时间成本，每个页面最多探索1-2个操作

请返回 JSON 格式（必须是有效 JSON）：
{{
    "should_explore": true/false,
    "action": "操作名称（如果 should_explore 为 true）",
    "reason": "决策原因（简短说明）"
}}
"""
    
    try:
        explorer = Agent(
            agentrun_model,
            system_prompt="你是舆情分析助手，帮助决定是否需要深入探索页面。只返回有效的 JSON。",
            retries=2,
        )
        
        result = await explorer.run(prompt)
        response_text = result.output if hasattr(result, 'output') else str(result.data)
        
        # 解析 JSON
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            decision = json.loads(json_match.group())
            return decision
    except Exception as e:
        print(f"   ⚠️ LLM 探索决策失败: {str(e)[:50]}")
    
    return {"should_explore": False, "action": None, "reason": "决策失败，跳过探索"}


async def explore_page_with_llm(
    page,
    keyword: str,
    url: str,
    source: str,
    initial_content: str
) -> str:
    """使用 LLM 控制的页面深入探索
    
    Args:
        page: Playwright 页面对象
        keyword: 搜索关键词
        url: 页面 URL
        source: 来源平台
        initial_content: 初始提取的内容
    
    Returns:
        探索后获取的额外内容
    """
    extra_content = ""
    
    # 根据平台定义可用操作
    available_actions = []
    
    if "weibo.com" in url:
        # 微博可用操作
        available_actions = [
            {"action": "view_comments", "description": "查看评论区内容", "selector": ".WB_feed_expand, [class*='comment'], .comment-list"},
            {"action": "view_retweets", "description": "查看转发内容", "selector": ".WB_feed_expand, [class*='repost']"},
        ]
    elif "zhihu.com" in url:
        # 知乎可用操作
        available_actions = [
            {"action": "view_more_answers", "description": "查看更多回答", "selector": ".AnswerItem, .List-item"},
            {"action": "view_comments", "description": "查看评论", "selector": ".Comments-container, .CommentItem"},
        ]
    elif "bilibili.com" in url:
        # B站可用操作
        available_actions = [
            {"action": "view_comments", "description": "查看评论区热门评论", "selector": ".reply-item, .root-reply"},
            {"action": "view_related", "description": "查看相关推荐视频", "selector": ".video-page-card, .recommend-list"},
        ]
    elif any(x in url for x in ["tieba.baidu.com"]):
        # 贴吧可用操作
        available_actions = [
            {"action": "view_replies", "description": "查看楼中楼回复", "selector": ".lzl_content, .j_lzl_c"},
        ]
    
    if not available_actions:
        return extra_content
    
    # 让 LLM 决定是否探索
    decision = await llm_decide_exploration(
        keyword=keyword,
        page_url=url,
        page_content=initial_content,
        source=source,
        available_actions=available_actions
    )
    
    if not decision.get("should_explore", False):
        print(f"   ℹ️ LLM 决定不探索: {decision.get('reason', '未知原因')}")
        return extra_content
    
    action = decision.get("action")
    print(f"   🔍 LLM 决定探索: {action} - {decision.get('reason', '')}")
    
    # 执行探索操作
    try:
        for action_def in available_actions:
            if action_def["action"] == action:
                selector = action_def["selector"]
                
                # 尝试滚动到评论区或相关区域
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(1)
                
                # 尝试点击展开按钮（如果有）
                expand_selectors = [
                    "button:has-text('展开')",
                    "a:has-text('展开')",
                    "span:has-text('展开')",
                    "button:has-text('查看更多')",
                    "a:has-text('查看更多')",
                    ".expand-btn",
                    ".more-btn",
                ]
                for exp_sel in expand_selectors:
                    try:
                        expand_btn = await page.query_selector(exp_sel)
                        if expand_btn:
                            await expand_btn.click()
                            await asyncio.sleep(1)
                            print(f"   ✅ 点击展开按钮")
                            break
                    except:
                        pass
                
                # 提取内容
                for sel in selector.split(", "):
                    try:
                        elems = await page.query_selector_all(sel.strip())
                        for elem in elems[:10]:  # 最多取10个元素
                            text = await elem.inner_text()
                            if text and len(text) > 10:
                                extra_content += text[:300] + "\n---\n"
                                if len(extra_content) > 2000:
                                    break
                        if len(extra_content) > 500:
                            break
                    except:
                        pass
                
                if extra_content:
                    print(f"   ✅ 探索获取到 {len(extra_content)} 字额外内容")
                break
                
    except Exception as e:
        print(f"   ⚠️ 探索操作失败: {str(e)[:50]}")
    
    return extra_content
    print(f"📡 状态已推送: {state.status} - {state.current_phase}")


@opinion_agent.tool
async def collect_data(
    ctx: RunContext[StateDeps],
    keyword: str,
) -> str:
    """
    收集舆情数据 - 流式输出，每条数据实时更新
    
    Args:
        keyword: 要分析的关键词
    
    Returns:
        收集结果描述
    """
    state = ctx.deps.state
    run_id = ctx.deps.run_id  # 从 deps 获取运行 ID
    
    state.keyword = keyword
    state.status = "collecting"
    state.current_phase = "数据收集"
    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 开始收集「{keyword}」的舆情数据...")
    state.raw_data = []
    state.collected_data_summary = []
    
    # 推送初始状态
    await push_state_event(run_id, state)
    
    target_count = state.max_results
    collected = []
    seen_urls = set()
    
    # 获取搜索查询
    queries = generate_search_queries(keyword)
    
    # 创建新的 Sandbox
    try:
        sandbox = await create_browser_sandbox()
        if not sandbox:
            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Browser Sandbox 未配置")
            state.status = "error"
            await push_state_event(run_id, state)
            return "Browser Sandbox 未配置，请设置 AGENTRUN_BROWSER_SANDBOX_NAME 环境变量"
    except SandboxTemplateNotFoundError as e:
        # 模板不存在 - 明确报错并结束任务
        error_msg = str(e)
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {error_msg}")
        state.status = "error"
        state.current_phase = "错误"
        await push_state_event(run_id, state)
        raise RuntimeError(f"无法启动数据收集: {error_msg}")
    except SandboxCreationError as e:
        # 其他创建错误
        error_msg = str(e)
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {error_msg}")
        state.status = "error"
        state.current_phase = "错误"
        await push_state_event(run_id, state)
        raise RuntimeError(f"无法启动数据收集: {error_msg}")
    
    # 更新 Sandbox 信息
    sandbox_info = await get_all_sandboxes()
    state.sandboxes = [SandboxInfo(**s) for s in sandbox_info]
    state.active_sandbox_id = sandbox.sandbox_id
    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 浏览器已就绪: {sandbox.sandbox_id[:8]}...")
    
    # 推送 Sandbox 就绪状态
    await push_state_event(run_id, state)
    
    # 跟踪每个搜索类别的连续低相关性次数
    category_low_relevance_count: Dict[str, int] = {}
    max_low_relevance_per_category = 2  # 连续 2 次低相关则跳过该类别
    skipped_categories: set = set()
    
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(sandbox.get_cdp_url())
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            
            query_index = 0
            max_retries = 5
            retry_count = 0
            sandbox_retry_count = 0  # Sandbox 重建次数
            max_sandbox_retries = 3  # 最多重建 3 次
            
            while len(collected) < target_count:
                if query_index >= len(queries):
                    if retry_count >= max_retries:
                        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 已达到最大重试次数，当前收集 {len(collected)} 条")
                        break
                    
                    retry_count += 1
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 数据不足 ({len(collected)}/{target_count})，第 {retry_count} 次补充搜索...")
                    
                    extra_queries = [
                        {"query": f"{keyword} 第{retry_count}页", "category": "extra"},
                        {"query": f"{keyword} 相关", "category": "extra"},
                        {"query": f"{keyword} 资讯", "category": "extra"},
                    ]
                    queries.extend(extra_queries)
                
                query_info = queries[query_index]
                query_index += 1
                
                query = query_info["query"]
                category = query_info["category"]
                
                # 检查该类别是否已被跳过
                if category in skipped_categories:
                    print(f"⏭️ 跳过低效类别: {category}")
                    continue
                
                state.current_phase = f"数据收集 ({len(collected)}/{target_count})"
                state.collection_progress = int(len(collected) / target_count * 100)
                
                try:
                    # URL 编码查询参数，使用 quote_plus 将空格编码为 + 而非 %20
                    from urllib.parse import quote_plus
                    encoded_query = quote_plus(query)
                    # 使用 cn.bing.com 中国版
                    search_url = f"https://cn.bing.com/search?q={encoded_query}"
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔎 搜索 [{category}]: {query[:30]}...")
                    print(f"🔎 搜索 URL: {search_url}")
                    
                    # 每次搜索前推送状态更新
                    await push_state_event(run_id, state)
                    
                    await page.goto(search_url, timeout=30000)
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2)
                    
                    # 检查当前 URL 是否仍然是搜索页面
                    current_url = page.url
                    print(f"📍 当前页面 URL: {current_url}")
                    
                    # 如果被重定向到非搜索页面，尝试重新搜索
                    if "bing.com/search" not in current_url:
                        print(f"⚠️ 页面被重定向，尝试重新导航...")
                        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 页面重定向，重试...")
                        await page.goto(search_url, timeout=30000)
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(2)
                    
                    # 只使用精确的选择器，避免选中无关元素
                    # .b_algo 是 Bing 搜索结果的标准类名
                    result_elements = await page.query_selector_all("li.b_algo")
                    
                    # 打印调试信息
                    print(f"🔢 找到 {len(result_elements) if result_elements else 0} 个搜索结果元素")
                    
                    # 如果没有结果，尝试其他选择器
                    if not result_elements:
                        # 尝试备用选择器
                        alt_selectors = [
                            "#b_results li.b_algo",
                            ".b_algo",
                            "#b_results > li",
                        ]
                        for alt_sel in alt_selectors:
                            result_elements = await page.query_selector_all(alt_sel)
                            if result_elements:
                                print(f"✅ 使用备用选择器 {alt_sel} 找到 {len(result_elements)} 个结果")
                                break
                    
                    # 如果仍然没有结果，记录日志并继续
                    if not result_elements:
                        print(f"⚠️ 搜索 [{category}] 未找到结果: {query[:30]}...")
                        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 未找到结果: {query[:30]}...")
                        # 打印页面 HTML 片段用于调试
                        try:
                            page_title = await page.title()
                            print(f"📄 页面标题: {page_title}")
                        except:
                            pass
                        continue
                    
                    new_results_in_query = 0
                    low_relevance_in_query = 0
                    
                    for elem in result_elements:
                        if len(collected) >= target_count:
                            break
                        
                        try:
                            title_elem = await elem.query_selector("h2 a")
                            snippet_elem = await elem.query_selector(".b_caption p")
                            
                            if title_elem:
                                title = await title_elem.inner_text()
                                url = await title_elem.get_attribute("href") or ""
                                
                                if url in seen_urls or not url:
                                    continue
                                
                                snippet = ""
                                if snippet_elem:
                                    snippet = await snippet_elem.inner_text()
                                
                                # 评估相关性
                                relevance = await evaluate_relevance(keyword, title, snippet)
                                
                                # 只保留相关性 >= 0.3 的结果
                                if relevance < 0.3:
                                    print(f"⏭️ 跳过低相关性结果: {title[:30]}... (得分: {relevance:.2f})")
                                    low_relevance_in_query += 1
                                    continue
                                
                                seen_urls.add(url)
                                
                                # 识别来源
                                source = "网络"
                                if "weibo.com" in url:
                                    source = "微博"
                                elif "zhihu.com" in url:
                                    source = "知乎"
                                elif "tieba.baidu.com" in url:
                                    source = "贴吧"
                                elif any(x in url for x in ["news", "sina", "sohu", "163", "qq.com", "people", "cctv", "xinhua"]):
                                    source = "新闻"
                                elif "bilibili.com" in url:
                                    source = "B站"
                                elif "douyin.com" in url or "tiktok.com" in url:
                                    source = "抖音"
                                
                                # 深入抓取：进入链接获取详细内容
                                detailed_content = ""
                                try:
                                    # 对于高相关性结果，尝试获取详细内容
                                    if relevance >= 0.6 and len(collected) < target_count:
                                        print(f"🔗 深入抓取: {url[:50]}...")
                                        
                                        # 打开新页面获取详细内容
                                        detail_page = await context.new_page()
                                        try:
                                            await detail_page.goto(url, timeout=15000)
                                            await detail_page.wait_for_load_state("domcontentloaded")
                                            await asyncio.sleep(1)
                                            
                                            # 根据不同平台提取内容
                                            if "zhihu.com" in url:
                                                # 知乎：提取问题描述和回答
                                                content_selectors = [
                                                    ".QuestionRichText",  # 问题描述
                                                    ".RichContent-inner",  # 回答内容
                                                    ".Post-RichText",  # 文章内容
                                                ]
                                                for sel in content_selectors:
                                                    elems = await detail_page.query_selector_all(sel)
                                                    for elem in elems[:3]:  # 最多取3个
                                                        text = await elem.inner_text()
                                                        if text and len(text) > 50:
                                                            detailed_content += text[:1000] + "\n\n"
                                                            if len(detailed_content) > 2000:
                                                                break
                                                    if len(detailed_content) > 500:
                                                        break
                                                        
                                            elif "weibo.com" in url:
                                                # 微博：提取微博正文
                                                content_selectors = [
                                                    ".WB_text",
                                                    "[class*='detail_wbtext']",
                                                    ".weibo-text",
                                                ]
                                                for sel in content_selectors:
                                                    elems = await detail_page.query_selector_all(sel)
                                                    for elem in elems[:5]:
                                                        text = await elem.inner_text()
                                                        if text and len(text) > 20:
                                                            detailed_content += text[:500] + "\n\n"
                                                    if detailed_content:
                                                        break
                                            
                                            elif "bilibili.com" in url:
                                                # B站：提取视频描述、评论等
                                                content_selectors = [
                                                    ".video-desc",  # 视频描述
                                                    ".desc-info-text",  # 新版描述
                                                    ".basic-desc-info",  # 基本描述
                                                    ".reply-content",  # 评论内容
                                                    ".root-reply-content",  # 根评论
                                                    ".article-content",  # 专栏文章
                                                    ".opus-module-content",  # 动态内容
                                                ]
                                                for sel in content_selectors:
                                                    elems = await detail_page.query_selector_all(sel)
                                                    for elem in elems[:8]:  # B站评论较多，多取一些
                                                        text = await elem.inner_text()
                                                        if text and len(text) > 15:
                                                            detailed_content += text[:400] + "\n\n"
                                                            if len(detailed_content) > 2500:
                                                                break
                                                    if len(detailed_content) > 800:
                                                        break
                                                        
                                            else:
                                                # 通用：提取文章正文
                                                content_selectors = [
                                                    "article",
                                                    ".article-content",
                                                    ".post-content",
                                                    ".content",
                                                    "main p",
                                                ]
                                                for sel in content_selectors:
                                                    elems = await detail_page.query_selector_all(sel)
                                                    for elem in elems[:3]:
                                                        text = await elem.inner_text()
                                                        if text and len(text) > 100:
                                                            detailed_content += text[:1500] + "\n\n"
                                                            if len(detailed_content) > 2000:
                                                                break
                                                    if len(detailed_content) > 500:
                                                        break
                                            
                                            if detailed_content:
                                                print(f"   ✅ 获取到 {len(detailed_content)} 字详细内容")
                                                
                                                # LLM 控制的深入探索（评论区、相关推荐等）
                                                try:
                                                    extra_content = await explore_page_with_llm(
                                                        page=detail_page,
                                                        keyword=keyword,
                                                        url=url,
                                                        source=source,
                                                        initial_content=detailed_content
                                                    )
                                                    if extra_content:
                                                        detailed_content += "\n\n【深入探索内容】\n" + extra_content
                                                        print(f"   ✅ 深入探索后总计 {len(detailed_content)} 字")
                                                except Exception as e:
                                                    print(f"   ⚠️ 深入探索失败: {str(e)[:50]}")
                                            else:
                                                print(f"   ⚠️ 未能提取详细内容")
                                                
                                        except Exception as e:
                                            print(f"   ⚠️ 深入抓取失败: {str(e)[:50]}")
                                        finally:
                                            await detail_page.close()
                                            
                                except Exception as e:
                                    print(f"   ⚠️ 深入抓取出错: {str(e)[:50]}")
                                
                                # 合并摘要和详细内容
                                full_content = snippet.strip()
                                if detailed_content:
                                    full_content = detailed_content.strip()[:3000]
                                
                                result = SearchResult(
                                    title=title.strip(),
                                    url=url,
                                    snippet=full_content[:500],  # 摘要保留500字
                                    source=source,
                                    date=datetime.now().strftime("%Y-%m-%d"),
                                    platform="bing",
                                    relevance_score=relevance,
                                    detailed_content=detailed_content[:3000] if detailed_content else ""  # 详细内容
                                )
                                
                                # 验证结果有效性
                                if not is_valid_result(result, keyword):
                                    continue
                                
                                collected.append(result)
                                state.raw_data.append(result)
                                state.collected_data_summary.append({
                                    "title": result.title[:50],
                                    "url": result.url,
                                    "source": result.source,
                                    "relevance": f"{relevance:.0%}",
                                })
                                state.collection_progress = int(len(collected) / target_count * 100)
                                new_results_in_query += 1
                                
                                # 流式输出：每收集一条就打印并推送状态
                                print(f"💾 [{len(collected)}/{target_count}] [{relevance:.0%}] {source}: {title[:40]}...")
                                
                                # 每收集 1 条数据就发送状态更新（实时）
                                await push_state_event(run_id, state)
                                
                        except Exception as e:
                            print(f"⚠️ 解析结果失败: {e}")
                            continue
                    
                    # 更新类别的低相关性计数
                    if new_results_in_query == 0 and low_relevance_in_query > 3:
                        category_low_relevance_count[category] = category_low_relevance_count.get(category, 0) + 1
                        if category_low_relevance_count[category] >= max_low_relevance_per_category:
                            skipped_categories.add(category)
                            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏭️ 跳过低效链路: {category}")
                            print(f"⏭️ 类别 {category} 连续 {max_low_relevance_per_category} 次低相关，已跳过")
                    elif new_results_in_query > 0:
                        # 重置计数
                        category_low_relevance_count[category] = 0
                    
                    if new_results_in_query > 0:
                        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ 本次获得 {new_results_in_query} 条有效结果")
                        # 有新结果时发送状态更新
                        await push_state_event(run_id, state)
                    
                except Exception as e:
                    error_msg = str(e)
                    print(f"⚠️ 搜索失败: {error_msg}")
                    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 搜索失败: {error_msg[:50]}")
                    
                    # 检测是否是 sandbox 关闭错误
                    if sandbox_retry_count < max_sandbox_retries:
                        new_sandbox = await recreate_sandbox_if_closed(sandbox.sandbox_id, error_msg)
                        if new_sandbox:
                            sandbox_retry_count += 1
                            sandbox = new_sandbox
                            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Sandbox 已重建 ({sandbox_retry_count}/{max_sandbox_retries})")
                            
                            # 更新 Sandbox 信息到状态
                            sandbox_info = await get_all_sandboxes()
                            state.sandboxes = [SandboxInfo(**s) for s in sandbox_info]
                            state.active_sandbox_id = sandbox.sandbox_id
                            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 新浏览器已就绪: {sandbox.sandbox_id[:8]}...")
                            
                            # 推送新的 sandbox 状态到前端
                            await push_state_event(run_id, state)
                            
                            # 重新连接浏览器
                            try:
                                browser = await playwright.chromium.connect_over_cdp(sandbox.get_cdp_url())
                                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                                page = context.pages[0] if context.pages else await context.new_page()
                                print(f"✅ 已重新连接到新 Sandbox")
                                continue  # 继续搜索循环
                            except Exception as reconnect_error:
                                print(f"❌ 重新连接 Sandbox 失败: {reconnect_error}")
                                state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 重新连接失败: {str(reconnect_error)[:50]}")
                
                await asyncio.sleep(1)
    
    except Exception as e:
        error_msg = str(e)
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 数据收集出错: {error_msg[:100]}")
        print(f"❌ 数据收集出错: {e}")
        
        # 在顶层异常处理中也检测 sandbox 关闭错误
        new_sandbox = await recreate_sandbox_if_closed(state.active_sandbox_id, error_msg)
        if new_sandbox:
            # 更新状态中的 sandbox 信息
            sandbox_info = await get_all_sandboxes()
            state.sandboxes = [SandboxInfo(**s) for s in sandbox_info]
            state.active_sandbox_id = new_sandbox.sandbox_id
            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Sandbox 已重建: {new_sandbox.sandbox_id[:8]}...")
            await push_state_event(run_id, state)
    
    # 按相关性排序
    state.raw_data.sort(key=lambda x: x.relevance_score, reverse=True)
    
    state.status = "collected"
    state.collection_progress = 100
    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 数据收集完成: {len(collected)} 条高质量数据")
    state.current_phase = f"已收集 {len(collected)} 条数据"
    
    # 发送最终状态
    await push_state_event(run_id, state)
    
    return f"数据收集完成，共 {len(collected)} 条高质量数据"


# =============================================================================
# 工具：数据分析（流式输出）
# =============================================================================

@opinion_agent.tool
async def analyze_data(
    ctx: RunContext[StateDeps],
) -> str:
    """
    分析收集到的数据 - 流式输出分析过程
    
    Returns:
        分析结果描述
    """
    state = ctx.deps.state
    run_id = ctx.deps.run_id  # 从 deps 获取运行 ID
    
    state.status = "analyzing"
    state.current_phase = "数据分析"
    state.analysis_progress = ""
    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 开始深度分析...")
    
    # 发送初始状态
    await push_state_event(run_id, state)
    
    # 统计来源分布
    source_stats = {}
    for item in state.raw_data:
        source_stats[item.source] = source_stats.get(item.source, 0) + 1
    
    # 流式输出：分析进度
    state.analysis_progress = "正在统计数据来源分布...\n"
    state.analysis_progress += f"数据来源: {json.dumps(source_stats, ensure_ascii=False)}\n\n"
    await push_state_event(run_id, state)
    
    # 准备数据 - 包含详细内容
    data_for_analysis = []
    detailed_contents = []
    for item in state.raw_data[:30]:  # 取前30条
        data_for_analysis.append({
            "title": item.title,
            "snippet": item.snippet[:300],
            "source": item.source,
            "relevance": item.relevance_score,
        })
        # 收集有详细内容的数据
        if item.detailed_content:
            detailed_contents.append({
                "title": item.title,
                "source": item.source,
                "content": item.detailed_content[:1500],  # 截取详细内容
            })
    
    state.analysis_progress += "正在提取关键词和情感分析...\n"
    state.analysis_progress += f"已获取 {len(detailed_contents)} 条详细内容用于深度分析\n"
    await push_state_event(run_id, state)
    
    # 构建详细内容部分
    detailed_section = ""
    if detailed_contents:
        detailed_section = f"""

【详细内容摘录】（深入抓取的原文内容）：
{json.dumps(detailed_contents[:10], ensure_ascii=False, indent=2)}
"""
    
    # 使用 LLM 分析
    analysis_prompt = f"""
请对以下关于「{state.keyword}」的 {len(state.raw_data)} 条舆情数据进行深度分析。

═══════════════════════════════════════════════════════════════
【数据概览】
═══════════════════════════════════════════════════════════════
- 分析主题: {state.keyword}
- 数据总量: {len(state.raw_data)} 条
- 数据来源分布: {json.dumps(source_stats, ensure_ascii=False)}
- 监测时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

═══════════════════════════════════════════════════════════════
【数据样本】（按相关性排序的代表性数据）
═══════════════════════════════════════════════════════════════
{json.dumps(data_for_analysis, ensure_ascii=False, indent=2)}

{detailed_section}

═══════════════════════════════════════════════════════════════
【分析要求】
═══════════════════════════════════════════════════════════════

请基于以上数据，进行以下维度的深度分析：

1. **关键词提取**: 
   - 提取 15-20 个核心关键词
   - 按重要性排序，包含主题词、事件词、情感词、人物/品牌词

2. **情感分析**:
   - 计算综合情感得分 (-1 到 1，负值表示负面，正值表示正面)
   - 统计正面、中性、负面的百分比分布
   - 分析情感倾向的主要原因

3. **热度趋势**:
   - 预估近 7 天的热度趋势 (0-100)
   - 识别热度峰值和低谷的原因

4. **关键观点提炼**:
   - 从数据中提炼 5-8 个最具代表性的观点
   - 标注观点来源和情感倾向
   - 引用原文中的关键表述

5. **风险评估**:
   - 传播风险：该话题继续扩散的可能性
   - 声誉风险：对相关主体形象的影响程度
   - 趋势判断：舆情是上升、平稳还是下降

请返回 JSON 格式（确保是有效的 JSON，不要有多余内容）：
{{
    "keywords": ["关键词1", "关键词2", "关键词3", ...],
    "sentiment_score": 0.0,
    "sentiment_distribution": {{"正面": 40, "中性": 35, "负面": 25}},
    "heat_trend": [30, 45, 60, 80, 70, 55, 40],
    "summary": "300-500字的深度分析摘要，包含：1)近期舆情背景 2)核心争议点 3)各方立场 4)发展态势",
    "key_opinions": [
        {{"viewpoint": "具体观点内容，引用原文", "source": "来源平台", "sentiment": "正面/负面/中性", "influence": "高/中/低"}}
    ],
    "risk_assessment": {{
        "spread_risk": "高/中/低",
        "spread_reason": "传播风险的具体原因",
        "reputation_risk": "高/中/低",
        "reputation_reason": "声誉风险的具体原因",
        "trend": "上升/平稳/下降",
        "trend_reason": "趋势判断的依据"
    }}
}}
"""
    
    try:
        analyzer = Agent(
            agentrun_model,
            system_prompt="""你是资深舆情数据分析师，擅长从海量数据中提炼关键洞察。

【分析原则】
1. 数据驱动：所有结论必须基于数据，不能凭空臆断
2. 深度洞察：不停留在表面，挖掘数据背后的深层含义
3. 观点引用：提炼观点时要引用原文中的关键表述
4. 量化分析：尽可能使用数字和百分比量化分析结果
5. 风险敏感：准确识别潜在风险点和预警信号

【输出要求】
- 必须返回有效的 JSON 格式
- summary 要详细，300-500 字
- key_opinions 要具体，引用原文
- 风险评估要有具体原因说明""",
            retries=3,
        )
        
        state.analysis_progress += "正在调用 AI 进行深度分析...\n"
        await push_state_event(run_id, state)
        
        # 使用 run_stream 实现流式输出分析过程
        response_text = ""
        last_event_length = 0
        last_event_time = asyncio.get_event_loop().time()
        
        async with analyzer.run_stream(analysis_prompt) as result:
            async for text in result.stream_text():
                response_text = text  # 累积获取完整响应
                
                # 实时显示分析进度
                current_time = asyncio.get_event_loop().time()
                content_delta = len(response_text) - last_event_length
                time_delta = current_time - last_event_time
                
                # 每 200 字符或每 0.5 秒更新一次
                if content_delta >= 200 or (content_delta > 0 and time_delta >= 0.5):
                    # 显示正在分析的进度
                    state.analysis_progress = f"正在分析中... ({len(response_text)} 字)\n"
                    await push_state_event(run_id, state)
                    last_event_length = len(response_text)
                    last_event_time = current_time
        
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            analysis_data = json.loads(json_match.group())
            
            state.analysis = AnalysisResult(
                keywords=analysis_data.get("keywords", [state.keyword]),
                sentiment_score=float(analysis_data.get("sentiment_score", 0)),
                sentiment_distribution=analysis_data.get("sentiment_distribution", {"正面": 33, "中性": 34, "负面": 33}),
                heat_trend=analysis_data.get("heat_trend", [50]*7),
                summary=analysis_data.get("summary", f"关于「{state.keyword}」的舆情分析"),
                key_opinions=analysis_data.get("key_opinions", []),
                risk_assessment=analysis_data.get("risk_assessment", {}),
            )
            
            # 流式输出：分析结果
            state.analysis_progress += f"\n✅ 分析完成！\n"
            state.analysis_progress += f"- 情感得分: {state.analysis.sentiment_score:.2f}\n"
            state.analysis_progress += f"- 关键词: {', '.join(state.analysis.keywords[:5])}\n"
            state.analysis_progress += f"- 情感分布: 正面 {state.analysis.sentiment_distribution.get('正面', 0)}%, "
            state.analysis_progress += f"中性 {state.analysis.sentiment_distribution.get('中性', 0)}%, "
            state.analysis_progress += f"负面 {state.analysis.sentiment_distribution.get('负面', 0)}%\n"
            
            state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 分析完成: 情感得分 {state.analysis.sentiment_score:.2f}")
        else:
            raise ValueError("无法解析 JSON")
            
    except Exception as e:
        print(f"⚠️ 分析出错: {e}")
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 分析出错，使用默认值")
        state.analysis_progress += f"\n⚠️ 分析出错: {str(e)[:50]}\n"
        
        state.analysis = AnalysisResult(
            keywords=[state.keyword],
            sentiment_score=0,
            sentiment_distribution={"正面": 33, "中性": 34, "负面": 33},
            heat_trend=[50, 50, 50, 50, 50, 50, 50],
            summary=f"关于「{state.keyword}」的舆情分析",
        )
    
    state.status = "analyzed"
    state.current_phase = "分析完成"
    
    # 发送最终状态
    await push_state_event(run_id, state)
    
    return "数据分析完成"


# =============================================================================
# 工具：撰写报告（流式输出）
# =============================================================================

@opinion_agent.tool
async def write_report(
    ctx: RunContext[StateDeps],
) -> str:
    """
    撰写舆情分析报告 - 流式输出报告内容
    
    Returns:
        报告撰写结果描述
    """
    state = ctx.deps.state
    run_id = ctx.deps.run_id  # 从 deps 获取运行 ID
    
    state.status = "writing"
    state.current_phase = "报告撰写"
    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📝 开始撰写报告...")
    state.report_text = ""
    
    # 发送初始状态
    await push_state_event(run_id, state)
    
    analysis = state.analysis or AnalysisResult()
    keyword = state.keyword
    data_count = len(state.raw_data)
    
    # 来源统计
    source_stats = {}
    for item in state.raw_data:
        source_stats[item.source] = source_stats.get(item.source, 0) + 1
    
    # 流式输出：先输出报告框架
    state.report_text = f"# {keyword} 舆情分析报告\n\n"
    state.report_text += f"> 正在生成报告，请稍候...\n\n"
    state.report_text += f"**数据基础**: {data_count} 条数据，来源: {', '.join(source_stats.keys())}\n\n"
    await push_state_event(run_id, state)
    
    # 准备引用数据（包含完整链接）
    references_data = []
    for i, item in enumerate(state.raw_data[:20]):
        ref = {
            "id": i + 1,
            "title": item.title,
            "source": item.source,
            "url": item.url,  # 完整链接
            "snippet": item.snippet[:200],
            "relevance": f"{item.relevance_score:.0%}",
        }
        if item.detailed_content:
            ref["content"] = item.detailed_content[:600]
        references_data.append(ref)
    
    # 生成引用列表（带链接）供报告附录使用
    references_list_md = "\n".join([
        f"[{ref['id']}] [{ref['title'][:50]}...]({ref['url']}) - {ref['source']}"
        for ref in references_data
    ])
    
    # 使用 LLM 生成深度报告
    report_prompt = f"""
请为「{keyword}」撰写一份专业的舆情分析报告。

═══════════════════════════════════════════════════════════════
【数据基础】
═══════════════════════════════════════════════════════════════
- 监测时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- 样本量: {data_count} 条有效数据
- 数据来源平台: {json.dumps(source_stats, ensure_ascii=False)}
- 情感分布: 正面 {analysis.sentiment_distribution.get('正面', 0)}%、中性 {analysis.sentiment_distribution.get('中性', 0)}%、负面 {analysis.sentiment_distribution.get('负面', 0)}%
- 综合情感得分: {analysis.sentiment_score:.2f} (范围 -1 到 1，正值表示正面倾向)
- 核心关键词: {', '.join(analysis.keywords[:15])}
- 风险评估: 传播风险 {analysis.risk_assessment.get('spread_risk', '中')}、声誉风险 {analysis.risk_assessment.get('reputation_risk', '中')}、趋势 {analysis.risk_assessment.get('trend', '平稳')}

═══════════════════════════════════════════════════════════════
【分析摘要】
═══════════════════════════════════════════════════════════════
{analysis.summary}

═══════════════════════════════════════════════════════════════
【关键观点提炼】
═══════════════════════════════════════════════════════════════
{json.dumps(analysis.key_opinions, ensure_ascii=False, indent=2)}

═══════════════════════════════════════════════════════════════
【数据来源与引用素材】（编号 [1]-[{len(references_data)}]，报告中必须引用）
═══════════════════════════════════════════════════════════════
{json.dumps(references_data, ensure_ascii=False, indent=2)}

═══════════════════════════════════════════════════════════════
【报告撰写要求】
═══════════════════════════════════════════════════════════════

**核心要求 - 必须包含以下四个维度的深度分析：**

1. **近期舆情背景与时间线**
   - 梳理近1-2周内与该话题相关的重要事件
   - 标注关键时间节点和里程碑事件
   - 分析舆情发展的起承转合
   - 引用具体数据来源说明事件经过

2. **网络主流观点分析**
   - 分平台汇总主流观点（微博、知乎、新闻、贴吧等）
   - 引用代表性声音和典型评论（使用 [编号] 格式引用上述数据）
   - 分析不同群体的态度差异
   - 识别意见领袖和关键传播节点

3. **未来发展趋势预测**
   - 短期预测（1-2周）：舆情走向、可能的爆发点
   - 中长期预测（1-3个月）：持续影响、潜在风险
   - 识别可能的转折点和触发因素
   - 量化风险等级和概率评估

4. **后续建议与行动方案**
   - 即时响应措施（24-48小时内）
   - 短期应对策略（1-2周）
   - 长期品牌/形象建设建议
   - 舆情监测重点和预警指标

**报告结构要求：**
- 篇幅: 3500-5000 字，内容翔实
- 格式: Markdown，层次清晰
- 必须包含的章节:
  1. 一、舆情概述与数据基础
  2. 二、舆情背景与时间线梳理
  3. 三、网络主流观点分析
  4. 四、成因与驱动因素分析
  5. 五、未来发展趋势预测
  6. 六、应对建议与行动方案
  7. 七、结论与核心要点
  8. 附录：数据来源引用

**引用规范（重要！）：**
- 在报告正文中，使用 Markdown 链接格式引用数据来源
- 格式示例：根据[知乎讨论](URL)，网友普遍认为...
- 或者：某微博用户[指出](URL)...
- 每个章节至少引用 2-3 个数据来源
- 引用要自然融入行文，增强说服力
- 附录中列出所有引用来源的完整链接列表

**写作风格：**
- 专业、客观、数据驱动
- 使用舆情分析专业术语
- 站在第三方专业立场
- 避免主观臆断，以数据说话

**附录格式要求：**
在报告末尾的"附录：数据来源引用"章节中，按以下格式列出所有引用：
{references_list_md}

请直接输出 Markdown 格式的报告，不要包含其他说明文字。
"""
    
    try:
        writer = Agent(
            agentrun_model,
            system_prompt="""你是顶级企业舆情分析师和报告撰写专家，拥有 15 年以上公关危机管理和舆情分析经验。
你曾服务于多家世界 500 强企业，擅长将复杂的舆情数据转化为可执行的战略建议。
你的报告需要达到可直接提交给 CEO/董事会的专业标准。

═══════════════════════════════════════════════════════════════
【核心能力】
═══════════════════════════════════════════════════════════════
1. **数据洞察**: 从海量数据中提炼关键信息，发现隐藏模式
2. **趋势预判**: 基于历史数据和行业经验，准确预测舆情走向
3. **风险评估**: 量化风险等级，识别潜在危机点
4. **策略建议**: 提供可落地的应对方案，区分优先级

═══════════════════════════════════════════════════════════════
【报告撰写原则】
═══════════════════════════════════════════════════════════════

**1. 数据驱动，有据可依**
- 每个结论必须有数据支撑
- 使用 [编号] 格式引用具体数据来源
- 引用要自然融入行文，例如：
  - "根据知乎讨论[3]，网友普遍认为..."
  - "微博热搜数据[5]显示..."
  - "综合多个新闻报道[2][7][9]..."

**2. 深度分析，洞察本质**
- 不停留在表面现象，挖掘深层原因
- 分析事件背后的社会心理、利益博弈
- 识别关键影响因素和传播规律

**3. 结构严谨，逻辑清晰**
- 使用清晰的标题层级（#、##、###）
- 善用列表、表格、引用块增强可读性
- 每个章节有明确的分析框架

**4. 专业表达，术语准确**
- 使用舆情分析专业词汇：舆情指数、传播链路、情感极性、意见领袖、舆论场域等
- 量化表达：百分比、趋势数值、风险等级
- 避免模糊表述，追求精准

**5. 战略视角，可执行性**
- 站在决策者角度思考
- 建议要具体、可操作、有时间节点
- 区分紧急响应和长期策略

**6. 客观中立，专业立场**
- 保持第三方专业立场
- 不带个人情感色彩
- 正面负面观点都要客观呈现

═══════════════════════════════════════════════════════════════
【质量标准】
═══════════════════════════════════════════════════════════════
- 篇幅: 3500-5000 字，内容翔实不空洞
- 引用: 每个章节至少 2-3 个数据来源引用
- 深度: 每个观点都有分析支撑，不能泛泛而谈
- 实用: 建议具体可执行，有明确时间节点""",
            retries=3,
        )
        
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📝 正在生成报告内容...")
        await push_state_event(run_id, state)
        
        # 使用 run_stream 实现 token-by-token 流式输出
        report_content = ""
        last_event_length = 0
        last_event_time = asyncio.get_event_loop().time()
        
        async with writer.run_stream(report_prompt) as result:
            async for text in result.stream_text():
                report_content = text  # 累积获取完整响应
                state.report_text = report_content
                
                current_time = asyncio.get_event_loop().time()
                content_delta = len(report_content) - last_event_length
                time_delta = current_time - last_event_time
                
                # 更细粒度的流式输出：每 100 字符或每 0.3 秒发送一次
                if content_delta >= 100 or (content_delta > 0 and time_delta >= 0.3):
                    await push_state_event(run_id, state)
                    last_event_length = len(report_content)
                    last_event_time = current_time
        
        # 清理可能的代码块标记
        report_content = re.sub(r'^```\w*\n?', '', report_content)
        report_content = re.sub(r'\n?```$', '', report_content)
        
        state.report_text = report_content
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 报告撰写完成: {len(report_content)} 字")
        
    except Exception as e:
        print(f"⚠️ 报告撰写出错: {e}")
        state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 报告撰写出错，使用模板")
        
        state.report_text = generate_template_report(state)
    
    state.status = "written"
    state.current_phase = "报告完成"
    
    # 发送最终状态
    await push_state_event(run_id, state)
    
    return f"报告撰写完成，共 {len(state.report_text)} 字"


def generate_template_report(state: OpinionState) -> str:
    """生成模板报告 - 包含四个核心部分"""
    analysis = state.analysis or AnalysisResult()
    keyword = state.keyword
    data_count = len(state.raw_data)
    
    source_stats = {}
    for item in state.raw_data:
        source_stats[item.source] = source_stats.get(item.source, 0) + 1
    
    return f"""# {keyword} 舆情分析报告

> **报告摘要**: {analysis.summary or f'基于 {data_count} 条数据的综合舆情分析'}

---

## 一、舆情背景与时间线

### 1.1 数据基础
- **监测时间**: {datetime.now().strftime('%Y-%m-%d')}
- **数据来源**: {', '.join(source_stats.keys()) if source_stats else '网络'}
- **样本量**: 共 {data_count} 条有效数据
- **数据来源分布**:
{chr(10).join([f'  - {k}: {v} 条 ({v/data_count*100:.1f}%)' for k, v in source_stats.items()]) if source_stats and data_count > 0 else '  - 暂无数据'}

### 1.2 近期舆情背景

「{keyword}」近期在网络上引发广泛关注，成为舆论热点。根据数据分析，该话题涉及以下核心议题：

{chr(10).join([f'- **{kw}**' for kw in (analysis.keywords[:6] if analysis.keywords else [keyword])])}

### 1.3 时间线梳理

| 阶段 | 特征 | 状态 |
|------|------|------|
| **起始期** | 话题开始在社交媒体上出现讨论 | 初步关注 |
| **发酵期** | 主流媒体跟进报道，话题热度上升 | 快速传播 |
| **高峰期** | 多平台联动传播，讨论达到顶峰 | 广泛讨论 |
| **当前状态** | {'持续发酵中，热度维持较高水平' if analysis.heat_trend and analysis.heat_trend[-1] > 50 else '趋于平稳，热度逐渐回落'} | {'活跃' if analysis.heat_trend and analysis.heat_trend[-1] > 50 else '平稳'} |

### 1.4 热度趋势
- **整体态势**: {'上升' if analysis.heat_trend and len(analysis.heat_trend) > 1 and analysis.heat_trend[-1] > analysis.heat_trend[0] else '平稳'}
- **情感分布**: 正面 {analysis.sentiment_distribution.get('正面', 33)}%、中性 {analysis.sentiment_distribution.get('中性', 34)}%、负面 {analysis.sentiment_distribution.get('负面', 33)}%
- **舆情指数**: {analysis.sentiment_score:.2f} (范围 -1 到 1)

---

## 二、网络主流观点分析

### 2.1 各平台观点汇总

**微博平台观点**:
- 用户讨论活跃，观点多元
- 热搜话题带动大量围观和讨论
- 情绪化表达较为明显

**知乎平台观点**:
- 专业分析和深度讨论较多
- 用户倾向于理性分析问题
- 长文回答提供多角度视角

**新闻媒体观点**:
- 主流媒体报道相对客观中立
- 关注事件本身和社会影响
- 部分媒体进行深度调查报道

### 2.2 代表性声音

**支持方观点 ({analysis.sentiment_distribution.get('正面', 30)}%)**:
{chr(10).join([f'- "{op.get("viewpoint", "")[:150]}..." [来源: {op.get("source", "网络")}]' for op in (analysis.key_opinions[:3] if analysis.key_opinions else [{"viewpoint": "总体持积极态度，认为发展前景良好", "source": "综合"}])])}

**质疑方观点 ({analysis.sentiment_distribution.get('负面', 30)}%)**:
- 部分网友对相关情况表示担忧和质疑
- 存在一定的负面评价和批评声音
- 关注潜在问题和风险

**中立方观点 ({analysis.sentiment_distribution.get('中性', 40)}%)**:
- 理性分析，客观看待问题
- 等待更多信息再做判断
- 关注事件后续发展

### 2.3 意见领袖影响

| 类型 | 影响力 | 主要观点倾向 |
|------|--------|--------------|
| 媒体机构 | 高 | 主流媒体报道影响舆论走向，整体偏向客观中立 |
| 行业专家 | 中高 | 专业分析和解读被广泛引用 |
| KOL/大V | 中 | 观点多元，带动粉丝讨论 |
| 普通网民 | 基础性 | 基数大，形成舆论基础 |

---

## 三、成因与驱动因素分析

### 3.1 直接诱因

「{keyword}」成为舆论焦点的直接原因：
1. **事件触发**: 相关事件或消息的发布引发公众关注
2. **媒体放大**: 社交媒体的快速传播放大了话题影响力
3. **KOL参与**: 意见领袖的参与推动了话题发酵
4. **算法推荐**: 平台算法推荐加速信息扩散

### 3.2 深层原因

- **社会背景**: 公众对相关领域的持续关注，话题具有广泛的社会关联性
- **利益相关**: 涉及多方利益群体，各方立场不同导致观点分化
- **传播机制**: 社交媒体的传播特性使话题快速扩散
- **情绪共鸣**: 话题触及公众关切点，引发情感共鸣

### 3.3 情感驱动分析

| 情感类型 | 占比 | 主要来源 |
|----------|------|----------|
| 正面情感 | {analysis.sentiment_distribution.get('正面', 33)}% | 认可、支持、期待、赞赏 |
| 中性态度 | {analysis.sentiment_distribution.get('中性', 34)}% | 观望、理性讨论、客观分析 |
| 负面情感 | {analysis.sentiment_distribution.get('负面', 33)}% | 质疑、担忧、批评、不满 |

---

## 四、未来发展趋势预测

### 4.1 短期预测（1-2周）

**热度走势**:
- 预计话题热度将{'持续维持较高水平，可能出现新的讨论高峰' if analysis.heat_trend and analysis.heat_trend[-1] > 50 else '逐渐降低，回归常态'}
- 需密切关注可能出现的新发展和突发事件
- 建议持续监测舆情动态，保持警惕

**关键节点**:
- 关注相关政策或官方回应
- 留意媒体深度报道和调查
- 监测意见领袖的后续发声

### 4.2 中长期预测（1-3个月）

**发展趋势**:
- {'舆情可能持续发酵，需要长期关注和应对' if analysis.risk_assessment.get('spread_risk') == '高' else '舆情预计逐步平息，但需要持续监测'}
- 对品牌/形象的潜在影响需要评估和管理
- 可能影响相关决策和公众认知

**潜在转折点**:
- 重大政策或官方声明发布
- 新的相关事件发生
- 媒体深度调查报道
- 意见领袖观点转变

### 4.3 风险等级评估

| 风险类型 | 等级 | 说明 | 应对优先级 |
|---------|------|------|-----------|
| 传播风险 | {'★★★★☆' if analysis.risk_assessment.get('spread_risk') == '高' else '★★★☆☆'} | {analysis.risk_assessment.get('spread_risk', '中')}风险 | {'高' if analysis.risk_assessment.get('spread_risk') == '高' else '中'} |
| 声誉风险 | {'★★★★☆' if analysis.risk_assessment.get('reputation_risk') == '高' else '★★★☆☆'} | {analysis.risk_assessment.get('reputation_risk', '中')}风险 | {'高' if analysis.risk_assessment.get('reputation_risk') == '高' else '中'} |
| 发展趋势 | {'★★★☆☆'} | {analysis.risk_assessment.get('trend', '平稳')} | 中 |

---

## 五、应对建议与行动方案

### 5.1 即时响应策略（24-72小时）

| 优先级 | 行动项 | 具体措施 |
|--------|--------|----------|
| **P0** | 监测预警 | 建立实时舆情监测机制，设置关键词预警 |
| **P0** | 快速响应 | 对重要舆情及时回应，控制负面信息扩散 |
| **P1** | 信息透明 | 主动发布权威信息，减少信息不对称 |
| **P1** | 舆论引导 | 通过正面内容引导舆论，传播正能量 |

### 5.2 中期策略（1-4周）

1. **舆情管理**
   - 建立专项舆情监测小组
   - 制定分级响应机制
   - 准备各类情景预案

2. **沟通策略**
   - 加强与媒体的沟通协调
   - 主动设置议程，引导讨论方向
   - 邀请专家学者发声

3. **内容运营**
   - 持续输出优质内容
   - 展示正面形象和成果
   - 回应公众关切

### 5.3 长期策略（1-3个月）

1. **品牌建设**: 持续强化正面形象，提升品牌美誉度
2. **危机预案**: 完善舆情危机应对预案，定期演练
3. **关系维护**: 加强与媒体、公众、意见领袖的沟通
4. **能力建设**: 提升舆情监测和应对能力

---

## 六、结论与核心要点

### 6.1 核心结论

1. **舆情态势**: 「{keyword}」当前舆情整体呈{'正面' if analysis.sentiment_score > 0.2 else '中性' if analysis.sentiment_score > -0.2 else '负面'}态势
2. **传播范围**: 舆情传播范围{'较广' if data_count > 15 else '一般'}，涉及{len(source_stats) if source_stats else 1}个主要平台
3. **关注程度**: 公众关注度{'较高' if analysis.heat_trend and max(analysis.heat_trend) > 60 else '中等'}，讨论热度{'持续' if analysis.heat_trend and analysis.heat_trend[-1] > 50 else '趋稳'}
4. **风险等级**: 综合风险等级为{analysis.risk_assessment.get('spread_risk', '中')}

### 6.2 关键行动建议

| 时间维度 | 核心行动 | 预期效果 |
|----------|----------|----------|
| **短期** | 加强舆情监测，及时响应重要舆情 | 控制风险扩散 |
| **中期** | 制定针对性的舆论引导策略 | 改善舆论环境 |
| **长期** | 建立完善的舆情管理体系 | 提升应对能力 |

### 6.3 后续跟踪要点

- 持续监测关键词热度变化
- 关注意见领袖观点动向
- 跟踪媒体报道趋势
- 评估应对措施效果

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据样本量**: {data_count} 条
**分析方法**: 多平台数据采集 + AI 深度分析

---

### 附录：重要数据来源

以下为本次分析的部分代表性数据来源：

{chr(10).join([f'{i+1}. [{item.title[:50]}...]({item.url}) - {item.source} (相关性: {item.relevance_score:.0%})' for i, item in enumerate(state.raw_data[:10])])}

---
*本报告由 AI 舆情分析系统自动生成，仅供参考。*
*⚠️ 内容由AI生成，仅供参考，您据此所作判断及操作均由您自行承担责任。*
"""


# =============================================================================
# 工具：渲染 HTML
# =============================================================================

@opinion_agent.tool
async def render_html(
    ctx: RunContext[StateDeps],
) -> str:
    """
    将 Markdown 报告渲染为 HTML，包含可视化图表
    
    Returns:
        渲染结果描述
    """
    state = ctx.deps.state
    run_id = ctx.deps.run_id  # 从 deps 获取运行 ID

    state.status = "rendering"
    state.current_phase = "HTML 渲染"
    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎨 渲染 HTML 和图表...")

    # 推送初始状态
    await push_state_event(run_id, state)

    try:
        import markdown
        report_html = markdown.markdown(
            state.report_text,
            extensions=["extra", "tables", "toc"]
        )
    except ImportError:
        report_html = state.report_text.replace("\n\n", "</p><p>").replace("\n", "<br>")
        report_html = f"<p>{report_html}</p>"

    # 准备图表数据
    analysis = state.analysis or AnalysisResult()

    # 情感分布数据
    sentiment_data = analysis.sentiment_distribution or {"正面": 33, "中性": 34, "负面": 33}
    sentiment_colors = {
        "正面": "#52c41a",
        "中性": "#1890ff", 
        "负面": "#ff4d4f"
    }

    # 热度趋势数据
    heat_trend = analysis.heat_trend or [50, 50, 50, 50, 50, 50, 50]
    heat_labels = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]

    # 关键词数据（用于词云）
    keywords = analysis.keywords or [state.keyword]
    keyword_weights = []
    for i, kw in enumerate(keywords[:20]):
        weight = 100 - i * 5  # 权重递减
        keyword_weights.append({"name": kw, "value": max(weight, 20)})

    # 来源分布数据
    source_stats = {}
    for item in state.raw_data:
        source_stats[item.source] = source_stats.get(item.source, 0) + 1

    state.final_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{state.keyword} - 舆情分析报告</title>
    <!-- 所有链接在新窗口打开 -->
    <base target="_blank">
    <script>
        // 动态加载 ECharts（支持 iframe 嵌入和独立打开）
        (function() {{
            var baseUrl = '';
            try {{
                // 如果在 iframe 中，使用父页面的 origin
                if (window.parent && window.parent.location && window.parent !== window) {{
                    baseUrl = window.parent.location.origin;
                }}
            }} catch(e) {{
                // 跨域情况下使用当前页面的 origin
                baseUrl = window.location.origin || '';
            }}
            
            function loadScript(url) {{
                return new Promise(function(resolve, reject) {{
                    var script = document.createElement('script');
                    script.src = baseUrl + url;
                    script.onload = resolve;
                    script.onerror = function() {{
                        // 如果本地加载失败，尝试 CDN
                        var fallbackUrl = url.includes('wordcloud') 
                            ? 'https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js'
                            : 'https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js';
                        var fallbackScript = document.createElement('script');
                        fallbackScript.src = fallbackUrl;
                        fallbackScript.onload = resolve;
                        fallbackScript.onerror = reject;
                        document.head.appendChild(fallbackScript);
                    }};
                    document.head.appendChild(script);
                }});
            }}
            
            // 按顺序加载 ECharts
            loadScript('/echarts/echarts.min.js').then(function() {{
                return loadScript('/echarts/echarts-wordcloud.min.js');
            }}).then(function() {{
                window.dispatchEvent(new CustomEvent('echarts-ready'));
            }}).catch(function(e) {{
                console.error('Failed to load ECharts:', e);
            }});
        }})();
    </script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            padding: 40px 20px;
            line-height: 1.8;
        }}
        .container {{ 
            max-width: 1100px; 
            margin: 0 auto; 
            background: rgba(255,255,255,0.98); 
            padding: 50px; 
            border-radius: 16px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .disclaimer {{
            background: linear-gradient(135deg, #fff3cd 0%, #ffe8a1 100%);
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 24px;
            font-size: 14px;
            color: #856404;
        }}
        h1 {{ 
            color: #1a202c; 
            border-bottom: 3px solid #667eea; 
            padding-bottom: 15px; 
            margin-bottom: 30px;
            font-size: 2em;
        }}
        h2 {{
            color: #2d3748;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
        }}
        h3 {{
            color: #4a5568;
            margin-top: 25px;
            margin-bottom: 15px;
        }}
        p {{ margin-bottom: 16px; color: #4a5568; }}
        ul, ol {{ margin-left: 24px; margin-bottom: 16px; color: #4a5568; }}
        li {{ margin-bottom: 8px; }}
        strong {{ color: #2d3748; }}
        blockquote {{
            background: #f7fafc;
            border-left: 4px solid #667eea;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #e2e8f0;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background: #f7fafc;
            font-weight: 600;
        }}
        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        hr {{
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 30px 0;
        }}
        code {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        
        /* 图表区域样式 */
        .charts-section {{
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border-radius: 12px;
            padding: 30px;
            margin: 30px 0;
        }}
        .charts-title {{
            text-align: center;
            color: #2d3748;
            font-size: 1.5em;
            margin-bottom: 25px;
            font-weight: 600;
        }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }}
        .chart-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        .chart-card-title {{
            text-align: center;
            color: #4a5568;
            font-size: 1em;
            margin-bottom: 15px;
            font-weight: 500;
        }}
        .chart-container {{
            width: 100%;
            height: 280px;
        }}
        .wordcloud-container {{
            grid-column: span 2;
        }}
        .wordcloud-chart {{
            height: 320px;
        }}
        
        @media (max-width: 768px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
            .wordcloud-container {{
                grid-column: span 1;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="disclaimer">
            ⚠️ <strong>免责声明</strong>：内容由AI生成，仅供参考，您据此所作判断及操作均由您自行承担责任。
        </div>
        
        <!-- 报告正文 -->
        {report_html}
        
        <!-- 可视化图表区域（放在文章后面） -->
        <div class="charts-section">
            <div class="charts-title">📊 舆情数据可视化</div>
            <div class="charts-grid">
                <!-- 情感分布饼图 -->
                <div class="chart-card">
                    <div class="chart-card-title">情感倾向分布</div>
                    <div id="sentimentChart" class="chart-container"></div>
                </div>
                
                <!-- 热度趋势折线图 -->
                <div class="chart-card">
                    <div class="chart-card-title">热度趋势变化</div>
                    <div id="heatChart" class="chart-container"></div>
                </div>
                
                <!-- 来源分布柱状图 -->
                <div class="chart-card">
                    <div class="chart-card-title">数据来源分布</div>
                    <div id="sourceChart" class="chart-container"></div>
                </div>
                
                <!-- 风险评估仪表盘 -->
                <div class="chart-card">
                    <div class="chart-card-title">舆情风险评估</div>
                    <div id="riskChart" class="chart-container"></div>
                </div>
                
                <!-- 关键词词云 -->
                <div class="chart-card wordcloud-container">
                    <div class="chart-card-title">关键词词云</div>
                    <div id="wordcloudChart" class="chart-container wordcloud-chart"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 等待 ECharts 加载完成后再初始化图表
        function initCharts() {{
            if (typeof echarts === 'undefined') {{
                // ECharts 还未加载，等待后重试
                setTimeout(initCharts, 100);
                return;
            }}
            
            // 情感分布饼图
            var sentimentChart = echarts.init(document.getElementById('sentimentChart'));
        sentimentChart.setOption({{
            tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}}% ({{d}}%)' }},
            legend: {{ bottom: '5%', left: 'center' }},
            series: [{{
                type: 'pie',
                radius: ['40%', '70%'],
                avoidLabelOverlap: false,
                itemStyle: {{ borderRadius: 10, borderColor: '#fff', borderWidth: 2 }},
                label: {{ show: false, position: 'center' }},
                emphasis: {{
                    label: {{ show: true, fontSize: 20, fontWeight: 'bold' }}
                }},
                labelLine: {{ show: false }},
                data: [
                    {{ value: {sentiment_data.get('正面', 33)}, name: '正面', itemStyle: {{ color: '#52c41a' }} }},
                    {{ value: {sentiment_data.get('中性', 34)}, name: '中性', itemStyle: {{ color: '#1890ff' }} }},
                    {{ value: {sentiment_data.get('负面', 33)}, name: '负面', itemStyle: {{ color: '#ff4d4f' }} }}
                ]
            }}]
        }});
        
        // 热度趋势折线图
        var heatChart = echarts.init(document.getElementById('heatChart'));
        heatChart.setOption({{
            tooltip: {{ trigger: 'axis' }},
            xAxis: {{ type: 'category', data: {json.dumps(heat_labels)}, boundaryGap: false }},
            yAxis: {{ type: 'value', min: 0, max: 100 }},
            series: [{{
                type: 'line',
                smooth: true,
                data: {json.dumps(heat_trend)},
                areaStyle: {{
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        {{ offset: 0, color: 'rgba(102, 126, 234, 0.5)' }},
                        {{ offset: 1, color: 'rgba(102, 126, 234, 0.05)' }}
                    ])
                }},
                lineStyle: {{ color: '#667eea', width: 3 }},
                itemStyle: {{ color: '#667eea' }}
            }}]
        }});
        
        // 来源分布柱状图
        var sourceChart = echarts.init(document.getElementById('sourceChart'));
        sourceChart.setOption({{
            tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
            xAxis: {{ type: 'category', data: {json.dumps(list(source_stats.keys()))} }},
            yAxis: {{ type: 'value' }},
            series: [{{
                type: 'bar',
                data: {json.dumps(list(source_stats.values()))},
                itemStyle: {{
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        {{ offset: 0, color: '#667eea' }},
                        {{ offset: 1, color: '#764ba2' }}
                    ]),
                    borderRadius: [5, 5, 0, 0]
                }}
            }}]
        }});
        
        // 风险评估仪表盘
        var riskChart = echarts.init(document.getElementById('riskChart'));
        var riskScore = {analysis.sentiment_score * 50 + 50};  // 转换为 0-100
        var riskColor = riskScore > 60 ? '#52c41a' : (riskScore > 40 ? '#faad14' : '#ff4d4f');
        riskChart.setOption({{
            series: [{{
                type: 'gauge',
                startAngle: 180,
                endAngle: 0,
                min: 0,
                max: 100,
                splitNumber: 5,
                itemStyle: {{ color: riskColor }},
                progress: {{ show: true, width: 20 }},
                pointer: {{ show: false }},
                axisLine: {{ lineStyle: {{ width: 20 }} }},
                axisTick: {{ show: false }},
                splitLine: {{ show: false }},
                axisLabel: {{ show: false }},
                title: {{ show: false }},
                detail: {{
                    valueAnimation: true,
                    fontSize: 28,
                    offsetCenter: [0, '0%'],
                    formatter: function(value) {{
                        if (value > 60) return '低风险';
                        if (value > 40) return '中风险';
                        return '高风险';
                    }},
                    color: riskColor
                }},
                data: [{{ value: riskScore }}]
            }}]
        }});
        
        // 关键词词云
        var wordcloudChart = echarts.init(document.getElementById('wordcloudChart'));
        wordcloudChart.setOption({{
            series: [{{
                type: 'wordCloud',
                shape: 'circle',
                left: 'center',
                top: 'center',
                width: '90%',
                height: '90%',
                sizeRange: [14, 60],
                rotationRange: [-45, 45],
                gridSize: 8,
                drawOutOfBound: false,
                textStyle: {{
                    fontFamily: 'PingFang SC, Microsoft YaHei, sans-serif',
                    fontWeight: 'bold',
                    color: function() {{
                        var colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7'];
                        return colors[Math.floor(Math.random() * colors.length)];
                    }}
                }},
                data: {json.dumps(keyword_weights)}
            }}]
        }});
        
            // 响应式调整
            window.addEventListener('resize', function() {{
                sentimentChart.resize();
                heatChart.resize();
                sourceChart.resize();
                riskChart.resize();
                wordcloudChart.resize();
            }});
        }}
        
        // 页面加载完成后初始化图表
        // 监听 echarts-ready 事件（优先）
        window.addEventListener('echarts-ready', initCharts);
        
        // 同时检查 ECharts 是否已加载（用于独立打开 HTML 的情况）
        if (document.readyState === 'complete') {{
            setTimeout(initCharts, 500);
        }} else {{
            window.addEventListener('load', function() {{
                setTimeout(initCharts, 500);
            }});
        }}
    </script>
</body>
</html>"""

    state.status = "complete"
    state.current_phase = "分析完成"
    state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 舆情分析完成")

    # 发送最终状态
    await push_state_event(run_id, state)

    return "HTML 渲染完成"
