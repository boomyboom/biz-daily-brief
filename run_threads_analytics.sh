#!/usr/bin/env bash
# Nightly Threads performance analysis → growth_insights.md + Telegram summary.
set -uo pipefail
REPO="/Applications/BoomyBoom-Biz"; cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }
PYTHON="${PYTHON_BIN:-/usr/bin/python3}"
mkdir -p "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"; LOG="$REPO/logs/analytics-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== analytics run start ====="
"$PYTHON" "$REPO/analyze_threads.py" >>"$LOG" 2>&1 && log "분석 완료" || { log "분석 실패"; exit 1; }
if [ -f "$REPO/logs/analytics_summary.txt" ]; then
  bash "$REPO/send_telegram.sh" "$(cat "$REPO/logs/analytics_summary.txt")" >>"$LOG" 2>&1 && log "요약 전송" || log "전송 실패"
fi
log "===== analytics run end ====="
