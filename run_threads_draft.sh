#!/usr/bin/env bash
# Threads draft runner — generates ONE Threads post draft (Sonnet, cheap) and
# sends it to Telegram for one-tap review. Invoked by launchd ~3-4x/day.
set -uo pipefail

REPO="/Applications/BoomyBoom-Biz"
cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }

PYTHON="${PYTHON_BIN:-/usr/bin/python3}"
CLAUDE="${CLAUDE_BIN:-claude}"
# 루틴 작업이라 저렴한 모델 사용. 필요시 .env에서 THREADS_MODEL 변경.
MODEL="${THREADS_MODEL:-sonnet}"

mkdir -p "$REPO/threads/queue" "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"
LOG="$REPO/logs/threads-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
send_alert() { bash "$REPO/send_telegram.sh" "$1" >>"$LOG" 2>&1 || true; }

log "===== threads draft run start (model=$MODEL) ====="

# 봇 티 안 나게: 정각 대신 매번 2~5분 랜덤 지연 후 진행
DELAY=$(( RANDOM % 181 + 120 ))
log "랜덤 지연 ${DELAY}초 후 시작"
sleep "$DELAY"

RUN_OUT="$REPO/logs/threads-claude-$TODAY.out"
BEFORE="$(ls "$REPO/threads/queue"/pending-*.json 2>/dev/null | wc -l | tr -d ' ')"

if ! command -v "$CLAUDE" >/dev/null 2>&1 && [ ! -x "$CLAUDE" ]; then
  log "ERROR: claude CLI not found."
  send_alert "⚠️ 스레드 초안 실패: claude CLI를 찾을 수 없어요 (.env CLAUDE_BIN 확인)."
  exit 1
fi

log "generating draft…"
"$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/threads/THREADS_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" \
  >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"

# 로그인 해제 감지
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  log "DETECTED: Claude 로그인/인증 문제"
  send_alert "🔒 Claude 로그인이 해제된 것 같아요. 스레드 초안 생성 실패.
재로그인: $CLAUDE → /login"
  exit 1
fi

# 마지막 질문 제거 (안전장치)
"$PYTHON" "$REPO/strip_closing_question.py" >>"$LOG" 2>&1 || true

AFTER="$(ls "$REPO/threads/queue"/pending-*.json 2>/dev/null | wc -l | tr -d ' ')"
if [ "$AFTER" -gt "$BEFORE" ]; then
  log "새 초안 생성됨 → 텔레그램 전송"
  "$PYTHON" "$REPO/threads_notify.py" >>"$LOG" 2>&1 && log "sent OK" || log "send FAILED"
else
  log "새 초안 없음 — 전송 생략"
fi

log "===== threads draft run end ====="
