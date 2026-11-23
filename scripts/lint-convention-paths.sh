#!/usr/bin/env bash
# Fail when a SKILL.md references a convention by bare `../conventions/…`.
#
# A bare relative path resolves against the model's cwd (a worker's worktree),
# not the skill's directory, so it fails at runtime. The harness replaces
# ${CLAUDE_SKILL_DIR} with the skill's absolute directory on load, so every
# reference must carry that prefix. See .claude/skills/conventions/file-writing.md #10.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

out=""
while IFS= read -r line; do
  allowed='\$\{CLAUDE_SKILL_DIR\}/'
  # Strip every prefixed occurrence; anything left is bare.
  if printf '%s' "$line" | sed -E "s#${allowed}\.\./conventions/##g" | grep -q '\.\./conventions/'; then
    out+="$line"$'\n'
  fi
done < <(grep -nE '\.\./conventions/' .claude/skills/*/SKILL.md || true)

if [ -n "$out" ]; then
  echo "Bare ../conventions/ references — prefix each with \${CLAUDE_SKILL_DIR}/:"
  printf '%s' "$out"
  exit 1
fi
echo "OK: every convention reference carries \${CLAUDE_SKILL_DIR}/."
