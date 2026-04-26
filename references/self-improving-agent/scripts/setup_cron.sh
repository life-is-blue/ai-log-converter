#!/bin/bash
# Register daily self-improvement analysis cron job with OpenClaw.
# Usage: bash scripts/setup_cron.sh
#
# Requires: openclaw CLI available in PATH
# Schedule: Every day at 08:30 CST (Asia/Shanghai)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANALYSIS_SCRIPT="$SCRIPT_DIR/daily_analysis.py"

# Verify prerequisites
if ! command -v openclaw &>/dev/null; then
    echo "[ERROR] openclaw CLI not found. Install it first." >&2
    exit 1
fi

if [ ! -f "$ANALYSIS_SCRIPT" ]; then
    echo "[ERROR] Analysis script not found: $ANALYSIS_SCRIPT" >&2
    exit 1
fi

# Build the cron message that the agent session will execute
CRON_MESSAGE=$(cat <<'PROMPT'
执行每日自我改进分析：

1. 运行分析脚本：
```bash
python3 /projects/.openclaw/skills/self-improving-agent/scripts/daily_analysis.py --auto-fix
```

2. 读取生成的报告文件（路径在脚本输出的最后一行）

3. 如果报告中有 "Action Items" 章节，通过 sessions_send 发送以下摘要到主 session：
   - 待处理的 action items 列表
   - 报告文件完整路径
   - 建议的下一步操作

4. 如果没有 action items，不打扰主 session
PROMPT
)

# Register the cron job
openclaw cron add job="$(cat <<EOF
{
  "enabled": true,
  "name": "Self-Improvement Daily Analysis",
  "schedule": {
    "kind": "cron",
    "expr": "30 8 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": $(python3 -c "import json; print(json.dumps('''$CRON_MESSAGE'''.strip()))"),
    "deliver": false
  }
}
EOF
)"

# Create marker file so the bootstrap hook knows cron is registered
MARKER_DIR="$HOME/.openclaw/workspace/.learnings"
mkdir -p "$MARKER_DIR"
touch "$MARKER_DIR/.cron-registered"

echo "[OK] Cron job registered: Self-Improvement Daily Analysis"
echo "     Schedule: 08:30 CST daily"
echo "     Target: isolated session"
echo "     Marker: $MARKER_DIR/.cron-registered"
echo ""
echo "Verify with: openclaw cron list"
echo "Manual run:  openclaw cron run <job-id>"
