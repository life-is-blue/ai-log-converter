#!/bin/bash
# Self-Improvement Activator Hook
# Triggers on UserPromptSubmit to remind Claude about learning capture
# Keep output minimal (~30 tokens) to minimize overhead

set -e

# Output reminder as system context
cat << 'EOF'
<self-improvement-reminder>
Task done? Log if: correction, error, knowledge gap, or better approach found.
Target: ~/.openclaw/workspace/.learnings/
</self-improvement-reminder>
EOF
