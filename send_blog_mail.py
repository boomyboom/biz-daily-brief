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


def humanize(t):
    """Strip AI-tell punctuation (가운뎃점, 긴 줄표) the owner asked us to avoid."""
    if not t:
        return t
    t = re.sub(r"[ \t]*[·・][ \t]*", ", ", t)
    t = re.sub(r"[ \t]*[—–][ \t]*", ", ", t)
    t = re.sub(r"(,[ \t]*){2,}", ", ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    out = []
    for ln in t.split("\n"):
        ln = ln.rstrip()
        ln = re.sub(r"^\s*,\s*", "", ln)
        ln = re.sub(r"\s*,\s*$", "", ln)
        ln = re.sub(r",\s*([.!?])", r"\1", ln)
        out.append(ln)
    return "\n".join(out)


def esc_html(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def thread_to_html(posts):
    """Render a thread chain (hook + reply chunks) as blog paragraphs."""
    out = []
    for chunk in posts:
        for para in re.split(r"\n\s*\n", humanize(chunk or "").strip()):
            if para.strip():
                out.append("<p>" + esc_html(para.strip()).replace("\n", "<br>") + "</p>")
    return "\n".join(out)


def collect_threads(date):
    """Today's threads (posted + still queued), oldest first. Returns [(topic, html)]."""
    import glob as _glob
    import json as _json
    stamp = date.replace("-", "")
    seen, items = set(), []
    for folder in ("posted", "queue"):
        for path in sorted(_glob.glob(os.path.join(ROOT, "threads", folder, f"*{stamp}*.json"))):
            name = os.path.basename(path)
            if name in seen:
                continue
            seen.add(name)
            try:
                d = _json.load(open(path))
            except Exception:
                continue
            posts = d.get("posts") or []
            if posts:
                items.append((humanize(d.get("topic") or ""), thread_to_html(posts), name))
    # 파일명 뒤 시각(HHMM) 기준 정렬
    items.sort(key=lambda x: re.sub(r"\D", "", x[2]))
    return [(t, h) for t, h, _ in items]


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


def send(to_addr, subject, text):
    """Send via Mail.app as PLAIN TEXT.

    Two hard-won details:
      * `html content` silently produces an empty body on this Mail version, so
        we send the HTML *source* as plain text — the user pastes it into
        Tistory's HTML mode, which preserves formatting exactly.
      * The body goes through a temp file; embedding it in the AppleScript
        source breaks on newlines.
    """
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    try:
        script = f'''
        set bodyText to (read POSIX file "{applescript_escape(tmp)}" as «class utf8»)
        tell application "Mail"
            set newMessage to make new outgoing message with properties {{subject:"{applescript_escape(subject)}", content:bodyText, visible:false}}
            tell newMessage
                make new to recipient at end of to recipients with properties {{address:"{applescript_escape(to_addr)}"}}
            end tell
            send newMessage
        end tell
        '''
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "osascript failed")
    finally:
        os.unlink(tmp)
    return True


def main():
    env = load_env()
    to_addr = env.get("MAIL_TO")
    if not to_addr:
        print("ERROR: MAIL_TO not set in .env", file=sys.stderr)
        return 1

    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

    title, body = "", ""
    path = os.path.join(ROOT, "posts", date, "blog.html")
    if os.path.exists(path):
        raw = open(path).read()
        lines = raw.split("\n")
        if lines and lines[0].startswith("<!-- 제목:"):
            title = humanize(re.sub(r"^<!-- 제목:\s*|\s*-->$", "", lines[0]).strip())
            body = humanize("\n".join(lines[1:]))
        else:
            body = humanize(raw)

    # 스레드는 각 초안이 생성될 때 개별 메일로 나가므로 여기서 묶지 않는다
    threads = []
    if not body:
        print(f"no blog.html for {date}", file=sys.stderr)
        return 1

    parts = []
    if title:
        parts.append(f"<h2>{esc_html(title)}</h2>")
    if body:
        parts.append(body)

    # 오늘 나간 스레드 글들도 블로그용으로 함께
    if threads:
        parts.append('<hr>\n<h2>오늘의 짧은 글</h2>')
        for topic, html in threads:
            if topic:
                parts.append(f"<h3>{esc_html(topic)}</h3>")
            parts.append(html)

    links = (f"[바로가기]\n"
             f"시장 브리핑: {env.get('MARKET_SITE_URL', 'https://boomyboom.github.io/market-daily-brief/')}\n"
             + (f"비즈 브리핑: {env['SITE_URL']}\n" if env.get("SITE_URL") else ""))
    guide = (f"[티스토리 발행 방법]\n"
             f"1. 티스토리 글쓰기 → 우측 상단 '기본모드'를 'HTML'로 변경\n"
             f"2. 아래 ===== 사이 내용을 전체 복사해서 붙여넣기\n"
             f"3. 다시 '기본모드'로 돌아오면 서식이 적용돼 있습니다\n"
             f"제목: {title}\n\n"
             f"{links}\n"
             f"=====================================\n")
    html = guide + "\n".join(parts) + "\n=====================================\n"
    subject = f"[티스토리 발행용] {date}" + (f" {title[:40]}" if title else "")
    send(to_addr, subject, html)
    print(f"OK: mailed {date} to {to_addr} (blog={'y' if body else 'n'}, threads={len(threads)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
