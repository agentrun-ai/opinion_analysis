"""
测试 V2 版本的实时状态同步功能
"""
import asyncio
from agent_v2 import opinion_agent, StateDeps, OpinionState

async def test_realtime_sync():
    """测试实时同步"""
    print("\n" + "="*80)
    print("🧪 测试 V2 实时同步功能")
    print("="*80 + "\n")
    
    # 创建初始状态
    state = OpinionState(max_results=5)
    deps = StateDeps(state)
    
    # 运行 Agent
    result = await opinion_agent.run(
        "请分析'雷军'的舆情，收集5条数据",
        deps=deps
    )
    
    print("\n" + "="*80)
    print("✅ 测试完成")
    print("="*80)
    print(f"📊 收集到 {len(state.raw_data)} 条数据")
    print(f"📊 前端摘要 {len(state.collected_data_summary)} 条")
    print(f"📊 分析结果: {state.analysis is not None}")
    print(f"📊 报告长度: {len(state.report_text)} 字符")
    print(f"📊 最终状态: {state.status}")
    print("="*80 + "\n")
    
    # 显示前端摘要（验证实时更新）
    if state.collected_data_summary:
        print("🔍 前端摘要列表（这些应该是逐条实时更新的）:")
        for i, item in enumerate(state.collected_data_summary, 1):
            print(f"  {i}. {item['source']}: {item['title'][:50]}...")
    
    return state

if __name__ == "__main__":
    asyncio.run(test_realtime_sync())

