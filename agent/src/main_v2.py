"""
V2 版本启动文件 - 实时状态同步优化
"""
import uvicorn
from agent_v2 import opinion_agent, StateDeps, OpinionState

# 创建 ag_ui 应用
app = opinion_agent.to_ag_ui(deps=StateDeps(OpinionState()))

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 启动 V2 舆情分析系统 (实时同步优化版)")
    print("="*80)
    print("📍 Agent UI: http://localhost:8000")
    print("📍 WebSocket: ws://localhost:8000/ws")
    print("="*80 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

