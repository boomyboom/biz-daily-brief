#!/usr/bin/env python3
"""Send pending Threads reply-drafts to Telegram (approve bot) for one-tap review."""
import json
import os
import sys
import glob
import html
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(ROOT, "threads", "replies_queue")


def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def esc(s):
    return html.escape(str(s or ""))


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
    if not token or not chat_id:
        print("ERROR: telegram creds missing", file=sys.stderr)
        return 1

    files = sorted(glob.glob(os.path.join(QUEUE, "pending-reply-*.json")))
    if not files:
        print("no pending reply drafts")
        return 0

    sent = 0
    for path in files:
        with open(path) as f:
            d = json.load(f)
        fname = os.path.basename(path)
        draft = (d.get("draft") or "").strip()
        L = ["💬 <b>새 댓글 · 답글 초안</b>"]
        L.append(f"<i>@{esc(d.get('comment_user'))} 님 댓글:</i>")
        L.append(f"“{esc(d.get('comment_text'))}”")
        L.append("")
        if draft:
            L.append("<b>↩︎ 답글 초안:</b>")
            L.append(esc(draft))
            buttons = [[
                {"text": "✅ 답글 게시", "callback_data": f"rok:{fname}"},
                {"text": "❌ 무시", "callback_data": f"rskip:{fname}"},
            ]]
        else:
            L.append(f"⚠️ <i>자동 스킵 권장: {esc(d.get('flag') or '부적절/민감으로 판단')}</i>")
            buttons = [[{"text": "❌ 무시(확인)", "callback_data": f"rskip:{fname}"}]]
        res = send(token, chat_id, "\n".join(L), reply_markup={"inline_keyboard": buttons})
        if res.get("ok"):
            sent += 1
    print(f"OK: sent {sent} reply draft(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
