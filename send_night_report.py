#!/usr/bin/env python3
"""Email the overnight work report to the owner's work address via Mail.app.

The Telegram digest is a one-liner; this is the full report. Sent as plain text
containing the HTML source is not useful here (it is meant to be read, not
pasted), so we send the readable text version rendered from the report HTML.
"""
import os
import re
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(ROOT, "logs", "night_report.html")


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


def html_to_text(html):
    """Mail.app's html content property is broken here, so render to readable text."""
    t = html
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"<svg\b.*?</svg>", "[개념도 생략]", t, flags=re.S | re.I)
    t = re.sub(r"</(h[1-6]|p|div|li|tr)>", "\n", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<li[^>]*>", "  - ", t, flags=re.I)
    t = re.sub(r"<h2[^>]*>", "\n\n■ ", t, flags=re.I)
    t = re.sub(r"<h3[^>]*>", "\n▸ ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def send(to_addr, subject, text):
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    try:
        script = f'''
        set bodyText to (read POSIX file "{applescript_escape(tmp)}" as «class utf8»)
        tell application "Mail"
            set m to make new outgoing message with properties {{subject:"{applescript_escape(subject)}", content:bodyText, visible:false}}
            tell m
                make new to recipient at end of to recipients with properties {{address:"{applescript_escape(to_addr)}"}}
            end tell
            send m
        end tell
        '''
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "osascript failed")
    finally:
        os.unlink(tmp)


def main():
    env = load_env()
    to_addr = env.get("NIGHT_REPORT_TO") or env.get("MAIL_TO")
    if not to_addr:
        print("ERROR: NIGHT_REPORT_TO not set in .env", file=sys.stderr)
        return 1
    if not os.path.exists(REPORT):
        print("no night_report.html", file=sys.stderr)
        return 1

    html = open(REPORT).read()
    m = re.match(r"\s*<!--\s*제목:\s*(.*?)\s*-->", html)
    date = datetime.now().strftime("%Y-%m-%d")
    subject = f"[야근 보고] {date} {m.group(1)[:50]}" if m else f"[야근 보고] {date}"

    send(to_addr, subject, html_to_text(html))
    print(f"OK: night report mailed to {to_addr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
