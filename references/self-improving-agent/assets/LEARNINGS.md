# Learnings

开发过程中捕获的纠正、洞察和知识缺口。

**分类**: correction | insight | knowledge_gap | best_practice
**领域**: frontend | backend | infra | tests | docs | config
**状态**: pending | in_progress | resolved | wont_fix | promoted | promoted_to_skill | promoted_to_gene

## 状态定义

| 状态 | 含义 |
|--------|---------|
| `pending` | 尚未处理 |
| `in_progress` | 正在处理中 |
| `resolved` | 问题已修复或知识已整合 |
| `wont_fix` | 决定不处理（原因记录在 Resolution 中） |
| `promoted` | 已提升到 CLAUDE.md、AGENTS.md 或 copilot-instructions.md |
| `promoted_to_skill` | 已提取为可复用技能 |
| `promoted_to_gene` | 已提取为可进化的 Gene（可复用方法论） |

## Skill 提取字段

当一个学习条目被提升为 Skill 时，添加以下字段：

```markdown
**Status**: promoted_to_skill
**Skill-Path**: skills/skill-name
```

示例：
```markdown
## [LRN-20250115-001] best_practice

**Logged**: 2025-01-15T10:00:00Z
**Priority**: high
**Status**: promoted_to_skill
**Skill-Path**: skills/docker-m1-fixes
**Area**: infra

### Summary
Docker build fails on Apple Silicon due to platform mismatch
...
```

## Gene 提取字段

当一个学习条目被提升为 Gene（可复用方法论）时，添加以下字段：

```markdown
**Status**: promoted_to_gene
**Gene-ID**: GEN-YYYYMMDD-XXX
**Gene-Path**: .genes/gene-name
```

示例：
```markdown
## [LRN-20260304-001] best_practice

**Logged**: 2026-03-04T10:00:00Z
**Priority**: high
**Status**: promoted_to_gene
**Gene-ID**: GEN-20260304-A1B
**Gene-Path**: .genes/tdd-red-green-refactor
**Area**: tests

### Summary
TDD red-green-refactor cycle with specific adaptation for AI coding agents
...
```

---
