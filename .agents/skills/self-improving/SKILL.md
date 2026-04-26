---
name: self-improving
description: "跨会话持续改进。触发：命令失败、用户纠正（'不对'/'其实应该'/'你为什么没有'）、发现更好方法、重要任务前复盘。自动记录到 ai-logs/LESSONS.md。"
allowed-tools: Bash, Read, Write, Edit
---

# 自我改进技能

记录经验教训到 LESSONS.md，推动跨 session 知识积累。
cron 每天自动将教训蒸馏到 MEMORY.md，形成闭环。

## 文件体系

| 文件 | 路径 | 职责 | 写入方 |
|------|------|------|--------|
| LESSONS.md | ai-logs/LESSONS.md | 经验教训（坑/因/法） | 本 skill + cron cmd_lessons |
| SOUL.md | ai-logs/SOUL.md | 行为观察 | cron cmd_soul |
| MEMORY.md | ai-logs/MEMORY.md | 行为规则 | cron cmd_distill |

## 何时触发

### 立即记录（L1: 追加到 LESSONS.md，不打断当前任务）

- 命令/操作失败且根因非显而易见
- 用户纠正你（"不对"/"其实应该"/"你为什么没有"/"为什么不结合"）
- 发现自身知识过时或错误
- 发现了更好的方法来完成重复任务
- 工具/API 行为与预期不一致

### 立即修复（L2: 先记录再修，不打断当前任务）

- 用户明确指出错误并给出正确做法
- 命令失败且你已知根因

L2 = L1 + 立即在当前 session 里修复。

### 不记录

- 显而易见的拼写/语法错误
- 用户的偏好/风格/工作节律（那是 SOUL.md 的职责，由 cron 自动提取）
- 项目内部特定函数的 bug（不可迁移——换个项目遇不到同一个函数）
- 已知最佳实践 / 通用 CS 知识
- /clear、/resume、/compact 等会话管理命令

## 条目格式

追加到 `ai-logs/LESSONS.md`，**严格遵守**：

```markdown
## kebab-case-slug
<!-- needs-review -->
> YYYY-MM-DD | pk: kebab-case-pattern-key

**坑**: 一句话描述问题现象
**因**: 一句话描述根本原因
**法**: 一句话描述修复方法或正确做法
```

### 格式规则

- slug: 2-6 英文词，kebab-case，全局唯一可辨识
- `<!-- needs-review -->` 标记**必须**紧跟 `## slug` 后一行（cron 会审查后替换为 absorbed 标记）
- pk: 2-4 英文词，kebab-case，描述核心模式，同一模式跨条目复用
- 坑/因/法全部用中文，每项一句话，不展开
- 只记录**跨项目可迁移**的教训
- 每次最多记录 2 条（宁缺毋滥）

### 可迁移性判断标准

问自己：**换一个项目、换一个人，这条教训是否仍有指导价值？**

可迁移示例：
- "Python bool 是 int 子类" → 任何 Python 项目都可能踩
- "rsync --delete-excluded 会删 .git" → 任何用 rsync 的场景
- "依赖缺失时硬失败优于静默降级" → 通用架构原则

不可迁移示例：
- "session_date() 改为 session_days()" → 只有本项目这个函数
- "SOUL.md 的 absorbed 标记格式" → 只有本项目这个文件

## 写入前去重

写入前**必须**先检查：

```bash
grep "^## " ai-logs/LESSONS.md
```

如果已有 slug 相同或内容相近的条目，**不重复记录**。

## 重要任务前复盘

开始以下类型任务前，先检索 LESSONS.md 相关条目：

- 修改 pipeline 或数据流
- 处理时间戳/日期/时区
- 配置 MCP/skill/hook
- 跨工具/跨平台集成
- rsync/git/CI 操作

```bash
grep -i "关键词" ai-logs/LESSONS.md
```

有相关教训时，在执行前引用。

## 晋升路径

LESSONS.md 条目**不手动晋升**。cron 每天自动运行：

```
cmd_lessons (补漏) → cmd_distill (晋升)
```

distill 同时读 SOUL.md + LESSONS.md 未吸收条目，统一蒸馏到 MEMORY.md。
教训被吸收后自动标记 `<!-- absorbed: true -->`，90 天后自动清理。

## 边界

- **不管理** SOUL.md —— cron cmd_soul 负责
- **不管理** reports/ —— cron cmd_report 负责
- **不修改** MEMORY.md —— cron cmd_distill 自动处理
- **不创建** Gene/Skill —— 手动处理（Gene 晋升建议由 cron cmd_distill 输出）
- 条目写入后是 **append-only**，不修改已有条目的内容
- 条目的 `<!-- needs-review -->` 标记由 cron 处理，不要手动改

## Gene 使用追踪

当你在会话中应用了 Gene 中记录的方法论时，更新该 Gene 的使用记录。

### 触发条件

- 你读取了某个 Gene 的 `variants/vN.yaml` 并按其 approach 步骤执行了任务
- 用户明确要求使用某个已有 Gene 的方法

### 更新操作

```bash
# 1. 确认 Gene 存在
ls ai-logs/.genes/<gene-name>/gene.yaml

# 2. 读取当前值
grep -E "usage_count|last_used" ai-logs/.genes/<gene-name>/gene.yaml

# 3. 原子更新（递增 usage_count，设置 last_used 为今天）
python3 -c "
import re, os; from pathlib import Path
p = Path('ai-logs/.genes/<gene-name>/gene.yaml')
c = p.read_text()
c = re.sub(r'^usage_count:.*', 'usage_count: <current+1>', c, flags=re.M)
c = re.sub(r'^last_used:.*', 'last_used: $(date -u +%Y-%m-%dT%H:%M:%SZ)', c, flags=re.M)
tmp = p.with_suffix('.tmp'); tmp.write_text(c); os.replace(tmp, p)
"
```

### 不更新

- 只是引用或讨论 Gene 但未实际按其 approach 执行
- 使用了类似但不同的方法（应记录为新 Lesson，而非更新已有 Gene）
- Gene 不存在（不要创建新 Gene，那是人类决策）
