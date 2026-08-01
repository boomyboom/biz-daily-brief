#!/usr/bin/env python3
"""Post text to Threads via the Threads Graph API.

Reads THREADS_TOKEN / THREADS_USER_ID from .env. Two-step publish:
  1) create a media container (media_type=TEXT)
  2) publish the container
Supports a thread series (post 1, then reply-chain the rest).

CLI:
  python3 post_to_threads.py --file threads/queue/pending-XXX.json
  python3 post_to_threads.py --text "한 줄 글"
  python3 post_to_threads.py --file ... --dry-run   # container만 생성(발행 안 함)
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://graph.threads.net/v1.0"


class ThreadsAPIError(RuntimeError):
    def __init__(self, status, detail):
        super().__init__(f"Threads API HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def _meta_error(e):
    """Extract the real Threads/Meta error message from an HTTPError body."""
    try:
        body = json.loads(e.read().decode())
        err = body.get("error", {})
        return f"{err.get('message')} (code {err.get('code')}, type {err.get('type')})"
    except Exception:
        return str(e)


def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def _post(path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise ThreadsAPIError(e.code, _meta_error(e))


def _get(path, params):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Threads API: {_meta_error(e)}")


def create_container(uid, token, text, reply_to_id=None, image_url=None):
    """Threads fetches images by public URL, so image_url must be reachable."""
    params = {"media_type": "TEXT", "text": text, "access_token": token}
    if image_url:
        params["media_type"] = "IMAGE"
        params["image_url"] = image_url
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    res = _post(f"{uid}/threads", params)
    return res["id"]


def publish(uid, token, creation_id):
    # 텍스트는 대개 즉시 발행되나, 처리 지연 대비 재시도
    last = None
    for attempt in range(6):
        try:
            res = _post(f"{uid}/threads_publish", {"creation_id": creation_id, "access_token": token})
            return res["id"]
        except ThreadsAPIError as e:
            last = str(e)
            processing_400 = e.status == 400 and any(
                hint in str(e.detail).lower()
                for hint in ("not ready", "not finished", "processing", "try again")
            )
            if not processing_400 and e.status != 429 and e.status < 500:
                raise
            time.sleep(5 * (attempt + 1))
        except urllib.error.URLError as e:
            last = str(e)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"publish failed: {last}")


def permalink(token, media_id):
    try:
        return _get(f"{media_id}", {"fields": "permalink", "access_token": token}).get("permalink", "")
    except Exception:
        return ""


def post_reply(uid, token, text, reply_to_id):
    """Post a single reply to a given comment/post id. Returns (media_id, permalink)."""
    cid = create_container(uid, token, text, reply_to_id=reply_to_id)
    time.sleep(2)
    mid = publish(uid, token, cid)
    return mid, permalink(token, mid)


def post_series(uid, token, posts, dry_run=False, images=None):
    """Post a list of texts as a reply-chained series. Returns (first_media_id, permalink).

    `images` maps a post index to a public image URL, so a card can be attached
    to the hook without forcing every chunk to carry one.
    """
    images = images or {}
    first_id, prev_id = None, None
    for i, text in enumerate(posts):
        cid = create_container(uid, token, text, reply_to_id=prev_id,
                               image_url=images.get(i) or images.get(str(i)))
        if dry_run:
            print(f"[dry-run] container {i+1}/{len(posts)} created: {cid} (발행 안 함)")
            return cid, ""
        time.sleep(2)
        mid = publish(uid, token, cid)
        if first_id is None:
            first_id = mid
        prev_id = mid
        time.sleep(2)
    return first_id, permalink(token, first_id)


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    env = load_env()
    token = env.get("THREADS_TOKEN")
    uid = env.get("THREADS_USER_ID")
    if not token or not uid:
        print("ERROR: THREADS_TOKEN / THREADS_USER_ID missing in .env", file=sys.stderr)
        return 1

    posts = None
    if "--file" in args:
        path = args[args.index("--file") + 1]
        with open(path) as f:
            posts = json.load(f).get("posts") or []
    elif "--text" in args:
        posts = [args[args.index("--text") + 1]]
    if not posts:
        print("ERROR: no posts (use --file or --text)", file=sys.stderr)
        return 1

    mid, url = post_series(uid, token, posts, dry_run=dry)
    print(json.dumps({"media_id": mid, "permalink": url, "dry_run": dry}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
