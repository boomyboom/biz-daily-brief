#!/usr/bin/env bash
# Weekly premium asset (report / lead magnet) → products/ + Telegram summary.
# NOT auto-published — a draft for the user to refine and sell.
set -uo pipefail
REPO="/Applications/BoomyBoom-Biz"; cd "$REPO" || exit 1
if [ -f "$REPO/.env" ]; then
  set -a
  source "$REPO/.env"
  set +a
fi
CLAUDE="${CLAUDE_BIN:-claude}"; MODEL="${ASSET_MODEL:-opus}"
mkdir -p "$REPO/logs" "$REPO/products"
TODAY="$(date +%Y-%m-%d)"; LOG="$REPO/logs/asset-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== asset run start (model=$MODEL) ====="
rm -f "$REPO/logs/asset_summary.txt"
RUN_OUT="$REPO/logs/asset-claude-$TODAY.out"
env -u TELEGRAM_BOT_TOKEN -u TELEGRAM_CHAT_ID -u TELEGRAM_APPROVE_BOT_TOKEN -u THREADS_TOKEN -u MAIL_TO -u NIGHT_REPORT_TO -u OBSIDIAN_VAULT "$CLAUDE" --model "$MODEL" -p "$(cat "$REPO/ASSET_PROMPT.md")" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
log "claude exit: $?"; cat "$RUN_OUT" >>"$LOG"
# 새벽 실행: 즉시 발송 안 함. 오류는 아침 다이제스트로.
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  echo "🔒 Claude 로그인 해제로 수익 자산 제작 실패 ($CLAUDE → /login)" >> "$REPO/logs/overnight_error.txt"; exit 1
fi
log "요약은 아침 07:45 다이제스트로 전송됨"
log "===== asset run end ====="
