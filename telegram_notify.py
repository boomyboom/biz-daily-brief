#!/usr/bin/env python3
"""Send the latest biz-insight brief to Telegram.

Reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / SITE_URL from .env, finds the
newest brief JSON, formats a concise summary, and pushes it.

Usage:
    python3 telegram_notify.py            # send latest
    python3 telegram_notify.py --date 2026-07-18
"""
import json
import os
import sys
import glob
import html
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
BRIEFS_DIR = os.path.join(ROOT, "briefs")
TG_LIMIT = 4096


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
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SITE_URL"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def latest_brief_path(date=None):
    if date:
        p = os.path.join(BRIEFS_DIR, f"{date}.json")
        return p if os.path.exists(p) else None
    files = sorted(glob.glob(os.path.join(BRIEFS_DIR, "20*-*-*.json")))
    return files[-1] if files else None


def esc(s):
    return html.escape(str(s or ""))


def format_message(brief, site_url=""):
    L = []
    L.append(f"💡 <b>오늘의 돈 되는 인사이트</b> — {esc(brief.get('date',''))}")
    if brief.get("headline"):
        L.append(f"<i>{esc(brief['headline'])}</i>")
    L.append("")

    insights = brief.get("insights") or []
    if insights:
        for s in insights[:5]:
            L.append(f"▪️ <b>{esc(s.get('title'))}</b>")
            if s.get("takeaway"):
                L.append(f"   → {esc(s['takeaway'])}")
            src = s.get("source_name") or s.get("source_type")
            if src:
                L.append(f"   <i>({esc(src)})</i>")
        L.append("")

    trends = brief.get("trends") or []
    if trends:
        L.append("📈 <b>지금 뜨는 트렌드</b>")
        for t in trends[:3]:
            L.append(f"• {esc(t.get('theme'))}")
        L.append("")

    cases = brief.get("cases") or []
    if cases:
        c = cases[0]
        who = esc(c.get("who"))
        L.append(f"🏆 <b>사례</b>: {who} — {esc(c.get('what'))}")
        if c.get("numbers"):
            L.append(f"   {esc(c['numbers'])}")
        L.append("")

    q = brief.get("quote") or {}
    if q.get("text"):
        author = f" — {esc(q['author'])}" if q.get("author") else ""
        L.append(f"💬 <i>\"{esc(q['text'])}\"{author}</i>")
        L.append("")

    if site_url:
        L.append("━━━━━━━━━━━━━━")
        L.append("📝 오늘의 뉴스레터 원고 + 채널별(블로그·스레드·인스타·유튜브) 변환본이 준비됐어요")
        L.append(f"📊 <a href=\"{esc(site_url)}\">사이트에서 전체 보기 →</a>")
    if brief.get("disclaimer"):
        L.append("")
        L.append(f"<i>{esc(brief['disclaimer'])}</i>")

    msg = "\n".join(L)
    if len(msg) > TG_LIMIT:
        msg = msg[: TG_LIMIT - 20].rstrip() + "\n…(생략)"
    return msg


def send(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    date = None
    if "--date" in sys.argv:
        date = sys.argv[sys.argv.index("--date") + 1]

    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set (.env)", file=sys.stderr)
        return 1

    path = latest_brief_path(date)
    if not path:
        print("ERROR: no brief JSON found", file=sys.stderr)
        return 1

    with open(path) as f:
        brief = json.load(f)

    text = format_message(brief, env.get("SITE_URL", ""))
    res = send(token, chat_id, text)
    if not res.get("ok"):
        print(f"ERROR: telegram send failed: {res}", file=sys.stderr)
        return 1
    print(f"OK: sent biz brief {brief.get('date')} to chat {chat_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
