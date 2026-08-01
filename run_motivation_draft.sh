#!/usr/bin/env bash
# Motivational insight-list Threads draft (Sonnet, verified quotes only).
# Self-review + polish, then Telegram (auto-post with cancel window). ~2x/week.
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

mkdir -p "$REPO/threads/queue" "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"
LOG="$REPO/logs/motivation-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
send_alert() { bash "$REPO/send_telegram.sh" "$1" >>"$LOG" 2>&1 || true; }

log "===== motivation draft run start (model=$MODEL) ====="

RUN_OUT="$REPO/logs/motivation-claude-$TODAY.out"
BEFORE="$(ls "$REPO/threads/queue"/pending-mot-*.json 2>/dev/null | wc -l | tr -d ' ')"

if ! command -v "$CLAUDE" >/dev/null 2>&1 && [ ! -x "$CLAUDE" ]; then
  log "ERROR: claude CLI not found"; send_alert "⚠️ 동기부여 초안 실패: claude CLI 없음"; exit 1
fi

log "generating…"
env -u TELEGRAM_BOT_TOKEN -u TELEGRAM_CHAT_ID -u TELEGRAM_APPROVE_BOT_TOKEN -u THREADS_TOKEN -u MAIL_TO -u NIGHT_REPORT_TO -u OBSIDIAN_VAULT "$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/threads/MOTIVATION_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  send_alert "🔒 Claude 로그인 해제됨 — 동기부여 초안 실패. $CLAUDE → /login"; exit 1
fi

# 문장 다듬기(·, — 제거 + 마지막 질문 제거)
"$PYTHON" "$REPO/strip_closing_question.py" >>"$LOG" 2>&1 || true

AFTER="$(ls "$REPO/threads/queue"/pending-mot-*.json 2>/dev/null | wc -l | tr -d ' ')"
if [ "$AFTER" -gt "$BEFORE" ]; then
  log "새 초안 생성 → 텔레그램 전송"
  "$PYTHON" "$REPO/threads_notify.py" >>"$LOG" 2>&1 && log "sent OK" || log "send FAILED"
else
  log "새 초안 없음 — 전송 생략"
fi
log "===== motivation draft run end ====="
