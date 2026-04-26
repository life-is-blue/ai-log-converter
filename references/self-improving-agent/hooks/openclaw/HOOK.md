---
name: self-improving-agent
description: "Injects self-improvement reminder and setup guide during agent bootstrap"
metadata: {"openclaw":{"emoji":"🧠","events":["agent:bootstrap"]}}
---

# Self-Improving Agent Hook

Injects a self-improvement reminder and detects missing setup during agent bootstrap.

## What It Does

- Fires on `agent:bootstrap` (before workspace files are injected)
- Checks workspace setup completeness (`~/.openclaw/workspace/.learnings/` directory, log files, cron registration)
- **Setup incomplete** → injects a setup guide with actionable commands + the learning reminder
- **Setup complete** → injects only the learning reminder (zero extra overhead)
- Skips sub-agent sessions (sessionKey containing `:subagent:`)

## Setup Detection

The hook checks for:

| Item | Path |
|------|------|
| Learnings directory | `~/.openclaw/workspace/.learnings/` |
| `LEARNINGS.md` | `~/.openclaw/workspace/.learnings/LEARNINGS.md` |
| `ERRORS.md` | `~/.openclaw/workspace/.learnings/ERRORS.md` |
| `FEATURE_REQUESTS.md` | `~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md` |
| Cron marker | `~/.openclaw/workspace/.learnings/.cron-registered` |

When any item is missing, a `SELF_IMPROVEMENT_SETUP_GUIDE.md` virtual file is injected with specific commands the agent can run to complete setup.

## Configuration

No configuration needed. Enable with:

```bash
openclaw hooks enable self-improving-agent
```
