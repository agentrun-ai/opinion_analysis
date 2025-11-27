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
@app.post("/api/agent/")
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


# ===== 静态文件路由 =====
def get_media_type(suffix: str) -> str:
    media_types = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.map': 'application/json',
        '.txt': 'text/plain',
    }
    return media_types.get(suffix.lower(), 'application/octet-stream')


@app.get("/")
async def serve_index():
    """主页"""
    if not STATIC_DIR.exists():
        return JSONResponse(
            status_code=500,
            content={"error": "静态文件目录不存在，请先运行 make build"}
        )
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "index.html 不存在"})


@app.get("/_next/{path:path}")
async def serve_next_static(path: str):
    """Next.js 静态资源"""
    file_path = STATIC_DIR / "_next" / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path, media_type=get_media_type(file_path.suffix))
    return JSONResponse(status_code=404, content={"error": "Not found"})


@app.get("/favicon.ico")
async def serve_favicon():
    """Favicon"""
    file_path = STATIC_DIR / "favicon.ico"
    if file_path.exists():
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"error": "Not found"})


@app.get("/{path:path}")
async def serve_static(path: str):
    """其他静态文件"""
    # 跳过 API 路径
    if path.startswith("api/"):
        return JSONResponse(status_code=404, content={"error": "API not found"})
    
    if not STATIC_DIR.exists():
        return JSONResponse(status_code=500, content={"error": "静态文件目录不存在"})
    
    file_path = STATIC_DIR / path
    if file_path.is_dir():
        file_path = file_path / "index.html"
    
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path, media_type=get_media_type(file_path.suffix))
    
    # SPA fallback
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    
    return JSONResponse(status_code=404, content={"error": f"Not found: {path}"})


@app.on_event("startup")
async def startup():
    print("\n" + "="*60)
    print("🚀 启动舆情分析系统")
    print("="*60)
    print(f"📍 服务地址: http://localhost:8000")
    print(f"📍 AG-UI API: http://localhost:8000/api/agent/")
    print(f"📍 静态文件: {STATIC_DIR}")
    print("")
    print("🔗 通信协议: AG-UI (HTTP SSE)")
    print("   无需 GraphQL，直接使用 SSE 流式通信")
    
    if not STATIC_DIR.exists():
        print(f"\n⚠️  静态文件目录不存在: {STATIC_DIR}")
        print("   请先运行: make build")
    else:
        print(f"\n✅ 静态文件目录已就绪")
    
    print("="*60 + "\n")


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
