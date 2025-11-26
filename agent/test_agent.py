#!/usr/bin/env python3
"""
测试脚本：验证 Opinion Agent 的工具调用逻辑
"""

import asyncio
import sys
sys.path.insert(0, '/Users/ohyee/projects/opinion_analysis/agent/src')

from agent import opinion_agent, OpinionState, StateDeps

async def test_agent():
    print("\n" + "="*60)
    print("🧪 TESTING OPINION AGENT")
    print("="*60)
    
    # 初始化状态
    state = OpinionState()
    deps = StateDeps(state)
    
    # 测试消息
    test_message = "请分析关键词：雷军"
    
    print(f"\n📝 Test Message: {test_message}")
    print(f"📊 Initial State: {state.model_dump()}")
    print(f"\n⏳ Running agent...\n")
    
    try:
        # 运行 Agent
        result = await opinion_agent.run(
            test_message,
            deps=deps
        )
        
        print("\n" + "="*60)
        print("✅ AGENT RESPONSE:")
        print("="*60)
        print(result.data)
        
        print("\n" + "="*60)
        print("📊 FINAL STATE:")
        print("="*60)
        print(f"Keyword: {state.keyword}")
        print(f"Status: {state.status}")
        print(f"Raw Data Count: {len(state.raw_data)}")
        print(f"Has Analysis: {state.analysis is not None}")
        print(f"Has Report: {len(state.report_text) > 0}")
        print(f"Has HTML: {len(state.final_html) > 0}")
        print(f"\nLogs ({len(state.logs)} entries):")
        for log in state.logs:
            print(f"  {log}")
        
        if state.raw_data:
            print(f"\n📦 Sample Data:")
            for i, item in enumerate(state.raw_data[:3], 1):
                print(f"  {i}. [{item.source}] {item.title}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())

