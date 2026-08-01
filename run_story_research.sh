#!/usr/bin/env bash
# Weekend story research (Sat 03:00, Opus). Uses idle overnight capacity to
# find and fact-check narrative candidates for the Sunday post.
set -uo pipefail

REPO="/Applications/BoomyBoom-Biz"
cd "$REPO" || exit 1
if [ -f "$REPO/.env" ]; then
  set -a
  source "$REPO/.env"
  set +a
fi

CLAUDE="${CLAUDE_BIN:-claude}"
MODEL="${STORY_RESEARCH_MODEL:-opus}"
mkdir -p "$REPO/logs" "$REPO/stories"
TODAY="$(date +%Y-%m-%d)"
LOG="$REPO/logs/story-research-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== story research start (model=$MODEL) ====="
RUN_OUT="$REPO/logs/story-research-claude-$TODAY.out"
env -u TELEGRAM_BOT_TOKEN -u TELEGRAM_CHAT_ID -u TELEGRAM_APPROVE_BOT_TOKEN -u THREADS_TOKEN -u MAIL_TO -u NIGHT_REPORT_TO -u OBSIDIAN_VAULT "$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/STORY_RESEARCH_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  echo "🔒 Claude 로그인 해제로 스토리 리서치 실패" >> "$REPO/logs/overnight_error.txt"
  exit 1
fi
N=$(/usr/bin/python3 -c "
import json
try:
    d=json.load(open('$REPO/stories/candidates.json'))
    print(sum(1 for c in d.get('candidates',[]) if not c.get('used')))
except Exception: print(0)
")
log "미사용 후보: ${N}건"
log "===== story research end ====="
