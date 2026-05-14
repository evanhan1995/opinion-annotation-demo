---
title: 操作日志
type: log
created: 2026-05-11
updated: 2026-05-15
---

## 2026-05-15 最终轮次开发日志

### 版本: v1.3.0

#### Phase 16a: 手工录入改造
- Tab1 从"手动输入+Demo"拆分为纯手工录入
- 删除 AI 标注按钮，改为全人工填写
- 必填 URL 字段（知识库溯源）
- txt 上传→AI 总结→填入简介
- 删除原文内容/评论区/发布者类型/互动数据（与社媒数据去重）
- "📋 下一个案例"一键清空表单
- 简介替代原文内容作为主字段

#### Phase 16b: 操作演示
- 新增 Tab5「🎬 操作演示」
- 4 步离线模拟：输入URL→抓取→标注→查看结果
- 预置 YouTube Demo 数据（China Observer / Temu 调查）
- 全程 0 API 调用，0 知识库写入
- 含纠偏表单模拟和重新演示按钮

#### Phase 14: 稳定性增强
- annotate.py 所有 OpenAI 调用加 timeout=90s
- txt 上传 API 调用加 timeout=30s
- Tab 隔离: `_result_source` 非破坏性过滤
- 输入校验: 内容长度提示、URL 格式检查
- 幽灵代码清理: 删除 `_pending_annotate_manual`、`manual_annotate_btn` handler、`DEMO_DATA`/`load_demo`

#### Phase 12: UI 细化
- 侧边栏重组: Dashboard 常驻、系统状态紧凑化、巡检+XHS 合并
- 5 Tab 架构: 📝手工录入 / 🔗URL抓取 / 📚知识库 / 💬扫地僧 / 🎬操作演示
- 入门指南更新为 5 Tab 版本
- 删除重复 Dashboard 块、重复近似舆情、过时 Demo 引用

#### Bug 修复 (本轮)
- 语法错误: Dashboard 双重 try 块→`SyntaxError: expected 'except'`
- Tab 跳转: demo `st.rerun()` 改为 `_needs_rerun` gate
- 演示无结果: Tab1 入口破坏性清理→改为 `_render_annotation_result` 来源过滤
- Cloud 部署失败: requirements.txt 缺 yt-dlp/httpx/xhshow
- SSH 推送: HTTPS 被网络拦截→生成 ed25519 密钥切 SSH
- f-string 转义: `\"` → 变量替代
- 入门指南残留旧文字

### 最终指标
- 代码: 5,283 行 (app.py 1,376 + engine 3,517 + tests 390)
- 测试: 21/21 全通过
- 资产: 27 案例 + 5 作者 + 5 概念 + 1 规范 + 16 outputs
- 部署: GitHub master + Streamlit Cloud 自动同步
- Prompt: 42K→10K tokens (-77%)
- YouTube 抓取: 171s→10s (评论限制+字幕按需)

---

## 2026-05-14 全 session 开发日志

### 版本演进: v0.5 → v1.2.0

#### 性能优化 (10a-opt)
- yt-dlp `max_comments=["50"]`: 7,626评论视频 171s→3s
- Playwright `wait_for_selector` 替代 `wait_for_timeout(2-3s)`
- Deferred annotation 模式: 按钮清空→下次运行执行→`_needs_rerun` gate
- 系统 prompt 缓存 + 后续改为相关性案例筛选 (42K→10K tokens, -77%)
- `do_scrape` 等函数移至 `st.tabs()` 前定义, 修复 NameError

#### 10b: 扫地僧跨平台查询
- AGENT_SYSTEM_PROMPT 新增跨平台引导 + `build_agent_context` synthesis 展开

#### 10c: 边界 Draft PR 建议
- `_generate_boundary_suggestion()` 三触发 (p1_uncovered/unusual_combo/new_platform)
- UI diff 格式呈现

#### 10d: index 表格结构化
- `_parse_row_to_dict()`/`_dict_to_row()` overview row dict 构建
- dimension 保留 `_upsert_dimension_row`

#### 11a: 批量导入
- checkbox + text_area + 进度条 + 摘要表, deferred pattern 复用

#### 11b: 标注历史回溯
- `find_annotation_history` + `diff_annotations` + 时间线 expander

#### 11c: 巡检监控
- `monitored_urls.json` + 侧边栏巡检按钮 + P0/P1 计数

#### 11d: P0/P1 醒目告警
- 标注结果页 error(红)/warning(黄) 横幅

#### 15a: 舆情分类系统 (6 类多选)
- CATEGORY_OPTIONS 常量 + prompt 两步指令 (前置+末尾双冗余)
- UI 彩色标签 + 纠偏 multiselect + frontmatter `categories:` + 按分类索引
- prompt 指令从末尾移至首步修复 LLM 空输出 `[]`

#### 15b: 社媒数据拆分
- scraper 4 平台输出 `社媒数据` 字典 (作者/国家/点赞/评论/粉丝/播放量/时长/作者主页)
- XHS `ip_location`→国家, `likes×80`→估算播放量
- YouTube 新增时长 (duration) + 描述 1000→2000 字符

#### 15c: 作者库
- `wiki/authors/` 新目录 + `_upsert_author()` 自动生成+跨平台合并
- case↔author 双向链接 (frontmatter `author:`)
- Agent 搜索 + Tab3 导航覆盖 authors/

#### YouTube AI 分析 + URL 校验
- `fetch_youtube_subtitles()` 按需字幕提取 (不默认下载, 加速40%)
- "🎬 AI 视频内容分析" 按钮 + "📥 下载字幕 TXT"
- `find_similar_cases()` 按 tag 命中数匹配 top 3 近似舆情
- Tab2 URL 校验: 非 YouTube/小红书 → 警告 + 按钮禁用
- 社媒卡增平台/发布时间/时长展示

#### Bug 修复
- `load_config()` 遗漏 `kb_password` 字段 → 知识库密码保护失效
- f-string `\"` 转义 → SyntaxError
- `st.rerun()` 在 button handler 内 → 双层重跑竞态 (回退+gate 模式)
- wikilink `\|` 转义警告

### 关键指标
- 代码: 5,232 行 (10 引擎 + 1 UI + 1 测试)
- 测试: 21/21 全通过
- 资产: 27 案例 + 5 概念 + 5 作者 + 16 outputs
- Prompt: 42K→10K tokens (-77%)
- 标注速度: ~23s→~10s (YouTube, 因字幕按需)
tags: [log, audit]
---

# 操作日志

> 本文件记录知识库的所有变更操作，采用 append-only 模式。
> 每次 ingest、query（如有写入）、lint 均需记录。

---

## 2026-05-11

### 🏗️ 知识库初始化

| 项目 | 内容 |
|------|------|
| **操作类型** | `init` |
| **操作者** | AI Agent (Claude) |
| **变更摘要** | 基于 Evan 在 TEMU 和 DJI 的双重舆情工作经验，采用 Karpathy LLM Wiki 方法论初始化舆情标注知识库 |

**创建的页面（共 16 篇）：**

| 类别 | 页面 | 说明 |
|------|------|------|
| 📄 Source | [[sources/evan-temu-opinion-summary]] | TEMU 舆情体系工作总结 |
| 📄 Source | [[sources/evan-dji-opinion-summary]] | DJI 舆情系统工作总结 |
| 🔬 Concept | [[concepts/severity-rating-matrix]] | 严重度评级矩阵 P0-P3 |
| 🔬 Concept | [[concepts/sentiment-analysis-dimensions]] | 多维度情感分析 |
| 🔬 Concept | [[concepts/public-opinion-triaging]] | 舆情分流判断 |
| 🔬 Concept | [[concepts/content-authenticity-assessment]] | 内容真实性评估 |
| 🔬 Concept | [[concepts/platform-adaptation]] | 平台特性适配 |
| 🏢 Entity | [[entities/meltwater]] | Meltwater 舆情监测工具 |
| 🏢 Entity | [[entities/sina-yuqingtong]] | 新浪舆情通 |
| 🔗 Synthesis | [[syntheses/opinion-annotation-spec]] | **标注规范活文档**（核心中枢） |
| 📋 Case | [[cases/index]] | 案例库索引 |
| 📋 Case | [[cases/case-001]] | P0 安全事故 + KOL + 高速传播 |
| 📋 Case | [[cases/case-002]] | P2 质量讨论 + 中等互动 |
| 📋 Case | [[cases/case-003]] | P3 物流吐槽 + 零传播 |
| 📋 Case | [[cases/case-004]] | 正面 KOL + 非赞助声明 |
| 📋 Case | [[cases/case-005]] | 竞品对比公正评测 + 大V |
| 📋 Case | [[cases/case-006]] | 疑似水军 + 虚假信号 |

**架构设计**：
- **案例库是迭代引擎**：每新增案例 → AI 检查规则边界 → 自动更新标注规范
- **活文档机制**：`[[syntheses/opinion-annotation-spec|标注规范]]` 随案例增长自动进化
- **案例覆盖度**：P0/P2/P3 已覆盖，P1 是最优先补充盲区

**创建目录结构**：`raw/`, `wiki/concepts/`, `wiki/entities/`, `wiki/sources/`, `wiki/syntheses/`, `wiki/cases/`, `outputs/`

---

*—— 后续所有操作记录将追加在此日志下方 ——*

### 2026-05-12 00:04 | 纠偏 | 生成 [[cases/case-007]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：significant
- **来源链接**：https://www.xiaohongshu.com/explore/69ef60d9000000001f00218a?xsec_token=ABzXNXkFByKYtnEdOQhDjTn9-s2sPbkvvPY9CZpCRHdVk=&xsec_source=pc_search&source=web_explore_feed
- **说明**：用户修正了 AI 标注结果，差异等级为 significant。新案例已写入 cases/。

### 2026-05-12 09:54 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.xiaohongshu.com/explore/69fe9f50000000003601c0aa?xsec_token=ABODr5NFOXzdtxjtXYX29o_9cfJfsUzyK2zzXFOgNr6Zs=&xsec_source=pc_search&source=web_search_result_notes
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-12 13:34 | 自动Ingest | 生成 [[cases/case-008]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：KOL负面
- **来源链接**：https://www.youtube.com/shorts/-VGsjKF27Fg
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-12 13:39 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.youtube.com/shorts/-VGsjKF27Fg
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-12 16:37 | 自动Ingest | 生成 [[cases/case-009]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：合规, KOL负面
- **来源链接**：https://www.youtube.com/shorts/c5erGGVmYxc
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-12 16:42 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.youtube.com/shorts/c5erGGVmYxc
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-13 10:43 | 自动Ingest | 生成 [[cases/case-011]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：质量, 客服
- **来源链接**：https://www.xiaohongshu.com/explore/6a0316b800000000070214e8?xsec_token=AB0aAQ16zym3D6C5W1Wf-ddw_4BIAfY34AUqkjr6A17xY=&xsec_source=pc_search&source=web_search_result_notes
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-13 11:03 | 自动Ingest | 生成 [[cases/case-012]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P1
- **分流建议**：立即处理
- **风险标签**：安全, 质量, 客服
- **来源链接**：https://www.xiaohongshu.com/explore/69ff2eea000000001f005fcc?xsec_token=ABsvTnU-6z5kvDrh9pcqF2ZMJS8-BlzDubVIaW2lVKVnE=&xsec_source=pc_search&source=web_search_result_notes
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-13 11:20 | 自动Ingest | 生成 [[cases/case-013]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：质量, KOL负面
- **来源链接**：https://www.youtube.com/watch?v=tPoD1BA41ik
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-13 11:42 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.youtube.com/watch?v=tPoD1BA41ik
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-14 08:31 | 自动Ingest | 生成 [[cases/case-014]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：质量, KOL负面
- **来源链接**：https://www.youtube.com/watch?v=y97kg30Qpww
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 08:33 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.youtube.com/watch?v=y97kg30Qpww
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-14 08:54 | 自动Ingest | 生成 [[cases/case-015]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P1
- **分流建议**：立即处理
- **风险标签**：安全, 合规, KOL负面
- **来源链接**：https://www.youtube.com/shorts/pWBPRh0lDmM
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 09:05 | 自动Ingest | 生成 [[cases/case-016]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P1
- **分流建议**：立即处理
- **风险标签**：KOL负面, 大规模传播
- **来源链接**：https://www.youtube.com/watch?v=36bb2b24Qto
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 09:06 | 自动Ingest | 生成 [[cases/case-017]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：合规, KOL负面
- **来源链接**：https://www.youtube.com/watch?v=-GoAFaMHYY8
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 09:12 | 自动Ingest | 生成 [[cases/case-018]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：客服
- **来源链接**：https://www.youtube.com/watch?v=1wrAT8jCmMs&t=43s
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 09:44 | 自动Ingest | 生成 [[cases/case-019]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：KOL负面
- **来源链接**：https://www.youtube.com/shorts/5qO_HjPxKOI
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 15:51 | 自动Ingest | 生成 [[cases/case-020]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P0
- **分流建议**：立即处理
- **风险标签**：合规, 安全, 大规模传播
- **来源链接**：https://www.youtube.com/watch?v=EalvgelUGf0
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 15:54 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.youtube.com/watch?v=EalvgelUGf0
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-14 15:55 | 自动Ingest | 生成 [[cases/case-021]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P1
- **分流建议**：立即处理
- **风险标签**：质量, 客服, 物流
- **来源链接**：https://www.youtube.com/watch?v=7kIJxo7XBLY
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 15:57 | 纠偏 | 生成 [[cases/case-022]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：significant
- **来源链接**：https://www.youtube.com/watch?v=7kIJxo7XBLY
- **说明**：用户修正了 AI 标注结果，差异等级为 significant。新案例已写入 cases/。

### 2026-05-14 19:13 | 自动Ingest | 生成 [[cases/case-023]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：质量, 客服
- **来源链接**：https://www.xiaohongshu.com/explore/6994a42e000000001a02c333?xsec_token=ABfjKyA2SDnOfAsI4E2dzFW1KPTe-Iz0tRtZab0NSsAPM=&xsec_source=pc_search&source=web_explore_feed
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 19:22 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.xiaohongshu.com/explore/6994a42e000000001a02c333?xsec_token=ABfjKyA2SDnOfAsI4E2dzFW1KPTe-Iz0tRtZab0NSsAPM=&xsec_source=pc_search&source=web_explore_feed
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-14 19:22 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.xiaohongshu.com/explore/6994a42e000000001a02c333?xsec_token=ABfjKyA2SDnOfAsI4E2dzFW1KPTe-Iz0tRtZab0NSsAPM=&xsec_source=pc_search&source=web_explore_feed
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-14 20:09 | 自动Ingest | 生成 [[cases/case-024]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P1
- **分流建议**：立即处理
- **风险标签**：质量, 合规, KOL负面
- **来源链接**：https://www.youtube.com/watch?v=DIBL7PKlzaU
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 21:00 | 纠偏 | 生成 [[cases/case-025]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：significant
- **来源链接**：https://www.youtube.com/watch?v=DIBL7PKlzaU
- **说明**：用户修正了 AI 标注结果，差异等级为 significant。新案例已写入 cases/。

### 2026-05-14 21:46 | 自动Ingest | 生成 [[cases/case-026]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P1
- **分流建议**：立即处理
- **风险标签**：质量, 竞品攻击, KOL负面
- **来源链接**：https://www.youtube.com/watch?v=vFII7t9FtO8
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。

### 2026-05-14 21:48 | 纠偏 | 生成 [[cases/(无新案例)]]

- **操作类型**：人工纠偏 → 生成校准案例
- **差异等级**：minor
- **来源链接**：https://www.youtube.com/watch?v=vFII7t9FtO8
- **说明**：用户修正了 AI 标注结果，差异等级为 minor。新案例已写入 cases/。

### 2026-05-14 21:54 | 自动Ingest | 生成 [[cases/case-027]]

- **操作类型**：自动 Ingest（标注完成自动生成）
- **严重度**：P2
- **分流建议**：持续观察
- **风险标签**：客服, 质量
- **来源链接**：https://www.xiaohongshu.com/explore/69fd59740000000010001c00?xsec_token=AByfWcg1eWWdWot40FUHsWNZMf4rAdp4xmQ4fDyhue8Ws=&xsec_source=pc_search&source=web_user_page
- **说明**：AI 完成标注后自动生成案例页面，已更新案例索引和操作日志。
