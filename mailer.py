#!/usr/bin/env python3
"""Shared Mail.app sender.

Every script that pushes to Telegram also mails the same thing, so the sending
logic lives here once. Mail.app's `html content` silently sends an empty body on
this machine, so we send plain text; and the body goes through a temp file
because embedding it in AppleScript source breaks on newlines.
No password is ever handled: Mail.app uses the account the owner configured.
"""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_env(root=None):
    env = {}
    p = os.path.join(root or ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def strip_html(t):
    """Turn a Telegram-flavoured HTML message into readable mail text."""
    t = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 (\1)", t, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return (t.replace("&amp;", "&").replace("&lt;", "<")
             .replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'"))


def send_mail(to_addr, subject, text, timeout=90):
    """Send plain-text mail through Mail.app. Raises on failure."""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    try:
        script = f'''
        set bodyText to (read POSIX file "{_esc(tmp)}" as «class utf8»)
        tell application "Mail"
            set m to make new outgoing message with properties {{subject:"{_esc(subject)}", content:bodyText, visible:false}}
            tell m
                make new to recipient at end of to recipients with properties {{address:"{_esc(to_addr)}"}}
            end tell
            send m
        end tell
        '''
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "osascript failed")
    finally:
        os.unlink(tmp)
    return True
