# 每日分析系统

每日分析系统提供对学习条目和技能健康状况的自动化审查，
用更节省 Token 的 Cron 方式替代基于 Hook 的提醒。

## 典型使用流程

```
1. 运行 bash scripts/setup_cron.sh 注册 Cron 任务（仅需一次）
2. 每天 08:30 自动运行分析，生成报告到 .learnings/reports/
3. 如有待办事项，自动发送摘要到主会话
4. 打开报告查看：
   - 今天新装了哪些 Skill / MCP？哪些被移除了？
   - 当前共有多少 Skill、MCP 服务器？
   - 哪些 Skill 长时间没更新，是否该淘汰？
   - 哪些 Gene 快过期了，需要审查或更新？
   - 有没有重复的学习条目需要合并？
   - 反复出现的错误是否该提取为 Skill？
5. 也可以手动运行：python3 scripts/daily_analysis.py --dry-run
```

## 架构

```
scripts/daily_analysis.py    <- 核心分析引擎（仅依赖 Python 3.11 标准库）
scripts/setup_cron.sh        <- Cron 注册助手
~/.openclaw/workspace/
  .learnings/
    reports/YYYY-MM-DD.md    <- 生成的报告
    ecosystem-snapshot.json  <- 生态系统快照（用于变更检测）
```

## 分析内容

### 学习条目分析

- 解析 `.learnings/LEARNINGS.md`、`ERRORS.md`、`FEATURE_REQUESTS.md`
- 按状态、优先级和领域统计条目数量
- 检测满足提升标准的 Pattern-Key 条目：
  - `Recurrence-Count >= 3`
  - 在 30 天窗口内
- 识别可提升的条目（已解决 + 高/关键优先级，或 See Also >= 2）
- 通过摘要关键词重叠检测潜在重复（Jaccard 相似度 >= 50%）

### Skill 健康检查

扫描 `/projects/.openclaw/skills/` 目录：

| 检查项 | 严重程度 |
|-------|----------|
| 缺少 SKILL.md | 错误 |
| frontmatter 缺失或格式错误 | 错误 |
| `name` 与目录名不匹配 | 警告 |
| `description` 缺失、过短或包含 TODO | 警告 |
| 正文内容过少（< 50 字符） | 警告 |
| Token 估算 > 6000 | 警告 |
| 包含 README.md（违反 Agent Skills 规范） | 警告 |
| 脚本缺少执行权限 | 可自动修复 |
| `.disabled` 状态 | 信息 |
| 断开的符号链接 | 错误 |

### 错误转 Skill 管道

- 按 Tags 聚合错误条目
- 当某个标签出现 >= 3 次时，建议提取为独立 Skill

### 生态系统演进追踪

盘点并追踪已安装的 Skill 和 MCP 生态系统的变化：

- 扫描 Skills 目录中所有已安装的 Skill（通过文件系统时间戳获取安装日期）
- 读取 `openclaw.json` 获取 ClawdHub 安装的 Skill（`knotInstalled`）和 MCP 类型的 Skill 条目
- 读取 `mcporter.json` 获取已配置的 MCP 服务器（本地和远程）
- 与已保存的快照比对，检测自上次运行以来新增/移除的 Skill 和 MCP 服务器
- 标记过期 Skill（>30 天未更新），作为清理候选
- 列出已禁用的 Skill 供重新考虑

**快照文件**：`~/.openclaw/workspace/.learnings/ecosystem-snapshot.json`

首次运行保存基线，后续运行显示变更差异。

## 自动修复范围

启用 `--auto-fix` 时，仅执行以下安全操作：

| 修复项 | 操作内容 |
|-----|-------------|
| `chmod +x` | 为 Skill `scripts/` 目录下的 `.sh` 和 `.py` 脚本添加执行权限 |
| 添加 `name` 字段 | 当 SKILL.md frontmatter 缺少 `name` 时，添加与目录名匹配的名称 |
| Gene 衰减更新 | 重新计算所有 Gene 的新鲜度分数和衰减状态 |

不执行破坏性操作。不删除文件。不移除内容。

## CLI 用法

```bash
# 仅预览报告（不写入文件）
python3 scripts/daily_analysis.py --dry-run

# 报告 + 自动修复预览
python3 scripts/daily_analysis.py --dry-run --auto-fix

# 生成报告（写入 ~/.openclaw/workspace/.learnings/reports/）
python3 scripts/daily_analysis.py

# 生成报告 + 执行修复
python3 scripts/daily_analysis.py --auto-fix

# 自定义路径
python3 scripts/daily_analysis.py --workspace /path/to/workspace --skills-dir /path/to/skills

# 自定义 Gene 和配置路径
python3 scripts/daily_analysis.py --genes-dir /path/to/genes --openclaw-config /path/to/openclaw.json --mcp-config /path/to/mcporter.json
```

## Cron 配置

注册每日分析为 OpenClaw Cron 任务：

```bash
bash scripts/setup_cron.sh
```

这会创建一个**每天 08:30 CST** 在隔离会话中运行的任务：
1. 带 `--auto-fix` 运行分析
2. 读取生成的报告
3. 如有待办事项，通过 `sessions_send` 发送摘要到主会话
4. 如无待办事项，保持静默

### 手动触发

```bash
openclaw cron list          # 查找任务 ID
openclaw cron run <job-id>  # 立即运行
```

## 报告格式

报告写入 `~/.openclaw/workspace/.learnings/reports/YYYY-MM-DD.md`，包含：

1. **学习摘要** - 条目计数、按优先级分组的待处理项
2. **生态系统演进报告** - Skill/MCP 盘点、新增安装、过期/已禁用项
3. **提升候选** - 满足标准的 Pattern-Key 条目
4. **可提升条目** - 高价值的已解决条目
5. **潜在重复** - 可能需要合并的相似条目
6. **错误转 Skill 建议** - 高频错误标签
7. **Skill 健康报告** - 所有 Skill 发现的问题
8. **Gene 健康报告** - Gene 衰减状态、Registry 一致性、表现最佳者
9. **自动修复操作** - 已自动修复的内容
10. **待办事项** - 建议的后续步骤汇总

## 设计决策

### Cron 优于 Hook

Hook 在每次提示时触发（每次约 50-100 Token）。一天 100+ 次提示，
仅提醒就消耗 5,000-10,000 Token。Cron 方案：
- 每天在隔离会话中运行一次
- 正常工作时零 Token 开销
- 比 Hook 提醒能做更深入的分析
- 产出持久化报告供审阅

### 仅依赖 Python 标准库

无 pip 依赖。脚本仅使用 Python 3.11 标准库模块。
确保在任何环境下无需额外安装即可运行。
