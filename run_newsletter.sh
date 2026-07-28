#!/usr/bin/env bash
# Dedicated newsletter pass (Opus). The daily brief run produces a lot at once,
# which left the newsletter thin; this rewrites it as a proper long-form piece.
set -uo pipefail

REPO="/Applications/BoomyBoom-Biz"
cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }

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
"$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/NEWSLETTER_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  send_alert "🔒 Claude 로그인 해제됨, 뉴스레터 집필 실패. $CLAUDE 실행 후 /login"; exit 1
fi

NL="$REPO/posts/$TODAY/newsletter.md"
if [ -f "$NL" ]; then
  LEN=$("$PYTHON" -c "print(len(open('$NL').read()))")
  log "뉴스레터 분량: ${LEN}자"
  if [ "$LEN" -lt 2500 ]; then
    log "WARN: 목표 분량(3000자) 미달"
  fi
else
  log "WARN: 뉴스레터 파일 없음"
fi

log "===== newsletter run end ====="
