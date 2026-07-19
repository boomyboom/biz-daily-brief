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
# 새벽 실행: 즉시 발송 안 함(밤에 안 울림). 오류는 아침 다이제스트로.
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  echo "🔒 Claude 로그인 해제로 사업 스카우트 실패 ($CLAUDE → /login)" >> "$REPO/logs/overnight_error.txt"; exit 1
fi
log "요약은 아침 07:45 다이제스트로 전송됨"
log "===== scout run end ====="
