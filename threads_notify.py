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

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(ROOT, "threads", "queue")


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
    L.append("————————")
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
    auto = bool(draft.get("review_ok"))          # 자가검열 통과 시에만 자동
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
    print(f"OK: sent {fname} (auto={auto})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
