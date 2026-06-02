# Spec: Monitor 日期区间搜索升级

## Objective

给 Monitor 模块新增**日期区间搜索模式**：指定 `date_from` / `date_to`，搜索该区间内全部内容（不限条数），作为现有按条数搜索模式的可选替代。

**目标用户**：舆情运营人员，在 Streamlit UI 手动触发巡逻时可选日期范围；定时巡逻自动按"上次巡逻时间 → 现在"搜索。

## Tech Stack

- Python 3.12（现有环境）
- bilibili-api-python（B站 API，已有 `time_start`/`time_end` 参数）
- yt-dlp（YouTube，已有 `dateafter`/`datebefore` 参数）
- TikTokDownloader + MediaCrawler（抖音，仅支持预设时间段）
- crawl4weibo（微博，仅客户端过滤）
- 无新依赖

## Commands

```bash
cd D:\Claude code\舆情标注Wiki
python -m pytest tests/ -x -q
python -m pytest tests/ -x -q -k "monitor"
python app.py
```

## Project Structure

```
D:\Claude code\舆情标注Wiki\
├── agents/
│   └── monitor.py             # MODIFIED: execute_job + 各搜索函数签名
├── scheduler.py               # MODIFIED: _wrapped_run_monitor 读/写 last_patrol.json
├── pipeline.py                # MODIFIED: 透传 date_from/date_to 到 execute_job
├── ui/
│   └── tab3_monitor.py        # MODIFIED: 日期区间选择器 + 模式切换
├── config/
│   ├── scheduler_config.json  # 不变
│   └── last_patrol.json       # NEW: 记录上次巡逻结束时间
├── agents/
│   └── orchestrator.py        # MODIFIED: run_active_monitor 透传 date 参数
└── tests/
    └── test_monitor.py        # MODIFIED: 新增日期模式测试
```

## Code Style

```python
# 新增常量和签名变更

# monitor.py 顶部新常量
_DATE_MODE_MAX_PAGES = 50    # date 模式下最大翻页数（~1000 条硬上限）
_DATE_MODE_FALLBACK_COUNT = 200  # 微博 date 模式下的抓取条数

# 搜索函数签名变更（仅 Bilibili/YouTube 实际使用）
def _search_bilibili(keyword: str, sort_type: str, count: int = 30,
                     date_from: str = "", date_to: str = "") -> list[SearchResult]:

def _search_youtube(keyword: str, sort_type: str, count: int = 30,
                    date_from: str = "", date_to: str = "") -> list[SearchResult]:

# 微博保持原签名，date 模式由 execute_job 层调大 count + 事后过滤
# 小红书/微信签名不变

# KeywordResult 新增字段
@dataclass
class KeywordResult:
    ...
    notes: list[str] = field(default_factory=list)  # NEW
```

命名约定：
- 新常量：`_DATE_MODE_*` 前缀（模块私有）
- 搜索函数参数：`date_from`/`date_to`（YYYY-MM-DD 字符串，空 = 不启用过滤）
- 笔记字段：`notes: list[str]`（人类可读中文信息）

## Data Flow

```
用户/调度器
    │
    ├─ 日期模式：execute_job(date_from="2026-05-31", date_to="2026-06-01")
    │     │
    │     ├─ 平台分发 ──────────────────────────────────────────
    │     │
    │     ├─ Bilibili: _search_bilibili(kw, "date", count=0, date_from, date_to)
    │     │     └─ search_by_type(time_start=date_from, time_end=date_to)
    │     │        翻页直到无结果 或 50 页上限
    │     │
    │     ├─ YouTube: _search_youtube(kw, "date", count=0, date_from, date_to)
    │     │     └─ ydl_opts["dateafter"] + ytsearch999:keyword
    │     │
    │     ├─ 抖音: _search_douyin(kw, "date", count=原count, date_from, date_to)
    │     │     └─ date_mode → PublishTimeType 最近似预设
    │     │        不支持精确日期 → notes 标注
    │     │
    │     ├─ 微博: _search_weibo(kw, "date", count=200)
    │     │     └─ date_mode → count 提到 200 → 客户端过滤 publish_time
    │     │        notes 标注"客户端过滤，可能不完整"
    │     │
    │     ├─ 小红书: SKIP → notes "平台不支持日期搜索，已跳过"
    │     └─ 微信:   SKIP → notes "平台不支持日期搜索，已跳过"
    │
    └─ 旧模式：execute_job()（行为不变）
```

## Platform Dispatch Table

| 平台 | date 模式策略 | count 参数 | API 日期过滤 | 备注 |
|------|-------------|-----------|-------------|------|
| Bilibili | API 过滤 + 翻页到底 | 忽略（翻页至空/50页） | `time_start`/`time_end` | |
| YouTube | API 过滤 | 忽略（传 999） | `dateafter`/`datebefore` | |
| 抖音 | 预设时间段近似 | 原 `result_count` | `PublishTimeType` | notes 标注不支持精确日期 |
| 微博 | 提量 + 客户端过滤 | 200 | 无 | notes 标注"客户端截断" |
| 小红书 | **跳过** | — | 无 | notes 标注原因 |
| 微信 | **跳过** | — | 无 | notes 标注原因 |

## KeywordResult.notes 示例

```python
# 正常（Bilibili/YouTube date 模式）
kr.notes = ["日期模式: 2026-05-31 ~ 2026-06-01, 获取 47 条"]

# 微博客户端过滤
kr.notes = ["日期模式: 客户端截断, 200 条过滤后剩余 23 条"]

# 抖音
kr.notes = ["日期模式: 仅支持预设区间(最近1周), 非精确日期"]

# 跳过
kr.notes = ["日期模式: 小红书平台不支持日期搜索，已跳过"]
```

## Scheduler 集成

### last_patrol.json

```json
{
  "last_patrol_end": "2026-06-01T12:07:00",
  "last_patrol_date": "2026-06-01"
}
```

### _wrapped_run_monitor 逻辑

```python
def _wrapped_run_monitor():
    last_path = PROJECT_ROOT / "config" / "last_patrol.json"
    date_from = ""
    date_to = datetime.now().strftime("%Y-%m-%d")
    if last_path.exists():
        data = json.loads(last_path.read_text(encoding="utf-8"))
        date_from = data.get("last_patrol_date", "")
    try:
        run_monitor(date_from=date_from, date_to=date_to)
        _scheduler_status["last_monitor"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # 写入本次巡逻结束时间
        last_path.parent.mkdir(parents=True, exist_ok=True)
        last_path.write_text(json.dumps({
            "last_patrol_end": datetime.now().isoformat(),
            "last_patrol_date": datetime.now().strftime("%Y-%m-%d"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        _scheduler_status["errors"].append(f"巡检失败: {e}")
```

## execute_job 签名变更

```python
def execute_job(progress_callback=None, sort_preference: str = "default",
                date_from: str = "", date_to: str = "") -> MonitorHarvest:
    """...
    Args:
        date_from: YYYY-MM-DD, 日期模式的开始日期。空字符串 = 按条数模式。
        date_to: YYYY-MM-DD, 日期模式的结束日期。空字符串 = 按条数模式。
        
    当 date_from 和 date_to 都不为空时，自动切换为日期模式。
    """
```

## Testing Strategy

**新增/修改测试用例：**

| # | 测试 | 覆盖 |
|---|------|------|
| 1 | `test_execute_job_date_mode` | execute_job(date_from, date_to) 返回有效 Harvest |
| 2 | `test_date_mode_skips_xhs_wechat` | 日期模式下小红书/微信被跳过，notes 有说明 |
| 3 | `test_date_mode_weibo_client_filter` | 微博 date 模式 count=200，结果按日期过滤 |
| 4 | `test_bilibili_date_params` | _search_bilibili 传递 date_from/date_to 到 API |
| 5 | `test_youtube_date_params` | _search_youtube 设置 ydl_opts dateafter/datebefore |
| 6 | `test_date_mode_empty_params_old_behavior` | date_from="" 时走旧逻辑 |
| 7 | `test_keyword_result_notes` | KeywordResult.notes 默认空列表 |
| 8 | `test_last_patrol_read_write` | last_patrol.json 读写正确 |

**现有测试不受影响：** execute_job 默认参数不变，旧模式行为完全保留。

## Boundaries

### Always do
- 运行 `python -m pytest tests/ -x -q` 确认通过
- 保持旧模式（date_from=""）行为 100% 不变
- 遵守 Agent 隔离规则（monitor.py 只读 Curator，不跨 Agent 通信）
- 保持 UTF-8 编码 + Windows 兼容

### Ask first
- 新增 Python 依赖（当前设计不引入）
- 修改 monitor_keywords.json 结构

### Never do
- 删除旧模式搜索逻辑
- 修改 ReportData 或 daily_report 相关代码
- 在 monitor.py 中 import 其他 agent 模块

## Success Criteria

1. `execute_job(date_from="2026-05-31", date_to="2026-06-01")` 对 Bilibili/YouTube 传递 API 日期参数
2. 日期模式下 Bilibili/YouTube 翻页至无结果或 50 页上限为止
3. 日期模式下小红书/微信自动跳过，KeywordResult.notes 记录原因
4. 日期模式下微博 count=200，客户端过滤 publish_time
5. `execute_job()` 无参数调用行为完全不变
6. Scheduler 自动写入/读取 `config/last_patrol.json`
7. Streamlit UI 新增日期区间选择器 + 模式切换
8. 所有新增测试通过，现有测试零回归
