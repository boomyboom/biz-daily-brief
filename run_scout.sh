#!/usr/bin/env bash
# Business-opportunity scout (healthcare/senior) → Obsidian 사업뇌/기회 + Telegram.
set -uo pipefail
REPO="/Applications/BoomyBoom-Biz"; cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }
CLAUDE="${CLAUDE_BIN:-claude}"; MODEL="${SCOUT_MODEL:-sonnet}"
VAULT="${OBSIDIAN_VAULT:-/Users/boomyboom/Documents/Obsidian Vault}"
mkdir -p "$REPO/logs" "$VAULT/20_사업뇌/기회"
TODAY="$(date +%Y-%m-%d)"; LOG="$REPO/logs/scout-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== scout run start (model=$MODEL) ====="
rm -f "$REPO/logs/scout_summary.txt"
PROMPT="$(cat "$REPO/SCOUT_PROMPT.md")

[실행 정보] 볼트 경로: $VAULT / 오늘 날짜: $TODAY"
RUN_OUT="$REPO/logs/scout-claude-$TODAY.out"
"$CLAUDE" --model "$MODEL" -p "$PROMPT" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" >"$RUN_OUT" 2>&1
log "claude exit: $?"; cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  bash "$REPO/send_telegram.sh" "🔒 Claude 로그인 해제됨 — 사업 스카우트 실패. $CLAUDE → /login" >>"$LOG" 2>&1 || true; exit 1
fi
if [ -f "$REPO/logs/scout_summary.txt" ]; then
  bash "$REPO/send_telegram.sh" "🔎 <b>오늘의 사업 기회</b>
$(cat "$REPO/logs/scout_summary.txt")

📓 Obsidian: 20_사업뇌/기회/$TODAY 기회.md" >>"$LOG" 2>&1 && log "요약 전송" || log "전송 실패"
fi
log "===== scout run end ====="
