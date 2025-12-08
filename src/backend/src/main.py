"""
舆情分析系统 - 纯 Python 后端

提供：
1. AG-UI API (/api/agent) - 支持实时状态推送的 SSE 通信
2. Browser VNC URL API (/api/browser/vnc) - 获取浏览器预览 URL
3. Browser Sandboxes API (/api/browser/sandboxes) - 获取所有 Sandbox 列表
"""
import uvicorn
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

from agent import opinion_agent, StateDeps, OpinionState, get_browser_sandbox, get_all_sandboxes
from event_queue import event_manager
from ag_ui.core import RunAgentInput, EventType


# ===== Lifespan =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*60)
    print("🚀 启动舆情分析系统")
    print("   - 实时状态推送")
    print("   - 代码控制流程")
    print("   - 严格数据收集")
    print("   - 多 Sandbox 支持")
    print("="*60)
    yield
    print("\n🛑 关闭舆情分析系统")


# ===== 主 FastAPI 应用 =====
app = FastAPI(title="舆情分析系统", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== AG-UI API with Real-time State Push =====
@app.post("/api/agent")
async def agent_endpoint(request: Request):
    """
    AG-UI 端点 - 支持实时状态推送
    
    工作原理：
    1. 解析请求获取 run_id
    2. 在后台运行 Agent
    3. 从事件队列实时消费并发送 STATE_SNAPSHOT 事件
    """
    # 解析请求体
    body = await request.json()
    run_input = RunAgentInput.model_validate(body)
    run_id = run_input.run_id
    thread_id = run_input.thread_id
    
    print(f"\n{'='*60}")
    print(f"🚀 开始处理请求: run_id={run_id}")
    print(f"{'='*60}")
    
    # 从请求中获取前端传递的状态，合并到默认状态
    frontend_state = body.get("state", {})
    state = OpinionState()
    
    # 应用前端传递的配置
    if frontend_state:
        if "max_results" in frontend_state:
            state.max_results = int(frontend_state["max_results"])
            print(f"📊 最大采集数量: {state.max_results}")
    
    deps = StateDeps(state)
    
    # 获取事件队列
    queue = event_manager.get_queue(run_id)
    
    async def event_generator():
        """SSE 事件生成器"""
        
        # 1. 发送 RUN_STARTED 事件
        run_started = {
            "type": "RUN_STARTED",
            "threadId": thread_id,
            "runId": run_id
        }
        yield f"data: {json.dumps(run_started)}\n\n"
        
        # 2. 在后台启动 Agent
        agent_task = asyncio.create_task(run_agent_in_background(run_input, deps, run_id))
        
        # 3. 消费事件队列
        agent_done = False
        
        while not agent_done:
            try:
                # 检查 Agent 是否完成
                if agent_task.done():
                    agent_done = True
                    # 处理可能的异常
                    try:
                        agent_task.result()
                    except Exception as e:
                        print(f"❌ Agent 执行错误: {e}")
                        error_event = {
                            "type": "RUN_ERROR",
                            "message": str(e)
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                
                # 非阻塞获取事件
                try:
                    event = queue.get_nowait()
                    # 编码事件
                    if hasattr(event, 'model_dump'):
                        event_dict = event.model_dump()
                    elif isinstance(event, dict):
                        event_dict = event
                    else:
                        event_dict = {"type": "UNKNOWN", "data": str(event)}
                    
                    yield f"data: {json.dumps(event_dict, ensure_ascii=False, default=str)}\n\n"
                except asyncio.QueueEmpty:
                    # 队列为空，等待一小段时间
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                print(f"❌ 事件生成器错误: {e}")
                break
        
        # 4. 清空队列中剩余的事件
        while not queue.empty():
            try:
                event = queue.get_nowait()
                if hasattr(event, 'model_dump'):
                    event_dict = event.model_dump()
                elif isinstance(event, dict):
                    event_dict = event
                else:
                    event_dict = {"type": "UNKNOWN", "data": str(event)}
                yield f"data: {json.dumps(event_dict, ensure_ascii=False, default=str)}\n\n"
            except:
                break
        
        # 5. 发送 RUN_FINISHED 事件
        run_finished = {
            "type": "RUN_FINISHED",
            "threadId": thread_id,
            "runId": run_id
        }
        yield f"data: {json.dumps(run_finished)}\n\n"
        
        # 6. 清理
        event_manager.remove_queue(run_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def run_agent_in_background(run_input: RunAgentInput, deps: StateDeps, run_id: str):
    """在后台运行 Agent"""
    # 从消息中提取用户输入
    user_message = ""
    for msg in run_input.messages:
        if msg.role == "user":
            if isinstance(msg.content, str):
                user_message = msg.content
            elif isinstance(msg.content, list):
                for part in msg.content:
                    if hasattr(part, 'text'):
                        user_message = part.text
                        break
            break
    
    if not user_message:
        user_message = "开始舆情分析"
    
    print(f"📝 用户消息: {user_message}")
    
    # 将 run_id 存储到 deps 中，供工具使用
    deps.run_id = run_id
    
    # 运行 Agent（使用流式调用以支持 qwen3-max）
    try:
        async with opinion_agent.run_stream(user_message, deps=deps) as result:
            # 消费流式响应
            async for _ in result.stream_text():
                pass
        print(f"✅ Agent 执行完成")
    except Exception as e:
        print(f"❌ Agent 执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise


# ===== Browser VNC/Livestream API =====
@app.get("/api/browser/vnc")
async def get_browser_vnc_url():
    """获取当前 Browser Sandbox 的 VNC/Livestream URL"""
    from urllib.parse import urlparse, parse_qs, urlencode
    
    try:
        sandbox = await get_browser_sandbox()
        if sandbox is None:
            return JSONResponse({
                "available": False,
                "vnc_url": None,
                "livestream_url": None,
                "sandbox_id": None,
                "message": "Browser Sandbox 未配置或不可用"
            })
        
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
        
        return JSONResponse({
            "available": True,
            "vnc_url": vnc_url,
            "livestream_url": livestream_url,
            "sandbox_id": sandbox.sandbox_id,
            "message": "VNC URL 获取成功"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "available": False,
            "vnc_url": None,
            "livestream_url": None,
            "sandbox_id": None,
            "message": f"获取 VNC URL 失败: {str(e)}"
        }, status_code=500)


# ===== Browser Sandboxes API =====
@app.get("/api/browser/sandboxes")
async def get_browser_sandboxes():
    """获取所有可用的 Browser Sandbox 列表"""
    try:
        sandboxes = await get_all_sandboxes()
        return JSONResponse({
            "sandboxes": sandboxes,
            "count": len(sandboxes),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "sandboxes": [],
            "count": 0,
            "error": str(e),
        }, status_code=500)


# ===== Browser Screenshot API =====
@app.get("/api/browser/screenshot")
async def get_browser_screenshot(sandbox_id: str = None):
    """获取指定 Browser Sandbox 的截图"""
    try:
        sandbox = await get_browser_sandbox(sandbox_id)
        if sandbox is None:
            return JSONResponse({
                "available": False,
                "message": "Browser Sandbox 未配置或不可用"
            }, status_code=404)
        
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(sandbox.get_cdp_url())
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
            
            return Response(
                content=screenshot_bytes,
                media_type="image/png",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "X-Sandbox-Id": sandbox.sandbox_id or ""
                }
            )
    except Exception as e:
        print(f"❌ 截图失败: {e}")
        return JSONResponse({
            "available": False,
            "message": f"截图失败: {str(e)}"
        }, status_code=500)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
        timeout_keep_alive=120,
        limit_concurrency=100,
    )
