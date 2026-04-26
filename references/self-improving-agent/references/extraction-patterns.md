# Extraction Patterns by Domain

Reference guide for extracting insights from articles across different technical domains.

## AI / Agent Technology

**Look for:**
- Prompt engineering techniques (few-shot, chain-of-thought, tool use patterns)
- Agent architecture patterns (ReAct, plan-then-execute, multi-agent coordination)
- Context window management strategies
- Evaluation and benchmarking methods
- Safety and alignment practices

**Map to:**
- Prompt techniques → `SOUL.md` (behavioral rules)
- Agent patterns → `AGENTS.md` (workflow strategies)
- Tool use patterns → `TOOLS.md` (integration tips)
- New capabilities → candidate for new skill

**Example extraction:**
> Article: "Building Reliable AI Agents with Structured Output"
> Insight: "Force JSON mode + schema validation on every LLM call that feeds into code logic"
> Target: AGENTS.md → "## Output Handling" section

## AI Coding / OpenClaw / Spec-Driven Development

**Look for:**
- Skill design best practices (description writing, progressive disclosure)
- Hook/cron optimization patterns
- Memory management strategies
- Workflow composition patterns
- spec-based development methodology

**Map to:**
- Skill patterns → optimize existing skills or skill-doctor rules
- Workflow patterns → `AGENTS.md`
- Memory strategies → `MEMORY.md` or self-improving-agent enhancement
- New methodology → candidate for new skill

**Example extraction:**
> Article: "Effective Skill Description Writing"
> Insight: "Trigger keywords in first 50 chars of description field"
> Target: Learning entry (already captured as LRN-20260226-001)

## Programming Languages / Frameworks

**Look for:**
- Language-specific best practices and idioms
- Performance optimization techniques
- Error handling patterns
- API design patterns
- Testing strategies

**Map to:**
- Language tips → `TOOLS.md` (under language-specific section)
- Gotchas/pitfalls → `.learnings/LEARNINGS.md`
- Build/test patterns → `TOOLS.md`
- Major methodology → candidate for new skill

**Example extraction:**
> Article: "Go Error Handling Best Practices 2026"
> Insight: "Use errors.Join for multi-error aggregation instead of custom error slices"
> Target: TOOLS.md → "## Go" section

## DevOps / Infrastructure

**Look for:**
- CI/CD pipeline optimization
- Container and orchestration patterns
- Monitoring and observability practices
- Security hardening techniques
- Automation recipes

**Map to:**
- Tool usage → `TOOLS.md`
- Deployment patterns → `AGENTS.md` (automation workflows)
- Security rules → `SOUL.md` (safety principles)
- Complex workflows → candidate for new skill

**Example extraction:**
> Article: "Zero-Downtime Deployments with Kubernetes"
> Insight: "Always set PDB (PodDisruptionBudget) before rolling updates on stateful services"
> Target: TOOLS.md → "## Kubernetes" section

## General / Cross-Domain

**Look for:**
- Productivity methodologies
- Communication patterns
- Decision-making frameworks
- Team collaboration strategies

**Map to:**
- Work patterns → `SOUL.md` or `AGENTS.md`
- Decision frameworks → `MEMORY.md` (reference knowledge)
- Novel methodologies → candidate for new skill
