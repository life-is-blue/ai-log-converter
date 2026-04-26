#!/bin/bash
# Self-Improvement Error Detector Hook
# Triggers on PostToolUse for Bash to detect command failures
# Reads CLAUDE_TOOL_OUTPUT environment variable
# Classifies errors as critical or normal severity

set -e

# Check if tool output indicates an error
# CLAUDE_TOOL_OUTPUT contains the result of the tool execution
OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"

# Critical error patterns — immediate logging recommended
CRITICAL_PATTERNS=(
    "fatal:"
    "Traceback"
    "Permission denied"
    "SEGFAULT"
    "Segmentation fault"
    "panic:"
    "OOM"
    "out of memory"
    "Out of memory"
)

# Normal error patterns — log if non-obvious
NORMAL_PATTERNS=(
    "error:"
    "Error:"
    "ERROR:"
    "failed"
    "FAILED"
    "command not found"
    "No such file"
    "Exception"
    "npm ERR!"
    "ModuleNotFoundError"
    "SyntaxError"
    "TypeError"
    "exit code"
    "non-zero"
)

# Check for critical errors first
is_critical=false
for pattern in "${CRITICAL_PATTERNS[@]}"; do
    if [[ "$OUTPUT" == *"$pattern"* ]]; then
        is_critical=true
        break
    fi
done

if [ "$is_critical" = true ]; then
    cat << 'EOF'
<error-detected severity="critical">
A critical error was detected. Log immediately to .learnings/ERRORS.md with Priority: high or critical.
Use format: [ERR-YYYYMMDD-XXX]
</error-detected>
EOF
    exit 0
fi

# Check for normal errors
is_normal=false
for pattern in "${NORMAL_PATTERNS[@]}"; do
    if [[ "$OUTPUT" == *"$pattern"* ]]; then
        is_normal=true
        break
    fi
done

if [ "$is_normal" = true ]; then
    cat << 'EOF'
<error-detected severity="normal">
A command error was detected. Consider logging to .learnings/ERRORS.md if non-obvious.
Use format: [ERR-YYYYMMDD-XXX]
</error-detected>
EOF
fi
