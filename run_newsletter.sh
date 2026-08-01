#!/usr/bin/env bash
# Dedicated newsletter pass (Opus). The daily brief run produces a lot at once,
# which left the newsletter thin; this rewrites it as a proper long-form piece.
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
MODEL="${NEWSLETTER_MODEL:-opus}"

mkdir -p "$REPO/logs"
TODAY="${1:-$(date +%Y-%m-%d)}"
LOG="$REPO/logs/newsletter-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
send_alert() { bash "$REPO/send_telegram.sh" "$1" >>"$LOG" 2>&1 || true; }

log "===== newsletter run start (model=$MODEL) ====="

if [ ! -f "$REPO/briefs/$TODAY.json" ]; then
  log "오늘($TODAY) 비즈 브리핑 없음, 건너뜀"; exit 0
fi

RUN_OUT="$REPO/logs/newsletter-claude-$TODAY.out"
NL="$REPO/posts/$TODAY/newsletter.md"
OLD_MTIME=0
[ ! -f "$NL" ] || OLD_MTIME="$(stat -f %m "$NL" 2>/dev/null || echo 0)"
env -u TELEGRAM_BOT_TOKEN -u TELEGRAM_CHAT_ID -u TELEGRAM_APPROVE_BOT_TOKEN \
  -u THREADS_TOKEN -u MAIL_TO -u NIGHT_REPORT_TO -u OBSIDIAN_VAULT \
  "$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/NEWSLETTER_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
CLAUDE_STATUS=$?
log "claude exit: $CLAUDE_STATUS"
cat "$RUN_OUT" >>"$LOG"
if [ "$CLAUDE_STATUS" -ne 0 ]; then
  send_alert "⚠️ 뉴스레터 생성 명령이 실패했어요. 기존 원고는 재사용하지 않습니다. 로그: $LOG"
  exit 1
fi
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  send_alert "🔒 Claude 로그인 해제됨, 뉴스레터 집필 실패. $CLAUDE 실행 후 /login"; exit 1
fi

if [ -f "$NL" ]; then
  NEW_MTIME="$(stat -f %m "$NL" 2>/dev/null || echo 0)"
  if [ "$NEW_MTIME" -le "$OLD_MTIME" ]; then
    log "ERROR: 이번 실행에서 뉴스레터 파일이 새로 작성되지 않음"
    exit 1
  fi
  "$PYTHON" "$REPO/validate_newsletter.py" "$NL" >>"$LOG" 2>&1 || { log "ERROR: 뉴스레터 품질 검증 실패"; exit 1; }
  log "뉴스레터 품질 검증 OK"
else
  log "WARN: 뉴스레터 파일 없음"
  exit 1
fi

log "===== newsletter run end ====="
