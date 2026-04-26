---
name: self-improving-agent
version: 2.2.0
description: "捕获学习、错误和纠正，实现跨会话持续改进。适用场景：(1) 命令或操作意外失败，(2) 用户纠正 Agent（'不对…'、'其实应该…'、'你为什么没有…'、'为什么不结合…'），(3) 用户需要不存在的功能，(4) 外部 API 或工具故障，(5) 发现自身知识过时或错误，(6) 为重复任务发现更好的方法，(7) 用户发送 URL 或说'learn this'/'学习一下'/'读这个'/'学学这个'/'/learn <url>'从文章中提取知识。(8) 发现已有 skill/能力未被主动整合联动时（'为什么不结合'、'这两个能打通吗'）。执行重要任务前也应复盘已有学习记录。"
metadata:
---

# 自我改进技能（Self-Improving Agent）

将学习记录和错误日志写入 markdown 文件，实现持续改进。重要学习提升为项目记忆，高价值方法论提取为 Gene，推动 Agent 不断进化。

> **平台**：本技能为 [OpenClaw](https://openclaw.dev) 设计，通过 Workspace 注入和 Skill 自动加载机制工作。

## 快速参考

| 场景 | 操作 |
|------|------|
| 命令/操作失败 | 记录到 `~/.openclaw/workspace/.learnings/ERRORS.md` |
| 用户纠正你 | 记录到 `~/.openclaw/workspace/.learnings/LEARNINGS.md`，分类 `correction` |
| 用户需要缺失功能 | 记录到 `~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md` |
| API/外部工具故障 | 记录到 `~/.openclaw/workspace/.learnings/ERRORS.md`，附集成细节 |
| 知识过时 | 记录到 `~/.openclaw/workspace/.learnings/LEARNINGS.md`，分类 `knowledge_gap` |
| 发现更好方法 | 记录到 `~/.openclaw/workspace/.learnings/LEARNINGS.md`，分类 `best_practice` |
| 简化/加固重复模式 | 更新 `~/.openclaw/workspace/.learnings/LEARNINGS.md`，设 `Source: simplify-and-harden` 和稳定的 `Pattern-Key` |
| 类似已有条目 | 用 `**See Also**` 关联，考虑提升优先级 |
| 广泛适用的学习 | 提升到 `AGENTS.md`、`SOUL.md`、`TOOLS.md` 或 `MEMORY.md` |
| 工作流改进 | 提升到 `AGENTS.md`（OpenClaw Workspace） |
| 工具踩坑 | 提升到 `TOOLS.md`（OpenClaw Workspace） |
| 行为模式 | 提升到 `SOUL.md`（OpenClaw Workspace） |
| 用户发送 URL 或说"learn this" | 抓取文章 → 提取洞察 → 提出进化方案（见"文章学习"章节） |
| 发现可复用方法/做法 | 提取为 Gene 到 `.genes/`（见"Gene 生命周期"章节） |
| 进化事件完成后 | 审查 `MEMORY.md`/`AGENTS.md` 是否需要优化，展示 diff 供用户决策 |
| 用户表达"不断优化/持续改进某能力" | **L1 主动指令**：纳入进化框架，不能只设 cron 提醒（见"意图分级"章节） |
| 已有 skill 未被主动整合联动 | **L1 主动指令**：读对应 SKILL.md，立即整合进当前方案 |
| 修改触发规则后 | 运行意图识别自测：`python3 ~/.openclaw/workspace/.learnings/scripts/test_intent_triggers.py` |

---

## 安装与配置

OpenClaw 通过 Workspace 注入机制自动加载技能，无需手动引用。

### 安装方式

**通过 ClawdHub 安装（推荐）：**
```bash
clawdhub install self-improving-agent
```

**手动安装：**
```bash
git clone https://github.com/peterskoett/self-improving-agent.git /projects/.openclaw/skills/self-improving-agent
```

> 原始仓库：https://github.com/pskoett/pskoett-ai-skills/tree/main/skills/self-improvement

### OpenClaw 目录结构

OpenClaw 在每次会话启动时注入以下 Workspace 文件：

```
~/.openclaw/workspace/                    # OpenClaw Workspace 根目录
├── AGENTS.md                             # 多 Agent 工作流、委派模式
├── SOUL.md                               # 行为准则、个性、原则
├── TOOLS.md                              # 工具能力、集成踩坑
├── MEMORY.md                             # 长期记忆（仅主会话）
├── memory/                               # 详细记忆文件（索引方式拆分）
│   └── *.md
├── .learnings/                           # 本技能的日志文件
│   ├── LEARNINGS.md                      # 学习记录
│   ├── ERRORS.md                         # 错误记录
│   ├── FEATURE_REQUESTS.md               # 功能需求记录
│   └── reports/                          # 每日分析报告
│       └── YYYY-MM-DD.md
├── .genes/                               # Gene 方法论（可版本化）
│   ├── registry.json                     # Gene 索引
│   └── <gene-name>/
│       ├── gene.yaml                     # Gene 元数据
│       └── variants/
│           └── v1.yaml                   # 方法变体
└── config/
    └── mcporter.json                     # MCP 服务器配置

/projects/.openclaw/                      # OpenClaw 项目配置根目录
├── openclaw.json                         # OpenClaw 主配置
└── skills/                               # 已安装的技能
    └── self-improving-agent/             # 本技能
        ├── SKILL.md                      # 技能定义（本文件）
        ├── CLAUDE.md                     # 开发指引
        ├── scripts/                      # 脚本工具
        ├── hooks/openclaw/               # OpenClaw Hook
        ├── assets/                       # 模板文件
        └── references/                   # 参考文档
```

### 创建学习文件

```bash
mkdir -p ~/.openclaw/workspace/.learnings
```

然后创建日志文件（或从 `assets/` 目录复制模板）：
- `LEARNINGS.md` — 纠正、知识差距、最佳实践
- `ERRORS.md` — 命令失败、异常
- `FEATURE_REQUESTS.md` — 用户需求的功能

### 提升目标

当学习经验被证明广泛适用时，提升到 OpenClaw Workspace 文件：

| 学习类型 | 提升到 | 示例 |
|---------|--------|------|
| 行为模式 | `SOUL.md` | "简洁表达，避免免责声明" |
| 工作流改进 | `AGENTS.md` | "长任务派生子 Agent" |
| 工具踩坑 | `TOOLS.md` | "Git push 前需先配置认证" |
| 通用知识/经验 | `MEMORY.md` | "Go import 必须跑 go mod tidy" |

### 跨会话通信

OpenClaw 提供以下工具在会话间共享学习：

- **sessions_list** — 查看活跃/最近的会话
- **sessions_history** — 读取其他会话的记录
- **sessions_send** — 向其他会话发送学习内容
- **sessions_spawn** — 派生子 Agent 执行后台任务

### 可选：启用 Hook

为会话启动时自动注入学习提醒：

```bash
# 复制 Hook 到 OpenClaw Hook 目录
cp -r hooks/openclaw ~/.openclaw/hooks/self-improvement

# 启用 Hook
openclaw hooks enable self-improvement
```

详见 `references/openclaw-integration.md`。

---

## 日志格式

### 学习条目

追加到 `~/.openclaw/workspace/.learnings/LEARNINGS.md`：

```markdown
## [LRN-YYYYMMDD-XXX] 分类

**Logged**: ISO-8601 时间戳
**Priority**: low | medium | high | critical
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### 摘要
一句话描述学到了什么

### 详情
完整上下文：发生了什么，什么是错的，正确做法是什么

### 建议操作
具体的修复或改进措施

### 元数据
- Source: conversation | error | user_feedback | article | simplify-and-harden
- Related Files: path/to/file.ext
- Tags: tag1, tag2
- See Also: LRN-20250110-001（如关联已有条目）
- Pattern-Key: simplify.dead_code | harden.input_validation（可选，用于重复模式追踪）
- Recurrence-Count: 1（可选）
- First-Seen: 2025-01-15（可选）
- Last-Seen: 2025-01-15（可选）
- Gene-ID: GEN-YYYYMMDD-XXX（可选，提升为 Gene 时添加）

---
```

### 错误条目

追加到 `~/.openclaw/workspace/.learnings/ERRORS.md`：

```markdown
## [ERR-YYYYMMDD-XXX] 技能或命令名

**Logged**: ISO-8601 时间戳
**Priority**: high
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### 摘要
简述什么操作失败了

### 错误
```
实际错误信息或输出
```

### 上下文
- 尝试的命令/操作
- 使用的输入或参数
- 相关的环境信息

### 建议修复
如能确定，说明可能的修复方式

### 元数据
- Reproducible: yes | no | unknown
- Related Files: path/to/file.ext
- See Also: ERR-20250110-001（如重复出现）

---
```

### 功能需求条目

追加到 `~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md`：

```markdown
## [FEAT-YYYYMMDD-XXX] 功能名称

**Logged**: ISO-8601 时间戳
**Priority**: medium
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### 需求描述
用户想做什么

### 用户场景
为什么需要这个功能，解决什么问题

### 复杂度评估
simple | medium | complex

### 建议实现
如何构建，可能扩展哪些现有功能

### 元数据
- Frequency: first_time | recurring
- Related Features: existing_feature_name

---
```

## ID 生成

格式：`TYPE-YYYYMMDD-XXX`
- TYPE：`LRN`（学习）、`ERR`（错误）、`FEAT`（功能需求）
- YYYYMMDD：当前日期
- XXX：顺序编号或随机 3 字符（如 `001`、`A7B`）

示例：`LRN-20250115-001`、`ERR-20250115-A3F`、`FEAT-20250115-002`

## 解决条目

问题修复后，更新条目：

1. 将 `**Status**: pending` 改为 `**Status**: resolved`
2. 在元数据后添加解决记录：

```markdown
### 解决记录
- **Resolved**: 2025-01-16T09:00:00Z
- **Commit/PR**: abc123 或 #42
- **Notes**: 简述做了什么
```

其他状态值：
- `in_progress` - 正在处理中
- `wont_fix` - 决定不修复（在解决记录的 Notes 中说明原因）
- `promoted` - 已提升到 Workspace 文件（MEMORY.md、AGENTS.md、SOUL.md 等）
- `promoted_to_skill` - 已提取为独立 Skill
- `promoted_to_gene` - 已提取为 Gene

## 提升到项目记忆

当学习经验广泛适用（不是一次性修复）时，提升为永久的项目记忆。

### 何时提升

- 学习适用于多个文件/功能
- 任何贡献者（人或 AI）都应该知道的知识
- 防止反复犯同一个错
- 记录项目特有的约定

### 提升目标

| 目标 | 适合放什么 |
|------|-----------|
| `MEMORY.md` | 长期知识、领域上下文、环境信息、经验教训 |
| `AGENTS.md` | Agent 工作流、委派模式、自动化规则 |
| `SOUL.md` | 行为准则、沟通风格、原则 |
| `TOOLS.md` | 工具能力、使用模式、集成踩坑 |

> 所有目标文件均位于 `~/.openclaw/workspace/` 下。

### 如何提升

1. **提炼**学习经验为简洁的规则或事实
2. **添加**到目标文件的合适章节
3. **更新**原始条目：
   - 将 `**Status**: pending` 改为 `**Status**: promoted`
   - 添加 `**Promoted**: MEMORY.md`（或其他目标文件）

### 提升示例

**学习条目**（详细版）：
> 项目用 pnpm workspaces。试了 `npm install` 但失败了。
> lock 文件是 `pnpm-lock.yaml`。必须用 `pnpm install`。

**提升到 MEMORY.md**（精炼版）：
```markdown
## 构建与依赖
- 包管理器：pnpm（非 npm）- 使用 `pnpm install`
```

**学习条目**（详细版）：
> 修改 API 端点后，必须重新生成 TypeScript 客户端。
> 忘记这步会在运行时出现类型不匹配。

**提升到 AGENTS.md**（可操作版）：
```markdown
## API 变更后
1. 重新生成客户端：`pnpm run generate:api`
2. 检查类型错误：`pnpm tsc --noEmit`
```

## 重复模式检测

如果要记录的内容与已有条目类似：

1. **先搜索**：`grep -r "关键词" ~/.openclaw/workspace/.learnings/`
2. **关联条目**：在元数据中添加 `**See Also**: ERR-20250110-001`
3. **提升优先级**：问题反复出现时
4. **考虑系统性修复**：重复问题通常意味着：
   - 缺少文档（→ 提升到 MEMORY.md 或 AGENTS.md）
   - 缺少自动化（→ 添加到 AGENTS.md）
   - 架构问题（→ 创建技术债务工单）

## 简化与加固工作流

从 `simplify-and-harden` 技能接收重复模式，转化为持久的 Agent 指导。

### 摄取工作流

1. 从任务摘要中读取 `simplify_and_harden.learning_loop.candidates`
2. 对每个候选项，使用 `pattern_key` 作为稳定的去重键
3. 在 `~/.openclaw/workspace/.learnings/LEARNINGS.md` 中搜索该 key 的已有条目：
   - `grep -n "Pattern-Key: <pattern_key>" ~/.openclaw/workspace/.learnings/LEARNINGS.md`
4. 如果找到：
   - 递增 `Recurrence-Count`
   - 更新 `Last-Seen`
   - 添加 `See Also` 关联
5. 如果未找到：
   - 创建新的 `LRN-...` 条目
   - 设置 `Source: simplify-and-harden`
   - 设置 `Pattern-Key`、`Recurrence-Count: 1`、`First-Seen`/`Last-Seen`

### 提升规则（系统提示反馈）

当满足以下全部条件时，将重复模式提升到 Workspace 文件：

- `Recurrence-Count >= 3`
- 在至少 2 个不同任务中出现
- 发生在 30 天窗口内

提升目标：
- `MEMORY.md` — 通用知识
- `AGENTS.md` — 工作流规则
- `SOUL.md` / `TOOLS.md` — Workspace 级行为/工具指导

提升的规则应写成简短的预防规则（编码前/中应该怎么做），而非冗长的事故报告。

## 定期审查

在自然的工作节点审查 `~/.openclaw/workspace/.learnings/`：

### 何时审查
- 开始新的重要任务前
- 完成一个功能后
- 在有过往学习的领域工作时
- 活跃开发期间每周一次

### 快速状态检查

```bash
# 统计待处理项
grep -h "Status\*\*: pending" ~/.openclaw/workspace/.learnings/*.md | wc -l

# 列出高优先级待处理项
grep -B5 "Priority\*\*: high" ~/.openclaw/workspace/.learnings/*.md | grep "^## \["

# 查找特定领域的学习
grep -l "Area\*\*: backend" ~/.openclaw/workspace/.learnings/*.md
```

### 审查操作
- 解决已修复的条目
- 提升适用的学习
- 关联相关条目
- 升级反复出现的问题

## 检测触发器

当注意到以下情况时自动记录：

**纠正**（→ 学习条目，分类 `correction`）：
- "不，那不对……"
- "其实应该是……"
- "你说错了……"
- "那个过时了……"

**功能需求**（→ 功能需求条目）：
- "能不能也……"
- "要是能……就好了"
- "有没有办法……"
- "为什么不能……"

**知识差距**（→ 学习条目，分类 `knowledge_gap`）：
- 用户提供了你不知道的信息
- 你引用的文档已过时
- API 行为与你的理解不同

**错误**（→ 错误条目）：
- 命令返回非零退出码
- 异常或堆栈跟踪
- 意外的输出或行为
- 超时或连接失败

**错误严重程度分级**：

| 严重程度 | 特征 | 操作 |
|---------|------|------|
| critical | fatal、panic、Traceback、Permission denied、OOM、SEGFAULT | 立即记录，Priority: high/critical |
| normal | 一般 error/failed、command not found、SyntaxError、TypeError | 仅在非显而易见时记录，Priority: medium |
| noise | 已知的安全可忽略错误（如 linter 配置警告、已预期的退出码） | 不记录 |

## 意图分级（执行前识别）

收到用户意图后先判断级别，再决定执行路径：

**L1 主动指令**（立即纳入进化框架，Priority: high）
- "帮我不断优化/持续改进X" / "这个能力需要自动化提升"
- "为什么不结合/打通" / "这两个能打通吗"
- "你为什么没有用Y" / "你怎么没用上 skill"
→ 读 self-improving-agent SKILL.md，用进化循环承接整个任务；**不能只设 cron 提醒**

**L2 被动纠正**（记录 + 立即修复，Priority: high）
- "不对" / "其实应该" / "你搞错了"
→ 写 correction LRN，立刻修复，修复后运行意图识别自测验证

**L3 文章学习**（提炼 + 按需提升，Priority: medium）
- 用户发 URL / "learn this" / "读这个" / "学学这个"
→ 提炼洞察，低风险自动执行，中高风险确认后执行

**L4 事后观察**（记录备查，Priority: low，不打断对话）
- 完成任务后发现更好方法 / 知识过时
→ 写 LRN，不打断当前流程

> **重要**：L1 触发后必须用进化框架承接，而不是另起一套独立方案（如单独设 cron 提醒）。这是最常见的漏洞场景。

## 意图识别自测

每次修改 `AGENTS.md` 或 skill `description` 后，运行自测验证覆盖完整性：

```bash
python3 ~/.openclaw/workspace/.learnings/scripts/test_intent_triggers.py
```

测试用例文件：`~/.openclaw/workspace/.learnings/intent-trigger-tests.yaml`

发现新的漏触发场景时：
1. 在 `intent-trigger-tests.yaml` 添加新用例（`expect_trigger: true`）
2. 在 `AGENTS.md` L1 触发词列表补充对应关键词
3. 重新运行直到全部通过
4. 写一条 LRN-YYYYMMDD-XXX（category: correction）

自测也集成在每周进化循环 cron 的 Step 0，每周一凌晨 2:00 自动运行。

## 优先级指南

| 优先级 | 使用场景 |
|--------|---------|
| `critical` | 阻塞核心功能、数据丢失风险、安全问题 |
| `high` | 影响大、涉及常见工作流、反复出现的问题 |
| `medium` | 中等影响、有变通方案 |
| `low` | 小不便、边缘情况、锦上添花 |

## 领域标签

用于按代码区域过滤学习：

| 领域 | 范围 |
|------|------|
| `frontend` | UI、组件、客户端代码 |
| `backend` | API、服务、服务端代码 |
| `infra` | CI/CD、部署、Docker、云 |
| `tests` | 测试文件、测试工具、覆盖率 |
| `docs` | 文档、注释 |
| `config` | 配置文件、环境、设置 |

## 最佳实践

1. **立即记录** — 问题发生后上下文最新鲜
2. **要具体** — 后续 Agent 需要快速理解
3. **包含复现步骤** — 特别是错误类条目
4. **关联相关文件** — 方便定位修复
5. **提出具体修复方案** — 不要只写"需要调查"
6. **使用一致的分类** — 便于筛选
7. **积极提升** — 有疑问就加到 Workspace 文件
8. **定期审查** — 过时的学习会失去价值

## Gitignore 配置

**保持学习文件为本地**（个人级）：
```gitignore
.learnings/
```

**跟踪学习文件到仓库**（团队级）：
不添加到 .gitignore — 学习成为共享知识。

**混合模式**（跟踪模板，忽略条目）：
```gitignore
.learnings/*.md
!.learnings/.gitkeep
```

## Hook 集成

通过 Agent Hook 启用自动提醒。这是**可选配置**——需要主动设置 Hook。

### OpenClaw Hook 配置

Hook 位于 `/projects/.openclaw/skills/self-improving-agent/hooks/openclaw/`，在 `agent:bootstrap` 事件时自动注入学习提醒。

```bash
# 安装 Hook
cp -r /projects/.openclaw/skills/self-improving-agent/hooks/openclaw ~/.openclaw/hooks/self-improvement

# 启用
openclaw hooks enable self-improvement

# 验证
openclaw hooks list
```

Hook 功能：
- 在 Agent 启动时注入自我改进提醒（先于 Workspace 文件加载）
- 自动跳过子 Agent 会话（sessionKey 包含 `:subagent:` 的会话）以避免引导问题

### 脚本 Hook（补充）

除了 OpenClaw Hook 外，还可以配置脚本级 Hook：

| 脚本 | Hook 类型 | 用途 |
|------|-----------|------|
| `scripts/activator.sh` | UserPromptSubmit | 每次提示后提醒评估学习（~30 Token 开销） |
| `scripts/error-detector.sh` | PostToolUse (Bash) | 检测命令错误时触发 |

配置方式（在 OpenClaw 或兼容 Agent 的 settings.json 中）：

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/projects/.openclaw/skills/self-improving-agent/scripts/activator.sh"
      }]
    }],
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "/projects/.openclaw/skills/self-improving-agent/scripts/error-detector.sh"
      }]
    }]
  }
}
```

详见 `references/hooks-setup.md`。

## 自动 Skill 提取

当学习经验有价值到足以成为可复用技能时，使用提取工具。

### Skill 提取标准

满足以下任一条件即可提取为 Skill：

| 标准 | 说明 |
|------|------|
| **重复出现** | 有 2+ 个 `See Also` 关联条目 |
| **已验证** | 状态为 `resolved`，修复有效 |
| **非显而易见** | 需要实际调试/调查才发现 |
| **广泛适用** | 非项目特有；跨代码库都有用 |
| **用户标记** | 用户说"保存为技能"或类似表述 |

### 提取工作流

1. **识别候选**：学习条目满足提取标准
2. **运行助手**（或手动创建）：
   ```bash
   /projects/.openclaw/skills/self-improving-agent/scripts/extract-skill.sh skill-name --dry-run
   /projects/.openclaw/skills/self-improving-agent/scripts/extract-skill.sh skill-name
   ```
3. **填写 SKILL.md**：用学习内容填充模板
4. **更新学习条目**：设置状态为 `promoted_to_skill`，添加 `Skill-Path`
5. **验证**：在新会话中读取 Skill 确认自包含

### 手动提取

如需手动创建：

1. 在 `/projects/.openclaw/skills/<skill-name>/` 下创建 `SKILL.md`
2. 使用 `assets/SKILL-TEMPLATE.md` 模板
3. 遵循 [Agent Skills 规范](https://agentskills.io/specification)：
   - YAML frontmatter 包含 `name` 和 `description`
   - `name` 必须与文件夹名一致
   - Skill 文件夹内不放 README.md

### 提取检测触发器

注意以下信号，表明学习应该提取为 Skill：

**在对话中：**
- "保存为技能"
- "我老是遇到这个问题"
- "这对其他项目也有用"
- "记住这个模式"

**在学习条目中：**
- 多个 `See Also` 关联（重复出现）
- 高优先级 + 已解决
- 分类 `best_practice` 且广泛适用
- 用户积极评价该方案

### Skill 质量检查

提取前确认：

- [ ] 方案已测试且有效
- [ ] 脱离原始上下文仍然清晰
- [ ] 代码示例自包含
- [ ] 无项目特有的硬编码值
- [ ] 遵循命名规范（小写、连字符）

## Gene 生命周期

Gene 代表**可复用的方法和做法**——支持版本化、使用追踪和新鲜度衰减的进化方法论单元。Skill 一旦提取即为静态，而 Gene 是随时间演进的活体。

### 使用场景

**场景 1：发现了一个好用的调试方法**
你在排查一个 API 超时问题时，总结出"先查日志 → 再看监控 → 最后抓包"的三步法。这个方法可能随着经验改进，适合提取为 Gene。

**场景 2：同一个问题有多种解决路径**
缓存失效可以用 TTL、事件驱动、或版本号三种策略。你把每种策略记为一个 variant，根据场景选用不同变体。

**场景 3：文章中学到一个新方法论**
读了一篇关于 TDD 的文章，提炼出适配 AI Agent 的红-绿-重构流程。先提取为 Gene v1，实践后发现需要调整步骤，创建 v2 变体。

**场景 4：每日报告发现 Gene 过期**
某个 Gene 90 天没用过，每日分析报告标记为 `degraded`。你审查后决定：更新方法继续用，或确认已无价值。

### Gene 与 Skill 的决策矩阵

| 特征 | 提取为 Skill | 提取为 Gene |
|------|-------------|-------------|
| 静态知识（注意事项、事实） | 是 | 否 |
| 可进化的方法论/做法 | 否 | 是 |
| 需要版本历史 | 否 | 是 |
| 可能有竞争性变体 | 否 | 是 |
| 一刀切的方案 | 是 | 否 |
| 依赖上下文的方法 | 否 | 是 |

### Gene 结构

每个 Gene 存放在 `~/.openclaw/workspace/.genes/<gene-name>/` 下：

```
~/.openclaw/workspace/.genes/
├── registry.json              # 所有 Gene 的索引
└── <gene-name>/
    ├── gene.yaml              # 元数据：标识、谱系、指标、衰减
    └── variants/
        ├── v1.yaml            # 初始方法
        ├── v2.yaml            # 进化版本
        └── ...
```

### Gene 提取标准

当学习条目满足以下条件时，应提取为 Gene：

| 标准 | 说明 |
|------|------|
| **方法论** | 描述的是可重复的做法，而非单纯的事实 |
| **可进化** | 随着经验积累可能会被改进 |
| **依赖上下文** | 在不同场景下做法可能不同 |
| **多步骤** | 涉及一系列操作，而非单行命令 |

### 提取工作流

1. **识别候选**：学习条目描述了一个可复用的方法/做法
2. **运行助手**：
   ```bash
   /projects/.openclaw/skills/self-improving-agent/scripts/extract-gene.sh gene-name --dry-run
   /projects/.openclaw/skills/self-improving-agent/scripts/extract-gene.sh gene-name --source-learning LRN-20260304-001
   ```
3. **完善 gene.yaml**：添加描述、上下文标签、适用领域
4. **填写变体**：在 `variants/v1.yaml` 中记录方法步骤
5. **更新学习条目**：设置状态为 `promoted_to_gene`，添加 `Gene-ID` 和 `Gene-Path`

### 创建变体

在以下情况创建新变体：

- 方法需要针对新场景做重大修改
- 发现了实现同一目标的全新技术
- 原有方法在某些场景下有已知局限

新变体放入 `variants/vN.yaml`，如果替代前一版本则设置 `supersedes`。

### 衰减机制

Gene 的**新鲜度分数**（0.0 到 1.0）基于最后使用时间随时间衰减：

| 状态 | 新鲜度 | 含义 |
|------|--------|------|
| `active` | > 0.5 | 近期使用过，健康 |
| `stale` | 0.2 - 0.5 | 近期未使用，需要审查 |
| `degraded` | < 0.2 | 长期未使用，需要决策 |

默认衰减窗口为 90 天。新鲜度由每日分析 Cron 重新计算。

**重要**：Gene 永远不会被自动归档或删除。stale/degraded 状态是人工审查的信号。

### Gene 元数据参考

| 字段 | 说明 |
|------|------|
| `gene_id` | 唯一 ID：`GEN-YYYYMMDD-XXX` |
| `name` | Gene 名称（与目录名一致） |
| `description` | 此 Gene 封装的方法描述 |
| `parent_gene` | 父 Gene 的 ID（如分叉而来） |
| `forked_from` | 分叉来源的 Gene ID |
| `current_version` | 最新变体版本 |
| `variant_count` | 变体数量 |
| `effectiveness_score` | 0.0-1.0 有效性评分 |
| `usage_count` | 被应用的次数 |
| `last_used` | 最后使用的 ISO 日期 |
| `created` | 创建时间的 ISO 时间戳 |
| `freshness_score` | 0.0-1.0 计算得出的新鲜度 |
| `decay_status` | `active` / `stale` / `degraded` |
| `decay_window_days` | 完全衰减的天数（默认 90） |
| `source_type` | `learning` / `article` / `observation` |
| `source_learning_ids` | 逗号分隔的来源学习条目 ID |
| `context_tags` | 逗号分隔的上下文标签 |
| `applicable_areas` | 逗号分隔的适用领域标签 |

## Workspace 优化（进化时审查）

每次发生"进化事件"时，除了记录学习、提取 Skill/Gene 外，还应审查并优化 `MEMORY.md` 和 `AGENTS.md`。这两个文件是 Agent 每次启动都会加载的核心上下文，质量直接影响 Agent 表现。

### 使用场景

**场景 1：记录学习后发现 MEMORY.md 需要更新**
你解决了一个 Go 编译问题，记录了学习条目。发现这个经验足够通用，应该加到 MEMORY.md 的"血泪教训"里。同时审查该章节是否有过时内容需要清理。

**场景 2：读文章提炼经验时顺带优化**
读了一篇 AI Coding 最佳实践的文章，提炼出 3 条经验。其中 1 条应加入 MEMORY.md，同时发现 MEMORY.md 的"Claude Code 最佳实践"章节可以精简合并。

**场景 3：提取 Gene 后更新 AGENTS.md 工作流**
提取了一个"TDD 方法论" Gene，发现 AGENTS.md 的 Self-Improvement 规则可以补充一行："发现可复用方法 → 提取为 Gene"。

**场景 4：每日分析报告触发优化**
报告显示 MEMORY.md 已超过 150 行（违反自己定的规则），需要将详细内容拆到 `memory/*.md`，只保留精简索引。

### 触发时机

| 进化事件 | 审查 MEMORY.md | 审查 AGENTS.md |
|---------|--------------|---------------|
| 记录学习条目（LRN/ERR/FEAT） | 是否有新经验值得加入 | — |
| 提升到项目记忆（promoted） | 新增内容 + 清理过时项 | 如涉及工作流变更则更新 |
| 读文章提炼经验 | 新增知识 + 审查相关章节 | 如涉及行为/工作流则更新 |
| 提取 Skill 或 Gene | 如涉及工具/环境则更新 | 如涉及流程/规范则更新 |
| 每日分析报告 | 检查行数、是否有过时内容 | 检查规则是否仍然适用 |

### 优化流程

每次进化事件执行后，按以下步骤审查：

**Step 1：读取现有文件**
- 读取 `~/.openclaw/workspace/MEMORY.md` 和 `~/.openclaw/workspace/AGENTS.md` 的当前内容
- 对照本次进化事件产生的新知识

**Step 2：生成优化建议**

分析并识别可优化的点：
- **可新增**：本次获得的新知识/规则是否应加入
- **可精简**：已有内容是否有重复、过时、或过于冗长的部分
- **可重组**：章节结构是否合理，相关内容是否分散
- **可拆分**：文件是否超过 150 行，是否应将详细内容外移到 `~/.openclaw/workspace/memory/*.md`

**Step 3：展示优化方案供用户决策**

输出格式：

```
## Workspace 优化建议

基于本次进化事件，对 workspace 文件提出以下优化：

### MEMORY.md 优化

#### 新增
- 在「血泪教训」章节追加：xxx

#### 精简
- 「记忆系统架构认知」章节内容已转化为 Gene，可精简为一行索引

#### 当前状态
- 行数：154 行（建议 ≤ 150 行）
- 章节数：12

---
以上优化是否执行？可选择：
1. 全部执行
2. 逐条确认
3. 跳过本次优化
```

**Step 4：执行用户确认的优化**

用户确认后执行编辑，执行后报告结果：

```
## Workspace 优化结果

- [x] MEMORY.md：新增「xxx」到血泪教训（+2 行）
- [x] MEMORY.md：精简记忆系统章节（-15 行，外移到 memory/memory-arch.md）
- [ ] AGENTS.md：无需修改
- 当前 MEMORY.md：142 行 ✓
```

### 优化原则

1. **MEMORY.md ≤ 150 行**——这是 Agent 自己定的规则，必须遵守。超出则拆分到 `~/.openclaw/workspace/memory/*.md`，MEMORY.md 只放精简索引
2. **AGENTS.md 精简高效**——每条规则必须有明确的触发条件和操作，删除模糊或重复的指导
3. **不破坏现有结构**——优化是渐进式的，不做大规模重写。每次只改动与本次进化相关的部分
4. **所有修改需用户确认**——不自动修改 workspace 文件。展示 diff 或描述变更，用户确认后执行
5. **保留归属信息**——从文章提炼的内容标注来源，从学习提升的内容标注原始 ID

## 每日分析（基于 Cron）

相比每次提示的 Hook（每次约 30 Token 开销），使用每日 Cron 任务进行更深入的分析，运行时零成本。

### 使用场景

**场景 1：每天早上了解系统进化状态**
Cron 任务每天 08:30 自动运行，生成报告。打开报告就能看到：今天装了几个新 Skill、MCP 服务器有哪些、哪些 Gene 快过期了。

**场景 2：发现有 Skill 装了很久没用过**
报告的"过期 Skill"列表显示 `docx` 已经 89 天没更新。你可以决定是继续保留还是卸载释放空间。

**场景 3：发现重复的学习条目**
报告检测到两条学习条目相似度 > 50%。你审查后合并为一条，避免知识碎片化。

**场景 4：某个错误反复出现**
同一个标签的错误出现 3 次以上，报告建议提取为 Skill。这样下次遇到同类问题时直接套用方案。

### 分析内容

- 解析所有 `~/.openclaw/workspace/.learnings/` 条目：计数、待处理项、优先级分布
- 检测满足提升标准的 Pattern-Key 条目（Recurrence >= 3，30 天窗口）
- 识别可提升条目（已解决的高/关键优先级，或 2+ 个 See Also 链接）
- 通过摘要相似度标记潜在重复条目
- 扫描 `/projects/.openclaw/skills/` 下所有 Skill 的健康问题（缺少 SKILL.md、frontmatter 错误、规范违规）
- 当某个错误标签出现 >= 3 次时，建议提取为 Skill
- 可选自动修复：修复脚本权限、补充缺失的 `name` 字段
- 扫描 `~/.openclaw/workspace/.genes/` 的 Gene 健康：衰减状态、Registry 一致性、缺失描述
- 重新计算 Gene 新鲜度分数并更新衰减状态（使用 `--auto-fix` 时）
- 追踪生态系统演进：盘点已安装的 Skill（读取 `/projects/.openclaw/openclaw.json`）、MCP 服务器（读取 `~/.openclaw/workspace/config/mcporter.json`）和 MCP Skills
- 检测自上次运行以来新增/移除的 Skill 和 MCP 服务器（通过快照差异比对）
- 标记过期 Skill（>30 天未更新）和已禁用 Skill 供审查
- 保存生态系统快照用于下次运行的比对

### 配置

```bash
# 注册 Cron 任务（每天 08:30 CST，隔离会话中运行）
bash /projects/.openclaw/skills/self-improving-agent/scripts/setup_cron.sh

# 验证
openclaw cron list
```

### 手动运行

```bash
# 预览模式（仅输出不写文件）
python3 /projects/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py --dry-run

# 生成报告并执行安全修复
python3 /projects/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py --auto-fix
```

### 报告

报告写入 `~/.openclaw/workspace/.learnings/reports/YYYY-MM-DD.md`。

发现待办事项时，Cron 会话通过 `sessions_send` 发送摘要到主会话。

详见 `references/daily-analysis.md`。

## 文章学习（读文章，长本事）

从技术文章中提取可操作的知识，驱动系统进化。

### 触发方式

| 触发条件 | 操作 |
|---------|------|
| 用户发送 URL | 抓取文章、分析内容、提出进化方案 |
| `/learn <url>` | 同上，显式调用 |
| "learn this" / "读这个" + URL | 同上 |
| 用户确认进化方案 | 执行已批准的变更 |

### 工作流

**Step 1：抓取并理解**
1. 使用 `WebFetch` 获取文章内容
2. 识别文章领域：AI/Agent、AI Coding/OpenClaw、编程语言/框架、DevOps/基础设施、其他
3. 用用户的语言生成 **3-5 句摘要**

**Step 2：提取洞察**

根据文章领域从以下角度分析：

| 领域 | 提取重点 |
|------|---------|
| AI/Agent | 提示词技巧、Agent 架构模式、多 Agent 协调、工具使用策略 |
| AI Coding/OpenClaw | Skill 设计模式、工作流优化、规范驱动开发、Hook/Cron 模式 |
| 编程/框架 | 最佳实践、反模式、性能技巧、API 踩坑 |
| DevOps/基础设施 | 工具用法、部署模式、监控策略、自动化方案 |

对每条洞察，确定：
- **内容**：具体的规则、模式或技巧
- **意义**：对当前工作流的影响
- **去向**：哪个进化目标（见 Step 3）
- **是否为方法论**：如果洞察描述的是可复用的做法/方法，考虑提取为 Gene 而非 Skill

**Step 3：映射到进化目标**

| 目标 | 放什么内容 | 风险等级 |
|------|-----------|---------|
| `~/.openclaw/workspace/.learnings/LEARNINGS.md` | 具体的技巧、踩坑、纠正 | 低（自动） |
| `~/.openclaw/workspace/MEMORY.md` | 事实、参考知识、领域上下文 | 低（自动） |
| `~/.openclaw/workspace/SOUL.md` | 行为规则、沟通模式 | 中（需确认） |
| `~/.openclaw/workspace/TOOLS.md` | 工具使用模式、集成技巧 | 中（需确认） |
| `~/.openclaw/workspace/AGENTS.md` | 工作流模式、委派策略 | 中（需确认） |
| 优化现有 Skill | 改进描述、添加规则、修复缺陷 | 高（需确认） |
| 创建新 Skill | 值得提取的新独立能力 | 高（需确认） |
| 提取为 Gene | 可版本化的可复用方法论（`~/.openclaw/workspace/.genes/`） | 高（需确认） |

**Step 4：展示进化方案**

输出格式：

```
## 文章摘要
<3-5 句>

## 提炼经验 (N 条)

### 1. [经验名称]
- 内容：<一句话>
- 增强方向：<目标文件或 Skill 名称>
- 风险：低/中/高 → 自动执行 / 需确认
- 理由：<为什么能改进系统>

### 2. ...

---
低风险项 (N 条) 将自动执行。
中/高风险项 (M 条) 需要你确认后执行。

是否确认执行？
```

**Step 5：执行（确认后）**

低风险 — 自动执行：
- 学习条目：追加到 `~/.openclaw/workspace/.learnings/LEARNINGS.md`，使用标准条目格式（LRN-YYYYMMDD-XXX，`Source: article`，文章 URL 放 Related Files，`Tags` 来自文章领域）
- 记忆更新：追加到 `~/.openclaw/workspace/MEMORY.md` 的合适章节

中/高风险 — 用户确认后：
- Workspace 文件（SOUL.md、TOOLS.md、AGENTS.md）：读取当前文件，找到合适章节，追加或更新
- Skill 优化：读取当前 SKILL.md，提出具体编辑，确认后执行
- 新 Skill 创建：在 `/projects/.openclaw/skills/<name>/` 下创建 `SKILL.md`

**Step 6：报告结果**

```
## 执行结果

- [x] 记录 learning: LRN-20260303-001 (xxx)
- [x] 更新 MEMORY.md: 新增 xxx 知识
- [x] 更新 TOOLS.md: 新增 xxx 用法 (已确认)
- [ ] 创建 skill「xxx」(用户跳过)

来源文章：<url>
```

**Step 7：Workspace 优化审查**

执行完进化操作后，按照"Workspace 优化"章节的流程审查 `~/.openclaw/workspace/MEMORY.md` 和 `~/.openclaw/workspace/AGENTS.md`。
读取当前内容，对照本次新增的知识，生成优化建议展示给用户决策。

### 文章学习条目格式

从文章创建学习条目时使用：

```markdown
## [LRN-YYYYMMDD-XXX] 分类

**Logged**: ISO-8601 时间戳
**Priority**: medium
**Status**: pending
**Area**: <根据文章领域推断>

### 摘要
<一句话提炼洞察>

### 详情
<文章中与此洞察相关的要点>

### 建议操作
<应用此知识的具体下一步>

### 元数据
- Source: article
- Related Files: <文章 URL>
- Tags: <领域标签>
- Article-Title: <文章原始标题>
```

### 文章学习准则

- **精选提炼**：不是文章每句话都是洞察。只提取可操作的、非显而易见的知识。
- **要具体**："使用缓存"不是洞察。"用 HTTP ETag 头做 API 响应缓存可减少 40% 带宽"才是。
- **去重**：创建学习条目前，检查 `~/.openclaw/workspace/.learnings/` 或 Workspace 文件中是否已有类似知识。
- **尊重范围**：不要过度提升。一个小众的 Go 技巧属于 `.learnings/`，不属于 `SOUL.md`。
- **保留归属**：始终包含文章 URL 作为来源。

详见 `references/extraction-patterns.md`。
