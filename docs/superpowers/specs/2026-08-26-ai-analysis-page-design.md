# AI 分析页体验优化设计

## 目标

优化 SQL Lab 的“AI 数据专家分析”窗口，使用户可以在更大的阅读区域中完成分析，保存会话时主动命名并获得明确反馈，同时将当前完整分析会话下载为 Markdown 或真正的 Word `.docx` 文件。

## 用户体验

- AI 分析窗口顶部工具栏按 A 方案排列：放大/还原、历史会话、保存会话、导出 Markdown、导出 Word、关闭。
- 默认仍以当前右侧分析窗口形式打开；点击放大后，分析窗口铺满浏览器视口并隐藏背景遮罩，点击还原回到默认宽度。该放大是页面内布局状态，不调用浏览器全屏 API，不改变 SQL Lab 主页面的全屏状态。
- “保存会话”仅在有消息时可用。点击后打开命名对话框，默认填入带时间的名称；名称去除首尾空格、不能为空且最多 200 个字符。取消不产生请求，确认后沿用现有 `/api/portal/lab/analysis-sessions` 保存接口。
- 保存成功沿用 SQL Lab 现有全局 Toast 显示“分析会话已保存”，失败显示“保存失败”；命名弹窗关闭后不会阻塞用户继续查看分析。
- 两个导出按钮仅在有消息且未处于流式生成时可用。导出的是点击时当前消息快照，生成文件后浏览器直接下载；导出失败显示 Toast，不影响会话内容。

## 导出内容

完整会话按消息顺序导出：

1. 文档标题、生成时间和当前 SQL（如果存在）。
2. 每一条用户提问。
3. 每一条 AI 回复的原始 Markdown 内容，包括标题、列表、引用、代码块和表格。
4. AI 回复关联的 ECharts 图表配置，以“图表 1/2 …”小节和格式化 JSON 保留，确保 Markdown 与 Word 中不会丢失图表数据定义。
5. AI 回复生成的引导性追问，以“继续探索建议”列表保留。

Markdown 导出使用 UTF-8 文本 Blob，扩展名为 `.md`。Word 导出使用前端 `docx` 库生成真正的 `.docx` 文件，包含标题、段落、基础 Markdown 结构、代码块、表格以及图表配置说明；文件名由会话标题生成并过滤文件系统不安全字符。

## 代码边界

- `frontend/src/components/sqllab/AnalysisChat.vue` 负责窗口状态、工具栏、命名弹窗、按钮可用性和 Toast 触发时机；保持现有会话 API 与父组件保存回调不变。
- 新增 `frontend/src/utils/analysisExport.ts`，负责将分析消息快照转换为 Markdown 文本和 `docx` 文档构建所需的结构，集中处理标题、角色、图表、建议、文件名安全化和空内容边界。
- `frontend/src/views/SQLLab.vue` 仅保留现有保存接口调用；不新增数据库字段、迁移或后端路由。
- `frontend/package.json` 与 `frontend/package-lock.json` 增加 `docx` 运行时依赖；复用已有 `file-saver` 下载机制。
- 不修改 SQL Lab 现有 Excel 导出、历史会话 CRUD 和全局 Toast 组件的行为。

## 数据流与错误处理

```text
用户点击保存 -> 命名弹窗校验 -> save-session 事件 -> SQLLab.vue POST -> 全局 Toast

用户点击导出 -> 复制当前 messages -> analysisExport 工具生成 Blob -> file-saver 下载
                                      \-> 生成异常 -> 导出失败 Toast
```

- 导出使用当前响应式消息的浅拷贝快照，不在异步生成期间读取可能变化的数组引用。
- 空标题、空消息列表、流式生成中均在按钮或表单层拦截，不发起无效请求或生成空文件。
- Word 生成只处理受控的文本节点和已有消息数据，不执行 AI 返回的 HTML；Markdown 预览仍沿用现有安全渲染函数。
- 图表配置序列化失败时，导出流程保留“图表暂无法序列化”的文字说明，不让单个异常图表阻断整个会话导出。

## 验证

- 为 `analysisExport.ts` 增加测试，先验证 Markdown 包含完整消息顺序、SQL、图表配置和建议，文件名过滤危险字符，空消息有明确行为；再验证 Word 构建返回可下载的 OOXML Blob/ArrayBuffer。
- 前端运行 `npm run typecheck` 和 `npm run build`。
- 手动验证：打开 SQL Lab 的 AI 分析，切换放大/还原，确认窗口铺满视口；输入会话名称保存并观察成功 Toast；模拟保存失败观察失败 Toast；分别下载 `.md` 和 `.docx`，检查内容包含用户提问、AI 回复、图表说明和建议；确认流式生成期间导出按钮禁用。
- 后端现有 `tests/api/portal/test_lab_enhancements.py::test_analysis_session_crud` 继续作为保存接口回归，不新增后端测试或迁移。
