#!/usr/bin/env python3
"""
测试多 Agent 系统
"""

import asyncio
import sys
sys.path.insert(0, '/Users/ohyee/projects/opinion_analysis/agent/src')

from agent import opinion_agent, OpinionState, StateDeps

async def test_multi_agent():
    print("\n" + "="*80)
    print("🧪 测试多 Agent 舆情分析系统")
    print("="*80)
    
    state = OpinionState()
    deps = StateDeps(state)
    
    test_message = "请分析关键词：雷军"
    
    print(f"\n📝 测试消息: {test_message}\n")
    
    try:
        result = await opinion_agent.run(test_message, deps=deps)
        
        print("\n" + "="*80)
        print("✅ 系统响应:")
        print("="*80)
        print(result.data)
        
        print("\n" + "="*80)
        print("📊 最终状态:")
        print("="*80)
        print(f"关键词: {state.keyword}")
        print(f"状态: {state.status}")
        print(f"原始数据: {len(state.raw_data)} 条")
        print(f"分析结果: {'✓' if state.analysis else '✗'}")
        print(f"报告: {'✓' if state.report_text else '✗'} ({len(state.report_text)} 字符)")
        print(f"HTML: {'✓' if state.final_html else '✗'} ({len(state.final_html)} 字符)")
        
        print(f"\n📋 系统日志 ({len(state.logs)} 条):")
        for log in state.logs:
            print(f"  {log}")
        
        if state.analysis:
            print(f"\n📈 分析结果:")
            print(f"  关键词: {state.analysis.keywords}")
            print(f"  情感得分: {state.analysis.sentiment_score}")
            print(f"  情感分布: {state.analysis.sentiment_distribution}")
        
        if state.report_text:
            print(f"\n📄 报告预览 (前500字):")
            print(state.report_text[:500] + "...")
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_multi_agent())

