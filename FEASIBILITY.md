# 可行性评估报告

> 评估日期：2026-05-23 | 评估人视角：老练软件开发工程师 | 基准：本项目 + Daily World 已验证经验

---

## 一、总评

**整体可行。** 7个模块中，4个是已有代码的迁移/封装，2个是已有模式的复用，仅Monitor的搜索接口存在真实技术不确定性。项目不会出现"做不出来"的情况，但XHS/抖音搜索是唯一需要Spike验证后才能确定方案细节的环节。

难度评级（5分制）：

| 模块 | 难度 | 说明 |
|------|------|------|
| Scraper Agent | ⭐ | 已有代码，改个门面 |
| Analyst Agent | ⭐ | 已有代码 + 加一个相关性判断字段 |
| Handler Agent | ⭐⭐ | 纯逻辑状态机，无外部依赖 |
| Curator Agent | ⭐⭐ | 文件操作+迁移脚本，体力活 |
| Daily Report Agent | ⭐⭐ | Daily World build_briefing 模式复用 |
| Orchestrator | ⭐⭐ | Daily World orchestrator 模式复用 |
| Monitor Agent | ⭐⭐⭐ | **搜索接口未知，反爬风险，SEO快照有难度** |
| Scheduler | ⭐ | Daily World scheduler.py 直接复用 |

---

## 二、逐模块可行性分析

### 2.1 Scraper Agent — 难度⭐，风险极低

**已有资产**：
- `engine/scraper.py` (505行)：5平台调度器，YT/Reddit/X已调通
- `engine/xhs_fetcher.py` (590行)：XHS-Downloader双通道（元数据cookie-free + 评论xhshow），Cookie三级兜底
- `engine/tt_fetcher.py` (313行)：TikTokDownloader Detail + Comment接口
- 测试：`test_xhs_adapter.py` (9项) + `test_tt_adapter.py` (7项)，全部通过

**需要做的**：
- 三个模块拼成一个Agent门面，统一输出 `RawData` dataclass
- 删掉Reddit/X的调度分支（或标记 `deprecated`）
- 新增人工喂料降级（UI端工作，Scraper本身不复杂）

**结论**：搬砖活。现有代码已经生产级（Cookie兜底、双通道隔离、标准输出格式），迁移出bug的概率极低。

---

### 2.2 Analyst Agent — 难度⭐，风险极低

**已有资产**：
- `engine/annotate.py` (844行)：完整的标注引擎，含动态prompt构建、多Provider、流式输出、案例选择、标注历史diff
- 67%纠偏率（13个校准案例驱动的反馈回路）
- 6类舆情分类（双信道prompt指令模式）
- 评论区红绿灯分析

**需要做的**：
- 迁移现有逻辑 + 新增一个字段：`relevance: "relevant" | "irrelevant_{keyword}_{platform}"` + `relevance_reason`
- 在System Prompt中加入相关性判定指令（约+5行prompt）
- 无关标记通过Orchestrator回传Monitor

**结论**：加一个字段的事。现有标注prompt已经很长很成熟，相关性判定本质是"在这条System Prompt里多问一个问题"，LLM完全能处理。

---

### 2.3 Handler Agent — 难度⭐⭐，风险低

**已有资产**：
- 零。这是全新模块。

**需要做的**：
- 5状态机（待跟进→处理中→已处理/已放弃/忽略），纯Python dict/list操作
- 处置方案生成：一次LLM调用，输入标注结果，输出步骤清单
- 状态变更→调用Curator.update_case_status()

**状态机实现**（~50行核心逻辑）：
```python
VALID_TRANSITIONS = {
    "待跟进": ["处理中", "已放弃", "忽略"],
    "处理中": ["已处理", "已放弃"],
    "已处理": [],   # 终态
    "已放弃": [],
    "忽略": [],
}
```
没有并发、没有分布式、没有事务——单用户Streamlit App，状态机实现是本科大作业难度。

**结论**：纯逻辑，没有技术风险。唯一需要注意的是 `update_case_status()` 写入KB时要原子化（临时文件→验证→rename）。

---

### 2.4 Curator Agent — 难度⭐⭐，风险中低

**已有资产**：
- `engine/ingestor.py` (520行)：去重、案例生成、作者库、三维索引、全局日志
- `engine/index_mgr.py` (265行)：共享索引管理
- `engine/linker.py` (312行)：跨平台关联检测
- `engine/agent.py` (331行)：扫地僧问答
- `engine/correction_handler.py` (266行)：人工纠偏
- 测试：`test_core.py` (21项)，索引/去重/纠偏全面覆盖

**需要做的**：
- 从扁平wiki迁移到四体系（foundation/cases/reports/authors）
- Case页面加四标签（平台/严重度/处置状态/收录日期）
- `update_case_status()`：接收Handler的状态变更→更新frontmatter+索引+日志
- 迁移现有34个case到新格式

**风险点**：
- **数据迁移**：34个case的frontmatter需要批量更新（加`status: 待跟进`默认值）。写迁移脚本 + 跑测试验证，不是大问题。
- **索引格式变更**：从三维（严重度/分流/平台）变为三维（平台×严重度×状态），`index_mgr.py`的表格生成逻辑需要改。但测试覆盖好（8个索引测试），改完跑测试即可。

**结论**：体力活，不是技术难题。风险在数据迁移，不在逻辑。

---

### 2.5 Daily Report Agent — 难度⭐⭐，风险低

**已有资产**：
- Daily World的 `build_briefing()` + `orchestrator.py` 模式
- Daily World的 `writer.py` 文案生成模式

**需要做的**：
- 从Curator查询当日/当月数据（结构化数据，不是原始文本）
- LLM生成摘要（声量趋势/情感分布/议题TOP5/风险汇总）
- 输出Markdown文件

**为什么简单**：日报的输入是Curator已经处理好的**结构化数据**（今天几个P0、几个P1、情感分布），不是原始网页文本。LLM做数据→文本的生成是它最擅长的，prompt写好格式约束即可。

**结论**：Daily World的 `build_briefing()` 做的是完全一样的事（结构化数据→Markdown简报），直接复用模式。

---

### 2.6 Orchestrator — 难度⭐⭐，风险低

**已有资产**：
- Daily World `agents/orchestrator.py`：成熟的流水线编排模式（阶段1写作→阶段2校对→阶段3重写循环）
- 流A（被动分析）本质是线性的：Scraper→Analyst→Handler→Curator
- 流C（日报生成）本质是：Curator.query→DailyReport.generate→输出

**需要做的**：
- 实现4条流（被动分析/主动监测/日报生成/KB问答）
- P0/P1熔断分支（if severity in [P0,P1] → emergency_dispatch）
- Agent间数据裁剪+传递

**最复杂的流是流B（主动监测）**，但本质是：
```
for each keyword × platform:
    Monitor.search() → MonitorHarvest
    for each url in harvest.new_items:
        Scraper.fetch() → Analyst.annotate() → [P0/P1熔断?] → Handler.triage() → Curator.ingest()
```
一个嵌套for循环，每次迭代是流A的简化版。

**结论**：Daily World的orchestrator已经验证了这种模式的可行性。本次只是参数不同、Agent数量不同，结构完全一致。

---

### 2.7 Monitor Agent — 难度⭐⭐⭐，风险中高

**这是整个项目唯一有真实技术风险的模块。**

#### 2.7.1 搜索接口——需要Spike验证

| 平台 | 搜索方案 | 验证状态 | 风险评估 |
|------|---------|---------|---------|
| YouTube | `yt-dlp "ytsearch30:关键词"` | ✅ 已验证 | yt-dlp搜索语法成熟，返回格式与普通视频一致 |
| 小红书 | XHS-Downloader搜索 | ❌ 未验证 | **只验证过笔记详情接口，不确定是否有搜索能力** |
| 抖音 | TikTokDownloader搜索 | ❌ 未验证 | **只验证过Detail+Comment接口，搜索接口格式未知** |

**最坏情况**：
- 小红书搜索不可用 → 降级为Playwright模拟搜索（打开探索页→输入关键词→滚动采集）。慢（每条>10s），但能做。
- 抖音搜索不可用 → 同样降级Playwright。抖音网页版反爬更严，可能需要mitmproxy。

**Spike必须在Phase 1启动前完成**，因为如果搜索方案不可行，Monitor的设计需要大改。

#### 2.7.2 反爬与Cookie生命周期

小红书和抖音是国内反爬最严的平台，这个问题不能回避：

- **XHS-Downloader**：使用curl_cffi做TLS指纹伪装，目前元数据接口cookie-free可用。但搜索接口如果存在，大概率需要Cookie。
- **TikTokDownloader**：Cookie存于settings.json，有过期时间。频繁搜索会加速封禁。
- **YouTube**：yt-dlp对搜索请求频率有内置限流，一般不会ban IP。

**缓解措施**（已在PRD中设计）：
- 人工喂料降级（3次失败→手动输入）
- 搜索频率控制（默认每6小时一次，不是每分钟）
- Cookie三级兜底（缓存→浏览器→手动扫码）

#### 2.7.3 SEO品牌词快照（M-10）

百度搜索爬取存在反爬风险（百度有验证码机制）。建议Phase 3a先做Google（无验证码），百度视情况用Playwright+手动打码或购买API。

---

### 2.8 Scheduler — 难度⭐，风险极低

Daily World的 `scheduler.py` 直接复用：
- 使用Python `schedule` 库
- 日报：每日21:00
- 月报：每月1日09:00
- 监测：每6小时
- Windows计划任务作为兜底

**结论**：照抄Daily World，0风险。

---

## 三、跨模块风险

### 3.1 反爬导致全链路瘫痪

**风险**：XHS/抖音Cookie被封 → Scraper失败 → Analyst/Handler/Curator无数据可处理

**缓解**：
- 人工喂料通道（PRD S-06）——即使所有平台都爬不了，分析师手动输入，系统照样运转
- 搜索频率保守（6小时间隔，不是实时）
- 这不是工程问题，是运维问题

### 3.2 知识库迁移数据丢失

**风险**：34个现有case迁移到四体系时frontmatter格式损坏

**缓解**：
- 迁移前备份整个wiki/目录（git commit）
- 迁移脚本 + 验证脚本（读回所有case frontmatter → 断言字段完整）
- 现有test_core.py的8个索引测试作为回归验证

### 3.3 LLM API成本

**估算**（以DeepSeek价格计）：
- 单次标注：~10K prompt tokens + ~500 output tokens ≈ ¥0.02
- 单次日报生成：~5K prompt + ~1K output ≈ ¥0.01
- 每日运营成本（假设20条新内容 + 1份日报）≈ ¥0.5
- 关键词搜索走的是平台搜索/爬虫，不走LLM

**结论**：成本不是问题。

---

## 四、难度热力图

```
模块          难度  风险  已有基础
───────────────────────────────────
Scraper        ⭐    极低  ██████████ 已有完整代码
Analyst        ⭐    极低  ██████████ 已有完整代码
Handler        ⭐⭐   低    ██░░░░░░░░ 全新但纯逻辑
Curator        ⭐⭐   中低  ████████░░ 已有代码+需迁移
Daily Report   ⭐⭐   低    ██████░░░░ Daily World模式复用
Orchestrator   ⭐⭐   低    ██████░░░░ Daily World模式复用
Monitor        ⭐⭐⭐  中高  ██░░░░░░░░ 搜索接口未知+反爬
Scheduler      ⭐    极低  ██████████ Daily World直接复用
───────────────────────────────────
整体           可行   可控  70%已有资产
```

---

## 五、推荐实施顺序

基于风险评估，建议调整Phase顺序：

```
Phase 0: Spike验证 (1天)
  └─ XHS/抖音/YT搜索接口3行spike → 确定Monitor技术方案

Phase 1: Agent骨架 (1天) ← 原Phase 1
  └─ 全部Agent模块+dataclass+测试

Phase 2: 迁移+重构 (2天) ← 原Phase 2
  └─ Scraper/Analyst/Curator迁移 + KB重构

Phase 3a: Monitor + 人工喂料 (2天) ← 最不确定，先做
  └─ 搜索→去重→Excel→人工喂料UI

Phase 3b: Handler + 状态同步 (1天)
  └─ 状态机→处置方案→Curator同步

Phase 3c: Daily Report (1天)
  └─ 日报+月报生成

Phase 4: Scheduler + 通知 (0.5天)

Phase 5: UI整合 (1天)
```

**总计：约9.5天**（如果Spike验证顺利，XHS/抖音搜索可用）

**如果Spike验证失败**（搜索接口不可用）：Monitor改Playwright方案，Phase 3a增加2天，总计约11.5天。

---

## 六、结论

**这个项目能做，而且大部分已经做完了。** 真正的增量工作在于：

1. Monitor的关键词搜索能力（需要Spike确认方案）
2. Handler的状态机（纯逻辑，不难）
3. Curator的KB重构（体力活）
4. 把所有东西用Orchestrator串起来（模式已验证）

不是从零开始，是在一个69测试全通过、架构干净的现有系统上，加3个新Agent、改3个旧模块。工程风险可控。
