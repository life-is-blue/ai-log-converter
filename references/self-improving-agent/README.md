# Self-Improving Agent

> OpenClaw AI Agent 自我进化 Skill —— 让你的 Agent 越用越聪明

## 这是什么

一个遵循 [Agent Skills 规范](https://agentskills.io/specification) 的 OpenClaw Skill，为 AI Agent 提供**持续学习和自我进化**能力。基于 [peterskoett/self-improving-agent](https://github.com/peterskoett/self-improving-agent) 增强开发。

## 核心能力

| 能力 | 说明 |
|------|------|
| **学习记录** | 自动捕获错误、纠正、最佳实践，写入 `.learnings/` |
| **Pattern-Key 追踪** | 标记反复出现的模式，自动计数，满足条件时触发晋升 |
| **晋升体系** | 从临时记录 → 项目记忆 → Workspace 文件 → 独立 Skill，逐级固化 |
| **每日分析 (Cron)** | 每天自动分析学习状态、检查 Skill 健康、检测可晋升条目 |
| **Skill 健康检查** | 扫描所有 Skill 的 SKILL.md 规范性、frontmatter、权限等 |
| **自动修复** | 修复脚本权限、补全缺失的 name 字段（仅安全操作） |
| **Error-to-Skill 管道** | 当某类错误出现 >= 3 次，建议提取为独立 Skill |
| **文章学习** | 发 URL 或说 "learn this"，自动提炼经验、分级审批、写入对应目标 |

## 安装


**手动安装:**
```bash
git clone https://git.woa.com/qijunwang/self-improving-agent.git ~/.openclaw/skills/self-improving-agent
```

## 文件结构

```
self-improving-agent/
├── SKILL.md                    # Skill 定义（核心）
├── CLAUDE.md                   # 开发文档
├── scripts/
│   ├── daily_analysis.py       # 每日分析引擎（Python 3.11 stdlib）
│   ├── setup_cron.sh           # Cron 定时任务注册
│   ├── extract-skill.sh        # Skill 提取助手
│   ├── activator.sh            # Hook: 提示记录学习
│   └── error-detector.sh       # Hook: 错误检测
├── hooks/openclaw/             # OpenClaw bootstrap hook
├── references/                 # 配置文档 + 文章提取模板
│   └── extraction-patterns.md  # 各领域知识提炼角度
├── assets/                     # 模板文件
└── .learnings/                 # 学习记录模板
```

## 快速开始

```bash
# 1. 安装后，创建学习文件
mkdir -p ~/.openclaw/workspace/.learnings

# 2. 手动运行一次分析（查看当前状态）
python3 ~/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py --dry-run

# 3. 注册每日自动分析（08:30 CST）
bash ~/.openclaw/skills/self-improving-agent/scripts/setup_cron.sh
```

## 学习记录格式

```markdown
## [LRN-20260303-001] best_practice

**Logged**: 2026-03-03T15:00:00+08:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
一行描述你学到了什么

### Details
完整上下文

### Metadata
- Source: conversation | error | user_feedback | article
- Tags: tag1, tag2
- Pattern-Key: xxx (可选，用于追踪反复出现的模式)
```

## 文章学习

直接给 Agent 发一个技术文章 URL：

```
https://example.com/some-article
```

Agent 会：抓取文章 → 提炼经验 → 展示进化方案 → 分级审批执行

| 操作 | 风险 | 审批 |
|------|------|------|
| 记录到 `.learnings/` | 低 | 自动 |
| 更新 MEMORY.md | 低 | 自动 |
| 更新 SOUL.md / TOOLS.md / AGENTS.md | 中 | 需确认 |
| 修改现有 Skill / 创建新 Skill | 高 | 需确认 |

## 设计理念

- **Cron 替代 Hook**：Hook 每次 prompt 消耗 50-100 tokens，Cron 每天运行一次，零运行时开销
- **纯 Python stdlib**：daily_analysis.py 不依赖 pip，任何环境开箱即用
- **安全优先**：自动修复仅限 chmod +x 和补全 name 字段，不做破坏性操作
- **兼容上游**：保持与 peterskoett/self-improving-agent 的兼容，可合并上游更新

## 兼容性

支持 OpenClaw、Claude Code、Codex CLI、GitHub Copilot。

## License

MIT