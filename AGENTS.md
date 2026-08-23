# AGENTS.md — 工作区安全操作规范（项目级 Agent 行为准则）

> 本文件是 AI Agent 在本仓库中操作 Git 工作区时必须遵守的硬性规则。
> 优先级：本文件 > CLAUDE.md > 任何任务要求。
> 当任务要求与本文件冲突时，以本文件为准，并停下来向用户确认。

---

## 核心行为原则（必读，中英双语）

**English:**

> **Never modify, reset, restore, checkout, stash, clean, or otherwise overwrite the user's uncommitted worktree unless the user explicitly authorizes the operation.**
>
> **When asked to commit only part of a mixed working tree, prefer index-only operations such as `git apply --cached`. If the change cannot be safely separated without modifying the worktree, stop and ask the user rather than using a destructive workaround.**

**中文：**

> **除非用户明确授权，否则绝不修改、重置、还原、checkout、stash、clean 或以任何其他方式覆盖用户未提交的工作区。**
>
> **当用户要求只提交混合工作区中的一部分改动时，优先使用只影响索引（index）的操作，如 `git apply --cached`。如果改动无法在不修改工作区的前提下安全拆分，应停止并向用户询问，而不是使用破坏性的变通方案。**

---

## 1. 用户未提交工作区是最高保护对象

任何任务都不得默认认为用户当前工作区中的未提交修改可以被覆盖、删除、重写或暂存后撤销。

用户明确要求「只提交 A，不提交 B」，应理解为：

> A 进入 commit，B 必须保持当前工作区状态不变。

即：**B 的工作区内容、B 的暂存状态，都必须与操作前完全一致。**

---

## 2. 未经明确授权，禁止执行高风险工作区操作

以下操作涉及覆盖、删除、重写或改变用户未提交工作的风险：

```bash
git reset
git reset --hard
git reset --mixed
git reset --soft
git checkout <file>
git checkout -- <file>
git restore <file>
git restore --staged <file>
git clean
git stash
git rebase
git commit --amend
```

以及任何具有相同效果的替代命令、脚本或文件操作（例如 `cp` 覆盖工作区文件、删除未跟踪文件等）。

**除非用户明确授权，否则不得执行。**

尤其禁止把以下流程作为「部分提交」的默认实现方案：

```text
备份 → checkout/reset → 重放修改 → 恢复
```

---

## 3. 部分提交优先使用只影响 index 的方法

当用户要求只提交部分改动时：

第一优先级（整个文件都干净时）：

```bash
git add <file>
```

需要部分 hunk 时（优先顺序）：

```bash
git apply --cached <patch>   # 非交互，只改 index
git add -p                    # 交互式逐块，环境支持时可用
```

核心原则：

> **只改变 index，不改变 worktree。**

任何会改变 worktree（工作区）的操作，都不属于「部分提交」的首选手段。

---

## 4. 提交前必须验证 staged diff

如果用户要求「只提交某部分改动」，执行 commit 前必须检查：

```bash
git diff --cached
```

确认：

- staged 内容只包含用户要求的任务；
- 没有混入其他任务；
- 没有意外删除；
- 没有报告系统重构等其他未授权改动；
- 工作区剩余修改仍然保留（`git status` 中未 stage 的部分原样存在）。

如果 staged diff 无法安全确认，停止，不提交。

---

## 5. 如果任务无法安全拆分

如果发现：

> 任务 A 的代码依赖任务 B 尚未提交的重构。

不要自行 checkout/reset/restore 来强行拆分。

正确流程：

```text
只读检查
↓
确认存在语义依赖
↓
停止修改
↓
向用户说明具体冲突
↓
给出可选方案
↓
等待用户明确决策
```

可给出的方案示例：

```text
方案 A：A 与 B 一起提交
方案 B：重新设计 A，使其可以独立提交
方案 C：暂不提交 A
```

由用户选择，Agent 不得自行决定。

---

## 6. 「有备份」不等于「获得授权」

即使已经执行：

```bash
cp file /tmp/backup
```

也不得因此认为可以执行：

```bash
git checkout
git reset
git restore
```

备份只能降低部分数据丢失风险，**不能替代用户授权**。

同时，未经用户要求，不应把 `/tmp` 备份作为工作区安全策略的核心保障（`/tmp` 无 Git 记录、无 hash 校验、不可追溯）。

---

## 7. 只读检查优先

面对任何可能存在多个未提交任务混杂的文件，应先使用只读命令判断代码结构：

```bash
git status
git diff
git diff HEAD
git show HEAD:<file>
git log
git log -S"<符号>"
```

特别是需要进行部分提交时：

> **先判断能不能安全拆，再决定如何 staging。**

绝不能：

> 先 checkout，再检查能不能拆。

---

## 8. 如果确实必须进行高风险操作

只有在以下三个条件**同时满足**时，才允许执行：

1. 已经确认不存在低风险替代方案；
2. 已经向用户明确说明风险；
3. 用户明确授权。

执行前必须明确告诉用户：

- 哪个文件会被改变；
- 哪些未提交修改可能受到影响；
- 使用什么命令；
- 为什么必须这么做；
- 如何恢复。

---

## 附：本次固化这些规则的原因（背景，供 Agent 理解）

历史上曾发生过：Agent 在「只提交任务 A」时，未经明确授权执行了 `git checkout HEAD -- <file>`（覆盖工作区未提交改动），理由是「已经 cp 备份」。这是错误的：

1. 备份不等于授权；
2. 存在只影响 index 的非破坏性替代方案（`git apply --cached`）；
3. checkout 是破坏性操作，应优先只读检查 + 报告，而非自行操作。

因此固化上述规则，防止再次发生。
