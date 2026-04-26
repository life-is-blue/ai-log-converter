/**
 * Self-Improvement Hook for OpenClaw
 *
 * Injects a reminder to evaluate learnings during agent bootstrap.
 * Also detects missing setup and injects a setup guide when needed.
 * Fires on agent:bootstrap event before workspace files are injected.
 */

import type { HookHandler } from 'openclaw/hooks';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

const REMINDER_CONTENT = `## Self-Improvement Reminder

After completing tasks, evaluate if any learnings should be captured:

**Log when:**
- User corrects you → \`.learnings/LEARNINGS.md\`
- Command/operation fails → \`.learnings/ERRORS.md\`
- User wants missing capability → \`.learnings/FEATURE_REQUESTS.md\`
- You discover your knowledge was wrong → \`.learnings/LEARNINGS.md\`
- You find a better approach → \`.learnings/LEARNINGS.md\`

**Promote when pattern is proven:**
- Behavioral patterns → \`SOUL.md\`
- Workflow improvements → \`AGENTS.md\`
- Tool gotchas → \`TOOLS.md\`

Keep entries simple: date, title, what happened, what to do differently.`;

/**
 * Check workspace setup completeness and return a list of missing items.
 * Returns an empty array when everything is properly configured.
 */
function checkSetup(skillDir: string): string[] {
  const workspaceDir = path.join(os.homedir(), '.openclaw', 'workspace');
  const learningsDir = path.join(workspaceDir, '.learnings');
  const missing: string[] = [];

  // Check .learnings/ directory
  if (!fs.existsSync(learningsDir)) {
    missing.push(`- [ ] 学习记录目录未创建 → \`mkdir -p ${learningsDir}\``);
  } else {
    // Check individual log files
    const files = ['LEARNINGS.md', 'ERRORS.md', 'FEATURE_REQUESTS.md'];
    for (const file of files) {
      if (!fs.existsSync(path.join(learningsDir, file))) {
        const templateSrc = path.join(skillDir, '.learnings', file);
        missing.push(
          `- [ ] \`${file}\` 缺失 → \`cp ${templateSrc} ${path.join(learningsDir, file)}\``
        );
      }
    }
  }

  // Check cron registration marker
  const cronMarker = path.join(learningsDir, '.cron-registered');
  if (!fs.existsSync(cronMarker)) {
    const setupScript = path.join(skillDir, 'scripts', 'setup_cron.sh');
    missing.push(`- [ ] 每日分析 Cron 未注册 → \`bash ${setupScript}\``);
  }

  return missing;
}

/**
 * Build the setup guide content from a list of missing items.
 */
function buildSetupGuide(missingItems: string[]): string {
  return `## Self-Improving Agent 安装引导

检测到以下配置未完成，部分功能无法正常工作：

${missingItems.join('\n')}

请协助用户执行以上命令完成设置。全部完成后，下次会话将不再显示此提醒。`;
}

const handler: HookHandler = async (event) => {
  // Safety checks for event structure
  if (!event || typeof event !== 'object') {
    return;
  }

  // Only handle agent:bootstrap events
  if (event.type !== 'agent' || event.action !== 'bootstrap') {
    return;
  }

  // Safety check for context
  if (!event.context || typeof event.context !== 'object') {
    return;
  }

  // Skip sub-agent sessions to avoid bootstrap issues
  // Sub-agents have sessionKey patterns like "agent:main:subagent:..."
  const sessionKey = event.sessionKey || '';
  if (sessionKey.includes(':subagent:')) {
    return;
  }

  // Ensure bootstrapFiles is available
  if (!Array.isArray(event.context.bootstrapFiles)) {
    return;
  }

  // Check setup completeness and inject guide if needed
  const skillDir = path.resolve(__dirname, '..', '..');
  const missingItems = checkSetup(skillDir);

  if (missingItems.length > 0) {
    event.context.bootstrapFiles.push({
      path: 'SELF_IMPROVEMENT_SETUP_GUIDE.md',
      content: buildSetupGuide(missingItems),
      virtual: true,
    });
  }

  // Always inject the learning reminder
  event.context.bootstrapFiles.push({
    path: 'SELF_IMPROVEMENT_REMINDER.md',
    content: REMINDER_CONTENT,
    virtual: true,
  });
};

export default handler;
