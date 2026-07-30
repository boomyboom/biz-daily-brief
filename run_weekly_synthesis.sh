#!/usr/bin/env bash
# Weekly synthesis — Opus reads the week's Obsidian notes, writes a synthesis
# note (patterns/relationships) to 30_종합/, and sends a Telegram summary.
set -uo pipefail

REPO="/Applications/BoomyBoom-Biz"
cd "$REPO" || exit 1
[ -f "$REPO/.env" ] && { set -a; source "$REPO/.env"; set +a; }

PYTHON="${PYTHON_BIN:-/usr/bin/python3}"
CLAUDE="${CLAUDE_BIN:-claude}"
MODEL="${SYNTHESIS_MODEL:-opus}"          # 복잡한 분석 → Opus
VAULT="${OBSIDIAN_VAULT:-/Users/boomyboom/Documents/Obsidian Vault}"

mkdir -p "$REPO/logs"
TODAY="$(date +%Y-%m-%d)"
WEEK="$(date +%Y-W%V)"
START="$(date -v-6d +%Y-%m-%d 2>/dev/null || date -d '6 days ago' +%Y-%m-%d)"
LOG="$REPO/logs/synthesis-$TODAY.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== weekly synthesis start (model=$MODEL, $START~$TODAY) ====="

if ! command -v "$CLAUDE" >/dev/null 2>&1 && [ ! -x "$CLAUDE" ]; then
  log "ERROR: claude CLI not found"; exit 1
fi

PROMPT="$(cat "$REPO/WIKI_MAINTAIN_PROMPT.md")

[실행 정보]
- 볼트 경로: $VAULT
- 분석 기간: $START ~ $TODAY
- 주차: $WEEK
- 저장 파일명: 30_종합/$WEEK 주간종합.md"

RUN_OUT="$REPO/logs/synthesis-claude-$TODAY.out"
rm -f "$REPO/logs/last_synthesis_summary.txt"
"$CLAUDE" --model "$MODEL" -p "$PROMPT" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep" >"$RUN_OUT" 2>&1
log "claude exit: $?"
cat "$RUN_OUT" >>"$LOG"
if grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized" "$RUN_OUT"; then
  bash "$REPO/send_telegram.sh" "🔒 Claude 로그인 해제됨 — 주간 종합 실패. $CLAUDE → /login" >>"$LOG" 2>&1 || true
  exit 1
fi

# 텔레그램 요약 발송
SUMM="$REPO/logs/last_synthesis_summary.txt"
if [ -f "$SUMM" ]; then
  MSG="🗓 <b>주간 종합</b> ($START~$TODAY)
$(cat "$SUMM")

📓 Obsidian: 30_종합/$WEEK 주간종합.md"
  bash "$REPO/send_telegram.sh" "$MSG" >>"$LOG" 2>&1 && log "텔레그램 요약 전송" || log "요약 전송 실패"
else
  log "요약 파일 없음 — 전송 생략"
fi

log "===== weekly synthesis end ====="
