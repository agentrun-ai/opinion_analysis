# 数据收集提前终止问题 - 修复记录

## 🐛 问题描述

### 用户反馈
1. **第一次测试**: 要求收集 5 条数据，但只收集到 4 条就结束
2. **第二次测试**: 要求收集 50 条数据，但只收集到 2 条就结束

### 问题分析

LLM 提前停止数据收集的原因：
1. **提示词不明确**: 没有清楚告知 LLM 需要收集多少条
2. **缺少进度反馈**: LLM 不知道当前进度和剩余任务
3. **没有强制约束**: 缺少"必须达到目标"的明确指令

---

## ✅ 修复方案

### 1. 增强 `start_collection` 工具

**修改前**:
```python
@opinion_agent.tool
async def start_collection(...) -> StateSnapshotEvent:
    """开始数据收集流程"""
    await log_and_update(ctx, "collecting", f"开始收集...")
    return StateSnapshotEvent(...)
```

**修改后**:
```python
@opinion_agent.tool
async def start_collection(...) -> str:
    """开始数据收集流程"""
    max_results = ctx.deps.state.max_results
    
    print(f"🎯 目标: 收集 {max_results} 条数据")
    
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
```

**改进点**:
- ✅ 明确返回目标数量
- ✅ 返回详细的操作指引
- ✅ 强调"必须收集满"

---

### 2. 优化 `save_search_result` 反馈

**修改前**:
```python
@opinion_agent.tool
async def save_search_result(...) -> StateSnapshotEvent:
    """保存一条搜索结果"""
    # 保存数据
    print(f"💾 [SAVED {current_count}/{max_count}]")
    return StateSnapshotEvent(...)  # 只返回事件，LLM 看不到进度
```

**修改后**:
```python
@opinion_agent.tool
async def save_search_result(...) -> str:
    """保存一条搜索结果 - 返回进度和指引"""
    
    remaining = max_count - current_count
    
    if remaining == 0:
        return f"""
✅ 数据保存成功！进度: {current_count}/{max_count} (100%)

⚡ 已达到目标数量！立即调用 finish_collection 完成收集！
"""
    else:
        return f"""
✅ 数据保存成功！进度: {current_count}/{max_count} ({percent}%)

还需收集: {remaining} 条

⚡ 继续搜索并保存数据，直到达到 {max_count} 条！
"""
```

**改进点**:
- ✅ 返回字符串而非 StateSnapshotEvent
- ✅ LLM 可以"看到"当前进度
- ✅ 明确告知还需多少条
- ✅ 给出下一步行动指引

---

### 3. 强化系统提示词

**修改前**:
```
1. 调用 start_collection(keyword)
2. 使用 baidu_search 搜索
3. 对每条结果调用 save_search_result
4. 达到 max_results 后调用 finish_collection
```

**修改后**:
```
1. 调用 start_collection(keyword)
   → 系统会告诉你需要收集多少条（max_results）

2. **持续搜索直到达到目标数量**:
   循环执行以下步骤，直到收集满 max_results 条：
   
   a. 使用 baidu_search 搜索（多角度）
   b. 从搜索结果中提取有价值的信息
   c. 对每条调用 save_search_result
   d. 检查进度：
      - 如果已达到 max_results → 调用 finish_collection
      - 如果未达到 → 继续搜索（回到步骤 a）

⚠️ 重要：不要提前停止！必须收集满 max_results 条数据！
```

**改进点**:
- ✅ 明确"循环执行"的概念
- ✅ 强调"持续搜索直到达到目标"
- ✅ 添加醒目警告："不要提前停止"

---

## 🔍 工作流程对比

### 修复前（问题流程）

```
用户: 收集 5 条数据

LLM:
1. start_collection() ← 没有明确目标
2. baidu_search() → 返回 10 个结果
3. save_search_result(第1条) ← 没有进度反馈
4. save_search_result(第2条) ← 没有进度反馈
5. save_search_result(第3条) ← 没有进度反馈
6. ❌ LLM 以为完成了，调用 finish_collection
   
结果: 只收集了 3 条（应该是 5 条）
```

### 修复后（正确流程）

```
用户: 收集 5 条数据

LLM:
1. start_collection()
   ← 返回: "目标数量: 5 条，必须收集满"

2. baidu_search()

3. save_search_result(第1条)
   ← 返回: "进度: 1/5 (20%)，还需 4 条，继续搜索！"

4. save_search_result(第2条)
   ← 返回: "进度: 2/5 (40%)，还需 3 条，继续搜索！"

5. save_search_result(第3条)
   ← 返回: "进度: 3/5 (60%)，还需 2 条，继续搜索！"

6. save_search_result(第4条)
   ← 返回: "进度: 4/5 (80%)，还需 1 条，继续搜索！"

7. save_search_result(第5条)
   ← 返回: "进度: 5/5 (100%)，已达到目标，立即调用 finish_collection！"

8. ✅ finish_collection()

结果: 成功收集 5 条
```

---

## 📊 关键改进点总结

| 问题 | 修复前 | 修复后 |
|------|--------|--------|
| **目标明确性** | ❌ LLM 不知道目标数量 | ✅ 明确告知 max_results |
| **进度可见性** | ❌ LLM 看不到当前进度 | ✅ 每次保存都返回进度 |
| **行动指引** | ❌ 没有下一步提示 | ✅ 明确"还需X条，继续搜索" |
| **强制约束** | ❌ 可以随时停止 | ✅ 强调"必须达到目标" |
| **返回类型** | `StateSnapshotEvent` | `str`（LLM 可读） |

---

## 🧪 测试验证

### 测试用例 1: 小规模收集

```
设置: max_results = 5

预期行为:
1. start_collection → "目标: 5 条"
2. save_search_result × 5 → 每次显示进度
3. finish_collection → 完成

预期结果: ✅ 收集到 5 条数据
```

### 测试用例 2: 大规模收集

```
设置: max_results = 50

预期行为:
1. start_collection → "目标: 50 条"
2. save_search_result × 50 → 实时进度
3. 可能需要多次 baidu_search
4. finish_collection → 完成

预期结果: ✅ 收集到 50 条数据
```

### 测试用例 3: 搜索结果不足

```
设置: max_results = 100
假设: baidu_search 每次只返回 10 条

预期行为:
1. start_collection → "目标: 100 条"
2. 循环多次 baidu_search
3. 持续调用 save_search_result
4. 直到达到 100 条
5. finish_collection

预期结果: ✅ 收集到 100 条（或尽可能多）
```

---

## 🔧 技术细节

### 为什么改用 `str` 返回类型？

**问题**: `StateSnapshotEvent` 只用于前端同步，LLM 看不到内容

```python
# ❌ LLM 看不到进度
return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state)
```

**解决**: 返回字符串，LLM 可以读取并理解

```python
# ✅ LLM 可以看到进度和指引
return "✅ 进度: 3/5 (60%)，还需 2 条，继续搜索！"
```

### 前端同步怎么办？

虽然 `save_search_result` 不再返回 `StateSnapshotEvent`，但状态仍然实时更新：

1. **状态已更新**: `ctx.deps.state.raw_data.append(result)`
2. **日志已更新**: `await log_and_update(...)`
3. **前端仍能看到**: 通过 `collected_data_summary`

---

## ✅ 部署状态

### 修改的文件

1. **agent/src/agent_v2.py**
   - `start_collection` 工具（返回类型和内容）
   - `save_search_result` 工具（返回类型和进度反馈）
   - 系统提示词（更强化的指引）

### 服务器状态

```bash
✅ Backend running on http://localhost:8000
✅ Collection logic improved
✅ Ready for testing
```

---

## 📝 后续建议

### 1. 监控建议

在后端日志中监控：
```bash
tail -f /tmp/v2_server.log | grep "进度"
```

应该能看到：
```
📊 [进度] 已完成 1/5，还需 4 条
📊 [进度] 已完成 2/5，还需 3 条
📊 [进度] 已完成 3/5，还需 2 条
...
```

### 2. 调试技巧

如果仍然提前停止，检查：
1. LLM 的工具调用日志
2. 是否每次都调用了 `save_search_result`
3. `finish_collection` 是在什么时候被调用的

### 3. 进一步优化

可能的改进：
- 添加最小收集数量检查
- 搜索结果不足时的降级策略
- 自动重试机制

---

## 🎯 总结

**核心修复**: 让 LLM "看见"进度，"知道"目标，"理解"任务

- ✅ start_collection 明确目标
- ✅ save_search_result 返回进度
- ✅ 系统提示词强化约束
- ✅ 每一步都有明确指引

**预期效果**: LLM 不会再提前停止，会持续收集直到达到 `max_results`！

