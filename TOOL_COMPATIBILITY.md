# 工具兼容性说明

## 数据收集工具兼容性

系统设计为**工具无关**，可以兼容不同类型的数据收集工具。

### 当前支持的工具类型

#### 1. 百度搜索工具 (web-search-baidu)
```python
agentrun_code_interpreter = toolset("web-search-baidu-8baa")
```

**工具接口**：
- 工具名称：通常是 `search` 或类似名称
- 参数：`keyword` 或 `query`
- 返回：搜索结果列表

**LLM 使用方式**：
- 自动检测工具名称
- 传递搜索关键词
- 解析返回的结果
- 调用 `save_search_result` 保存

#### 2. Playwright Browser Use
```python
agentrun_browser = sandbox_toolset(
    "sdk-test-browser",
    template_type=TemplateType.BROWSER,
)
```

**工具接口**：
- `browser_navigate(url)`: 导航到URL
- `browser_snapshot()`: 获取页面快照
- `browser_click(selector)`: 点击元素
- `browser_type(selector, text)`: 输入文本
- 等...

**LLM 使用方式**：
- 自动检测可用的 browser 工具
- 规划浏览器操作序列：
  1. `browser_navigate` 到搜索引擎
  2. `browser_type` 输入关键词
  3. `browser_click` 点击搜索按钮
  4. `browser_snapshot` 获取结果页面
  5. 解析页面内容
  6. 调用 `save_search_result` 保存

### 兼容性保证

#### 关键设计点

1. **工具检测**：
```python
collection_tools = [*agentrun_code_interpreter] if len(agentrun_code_interpreter) > 0 else []
```

2. **灵活的 System Prompt**：
```python
system_prompt=dedent(f"""
    你是数据收集专家。
    
    可用工具: {len(collection_tools)} 个数据收集工具
    
    工作流程：
    1. 查看你拥有的工具列表
    2. 选择最合适的工具进行数据收集
    3. 对每条信息调用 save_search_result
    4. 完成后调用 finish_collection
""")
```

3. **工具无关的保存接口**：
```python
@data_collector.tool
async def save_search_result(
    ctx, title, url, snippet, source, date
) -> StateSnapshotEvent:
    # 统一的保存接口，不关心数据来源
    ...
```

### 切换工具的步骤

#### 从百度搜索切换到 Playwright

1. **修改工具配置**：
```python
# 旧配置
agentrun_code_interpreter = toolset("web-search-baidu-8baa")

# 新配置
agentrun_browser = sandbox_toolset(
    "sdk-test-browser",
    template_type=TemplateType.BROWSER,
)
collection_tools = [*agentrun_browser]
```

2. **无需修改其他代码**：
- `data_collector` Agent 会自动检测新工具
- System Prompt 中的 `{len(collection_tools)}` 自动更新
- LLM 会根据可用工具自动调整策略

3. **LLM 自动适配**：
- 检测到 `browser_navigate` → 知道是浏览器工具
- 检测到 `search` → 知道是搜索工具
- 根据工具签名自动生成正确的调用参数

### 最佳实践

1. **工具命名清晰**：
   - 工具名称应该描述性强（如 `browser_navigate` vs `navigate`）
   - 参数名称要直观（如 `url`, `keyword`, `query`）

2. **提供工具描述**：
   - 每个工具应该有清晰的 docstring
   - LLM 会读取工具描述来理解如何使用

3. **统一数据格式**：
   - 无论使用什么工具收集数据
   - 最终都通过 `save_search_result` 统一保存
   - 保证数据格式一致性

### 示例对比

#### 百度搜索工具使用

```
LLM 思考过程：
1. 我看到有 "search" 工具
2. 参数需要 keyword="雷军"
3. 调用 search(keyword="雷军")
4. 获得结果列表
5. 对每个结果调用 save_search_result
```

#### Playwright 使用

```
LLM 思考过程：
1. 我看到有 browser_navigate, browser_type 等工具
2. 我需要模拟用户搜索行为
3. browser_navigate("https://www.baidu.com")
4. browser_type("#kw", "雷军")
5. browser_click("#su")
6. browser_snapshot()
7. 解析快照内容
8. 对每个结果调用 save_search_result
```

### 测试兼容性

如果切换工具后遇到问题，检查：

1. ✅ 工具是否正确加载
```python
print(f"Collection Tools: {len(collection_tools)}")
```

2. ✅ 工具签名是否清晰
```python
# 查看工具定义
for tool in collection_tools:
    print(tool.__name__, tool.__doc__)
```

3. ✅ LLM 是否理解工具用途
- 观察日志中的工具调用
- 检查参数是否正确

4. ✅ 数据是否正确保存
- 检查 `state.raw_data` 是否有数据
- 验证数据格式是否符合 `SearchResult`

### 结论

系统通过以下机制保证工具兼容性：

- ✅ **动态工具检测**
- ✅ **灵活的 Prompt Engineering**
- ✅ **统一的数据接口**
- ✅ **LLM 的自适应能力**

无论使用百度搜索、Playwright、或其他任何工具，只要：
1. 工具能被 PydanticAI 识别
2. 工具签名清晰
3. 最终调用 `save_search_result` 保存数据

系统就能正常工作！

