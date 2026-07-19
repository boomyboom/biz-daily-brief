#!/usr/bin/env bash
# Market brief -> Threads draft. Summarizes today's market brief into a Threads
# post (Sonnet, informational only), sends to Telegram (approve bot). ~08:20 KST.
set -uo pipefail

REPO="/Applications/BoomyBoom-Biz"
MARKET_REPO="/Applications/BoomyBoom"
cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }

PYTHON="${PYTHON_BIN:-/usr/bin/python3}"
CLAUDE="${CLAUDE_BIN:-claude}"
MODEL="${THREADS_MODEL:-sonnet}"

mkdir -p "$REPO/threads/queue" "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"
LOG="$REPO/logs/market-threads-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
send_alert() { bash "$REPO/send_telegram.sh" "$1" >>"$LOG" 2>&1 || true; }

log "===== market->threads run start ====="

# 오늘 시장 브리핑이 있어야 함 (없으면 휴장/미생성 → 건너뜀)
if [ ! -f "$MARKET_REPO/briefs/$TODAY.json" ]; then
  log "오늘($TODAY) 시장 브리핑 없음 — 건너뜀"; exit 0
fi

RUN_OUT="$REPO/logs/market-threads-claude-$TODAY.out"
BEFORE="$(ls "$REPO/threads/queue"/pending-mkt-*.json 2>/dev/null | wc -l | tr -d ' ')"

if ! command -v "$CLAUDE" >/dev/null 2>&1 && [ ! -x "$CLAUDE" ]; then
  log "ERROR: claude CLI not found"; send_alert "⚠️ 시장→스레드 실패: claude CLI 없음"; exit 1
fi

log "generating (model=$MODEL)…"
"$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/threads/MARKET_THREADS_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  send_alert "🔒 Claude 로그인 해제됨 — 시장 스레드 초안 실패. $CLAUDE → /login"; exit 1
fi

# 마지막 질문 제거 (안전장치)
"$PYTHON" "$REPO/strip_closing_question.py" >>"$LOG" 2>&1 || true

AFTER="$(ls "$REPO/threads/queue"/pending-mkt-*.json 2>/dev/null | wc -l | tr -d ' ')"
if [ "$AFTER" -gt "$BEFORE" ]; then
  log "새 시장 초안 생성 → 텔레그램 전송"
  "$PYTHON" "$REPO/threads_notify.py" >>"$LOG" 2>&1 && log "sent OK" || log "send FAILED"
else
  log "새 초안 없음 — 전송 생략"
fi
log "===== market->threads run end ====="
