"""
舆情分析系统 - 纯 Python 后端
使用 AG-UI 协议通过 HTTP SSE 通信，无需 GraphQL

提供：
1. AG-UI API (/api/agent) - 直接 SSE 通信
2. 静态文件服务 (前端)
"""
import uvicorn
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from agent import opinion_agent, StateDeps, OpinionState
from pydantic_ai.ag_ui import handle_ag_ui_request

# 静态文件目录
_agent_dir = Path(__file__).parent.parent.parent
_dev_static = _agent_dir / "out"
_prod_static = _agent_dir / 'frontend' / "out"

if _dev_static.exists():
    STATIC_DIR = _dev_static
else:
    STATIC_DIR = _prod_static

# ===== 主 FastAPI 应用 =====
app = FastAPI(title="舆情分析系统")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== AG-UI API =====
# 为每个请求创建新的状态实例，避免状态污染
@app.post("/api/agents")
async def agent_endpoint(request: Request):
    """AG-UI 端点 - 每次请求创建新的状态"""
    # 创建新的状态实例
    deps = StateDeps(OpinionState())
    
    # 使用 PydanticAI 的 handle_ag_ui_request 处理请求
    return await handle_ag_ui_request(
        opinion_agent,
        request,
        deps=deps,
    )


@app.on_event("startup")
async def startup():
    print("\n" + "="*60)
    print("🚀 启动舆情分析系统")
    print("="*60)


if __name__ == "__main__":
    # 配置 uvicorn 以提高稳定性
    # - timeout_keep_alive: 保持连接的超时时间
    # - limit_concurrency: 限制并发连接数，避免资源耗尽
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
        timeout_keep_alive=120,  # SSE 需要较长的保持时间
        limit_concurrency=100,   # 限制并发
    )
