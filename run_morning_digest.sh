#!/usr/bin/env bash
# Morning digest (07:45): bundle overnight job results into ONE Telegram message
# so nothing pings during the night. Sends then clears the summary files.
set -uo pipefail
REPO="/Applications/BoomyBoom-Biz"; cd "$REPO" || exit 1
if [ -f "$REPO/.env" ]; then
  set -a
  source "$REPO/.env"
  set +a
fi
mkdir -p "$REPO/logs"
LOG="$REPO/logs/digest-$(date +%Y-%m-%d).log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

A="$REPO/logs/analytics_summary.txt"
S="$REPO/logs/scout_summary.txt"
D="$REPO/logs/asset_summary.txt"
E="$REPO/logs/overnight_error.txt"

MSG="🌙 밤사이 야근 결과"
HAS=0
if [ -f "$A" ]; then MSG="$MSG

$(cat "$A")"; HAS=1; fi
if [ -f "$S" ]; then MSG="$MSG

🔎 오늘의 사업 기회
$(cat "$S")
📓 Obsidian: 20_사업뇌/기회/"; HAS=1; fi
if [ -f "$D" ]; then MSG="$MSG

💎 이번 주 수익 자산 초안
$(cat "$D")
📁 products/ 에 저장됨 (검토·판매용)"; HAS=1; fi
if [ -f "$E" ]; then MSG="$MSG

⚠️ 밤사이 오류
$(cat "$E")"; HAS=1; fi

if [ "$HAS" = "0" ]; then
  log "밤사이 결과 없음 — 전송 생략"; exit 0
fi

bash "$REPO/send_telegram.sh" "$MSG" >>"$LOG" 2>&1 && log "다이제스트 전송" || log "전송 실패"
# 보낸 요약은 정리 (다음 날 중복 방지)
rm -f "$A" "$S" "$D" "$E"
log "===== digest done ====="
