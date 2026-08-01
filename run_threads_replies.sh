#!/usr/bin/env bash
# Threads reply engine — fetch new comments, draft replies (Sonnet), send to
# Telegram (approve bot) for one-tap approval. Invoked by launchd a few times/day.
set -uo pipefail

REPO="/Applications/BoomyBoom-Biz"
cd "$REPO" || exit 1
if [ -f "$REPO/.env" ]; then
  set -a
  source "$REPO/.env"
  set +a
fi

PYTHON="${PYTHON_BIN:-/usr/bin/python3}"
CLAUDE="${CLAUDE_BIN:-claude}"
MODEL="${THREADS_MODEL:-sonnet}"

mkdir -p "$REPO/threads/replies_queue" "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"
LOG="$REPO/logs/replies-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
send_alert() { bash "$REPO/send_telegram.sh" "$1" >>"$LOG" 2>&1 || true; }

log "===== reply engine run start ====="

# 1) 새 댓글 수집
OUT="$("$PYTHON" "$REPO/fetch_replies.py" 2>>"$LOG")"; log "$OUT"
if echo "$OUT" | grep -q "no new comments"; then
  log "새 댓글 없음 — 종료"; log "===== end ====="; exit 0
fi

# 2) 답글 초안 (Sonnet)
RUN_OUT="$REPO/logs/replies-claude-$TODAY.out"
env -u TELEGRAM_BOT_TOKEN -u TELEGRAM_CHAT_ID -u TELEGRAM_APPROVE_BOT_TOKEN -u THREADS_TOKEN -u MAIL_TO -u NIGHT_REPORT_TO -u OBSIDIAN_VAULT "$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/threads/REPLIES_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  send_alert "🔒 Claude 로그인 해제됨 — 답글 초안 생성 실패. $CLAUDE → /login"
  exit 1
fi

# 3) 초안 인박스 정리 + 문장 다듬기(·, — 제거)
rm -f "$REPO/threads/replies_queue"/inbox-*.json
"$PYTHON" "$REPO/strip_closing_question.py" >>"$LOG" 2>&1 || true

# 4) 텔레그램으로 승인 요청
"$PYTHON" "$REPO/replies_notify.py" >>"$LOG" 2>&1 && log "답글 초안 전송" || log "전송 실패"

log "===== reply engine run end ====="
