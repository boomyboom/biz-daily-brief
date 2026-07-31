#!/usr/bin/env bash
# Weekend story thread (Sun 10:30). Writes one researched story as a thread and
# lets the normal auto-post flow publish it after the cancel window.
set -uo pipefail

REPO="/Applications/BoomyBoom-Biz"
cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }

PYTHON="${PYTHON_BIN:-/usr/bin/python3}"
CLAUDE="${CLAUDE_BIN:-claude}"
MODEL="${THREADS_MODEL:-sonnet}"
mkdir -p "$REPO/threads/queue" "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"
LOG="$REPO/logs/story-thread-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== story thread start ====="

AVAIL=$("$PYTHON" -c "
import json
try:
    d=json.load(open('$REPO/stories/candidates.json'))
    print(sum(1 for c in d.get('candidates',[]) if not c.get('used')))
except Exception: print(0)
")
if [ "$AVAIL" = "0" ]; then
  log "사용 가능한 후보 없음, 건너뜀"; exit 0
fi

DELAY=$(( RANDOM % 181 + 120 ))
log "랜덤 지연 ${DELAY}초"
sleep "$DELAY"

RUN_OUT="$REPO/logs/story-thread-claude-$TODAY.out"
BEFORE="$(ls "$REPO/threads/queue"/pending-story-*.json 2>/dev/null | wc -l | tr -d ' ')"
"$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/threads/STORY_THREAD_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  bash "$REPO/send_telegram.sh" "🔒 Claude 로그인 해제됨, 주말 스토리 스레드 실패" >>"$LOG" 2>&1 || true
  exit 1
fi

"$PYTHON" "$REPO/strip_closing_question.py" >>"$LOG" 2>&1 || true

AFTER="$(ls "$REPO/threads/queue"/pending-story-*.json 2>/dev/null | wc -l | tr -d ' ')"
if [ "$AFTER" -gt "$BEFORE" ]; then
  log "새 스토리 초안 생성, 텔레그램 전송"
  "$PYTHON" "$REPO/threads_notify.py" >>"$LOG" 2>&1 && log "sent OK" || log "send FAILED"
else
  log "새 초안 없음"
fi
log "===== story thread end ====="
