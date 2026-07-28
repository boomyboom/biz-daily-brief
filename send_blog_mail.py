#!/usr/bin/env python3
"""Email the day's Tistory-ready blog HTML to the owner via Mail.app.

Uses AppleScript so no password is ever handled by this script — it relies on
the account already configured in Mail.app. Sends ONLY to MAIL_TO (the owner's
own address) defined in .env.

Usage:
    python3 send_blog_mail.py                     # today's post
    python3 send_blog_mail.py 2026-07-28
"""
import os
import re
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))


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


def applescript_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def send(to_addr, subject, html):
    script = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties ¬
            {{subject:"{applescript_escape(subject)}", visible:false}}
        tell newMessage
            set html content to "{applescript_escape(html)}"
            make new to recipient at end of to recipients ¬
                with properties {{address:"{applescript_escape(to_addr)}"}}
            send
        end tell
    end tell
    '''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "osascript failed")
    return True


def main():
    env = load_env()
    to_addr = env.get("MAIL_TO")
    if not to_addr:
        print("ERROR: MAIL_TO not set in .env", file=sys.stderr)
        return 1

    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(ROOT, "posts", date, "blog.html")
    if not os.path.exists(path):
        print(f"no blog.html for {date}", file=sys.stderr)
        return 1

    raw = open(path).read()
    lines = raw.split("\n")
    title = ""
    if lines and lines[0].startswith("<!-- 제목:"):
        title = re.sub(r"^<!-- 제목:\s*|\s*-->$", "", lines[0]).strip()
        body = "\n".join(lines[1:])
    else:
        body = raw

    guide = ('<p style="color:#888;font-size:13px">↓ 아래 제목부터 끝까지 드래그해서 복사 '
             '→ 티스토리 에디터에 붙여넣기 (서식 유지됨)</p><hr>')
    heading = f"<h2>{title}</h2>" if title else ""
    html = guide + heading + body

    subject = f"[티스토리 발행용] {date}" + (f" · {title[:40]}" if title else "")
    send(to_addr, subject, html)
    print(f"OK: mailed {date} blog to {to_addr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
