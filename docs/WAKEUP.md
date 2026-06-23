# 项目唤醒 Prompt

## 今天用这个（5/15 三阶段优先）

```text
我正在开发"舆情智能标注系统"，项目位于 D:\Claude code\舆情标注Wiki。

请先阅读 DESIGN.md 了解当前状态（v1.3.0），再读 WAKEUP.md 了解今天的任务。

今天按顺序推进 Phase 17a → 17b → 17c，每做完一个 Phase 运行
python -m pytest tests/test_core.py -v 确保 21/21 通过，然后继续下一个。

Phase 17a: app.py 拆分（半天）
- app.py 1,376 行单文件拆为：
  app.py (~200行入口) + ui/sidebar.py + ui/shared.py +
  ui/tab1_manual.py + ui/tab2_url.py + ui/tab5_demo.py
- 提取逻辑不做改动，只移动函数和代码块
- 拆分后 Streamlit 启动正常、功能无变化

Phase 17b: 测试补盲（半天）
- 至少补 3 个集成测试：
  1. Deferred flow: button click → flag → rerun → session_state 链路
  2. Tab 隔离: _result_source 过滤逻辑
  3. 手工录入保存 → ingest 入库
- 放在 tests/test_core.py 末尾或新建 tests/test_app_state.py

Phase 17c: XHS Cookie 攻坚（一天）
- 第一步：用 Debug 模式抓一次小红书笔记，打印 API 返回的完整 JSON
- 第二步：对比 xhshow 签名需要的 Cookie 和 Playwright 实际获取的 Cookie
- 第三步：定位差异，补充缺失的 Cookie 提取逻辑
- 目标：扫码 → 保存 Cookie → 抓取成功

做完每个 Phase 后：
1. 自省 2 分钟，写入一条记忆
2. 更新 DESIGN.md 路线图状态
3. git commit + push (SSH 方式: git@github.com:evanhan1995/opinion-annotation-demo.git)
```

---

## v1.3.0 速览

```
舆情智能标注系统 — LLM + Wiki 知识库的智能打标与分流判断

5 Tab: 📝手工录入 | 🔗URL抓取 | 📚知识库 | 💬扫地僧 | 🎬操作演示
5,283 行 Python | 21/21 测试 | 27 案例 | 5 作者

URL → scraper(YouTube+小红书) → annotate(LLM流式+10K token prompt) → outputs/
                                        ↘ ingestor → wiki/cases/ + wiki/authors/
                                        ↘ correction_handler (人工纠偏)
                                        ↘ agent (知识库问答)
```

## 关键架构规则

1. **Deferred Pattern**: 按钮只做 `清空+flag+st.rerun()` → 下次运行 Tab 块内执行实际工作
2. **`_needs_rerun` gate**: 脚本末尾统一重跑，绝不在 `if st.button():` 内调 `st.rerun()`
3. **Tab 隔离**: `_render_annotation_result` 内 `_result_source` 非破坏性过滤
4. **yt-dlp**: `max_comments=["50"]` 不可删除
5. **测试先跑**: `python -m pytest tests/test_core.py -v`，21/21
6. **SSH 推送**: `git remote -v` 应为 `git@github.com:evanhan1995/opinion-annotation-demo.git`

## 常见陷阱

- `st.rerun()` 绝不在 button handler 内 → 用 `_needs_rerun = True`
- 删 UI 组件必同步删 handler、flag、session_state key
- f-string 内禁 `\"` 转义 → 用变量
- 新增 config 字段验证三端: 写入 → 传输 → 消费
- 改 index.md 表格逻辑→测 split→modify→rebuild 全周期
