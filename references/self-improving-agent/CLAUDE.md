# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目简介

一个 AI 编程 Agent 技能（遵循 [Agent Skills 规范](https://agentskills.io/specification)），用于捕获学习、错误和纠正，实现跨会话的持续改进。支持 Claude Code、Codex CLI、GitHub Copilot 和 OpenClaw。

## 仓库结构

- `SKILL.md` - 主技能定义文件（YAML frontmatter + markdown 正文）。按 Agent Skills 规范，这是唯一必需的文件。
- `hooks/openclaw/` - OpenClaw 专用 Hook（`handler.ts` / `handler.js`），在 `agent:bootstrap` 事件时注入学习提醒，先于 workspace 文件加载。子 Agent 会话（sessionKey 包含 `:subagent:`）会跳过以避免引导问题。
- `scripts/` - Hook 脚本和分析工具：
  - `activator.sh` - UserPromptSubmit Hook；输出约 30 Token 的 XML 提醒
  - `error-detector.sh` - PostToolUse (Bash) Hook；模式匹配 `CLAUDE_TOOL_OUTPUT` 中的错误指标，分 critical/normal 两级严重度
  - `extract-skill.sh` - 从学习条目创建 Skill 脚手架（支持 `--dry-run`、`--output-dir`；拒绝绝对路径和 `..`）
  - `extract-gene.sh` - 创建 Gene 脚手架和变体（支持 `--dry-run`、`--output-dir`、`--source-learning`、`--source-type`；路径安全检查同 extract-skill.sh）
  - `daily_analysis.py` - 每日分析引擎：学习统计、晋升候选评估、提升检测、Skill 健康检查、Gene 健康/衰减分析、生态系统演进追踪、自动修复（仅依赖 Python 3.11 标准库）
  - `setup_cron.sh` - 注册每日分析为 OpenClaw Cron 任务（08:30 CST）
- `assets/` - 模板文件：`LEARNINGS.md`（学习文件头/格式）、`SKILL-TEMPLATE.md`（Skill 提取模板）、`GENE-TEMPLATE.yaml` / `VARIANT-TEMPLATE.yaml`（Gene 提取模板）
- `references/` - Hook 配置指南、OpenClaw 集成、条目格式示例、每日分析文档、文章提取模式
- `.learnings/` - 空模板文件（LEARNINGS.md、ERRORS.md、FEATURE_REQUESTS.md），展示日志结构

## 核心概念

**学习生命周期**：发现 -> 记录到 `.learnings/` -> 审查 -> 提升到项目记忆 -> 提取为 Skill

**Gene 生命周期**：发现可复用方法 -> 提取到 `.genes/` -> 追踪使用 -> 衰减/刷新 -> 演进变体。Gene 是可版本化的方法论单元（对比静态的 Skill）。详见 SKILL.md "Gene Lifecycle" 章节。

**Workspace 优化**：每次进化事件（记录学习、读文章、提取 Skill/Gene）后，审查 `MEMORY.md` 和 `AGENTS.md` 是否需要新增、精简或重组，生成优化建议展示给用户确认后执行。详见 SKILL.md "Workspace 优化" 章节。

**提升层级**（持久性递增）：
1. `.learnings/` - 原始会话级条目
2. `CLAUDE.md` / `.github/copilot-instructions.md` - 项目级约定
3. `AGENTS.md` / `SOUL.md` / `TOOLS.md` - OpenClaw workspace 文件
4. `skills/<name>/SKILL.md` - 独立可复用技能
5. `.genes/<name>/gene.yaml` - 可进化的可复用方法论

**条目 ID 格式**：`TYPE-YYYYMMDD-XXX`，TYPE 为 `LRN`、`ERR` 或 `FEAT`，XXX 为顺序编号或随机 3 字符。

**学习条目元数据**（上游新增）：`Pattern-Key`、`Recurrence-Count`、`First-Seen`、`Last-Seen` 字段用于重复模式追踪。提升规则：Recurrence >= 3，30 天窗口，2+ 个不同任务。

## 约定

- Skill 名称必须为小写加连字符（由 extract-skill.sh 中的正则 `^[a-z0-9]+(-[a-z0-9]+)*$` 校验）
- Gene 名称遵循相同约定（由 extract-gene.sh 校验）
- Gene ID 格式：`GEN-YYYYMMDD-XXX`（与 `LRN`/`ERR`/`FEAT` ID 模式并行）
- Skill 文件夹不得包含 README.md；`SKILL.md` 是唯一入口
- SKILL.md 需要 YAML frontmatter 包含 `name`（必须与文件夹名一致）和 `description` 字段
- Hook 脚本必须有可执行权限（`chmod +x`）
- OpenClaw Hook handler 同时存在 TypeScript（`handler.ts`，使用 `openclaw/hooks` 类型导入）和纯 JavaScript（`handler.js`，CommonJS 导出）版本——需保持同步

## 测试变更

无自动化测试套件。请手动验证：

```bash
# 测试 Skill 提取（预览模式）
./scripts/extract-skill.sh test-skill --dry-run

# 测试 activator Hook 输出
bash ./scripts/activator.sh

# 测试错误检测器（模拟错误输出）
CLAUDE_TOOL_OUTPUT="error: something failed" bash ./scripts/error-detector.sh

# 测试错误检测器（无错误——应无输出）
CLAUDE_TOOL_OUTPUT="success" bash ./scripts/error-detector.sh

# 测试每日分析（预览模式）
python3 scripts/daily_analysis.py --dry-run

# 测试每日分析含自动修复预览
python3 scripts/daily_analysis.py --dry-run --auto-fix

# 测试 Gene 提取（预览模式）
./scripts/extract-gene.sh test-gene --dry-run

# 测试 Gene 提取关联来源学习条目
./scripts/extract-gene.sh test-gene --source-learning LRN-20260304-001

# 测试 Gene 名称校验（应失败）
./scripts/extract-gene.sh Invalid_Name

# 注册 Cron 任务
bash scripts/setup_cron.sh
```

OpenClaw Hook 的验证方式：检查 `openclaw hooks list` 并在新会话中测试。
