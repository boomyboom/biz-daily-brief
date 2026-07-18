#!/usr/bin/env python3
"""Send the newest pending Threads draft to Telegram for one-tap review.

Reads the newest threads/queue/pending-*.json, formats it, and sends to
Telegram. If THREADS_TOKEN is configured later, an approval listener can
turn a tap into an actual post; for now the draft is copy-paste ready.
"""
import json
import os
import sys
import glob
import html
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(ROOT, "threads", "queue")


def load_env():
    env = {}
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def esc(s):
    return html.escape(str(s or ""))


def newest_pending():
    files = sorted(glob.glob(os.path.join(QUEUE, "pending-*.json")))
    return files[-1] if files else None


def format_message(draft):
    posts = draft.get("posts") or []
    L = ["🧵 <b>스레드 초안</b> (승인 대기)"]
    if draft.get("topic"):
        L.append(f"<i>주제: {esc(draft['topic'])}</i>")
    L.append("")
    for i, p in enumerate(posts, 1):
        prefix = f"<b>{i}/{len(posts)}</b> " if len(posts) > 1 else ""
        L.append(f"{prefix}{esc(p)}")
        L.append("")
    if draft.get("source_name"):
        L.append(f"<i>출처: {esc(draft['source_name'])}</i>")
    L.append("————————")
    L.append("👉 마음에 들면 <b>복사해서 스레드에 게시</b>하세요.")
    L.append("(자동 게시는 Threads API 토큰 설정 후 활성화됩니다)")
    return "\n".join(L)


def send(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: telegram creds missing", file=sys.stderr)
        return 1
    path = newest_pending()
    if not path:
        print("no pending draft", file=sys.stderr)
        return 1
    with open(path) as f:
        draft = json.load(f)
    res = send(token, chat_id, format_message(draft))
    if not res.get("ok"):
        print(f"ERROR: send failed: {res}", file=sys.stderr)
        return 1
    print(f"OK: sent threads draft {os.path.basename(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
