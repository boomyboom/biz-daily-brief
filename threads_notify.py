#!/usr/bin/env python3
"""Send the newest pending Threads draft to Telegram.

- If the draft passed self-review (review_ok: true): schedule AUTO-POST after a
  short cancel window; buttons = [✅ 지금 게시] [❌ 취소]. The listener fires it.
- If self-review flagged it (review_ok: false): require manual approval;
  buttons = [✅ 게시] [❌ 스킵]. No auto-post.
Stores tg_message_id / auto_post_at back into the draft so the listener can
auto-fire and edit the message.
"""
import json
import os
import sys
import glob
import html
import time
import urllib.request
import urllib.parse
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(ROOT, "threads", "queue")
BAD_PUNCT = ("·", "・", "—", "–")
SENSITIVE = (
    "대통령", "국회의원", "정당", "선거", "탄핵", "좌파", "우파",
    "젠더갈등", "남녀갈등", "지역갈등", "인종갈등", "참사", "재난",
    "노조", "파업",
)
DIRECT_ADVICE = ("매수하세요", "매도하세요", "사세요", "팔아야 합니다", "추천 종목", "진입가", "손절가", "익절가", "수익 보장")


def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def esc(s):
    return html.escape(str(s or ""))


def newest_pending():
    files = glob.glob(os.path.join(QUEUE, "pending-*.json"))
    # 이미 자동게시 예약된 것은 제외 (중복 발송 방지)
    files = [f for f in files if not json.load(open(f)).get("auto_post_at")]
    return max(files, key=os.path.getmtime) if files else None


def deterministic_review(draft):
    errors = []
    posts = draft.get("posts") or []
    if not 1 <= len(posts) <= 8:
        errors.append("포스트 수가 1~8개 범위를 벗어남")
    for index, post in enumerate(posts, 1):
        text = str(post or "").strip()
        if not text:
            errors.append(f"{index}번 포스트가 비어 있음")
        if len(text) > 500:
            errors.append(f"{index}번 포스트가 500자 초과")
        if any(mark in text for mark in BAD_PUNCT):
            errors.append(f"{index}번 포스트에 금지 문장부호 포함")
        hit = next((word for word in SENSITIVE if word in text), None)
        if hit:
            errors.append(f"{index}번 포스트에 민감 주제 포함 ({hit})")
        advice = next((word for word in DIRECT_ADVICE if word in text), None)
        if advice:
            errors.append(f"{index}번 포스트에 직접 투자 지시 포함 ({advice})")
    if posts:
        last = str(posts[-1]).strip()
        if last.endswith("?") or re.search(r"(어떻게 생각|무엇인가요|어디인가요|하시나요|인가요)[?.!]*$", last):
            errors.append("마지막 질문 문장 포함")
    return errors


def format_message(draft, auto, delay_min, reason):
    posts = draft.get("posts") or []
    L = ["🧵 <b>스레드 초안</b>"]
    if draft.get("topic"):
        L.append(f"<i>주제: {esc(draft['topic'])}</i>")
    L.append("")
    for i, p in enumerate(posts, 1):
        prefix = f"<b>{i}/{len(posts)}</b> " if len(posts) > 1 else ""
        L.append(f"{prefix}{esc(p)}")
        L.append("")
    L.append("========")
    if auto:
        L.append(f"🕒 <b>{delay_min}분 후 자동 게시</b> 됩니다. 문제 있으면 ❌ 취소를 눌러주세요.")
    else:
        L.append(f"⚠️ <b>자가검열 확인 필요</b>: {esc(reason or '검토 요망')}\n확인 후 ✅ 게시 또는 ❌ 스킵.")
    return "\n".join(L)


def send(token, chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": "true"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    data = urllib.parse.urlencode(payload).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    env = load_env()
    token = env.get("TELEGRAM_APPROVE_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    delay_sec = int(env.get("AUTO_POST_DELAY_SEC", "180"))
    if not token or not chat_id:
        print("ERROR: telegram creds missing", file=sys.stderr)
        return 1
    path = newest_pending()
    if not path:
        print("no pending draft", file=sys.stderr)
        return 1
    with open(path) as f:
        draft = json.load(f)
    fname = os.path.basename(path)
    gate_errors = deterministic_review(draft)
    if gate_errors:
        draft["review_ok"] = False
        draft["review_reason"] = "; ".join(gate_errors)
    auto = bool(draft.get("review_ok")) and not gate_errors
    reason = draft.get("review_reason", "")
    if auto:
        buttons = [[
            {"text": "✅ 지금 게시", "callback_data": f"ok:{fname}"},
            {"text": "❌ 취소", "callback_data": f"cancel:{fname}"},
        ]]
    else:
        buttons = [[
            {"text": "✅ 게시", "callback_data": f"ok:{fname}"},
            {"text": "❌ 스킵", "callback_data": f"skip:{fname}"},
        ]]
    text = format_message(draft, auto, delay_sec // 60, reason)
    res = send(token, chat_id, text, reply_markup={"inline_keyboard": buttons})
    if not res.get("ok"):
        print(f"ERROR: send failed: {res}", file=sys.stderr)
        return 1
    # 자동게시 예약 정보를 초안에 기록 (리스너가 발사·수정)
    draft["tg_message_id"] = res["result"]["message_id"]
    draft["tg_chat_id"] = chat_id
    draft["tg_text"] = text
    if auto:
        draft["auto_post_at"] = int(time.time()) + delay_sec
    json.dump(draft, open(path, "w"), ensure_ascii=False, indent=2)
    # 메일은 스레드 초안이 아니라 복붙용 HTML 글로 보낸다 (사장 요청).
    # 한국장 스레드는 브리핑 메일과 겹치므로 메일을 보내지 않는다.
    # 2026-07-30: 사장 요청으로 [발행용] 메일은 일단 보내지 않음 (코드는 유지, .env에서 재활성화 가능)
    try:
        if env.get("SEND_ARTICLE_MAIL", "0") == "1" and not fname.startswith("pending-kr-"):
            import mailer, piece_to_html
            to_addr = env.get("MAIL_TO")
            if to_addr:
                title, article = piece_to_html.build(draft, piece_to_html.today_brief())
                guide = ("[티스토리 발행 방법]\n"
                         "1. 글쓰기에서 '기본모드'를 'HTML'로 변경\n"
                         "2. 아래 ===== 사이를 전체 복사해서 붙여넣기\n"
                         "3. 다시 '기본모드'로 돌아오면 서식이 적용됩니다\n\n"
                         "=====================================\n")
                mailer.send_mail(to_addr, f"[발행용] {title[:45]}",
                                 guide + article + "\n=====================================\n")
    except Exception as e:
        print(f"mail skipped: {e}")
    print(f"OK: sent {fname} (auto={auto})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
