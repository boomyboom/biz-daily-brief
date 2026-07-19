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
    # 파일명 정렬이 아니라 '가장 최근 생성(mtime)' 기준으로 골라야 함
    # (pending-mkt-* 가 이름순으로 뒤에 와서 엉뚱하게 잡히던 버그 수정)
    files = glob.glob(os.path.join(QUEUE, "pending-*.json"))
    return max(files, key=os.path.getmtime) if files else None


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
    L.append("아래 버튼으로 바로 게시하거나, 복사해서 직접 올리셔도 돼요.")
    return "\n".join(L)


def send(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    data = urllib.parse.urlencode(payload).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    env = load_env()
    # 스레드 승인은 전용 봇으로 (getUpdates 충돌 방지). 없으면 메인 봇 폴백.
    token = env.get("TELEGRAM_APPROVE_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN")
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
    fname = os.path.basename(path)
    keyboard = {"inline_keyboard": [[
        {"text": "✅ 스레드에 게시", "callback_data": f"ok:{fname}"},
        {"text": "❌ 스킵", "callback_data": f"skip:{fname}"},
    ]]}
    res = send(token, chat_id, format_message(draft), reply_markup=keyboard)
    if not res.get("ok"):
        print(f"ERROR: send failed: {res}", file=sys.stderr)
        return 1
    print(f"OK: sent threads draft {os.path.basename(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
