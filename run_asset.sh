#!/usr/bin/env bash
# Weekly premium asset (report / lead magnet) → products/ + Telegram summary.
# NOT auto-published — a draft for the user to refine and sell.
set -uo pipefail
REPO="/Applications/BoomyBoom-Biz"; cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }
CLAUDE="${CLAUDE_BIN:-claude}"; MODEL="${ASSET_MODEL:-opus}"
mkdir -p "$REPO/logs" "$REPO/products"
TODAY="$(date +%Y-%m-%d)"; LOG="$REPO/logs/asset-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== asset run start (model=$MODEL) ====="
rm -f "$REPO/logs/asset_summary.txt"
RUN_OUT="$REPO/logs/asset-claude-$TODAY.out"
"$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/ASSET_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
log "claude exit: $?"; cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  bash "$REPO/send_telegram.sh" "🔒 Claude 로그인 해제됨 — 수익 자산 제작 실패. $CLAUDE → /login" >>"$LOG" 2>&1 || true; exit 1
fi
if [ -f "$REPO/logs/asset_summary.txt" ]; then
  bash "$REPO/send_telegram.sh" "💎 <b>이번 주 수익 자산 초안</b>
$(cat "$REPO/logs/asset_summary.txt")

📁 $REPO/products/ 에 저장됨 (검토·판매용)" >>"$LOG" 2>&1 && log "요약 전송" || log "전송 실패"
fi
log "===== asset run end ====="
