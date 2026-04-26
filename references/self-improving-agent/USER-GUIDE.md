# Self-Improving Agent 用户指南

> 让你的 OpenClaw Agent 越用越聪明——通过自动记录、反思、进化，构建持续改进的 AI 工作伙伴。

## 一句话说清楚

你和 Agent 协作时产生的经验（踩坑、纠正、好方法），**不应该随会话结束而消失**。这个 Skill 帮 Agent 把经验记下来、整理好、用起来，让它下次不再犯同样的错。

---

## 目录

1. [安装](#安装)
2. [日常使用场景](#日常使用场景)
   - [场景 1：Agent 犯了错，你纠正它](#场景-1agent-犯了错你纠正它)
   - [场景 2：命令执行失败](#场景-2命令执行失败)
   - [场景 3：你想要一个 Agent 没有的能力](#场景-3你想要一个-agent-没有的能力)
   - [场景 4：发现更好的做事方法](#场景-4发现更好的做事方法)
   - [场景 5：读技术文章，提炼经验](#场景-5读技术文章提炼经验)
   - [场景 6：把方法论固化为可进化的 Gene](#场景-6把方法论固化为可进化的-gene)
   - [场景 7：每天早上看进化报告](#场景-7每天早上看进化报告)
   - [场景 8：重复踩坑，提取为独立 Skill](#场景-8重复踩坑提取为独立-skill)
   - [场景 9：Workspace 文件越来越臃肿](#场景-9workspace-文件越来越臃肿)
3. [知识流转全景图](#知识流转全景图)
4. [文件说明](#文件说明)
5. [常用命令速查](#常用命令速查)
6. [FAQ](#faq)

---

## 安装

**通过 ClawdHub：**
```bash
clawdhub install self-improving-agent
```

**手动安装：**
```bash
git clone https://git.woa.com/qijunwang/self-improving-agent.git /projects/.openclaw/skills/self-improving-agent
```

**安装后初始化：**
```bash
# 创建学习记录目录
mkdir -p ~/.openclaw/workspace/.learnings

# 验证安装（预览模式，不写文件）
python3 /projects/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py --dry-run

# 注册每日自动分析（每天 08:30 运行）
bash /projects/.openclaw/skills/self-improving-agent/scripts/setup_cron.sh
```

安装完成后，OpenClaw 会在每次会话启动时自动加载此 Skill，无需手动引用。

---

## 日常使用场景

### 场景 1：Agent 犯了错，你纠正它

**情况**：你让 Agent 用 `npm install` 安装依赖，但项目实际用的是 pnpm。你告诉它"不对，要用 pnpm install"。

**Agent 会做什么**：
1. 自动记录一条学习到 `~/.openclaw/workspace/.learnings/LEARNINGS.md`：

```markdown
## [LRN-20260304-001] correction

**Logged**: 2026-03-04T10:30:00+08:00
**Priority**: medium
**Status**: pending
**Area**: config

### 摘要
项目使用 pnpm 而非 npm 作为包管理器

### 详情
尝试执行 npm install 失败。项目根目录有 pnpm-lock.yaml，
使用 pnpm workspaces 管理依赖。

### 建议操作
检查 pnpm-lock.yaml 或 pnpm-workspace.yaml 后再决定包管理器。

### 元数据
- Source: user_feedback
- Related Files: pnpm-lock.yaml
- Tags: pnpm, package-manager
```

2. 如果这个经验足够通用，后续会提升到 `MEMORY.md` 的"血泪教训"章节
3. 下次新会话开始时，Agent 就知道这个项目用 pnpm 了

**你需要做什么**：什么都不用做，正常纠正 Agent 就行。Skill 会自动提醒 Agent 记录。

---

### 场景 2：命令执行失败

**情况**：Agent 跑 `go build ./...` 时报了一堆 import 错误。

**Agent 会做什么**：
1. 检测到命令失败（通过 error-detector Hook 或 Agent 自身判断）
2. 记录到 `~/.openclaw/workspace/.learnings/ERRORS.md`：

```markdown
## [ERR-20260304-001] go_build

**Logged**: 2026-03-04T11:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### 摘要
go build 因 import 路径错误失败

### 错误
could not import github.com/xxx/yyy (no required module provides package)

### 上下文
- 命令：go build ./...
- 原因：AI 生成的代码引入了不存在的 import 路径

### 建议修复
生成代码后执行 go mod tidy + goimports，确保 import 路径正确

### 元数据
- Reproducible: yes
- Related Files: go.mod
- Tags: go, import, build
```

3. 如果同类错误第 3 次出现，每日报告会建议提取为 Skill

**你需要做什么**：正常解决问题。如果 Agent 修好了，你可以说"把这个标记为已解决"。

---

### 场景 3：你想要一个 Agent 没有的能力

**情况**：你说"能不能帮我把分析结果导出成 Excel？"

**Agent 会做什么**：
记录到 `~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md`：

```markdown
## [FEAT-20260304-001] export_to_excel

**Logged**: 2026-03-04T14:00:00+08:00
**Priority**: medium
**Status**: pending
**Area**: backend

### 需求描述
将分析结果导出为 Excel 格式

### 用户场景
需要把报告分享给非技术同事，Excel 比 markdown 更方便

### 复杂度评估
medium

### 建议实现
使用 openpyxl 库，扩展现有的报告生成流程
```

**你需要做什么**：正常提需求。功能需求会被追踪，每日报告里能看到待处理列表。

---

### 场景 4：发现更好的做事方法

**情况**：你和 Agent 在调试一个接口问题时，发现"先看日志、再查监控、最后抓包"的方法比盲目改代码效率高很多。

**Agent 会做什么**：
1. 记录到 `~/.openclaw/workspace/.learnings/LEARNINGS.md`，分类 `best_practice`
2. 你可以说"**这个方法提升到 AGENTS.md**"，Agent 会把它精炼为一条工作流规则

提升后在 `~/.openclaw/workspace/AGENTS.md` 中变成：

```markdown
## 接口问题排查
1. 先查日志（grep 错误关键词 + 时间范围）
2. 看监控面板（QPS、延迟、错误率）
3. 必要时抓包分析请求/响应
→ 不要一上来就改代码
```

**你需要做什么**：发现好方法时告诉 Agent"记下来"或"提升到 AGENTS.md"。

---

### 场景 5：读技术文章，提炼经验

**情况**：你看到一篇关于 AI Coding 最佳实践的文章，想让 Agent 学习。

**怎么触发**：直接发文章链接，或说"learn this"：

```
https://example.com/ai-coding-best-practices
```

**Agent 会做什么**：
1. 抓取文章内容
2. 识别领域（AI Coding），按对应角度提炼
3. 提取 N 条可操作的洞察
4. 展示进化方案：

```
## 文章摘要
这篇文章讨论了 AI Coding Agent 的 7 个最佳实践...

## 提炼经验 (4 条)

### 1. 永远从 Plan Mode 开始
- 内容：让 Agent 先规划再动手，减少返工
- 增强方向：AGENTS.md
- 风险：中 → 需确认
- 理由：当前工作流缺少"先规划"这一步

### 2. CLAUDE.md 控制在 150 行以内
- 内容：系统文件过长会降低 Agent 注意力
- 增强方向：MEMORY.md
- 风险：低 → 自动执行

...

低风险项 (2 条) 将自动执行。
中/高风险项 (2 条) 需要你确认后执行。

是否确认执行？
```

5. 你确认后，Agent 自动执行变更并报告结果
6. 执行完后还会审查 MEMORY.md 和 AGENTS.md 是否需要优化

**你需要做什么**：发链接，审核方案，确认或拒绝。

---

### 场景 6：把方法论固化为可进化的 Gene

**情况**：你总结出一个"TDD 适配 AI Agent"的方法论——红、绿、重构三步法，每步有具体操作。这不是静态知识，而是会随经验改进的做事方法。

**怎么触发**：告诉 Agent"把这个方法提取为 Gene"，或 Agent 自己识别出可复用的方法论。

**Agent 会做什么**：

```bash
# 1. 运行提取脚本
/projects/.openclaw/skills/self-improving-agent/scripts/extract-gene.sh tdd-for-ai-agent \
  --source-learning LRN-20260304-003
```

这会创建：

```
~/.openclaw/workspace/.genes/tdd-for-ai-agent/
├── gene.yaml          # 元数据（ID、创建时间、衰减窗口等）
└── variants/
    └── v1.yaml        # 初始方法：红-绿-重构三步法
```

**后续进化**：
- 实践中发现步骤需要调整 → 创建 `v2.yaml`
- 换了一种 TDD 框架 → 创建 `v3.yaml`，标注 `supersedes: v2`
- 90 天没用过 → 每日报告标记为 `stale`，提醒你审查

**Gene 和 Skill 的区别**：
- **Skill**：静态知识（"Docker 在 M1 上要加 --platform 参数"）——提取后不变
- **Gene**：活的方法论（"TDD 三步法"）——会随经验进化出多个版本

**你需要做什么**：识别到好方法时说"提取为 Gene"。之后定期审查每日报告中的 Gene 健康状态。

---

### 场景 7：每天早上看进化报告

**情况**：Cron 任务每天 08:30 自动运行分析，生成一份报告。

**报告位置**：`~/.openclaw/workspace/.learnings/reports/YYYY-MM-DD.md`

**报告包含什么**：

```markdown
# 每日分析报告 - 2026-03-04

## 学习统计
- 总条目：23 条
- 待处理：5 条（2 条高优先级）
- 本周新增：3 条

## 晋升候选
- LRN-20260302-001 (go_import)：Recurrence=3，建议提升到 MEMORY.md

## 潜在重复
- LRN-20260301-002 与 LRN-20260228-001 相似度 65%，建议合并

## Skill 健康
- 已安装 Skill：12 个
- 健康：10 个
- 问题：docx（缺少 description 字段）、test-runner（脚本无执行权限）

## Gene 健康
- Active：3 个
- Stale：1 个 → tdd-for-ai-agent（60 天未用，新鲜度 0.33）
- Degraded：0 个

## 生态系统
- 已安装 Skill：12 个（昨日新增：code-reviewer）
- MCP 服务器：5 个
- MCP Skills：8 个
- 过期 Skill（>30天未更新）：docx（89 天）

## 建议操作
1. 审查并合并 2 条潜在重复
2. 审查 tdd-for-ai-agent Gene 是否仍有价值
3. 修复 docx Skill 的 description 字段
```

**你需要做什么**：每天花 2 分钟扫一眼报告，处理建议操作。或者忽略——报告不会消失，下次有空再看。

---

### 场景 8：重复踩坑，提取为独立 Skill

**情况**：你的 Agent 第三次遇到"Go 生成代码后 import 路径错误"的问题。

**Agent 会做什么**：
1. 每日报告检测到 `go_import` 标签出现 >= 3 次
2. 建议提取为独立 Skill

```bash
# Agent 运行
/projects/.openclaw/skills/self-improving-agent/scripts/extract-skill.sh go-import-fixer --dry-run
# 确认后
/projects/.openclaw/skills/self-improving-agent/scripts/extract-skill.sh go-import-fixer
```

创建的 Skill 结构：

```
/projects/.openclaw/skills/go-import-fixer/
└── SKILL.md    # 包含问题描述、解决方案、触发条件
```

之后每次 Agent 遇到 import 错误，就会自动加载这个 Skill 里的解决方案。

**你需要做什么**：确认提取，审查生成的 SKILL.md 内容。

---

### 场景 9：Workspace 文件越来越臃肿

**情况**：用了一段时间后，MEMORY.md 已经 180 行了（规则是 ≤ 150 行），而且有些内容已经过时。

**怎么触发**：每次进化事件（记录学习、读文章、提取 Gene）后，Agent 自动审查。

**Agent 会做什么**：

```
## Workspace 优化建议

基于本次进化事件，对 workspace 文件提出以下优化：

### MEMORY.md 优化

#### 新增
- 在「血泪教训」章节追加：Go 生成代码后必须 go mod tidy

#### 精简
- 「记忆系统架构认知」章节（30 行）→ 拆到 memory/memory-arch.md，只保留 1 行索引
- 「Cron 任务配置规则」已整合到 AGENTS.md，可删除

#### 当前状态
- 行数：180 行（超出建议 ≤ 150 行）
- 优化后预计：138 行 ✓

---
以上优化是否执行？可选择：
1. 全部执行
2. 逐条确认
3. 跳过本次优化
```

**你需要做什么**：审查方案，选择全部执行、逐条确认、或跳过。Agent 不会在没有你同意的情况下修改 Workspace 文件。

---

## 知识流转全景图

```
你和 Agent 的日常协作
        │
        ▼
┌─────────────────────────────┐
│  自动捕获                     │
│  纠正 → .learnings/LEARNINGS.md  │
│  错误 → .learnings/ERRORS.md     │
│  需求 → .learnings/FEATURE_REQUESTS.md │
│  文章 → .learnings/LEARNINGS.md  │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  每日分析 (Cron 08:30)        │
│  · 统计、去重、关联           │
│  · 检测可晋升条目             │
│  · Gene 衰减更新              │
│  · 生态系统盘点               │
└──────────┬──────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌─────────┐
│ 提升到    │  │ 提取为    │
│ Workspace│  │ 独立单元   │
│          │  │          │
│ MEMORY.md│  │ Skill    │
│ AGENTS.md│  │ (.openclaw│
│ SOUL.md  │  │ /skills/)│
│ TOOLS.md │  │          │
│          │  │ Gene     │
│          │  │ (.genes/)│
└─────────┘  └─────────┘
```

**知识的持久性从低到高**：
1. **`.learnings/`** — 原始记录，会话级
2. **`MEMORY.md`** — 长期记忆，每次启动加载
3. **`AGENTS.md` / `SOUL.md` / `TOOLS.md`** — Workspace 核心文件，影响 Agent 行为
4. **独立 Skill** — 可复用的静态知识包
5. **Gene** — 可进化的方法论，带版本和衰减追踪

---

## 文件说明

所有文件基于 OpenClaw 目录结构：

| 路径 | 说明 |
|------|------|
| `/projects/.openclaw/skills/self-improving-agent/SKILL.md` | 技能定义（核心，Agent 自动加载） |
| `/projects/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py` | 每日分析引擎（Python 3.11 标准库，无额外依赖） |
| `/projects/.openclaw/skills/self-improving-agent/scripts/setup_cron.sh` | 注册每日 Cron 任务 |
| `/projects/.openclaw/skills/self-improving-agent/scripts/extract-skill.sh` | Skill 提取助手 |
| `/projects/.openclaw/skills/self-improving-agent/scripts/extract-gene.sh` | Gene 提取助手 |
| `/projects/.openclaw/skills/self-improving-agent/scripts/activator.sh` | Hook：每次提示后提醒记录学习 |
| `/projects/.openclaw/skills/self-improving-agent/scripts/error-detector.sh` | Hook：检测命令错误 |
| `/projects/.openclaw/skills/self-improving-agent/hooks/openclaw/` | OpenClaw 启动 Hook（agent:bootstrap 注入） |
| `/projects/.openclaw/skills/self-improving-agent/assets/` | 模板文件（LEARNINGS.md、GENE-TEMPLATE.yaml 等） |
| `/projects/.openclaw/skills/self-improving-agent/references/` | 参考文档（Hook 配置、每日分析、Gene 生命周期等） |
| `~/.openclaw/workspace/.learnings/` | 学习记录存放处 |
| `~/.openclaw/workspace/.learnings/reports/` | 每日分析报告 |
| `~/.openclaw/workspace/.genes/` | Gene 方法论存放处 |
| `~/.openclaw/workspace/MEMORY.md` | 长期记忆 |
| `~/.openclaw/workspace/AGENTS.md` | Agent 工作流规则 |
| `~/.openclaw/workspace/SOUL.md` | Agent 行为准则 |
| `~/.openclaw/workspace/TOOLS.md` | 工具使用指南 |

---

## 常用命令速查

```bash
# ── 安装与初始化 ──
mkdir -p ~/.openclaw/workspace/.learnings                    # 创建学习目录
bash /projects/.openclaw/skills/self-improving-agent/scripts/setup_cron.sh  # 注册每日 Cron

# ── 每日分析 ──
python3 /projects/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py --dry-run      # 预览（不写文件）
python3 /projects/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py --auto-fix     # 执行并自动修复
openclaw cron list                                                                                # 查看 Cron 任务

# ── Skill 提取 ──
/projects/.openclaw/skills/self-improving-agent/scripts/extract-skill.sh my-skill --dry-run      # 预览
/projects/.openclaw/skills/self-improving-agent/scripts/extract-skill.sh my-skill                 # 执行

# ── Gene 提取 ──
/projects/.openclaw/skills/self-improving-agent/scripts/extract-gene.sh my-gene --dry-run        # 预览
/projects/.openclaw/skills/self-improving-agent/scripts/extract-gene.sh my-gene --source-learning LRN-20260304-001  # 关联来源

# ── 快速查询 ──
grep -h "Status\*\*: pending" ~/.openclaw/workspace/.learnings/*.md | wc -l     # 待处理条目数
grep -B5 "Priority\*\*: high" ~/.openclaw/workspace/.learnings/*.md | grep "^## \["  # 高优先级项

# ── Hook 管理 ──
openclaw hooks list                                          # 查看已安装 Hook
openclaw hooks enable self-improvement                       # 启用 Hook
```

---

## FAQ

### Q：安装后需要做什么才能让 Agent 开始学习？

创建 `~/.openclaw/workspace/.learnings` 目录即可。Skill 安装后 OpenClaw 会自动加载，Agent 在工作过程中会自动捕获和记录。

### Q：学习记录会消耗多少 Token？

每日 Cron 分析**零运行时开销**——它在独立会话中运行，不占你的对话上下文。如果启用了 activator.sh Hook，每次提示约增加 50-100 Token。

### Q：Agent 会自动修改我的 MEMORY.md 或 AGENTS.md 吗？

**不会**。所有对 Workspace 文件的修改都会先展示方案，等你明确确认后才执行。唯一自动写入的是 `.learnings/` 下的日志文件。

### Q：Gene 过期了（degraded）会被自动删除吗？

**不会**。stale/degraded 只是标记状态，提醒你审查。所有淘汰决策都由你做。

### Q：我不想用 Gene 功能，可以只用学习记录吗？

完全可以。Gene 是可选的高级功能。只用 `.learnings/` + 每日分析就已经能实现持续改进。

### Q：多个会话之间的学习怎么共享？

学习记录写在 `~/.openclaw/workspace/.learnings/`（Workspace 级），所有会话共享同一个目录。OpenClaw 还提供 `sessions_send` 工具可以主动向其他会话发送信息。

### Q：怎么知道某条学习有没有被用上？

- 查看条目的 `Status` 字段：`promoted` 表示已提升到 Workspace 文件
- 每日报告的"晋升候选"章节会标记可以提升的条目
- Gene 有 `usage_count` 追踪使用次数
