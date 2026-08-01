#!/usr/bin/env bash
# Biz insight brief runner — invoked by launchd at 12:00 KST.
# Invokes Claude Code headless to generate the brief + newsletter + variants, then Telegram.
# 실행 도중 이 파일이 수정돼도 bash 가 엉뚱한 위치를 읽지 않도록
# 전체를 함수로 감싸 미리 파싱시킨다.
main() {
  set -uo pipefail

  REPO="/Applications/BoomyBoom-Biz"
  cd "$REPO" || exit 1

  # ---- load .env ----
  if [ -f "$REPO/.env" ]; then
    set -a
    source "$REPO/.env"
    set +a
  fi

  # ---- resolve binaries (launchd has a minimal PATH) ----
  PYTHON="${PYTHON_BIN:-/usr/bin/python3}"
  GIT="${GIT_BIN:-/usr/bin/git}"
  CLAUDE="${CLAUDE_BIN:-claude}"

  # ---- logging ----
  mkdir -p "$REPO/logs"
  TODAY="$(date +%Y-%m-%d)"
  LOG="$REPO/logs/$TODAY.log"
  log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
  send_alert() { bash "$REPO/send_telegram.sh" "$1" >>"$LOG" 2>&1 && log "alert sent" || log "alert send FAILED"; }
  ALERTED=0

  log "===== biz brief run start ====="

  # ---- record git state before ----
  REV_BEFORE="$("$GIT" rev-parse HEAD 2>/dev/null || echo none)"

  # ---- invoke Claude Code headless ----
  RUN_OUT="$REPO/logs/claude-$TODAY.out"
  if ! command -v "$CLAUDE" >/dev/null 2>&1 && [ ! -x "$CLAUDE" ]; then
    log "ERROR: claude CLI not found (set CLAUDE_BIN in .env)."
    send_alert "⚠️ BoomyBoom 비즈 브리핑 실패
  claude CLI를 찾을 수 없어요. .env의 CLAUDE_BIN 경로를 확인해주세요."
    ALERTED=1
  else
    # 빈손으로 끝나는 경우가 있어 한 번 재시도한다
    for attempt in 1 2; do
      log "invoking Claude Code headless… (시도 $attempt)"
      env -u TELEGRAM_BOT_TOKEN -u TELEGRAM_CHAT_ID -u TELEGRAM_APPROVE_BOT_TOKEN \
        -u THREADS_TOKEN -u MAIL_TO -u NIGHT_REPORT_TO -u OBSIDIAN_VAULT \
        "$CLAUDE" -p "$(cat "$REPO/BRIEF_PROMPT.md")" \
        --allowedTools "Task,Bash,WebSearch,WebFetch,Read,Write,Edit,Glob,Grep" \
        >"$RUN_OUT" 2>&1
      log "claude exit status: $?"
      cat "$RUN_OUT" >>"$LOG"
      [ -f "$REPO/briefs/$TODAY.json" ] && break
      if [ "$attempt" = "1" ]; then log "생성 안 됨, 60초 뒤 재시도"; sleep 60; fi
    done

    # 로그인/인증 해제 감지 → 텔레그램 경고
    if [ ! -f "$REPO/briefs/$TODAY.json" ] && grep -qiE "Not logged in|Please run /login|Invalid API key|authentication_error|Unauthorized|please log in" "$RUN_OUT"; then
      log "DETECTED: Claude 로그인/인증 문제"
      send_alert "🔒 Claude 로그인이 해제된 것 같아요.
  오늘($TODAY) 비즈 인사이트 브리핑이 생성되지 않았습니다.

  터미널에서 재로그인 해주세요:
    $CLAUDE
  → 실행한 뒤 /login 입력

  재로그인 후 수동 실행: bash $REPO/run_daily_brief.sh"
      ALERTED=1
    fi
  fi

  # ---- safety: refresh manifest ----
  "$PYTHON" "$REPO/cleanup_old_briefs.py" >>"$LOG" 2>&1 || log "cleanup failed"

  # ---- 문장부호 정리 (가운뎃점, 긴 줄표 제거) ----
  if [ -f "$REPO/briefs/$TODAY.json" ]; then
    "$PYTHON" "$REPO/humanize_brief.py" "$REPO/briefs/$TODAY.json" >>"$LOG" 2>&1 || log "humanize 실패"
  fi

  if [ -f "$REPO/briefs/$TODAY.json" ]; then
    if ! "$PYTHON" "$REPO/validate_biz_brief.py" "$REPO/briefs/$TODAY.json" >>"$LOG" 2>&1; then
      log "ERROR: 비즈 브리핑 발행 전 검증 실패"
      send_alert "⚠️ 오늘($TODAY) 비즈 브리핑이 품질 검증을 통과하지 못해 발행을 멈췄어요.\n로그: $LOG"
      exit 1
    fi
    log "비즈 브리핑 발행 전 검증 OK"
  fi

  # ---- Obsidian 제2의 뇌 기록 ----
  if [ -f "$REPO/briefs/$TODAY.json" ]; then
    OBSIDIAN_FAILED=0
    "$PYTHON" "$REPO/brief_to_obsidian.py" "$REPO/briefs/$TODAY.json" >>"$LOG" 2>&1 && log "obsidian 기록 OK" || { log "obsidian 기록 일부 또는 전체 실패"; OBSIDIAN_FAILED=1; }
    # 위키 색인과 로그 갱신
    "$PYTHON" "$REPO/wiki_tools.py" index >>"$LOG" 2>&1 || log "wiki index 갱신 실패"
    "$PYTHON" "$REPO/wiki_tools.py" log "비즈 브리핑 $TODAY 기록" >>"$LOG" 2>&1 || log "wiki log 갱신 실패"
  fi

  # ---- 뉴스레터 심화 집필 (Opus 별도 패스) ----
  NEWSLETTER_OK=1
  bash "$REPO/run_newsletter.sh" "$TODAY" >>"$LOG" 2>&1 && log "뉴스레터 집필 OK" || { log "뉴스레터 집필 또는 검증 실패"; NEWSLETTER_OK=0; }

  # ---- 티스토리 발행용 HTML 변환 (Open API 종료로 복붙 발행) ----
  # 깊이 있는 뉴스레터를 우선 발행용으로 쓰고, 없으면 blog.md 로 폴백
  SRC="$REPO/posts/$TODAY/newsletter.md"
  [ -f "$SRC" ] || SRC="$REPO/posts/$TODAY/blog.md"
  if [ -f "$SRC" ] && [ "$NEWSLETTER_OK" = "1" ]; then
    "$PYTHON" "$REPO/blog_to_html.py" "$SRC" >>"$LOG" 2>&1 && log "발행용 HTML 생성 OK ($(basename "$SRC"))" || log "발행용 HTML 변환 실패"
    # Mail.app 계정이 설정돼 있으면 본인 주소로 발송 (없으면 조용히 건너뜀)
    "$PYTHON" "$REPO/send_blog_mail.py" "$TODAY" >>"$LOG" 2>&1 && log "블로그 메일 발송 OK" || log "블로그 메일 발송 skip/실패 (Mail.app 계정 확인)"
  fi

  # 모델 초안이 아니라 뉴스레터와 HTML까지 완성된 최종본을 GitHub에 반영한다.
  if [ -f "$REPO/briefs/$TODAY.json" ]; then
    PUBLISH_PATHS=("briefs/$TODAY.json" "briefs/seen_urls.json" "briefs/manifest.json")
    [ "$NEWSLETTER_OK" = "1" ] && PUBLISH_PATHS+=("posts/$TODAY")
    if "$GIT" add -- "${PUBLISH_PATHS[@]}" >>"$LOG" 2>&1; then
      if ! "$GIT" diff --cached --quiet -- "${PUBLISH_PATHS[@]}"; then
        if "$GIT" commit --only -m "brief: $TODAY (validated)" -- "${PUBLISH_PATHS[@]}" >>"$LOG" 2>&1; then
          log "최종 산출물 커밋 OK"
          "$GIT" push origin HEAD >>"$LOG" 2>&1 && log "비즈 사이트 반영 요청 OK" || log "GitHub push 실패"
        else
          log "최종 산출물 커밋 실패, push 생략"
        fi
      fi
    else
      log "git add 실패"
    fi
  fi

  # ---- record git state after ----
  REV_AFTER="$("$GIT" rev-parse HEAD 2>/dev/null || echo none)"

  # ---- safety net: 오늘 브리핑이 아예 안 만들어졌으면 경고 ----
  if [ ! -f "$REPO/briefs/$TODAY.json" ] && [ "$ALERTED" = "0" ]; then
    log "WARN: 오늘($TODAY) 브리핑 파일이 생성되지 않음"
    send_alert "⚠️ BoomyBoom 비즈: 오늘($TODAY) 브리핑이 생성되지 않았어요.
  로그 확인: $REPO/logs/$TODAY.log"
    ALERTED=1
  fi

  # ---- notify only if content changed (or NOTIFY_ALWAYS=1) ----
  if [ "$REV_BEFORE" != "$REV_AFTER" ] || [ "${NOTIFY_ALWAYS:-0}" = "1" ]; then
    log "changes detected → sending Telegram push"
    "$PYTHON" "$REPO/telegram_notify.py" >>"$LOG" 2>&1 && log "telegram push OK" || log "telegram push FAILED"
  else
    log "no changes ($REV_BEFORE) — skipping Telegram push"
  fi

  log "===== biz brief run end ====="
  [ "${OBSIDIAN_FAILED:-0}" = "0" ] || return 2

}

main "$@"
