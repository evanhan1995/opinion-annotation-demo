# Spec: 批量卡片审核台

## Objective

Monitor巡检结果一键批量导入→自动抓取+AI研判→折叠卡片展示→审核修改→逐条/批量保存到知识库。消除当前"逐条点击抓取→等待→看表单→点保存"的重复操作，将10条案例从~40次点击降到~5次点击。

**用户故事**: 作为舆情分析师，我在Monitor搜索到10条相关结果后，想一键将它们全部导入研判，快速浏览AI的自动判定结果，修正个别不准确的字段，然后一次性保存到知识库。

## Tech Stack

- Python 3.x + Streamlit (现有)
- DeepSeek/OpenAI API (现有 annotate.py)
- 复用: `engine/scraper.py::scrape()`, `engine/annotate.py::annotate_one_stream()`, `engine/ingestor.py::ingest()`, `ui/shared.py::_save_annotation_output()`

## Commands

```
Run:    streamlit run app.py
Test:   python -m pytest tests/ -x -q
Lint:   (no linter configured)
```

## Project Structure

```
ui/
├── tab_entry.py          ← 主改动: 新增 _render_batch_review() ~150行
├── tab3_monitor.py       ← 小改: 新增"导入并自动研判"按钮 + 触发逻辑
├── shared.py             ← 可能提取公共渲染函数
app.py                    ← 无需改动(Tab路由不变)
engine/
├── scraper.py            ← 复用 scrape()
├── annotate.py           ← 复用 annotate_one_stream()
├── ingestor.py           ← 复用 ingest()
```

## Data Model

### session_state 新增键

```python
# 批量处理触发标志 (Monitor设置, Tab2检测)
batch_auto_process: bool = False

# 批量条目列表
batch_items: list[dict] = [
    {
        "url": str,              # 原文链接
        "title": str,            # 标题(抓取后填充)
        "platform": str,         # 来源平台
        "status": str,           # "pending" | "processing" | "success" | "failed"
        "scraped_data": dict | None,   # scrape()返回值
        "annotation": dict | None,     # annotate_one_stream()返回值
        "error": str | None,           # 失败原因
        "saved": bool,                 # 是否已确认保存
        "expanded": bool,              # expander是否展开
    },
    ...
]
```

### 状态机

```
pending → processing → success → saved=True (用户点击保存)
                     → failed   (抓取或研判失败, error字段填充)
```

## UI Layout (Tab2 批量审核模式)

```
┌─────────────────────────────────────────────┐
│ 📋 批量审核 (8/10 成功, 2 失败)            │
│                                             │
│ ┌─ B站 | P2 | 持续观察 | oppo野妈评测... ─┐│  ← st.expander(绿色边框)
│ │ [展开内部]                                ││
│ │  快速编辑: [严重度▼] [分流建议▼]         ││
│ │  摘要: [text_area]                       ││
│ │  [完整编辑 ▸]  ← inner expander          ││
│ │    社媒数据 / 原文 / 情感 / 分类 / 理由  ││
│ │  [💾 确认保存]  ← 逐条保存按钮           ││
│ └──────────────────────────────────────────┘│
│                                             │
│ ┌─ 失败 | DY | oppo 野妈搜索... ──────────┐│  ← st.expander(红色边框)
│ │ ❌ 抓取失败: Connection timeout          ││
│ │ [🔄 重试]                                ││
│ └──────────────────────────────────────────┘│
│                                             │
│ ─────────────────────────────────────────  │
│ [💾 全部保存到知识库 (5条未保存)]           │  ← 批量保存
│ [🗑️ 清空审核台]                            │
└─────────────────────────────────────────────┘
```

## Code Style

遵循项目现有风格:
- `st.expander` 做折叠卡片
- `st.columns` 做多列布局
- session_state key 用 `f"{TAB_KEY}..."` 前缀
- 无注释(除非逻辑非显而易见)

## Key Design Decisions (grill-me确认)

| # | 决策 | 选择 |
|---|------|------|
| 1 | 触发按钮位置 | Monitor Tab新按钮"导入并自动研判"→自动切Tab2 |
| 2 | 状态管理 | `batch_items` 单一列表, status字段区分 |
| 3 | 处理方式 | 同步全处理, spinner+进度文字 |
| 4 | 卡片组件 | `st.expander`, 标题栏severity颜色 |
| 5 | 编辑范围 | 快速编辑(严重度/分流建议/摘要) + inner expander完整编辑 |
| 6 | 保存方式 | 逐条+批量，`saved`标志防重复 |

## Testing Strategy

- 现有 173 测试必须全部通过
- 新增测试文件 `tests/test_batch_review.py`:
  - `test_batch_items_state_machine` — 状态转换 pending→success/failed
  - `test_batch_save_dedup` — saved标志防重复入库
  - `test_batch_failed_skip` — 失败条目不阻塞成功条目
  - `test_batch_empty_queue` — 空队列不触发批量模式
- 手动验证: Monitor搜索关键词→勾选3条→点击"导入并自动研判"→确认Tab2卡片展示→修改1条→确认逐条保存→全部保存→检查知识库

## Boundaries

- Always:
  - 现有单条录入流程不受影响 (entry_queue + queue模式照旧)
  - 复用 scrape/annotate/ingest 管道, 不改函数签名
  - 改代码后跑 `python -m pytest tests/ -x -q`
- Ask first:
  - 如涉及 shared.py 公共函数签名变更
  - 如需修改 app.py 的 Tab 路由
- Never:
  - 不修改 engine/ 下的核心管道逻辑
  - 不破坏现有 session_state 键名

## Success Criteria

1. Monitor勾选N条URL → 点"导入并自动研判" → Tab2自动切换 → spinner+进度 → 折叠卡片全部展示
2. 成功条目: expander标题显示平台/严重度/分流建议/标题, 颜色按severity区分
3. 展开成功条目: 可修改严重度/分流建议/摘要, inner expander显示完整编辑表单
4. 失败条目: 红色标记, 显示具体错误原因
5. 逐条保存: 点"确认保存" → 入库 → 标记saved=True
6. 全部保存: 点底部按钮 → 仅保存未saved的条目 → 批量入库
7. 现有173测试全部通过, 新增≥4个测试

## Open Questions

- 批量处理时如果用户刷新页面(F5), 状态丢失是否可接受? (当前: 接受, 不持久化)
