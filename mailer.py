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
import hashlib
import json
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(ROOT, "logs", "mail_queue")


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


def ensure_mail_running(wait=25):
    """Start Mail.app and wait until it answers Apple events.

    Scheduled sends were hanging the full timeout because Mail was not running:
    `tell application "Mail"` tries to launch it, and that launch stalls in a
    background launchd context. Launching it explicitly first fixes that.
    """
    running = subprocess.run(["pgrep", "-x", "Mail"], capture_output=True).returncode == 0
    if not running:
        subprocess.run(["open", "-g", "-a", "Mail"], capture_output=True)
    deadline = time.time() + wait
    while time.time() < deadline:
        probe = subprocess.run(
            ["osascript", "-e", 'with timeout of 5 seconds\ntell application "Mail" to count accounts\nend timeout'],
            capture_output=True, text=True, timeout=15)
        if probe.returncode == 0:
            return True
        time.sleep(2)
    return False


def _queue_failure(to_addr, subject, text, error):
    """Keep a deduplicated local copy when Mail.app cannot accept the message."""
    os.makedirs(QUEUE_DIR, mode=0o700, exist_ok=True)
    os.chmod(QUEUE_DIR, 0o700)
    digest = hashlib.sha256(
        (to_addr + "\0" + subject + "\0" + text).encode("utf-8")
    ).hexdigest()[:16]
    path = os.path.join(QUEUE_DIR, f"pending-{digest}.json")
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "status": "needs_review" if "timed out" in str(error).lower() else "pending",
        "created_at": created,
        "updated_at": created,
        "to": to_addr,
        "subject": subject,
        "body": text,
        "last_error": str(error),
    }
    if os.path.exists(path):
        try:
            previous = json.load(open(path))
            payload["created_at"] = previous.get("created_at", created)
        except (OSError, ValueError):
            pass
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    return path


def _notify_failure(subject, queue_path, error):
    """Send a short alert without including the private mail body."""
    script = os.path.join(ROOT, "send_telegram.sh")
    if not os.path.exists(script):
        return
    message = ("⚠️ 메일 자동 발송 실패\n"
               f"제목: {subject[:80]}\n"
               f"대기열: {os.path.basename(queue_path)}\n"
               f"원인: {str(error)[:180]}")
    try:
        subprocess.run(["/bin/bash", script, message], capture_output=True,
                       text=True, timeout=20)
    except Exception:
        pass


def send_mail(to_addr, subject, text, timeout=45, retries=2, queue_on_failure=True):
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
        last = None
        for attempt in range(retries + 1):
            if not ensure_mail_running():
                last = "Mail.app did not answer Apple events"
                if attempt < retries:
                    time.sleep(3 * (attempt + 1))
                continue
            try:
                r = subprocess.run(["osascript", "-e", script],
                                   capture_output=True, text=True, timeout=timeout)
                if r.returncode == 0:
                    return True
                last = r.stderr.strip() or "osascript failed"
                break
            except subprocess.TimeoutExpired:
                last = f"timed out after {timeout}s"
                break
        if queue_on_failure:
            queue_path = _queue_failure(to_addr, subject, text, last)
            _notify_failure(subject, queue_path, last)
            raise RuntimeError(f"{last}; queued at {queue_path}")
        raise RuntimeError(last)
    finally:
        os.unlink(tmp)
