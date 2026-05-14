# 项目唤醒 Prompt

> 在新对话中粘贴此 Prompt，快速恢复项目上下文。

---

```text
我正在开发"舆情智能标注系统"，项目位于 D:\Claude code\舆情标注Wiki。

请先阅读 DESIGN.md 了解当前状态和路线图，再阅读 CONTINUITY.md 了解架构。
确认理解后告诉我：
1) 项目目前做到什么地步
2) 下一步是什么
3) 上次会话遗留的注意事项
```

---

## v1.3.0 速览

```
舆情智能标注系统 — 基于 LLM + Wiki 知识库的智能打标与分流判断

5 Tab: 📝手工录入 | 🔗URL抓取 | 📚知识库 | 💬扫地僧 | 🎬操作演示
5,283 行 Python | 21/21 测试 | 27 案例 | 5 作者 | 5 概念

URL → scraper(YouTube+小红书) → annotate(LLM流式+10K prompt) → outputs/
                                        ↘ ingestor → wiki/cases/ + wiki/authors/ + index
                                        ↘ correction_handler (人工纠偏)
                                        ↘ agent (知识库问答)
                                        ↘ linker (跨平台关联)
```

## 关键架构规则

1. **Deferred Pattern**: 按钮只做 `清空+flag+st.rerun()`，实际工作在下次运行的 Tab 块内完成
2. **`_needs_rerun` gate**: 脚本末尾统一处理重跑，绝不在 button handler 内调 `st.rerun()`
3. **Tab 隔离**: `_render_annotation_result` 内用 `_result_source` 做非破坏性过滤
4. **yt-dlp**: `max_comments=["50"]` 不可删除
5. **测试先跑**: `python -m pytest tests/test_core.py -v`，21/21
6. **Prompt 相关性**: `build_system_prompt(content)` 按内容选 top-5 案例，10K tokens
7. **配置安全**: API Key/密码在 `engine/config.json` (gitignored)，源码零敏感信息

## 常见陷阱

- `st.rerun()` 永远不要在 `if st.button():` 内调用 → 用 `_needs_rerun = True`
- 删除 UI 组件时必须同步删其 handler、flag、session_state key
- f-string 内不能有 `\"` 转义 → 用变量替代
- `load_config()` 新增字段需验证三端: config.json → load_config 返回 → 消费端读取
- 修改 ingestor 的表格逻辑后必须测 split→modify→rebuild 全周期

## 剩余路线

| 优先级 | 内容 |
|--------|------|
| 短期 | 用户提供新素材 → 生成案例/概念/Source 入库 |
| 中期 | XHS Cookie 稳定性 / 小红书图片OCR+视频ASR |
| 长期 | 向量检索(>500案例) / 飞书多人协作 / 多语言A/B |
