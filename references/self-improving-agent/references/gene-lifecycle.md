# Gene 生命周期系统

Gene 系统为可复用的方法论和做法提供了一个进化层。
与 Skill（一旦提取即为静态）不同，Gene 支持版本化、使用追踪和新鲜度衰减——
适用于会随时间演进的知识。

## 典型使用流程

```
1. 在工作中发现一个好用的方法（如三步调试法、API 重试策略）
2. 运行 ./scripts/extract-gene.sh <name> 创建 Gene 脚手架
3. 填写 gene.yaml（描述、标签）和 variants/v1.yaml（方法步骤）
4. 以后再用到这个方法时，更新 usage_count 和 last_used
5. 发现方法需要改进时，创建新变体 variants/v2.yaml
6. 每日分析报告自动追踪哪些 Gene 活跃、哪些该审查
```

## 架构

```
.genes/
├── registry.json              # 所有 Gene 的中央索引
└── <gene-name>/
    ├── gene.yaml              # 元数据：标识、谱系、指标、衰减
    └── variants/
        ├── v1.yaml            # 初始方法
        ├── v2.yaml            # 进化版本
        └── ...

scripts/
├── extract-gene.sh            # Gene 脚手架生成器
└── daily_analysis.py          # 包含 Gene 健康分析 + 衰减更新
```

## 核心概念

### 什么是 Gene？

Gene 是一个**可复用的方法或做法**——一个可以进化的方法论单元。
示例：
- "适配 AI Agent 的 TDD 红-绿-重构循环"
- "带指数退避的 API 重试策略"
- "React 组件的错误边界模式"
- "数据库迁移回滚流程"

### Gene 与 Skill 的区别

| 维度 | Skill | Gene |
|--------|-------|------|
| 本质 | 静态知识、事实、注意事项 | 可进化的方法论、做法 |
| 版本管理 | 无（单个 SKILL.md） | 有（variants/vN.yaml） |
| 衰减追踪 | 无 | 有（新鲜度分数） |
| 分叉 | 无 | 有（parent_gene、forked_from） |
| 使用指标 | 无 | 有（usage_count、effectiveness_score） |
| 适用场景 | "做什么" | "怎么做" |

### 衰减模型

Gene 的新鲜度分数在可配置的时间窗口内线性衰减：

```
freshness = max(0, 1.0 - (距上次使用的天数 / decay_window_days))
```

默认衰减窗口：90 天。

| 新鲜度 | 状态 | 含义 |
|-----------|--------|---------|
| > 0.5 | `active` | 近期使用过，健康 |
| 0.2 - 0.5 | `stale` | 需要审查——还有用吗？ |
| < 0.2 | `degraded` | 长期未使用——需更新、淘汰或确认仍有效 |

**重要**：Gene 永远不会被自动删除或归档。stale/degraded 状态仅作为人工决策的信号。

## Gene 提取

### 何时提取

当一个学习条目描述了以下内容时，应提取为 Gene：
- **可重复的流程**（不是一次性修复）
- **会随经验演进的方法论**
- **因上下文不同而有差异的做法**
- **值得编纂的多步骤流程**

### 使用脚本

```bash
# 预览将创建的内容
./scripts/extract-gene.sh api-retry-backoff --dry-run

# 创建并关联来源学习条目
./scripts/extract-gene.sh api-retry-backoff --source-learning LRN-20260304-001

# 指定来源类型
./scripts/extract-gene.sh error-boundary --source-type article

# 自定义输出目录
./scripts/extract-gene.sh my-gene --output-dir ./my-project/.genes
```

### 创建后的产物

```
.genes/api-retry-backoff/
├── gene.yaml          # 元数据（需要填写 description、tags）
└── variants/
    └── v1.yaml        # 初始变体（需要填写 approach 步骤）
```

同时会在 `.genes/registry.json` 中追加一条记录。

### 提取后的操作

1. 编辑 `gene.yaml`：添加有意义的描述、上下文标签、适用领域
2. 编辑 `variants/v1.yaml`：记录分步方法论
3. 更新来源学习条目：
   ```markdown
   **Status**: promoted_to_gene
   **Gene-ID**: GEN-20260304-A1B
   **Gene-Path**: .genes/api-retry-backoff
   ```

## 变体管理

### 何时创建新变体

- 方法需要针对新场景做**重大修改**
- 发现了实现同一目标的**全新技术**
- 原有方法在某些场景下有**已知局限**
- 发现了**更优方法**来替代原有版本

### 创建变体

1. 创建 `variants/vN.yaml`（递增版本号）
2. 如果替代前一版本，设置 `supersedes: vN-1`
3. 更新 `gene.yaml`：递增 `current_version` 和 `variant_count`
4. 在 `notes` 字段中记录**为什么**需要这个变体

### 变体字段

| 字段 | 说明 |
|-------|-------------|
| `version` | 版本标签（v1、v2、...） |
| `created` | ISO 时间戳 |
| `author` | 创建者（initial、user、analysis） |
| `supersedes` | 替代的版本（如仅为追加则留空） |
| `summary` | 一行描述 |
| `approach` | 多行分步方法论 |
| `example` | 可选的代码/使用示例 |
| `trigger` | 何时应用此变体 |
| `source_learning_id` | 启发此变体的学习条目 |
| `notes` | 自由备注 |

## Gene 健康分析

每日分析脚本（`daily_analysis.py`）包含 Gene 健康检查：

### 检查项

| 检查项 | 说明 |
|-------|-------------|
| 衰减状态 | 重新计算所有 Gene 的新鲜度 |
| Registry 一致性 | 磁盘上的 Gene 与 registry.json 条目比对 |
| 缺失描述 | 描述为 TODO 或空的 Gene |
| 零使用 | 创建以来从未使用的 Gene |
| 表现最佳 | 按 effectiveness_score 排序 |

### 报告内容

每日报告包含 "Gene 健康报告" 章节：
- 状态概览（active/stale/degraded 计数）
- 需要审查的 stale Gene 列表
- 需要决策的 degraded Gene 列表
- 表现最佳的 Gene
- Registry 和质量问题

### 自动修复 (--auto-fix)

启用 `--auto-fix` 时，衰减更新器会：
1. 重新计算所有 Gene 的新鲜度分数
2. 更新每个 `gene.yaml` 中的 `freshness_score` 和 `decay_status`
3. 同步更新 `registry.json`

不执行任何破坏性操作。

## Gene 元数据参考

### gene.yaml 字段

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `gene_id` | string | `GEN-YYYYMMDD-XXX` 唯一标识 |
| `name` | string | Gene 名称（必须与目录名一致） |
| `description` | string | 此 Gene 封装的方法描述 |
| `parent_gene` | string | 父 Gene 的 ID（原创则留空） |
| `forked_from` | string | 分叉来源的 Gene ID |
| `current_version` | string | 最新变体版本（如 `v1`） |
| `variant_count` | int | 变体文件数量 |
| `effectiveness_score` | float | 0.0-1.0 有效性评分 |
| `usage_count` | int | 被应用的次数 |
| `last_used` | string | 最后使用日期（ISO 格式） |
| `created` | string | 创建时间戳（ISO 格式） |
| `freshness_score` | float | 0.0-1.0 由衰减系统计算 |
| `decay_status` | string | `active` / `stale` / `degraded` |
| `decay_window_days` | int | 完全衰减天数（默认 90） |
| `source_type` | string | `learning` / `article` / `observation` |
| `source_learning_ids` | string | 逗号分隔的来源学习条目 ID |
| `context_tags` | string | 逗号分隔的上下文标签 |
| `applicable_areas` | string | 逗号分隔的适用领域标签 |

### registry.json 结构

```json
{
  "genes": [
    {
      "gene_id": "GEN-20260304-A1B",
      "name": "api-retry-backoff",
      "path": "api-retry-backoff",
      "created": "2026-03-04T10:00:00Z",
      "decay_status": "active",
      "freshness_score": 1.0
    }
  ]
}
```

## 与学习生命周期的集成

Gene 系统扩展了现有的学习生命周期：

```
发现
  → 记录到 .learnings/
    → 审查
      → 提升到项目记忆（CLAUDE.md、AGENTS.md 等）
      → 提取为 Skill（静态知识）
      → 提取为 Gene（可进化方法论）  ← 新增
        → 追踪使用
        → 衰减/刷新循环
        → 演进变体
```

### 记录 Gene 使用

当你应用了某个 Gene 的方法论时，更新：
1. `gene.yaml`：递增 `usage_count`，更新 `last_used`
2. `registry.json`：同步 `freshness_score` 和 `decay_status`

这样可以保持衰减系统的准确性，并呈现哪些 Gene 在持续产生价值。
