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
# 새벽 실행: 텔레그램 즉시 발송 안 함. 요약 파일만 남기면 07:45 다이제스트가 보냄.
"$PYTHON" "$REPO/analyze_threads.py" >>"$LOG" 2>&1 && log "분석 완료(요약은 아침 다이제스트로)" || log "분석 실패"
log "===== analytics run end ====="
