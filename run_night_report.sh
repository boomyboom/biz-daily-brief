#!/usr/bin/env bash
# Overnight work report (Opus), written at ~07:30 and mailed to the work address.
# The Telegram digest stays as the short version; this is the full account.
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
MODEL="${NIGHT_REPORT_MODEL:-opus}"

mkdir -p "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"
LOG="$REPO/logs/nightreport-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== night report start (model=$MODEL) ====="
rm -f "$REPO/logs/night_report.html"

RUN_OUT="$REPO/logs/nightreport-claude-$TODAY.out"
env -u TELEGRAM_BOT_TOKEN -u TELEGRAM_CHAT_ID -u TELEGRAM_APPROVE_BOT_TOKEN -u THREADS_TOKEN -u MAIL_TO -u NIGHT_REPORT_TO -u OBSIDIAN_VAULT "$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/NIGHT_REPORT_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  echo "🔒 Claude 로그인 해제로 야근 보고서 생성 실패" >> "$REPO/logs/overnight_error.txt"
  exit 1
fi

if [ -f "$REPO/logs/night_report.html" ]; then
  "$PYTHON" "$REPO/send_night_report.py" >>"$LOG" 2>&1 && log "야근 보고 메일 발송 OK" || log "야근 보고 메일 발송 실패"
else
  log "WARN: 보고서 파일이 생성되지 않음"
fi

log "===== night report end ====="
