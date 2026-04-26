# Changelog

## v2.0.0 (2026-03-04)

重大版本升级：新增 Gene 进化系统、生态追踪、Workspace 优化，全面中文化并以 OpenClaw 为唯一平台视角重写。

### 新增功能

#### Gene 进化系统
- Gene 抽象层：可版本化的方法论单元，支持 variant 分叉和谱系追踪
- 衰减标记机制：基于最后使用时间的新鲜度衰减（active/stale/degraded），仅标记不自动删除
- `scripts/extract-gene.sh`：Gene 提取脚手架（支持 `--dry-run`、`--source-learning`、路径安全检查）
- `assets/GENE-TEMPLATE.yaml` / `VARIANT-TEMPLATE.yaml`：Gene 和 Variant 模板
- `references/gene-lifecycle.md`：Gene 生命周期完整文档

#### 生态系统演进追踪
- 每日分析新增生态扫描：盘点已安装 Skill 数、MCP 服务器数、MCP Skills 数
- 快照差异比对：检测新增/移除的 Skill 和 MCP 服务器
- 过期 Skill 标记（>30 天未更新）和已禁用 Skill 提醒

#### Workspace 优化
- 进化事件后自动审查 MEMORY.md 和 AGENTS.md
- 生成优化建议（新增/精简/重组/拆分）展示给用户决策
- MEMORY.md ≤ 150 行规则自动检测

#### 每日分析增强
- Gene 健康分析：衰减状态分组、Registry 一致性检查、零使用检测
- Gene 新鲜度重算和衰减状态更新（`--auto-fix` 模式）
- 生态系统演进报告章节
- 新增 CLI 参数：`--genes-dir`、`--openclaw-config`、`--mcp-config`

### 重大变更

#### SKILL.md 全面重写
- `name` 字段从 `self-improvement` 改为 `self-improving-agent`（匹配目录名）
- `description` 字段改为中文
- 所有英文内容转为中文
- 移除 Generic Setup、Claude Code/Codex/Copilot 专属章节
- 以 OpenClaw 为唯一平台视角，所有路径使用 OpenClaw 目录结构
- 新增使用场景描述（Gene、每日分析、Workspace 优化各 4 个场景）

#### 文档中文化
- CLAUDE.md：全面中文
- assets/LEARNINGS.md：全面中文，新增 `promoted_to_gene` 状态和 Gene 提取字段
- references/daily-analysis.md：全面中文
- references/gene-lifecycle.md：新建，全中文

#### Hook 更新
- `hooks/openclaw/handler.ts` / `handler.js`：新增 Gene 提醒和 Workspace 优化提醒
- `scripts/activator.sh`：新增 Gene 提取和 Workspace 优化提醒行

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| SKILL.md | 重写 | 全面中文化，OpenClaw 平台视角 |
| CLAUDE.md | 修改 | 中文化，新增 Gene/生态追踪说明 |
| scripts/daily_analysis.py | 大幅修改 | +Gene 分析 +生态追踪 +衰减更新 |
| scripts/extract-gene.sh | 新建 | Gene 提取脚手架 |
| assets/GENE-TEMPLATE.yaml | 新建 | Gene 元数据模板 |
| assets/VARIANT-TEMPLATE.yaml | 新建 | Variant 方法模板 |
| assets/LEARNINGS.md | 修改 | 新增 Gene 相关状态和字段 |
| references/gene-lifecycle.md | 新建 | Gene 生命周期文档 |
| references/daily-analysis.md | 修改 | 中文化，新增生态追踪说明 |
| hooks/openclaw/handler.ts | 修改 | 新增 Gene 和优化提醒 |
| hooks/openclaw/handler.js | 修改 | 同步 handler.ts |
| scripts/activator.sh | 修改 | 新增 Gene 和优化提醒行 |
| CHANGELOG.md | 修改 | 新增 v2.0.0 记录 |

### 基于

v1.0.0 基础上增强开发

---

## v1.0.0 (2026-03-03)

首个正式版本，包含完整的自我进化 + 文章学习能力。

### 核心功能

#### 学习记录系统
- 自动捕获错误、纠正、知识缺口、最佳实践
- 标准化条目格式：`LRN/ERR/FEAT-YYYYMMDD-XXX`
- Pattern-Key 追踪反复出现的模式，支持 Recurrence-Count 自动晋升

#### 晋升体系
- `.learnings/` → `CLAUDE.md` → `AGENTS.md/SOUL.md/TOOLS.md` → 独立 Skill
- Simplify & Harden Feed：从 simplify-and-harden skill 摄入反复模式

#### 每日分析 (Cron)
- `scripts/daily_analysis.py`：纯 Python stdlib，无 pip 依赖
- 学习统计、Skill 健康检查、晋升候选检测、重复条目识别
- 安全自动修复：脚本权限 + 缺失 name 字段
- Error-to-Skill 管道：错误 tag >= 3 次建议提取为 Skill
- `scripts/setup_cron.sh`：注册每日 08:30 CST 定时分析

#### 文章学习 (Article Learning)
- 发 URL 或 `/learn <url>`，自动抓取文章并提炼经验
- 按领域分析：AI/Agent、AI Coding/OpenClaw、编程语言、DevOps
- 分级审批：低风险自动执行，中高风险需确认
- 所有写入带 `Source: article` 溯源标记

#### 安全校验
- `extract-skill.sh` 拒绝绝对路径和 `...` 路径遍历

### 文件清单

| 文件 | 说明 |
|------|------|
| SKILL.md | Skill 定义（含文章学习章节） |
| CLAUDE.md | 开发文档 |
| README.md | 分享用 README |
| scripts/daily_analysis.py | 每日分析引擎 |
| scripts/setup_cron.sh | Cron 注册脚本 |
| scripts/extract-skill.sh | Skill 提取助手（含安全校验） |
| scripts/activator.sh | Hook: 学习提醒 |
| scripts/error-detector.sh | Hook: 错误检测 |
| references/daily-analysis.md | 分析系统文档 |
| references/extraction-patterns.md | 文章提炼角度模板 |

### 基于

[peterskoett/self-improving-agent](https://github.com/peterskoett/self-improving-agent) 增强开发
