#!/usr/bin/env python3
"""Fetch NEW replies (from other people) on my recent Threads posts.

Writes them to threads/replies_queue/inbox-<ts>.json for the drafter, and
records their ids in threads/replies_seen.json so each comment is handled once.
Skips my own replies and already-seen ones.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://graph.threads.net/v1.0"
QUEUE = os.path.join(ROOT, "threads", "replies_queue")
SEEN_PATH = os.path.join(ROOT, "threads", "replies_seen.json")


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


def get(path, params):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


import urllib.parse  # noqa: E402


def load_seen():
    try:
        return set(json.load(open(SEEN_PATH)).get("ids", []))
    except Exception:
        return set()


def save_seen(seen):
    json.dump({"ids": sorted(seen)}, open(SEEN_PATH, "w"), ensure_ascii=False, indent=2)


def too_old(ts, hours):
    """True if the comment timestamp is older than `hours` ago."""
    if not ts:
        return False
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(ts.replace("+0000", "+00:00").replace("Z", "+00:00"), fmt)
            break
        except ValueError:
            dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            return False
    return datetime.now(timezone.utc) - dt > timedelta(hours=hours)


def main():
    env = load_env()
    token = env.get("THREADS_TOKEN")
    me = (env.get("THREADS_USER_HANDLE") or "").lstrip("@")
    lookback = int(env.get("REPLY_LOOKBACK_HOURS", "48"))
    if not token:
        print("ERROR: THREADS_TOKEN missing", file=sys.stderr)
        return 1
    os.makedirs(QUEUE, exist_ok=True)
    seen = load_seen()

    # 최근 내 글
    posts = get("me/threads", {"fields": "id,text", "limit": 25, "access_token": token}).get("data", [])
    new_comments = []
    for p in posts:
        pid = p["id"]
        try:
            reps = get(f"{pid}/replies", {
                "fields": "id,text,username,timestamp,hide_status", "access_token": token,
            }).get("data", [])
        except Exception as e:
            print(f"replies fetch failed for {pid}: {e}", file=sys.stderr)
            continue
        for c in reps:
            cid = c.get("id")
            user = (c.get("username") or "").lstrip("@")
            if not cid or cid in seen:
                continue
            if user == me:            # 내 답글은 제외
                seen.add(cid)
                continue
            if c.get("hide_status") == "HIDDEN":
                seen.add(cid)
                continue
            if too_old(c.get("timestamp"), lookback):   # 오래된 댓글 제외
                seen.add(cid)
                continue
            new_comments.append({
                "comment_id": cid,
                "comment_user": user,
                "comment_text": c.get("text", ""),
                "post_id": pid,
                "post_text": p.get("text", ""),
            })
            seen.add(cid)

    save_seen(seen)
    if new_comments:
        fn = os.path.join(QUEUE, f"inbox-{time.strftime('%Y%m%d-%H%M%S')}.json")
        json.dump(new_comments, open(fn, "w"), ensure_ascii=False, indent=2)
        print(f"NEW {len(new_comments)} comment(s) -> {os.path.basename(fn)}")
    else:
        print("no new comments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
