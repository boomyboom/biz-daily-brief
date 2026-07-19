#!/usr/bin/env python3
"""Telegram approval listener for Threads posting.

Long-polls Telegram for inline-button taps on Threads draft messages.
- ✅ tap  -> publish that draft to Threads, reply with the permalink
- ❌ tap  -> skip (archive the draft)

Only callbacks from the configured TELEGRAM_CHAT_ID are honored. This turns
each tap into an explicit, per-post human approval before anything goes public.
Run continuously (launchd KeepAlive).
"""
import json
import os
import sys
import time
import shutil
import urllib.request
import urllib.parse
import urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import post_to_threads as threads  # noqa: E402

QUEUE = os.path.join(ROOT, "threads", "queue")
POSTED = os.path.join(ROOT, "threads", "posted")
SKIPPED = os.path.join(ROOT, "threads", "skipped")
OFFSET_FILE = os.path.join(ROOT, "threads", ".tg_offset")
LOG = os.path.join(ROOT, "logs", "threads-listener.log")


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


ENV = load_env()
# 스레드 승인 전용 봇 우선 (getUpdates 충돌 방지). 없으면 메인 봇 폴백.
TOKEN = ENV.get("TELEGRAM_APPROVE_BOT_TOKEN") or ENV.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = str(ENV.get("TELEGRAM_CHAT_ID", ""))
API = f"https://api.telegram.org/bot{TOKEN}"


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def api(method, params, tmo=60):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=tmo) as r:
        return json.loads(r.read().decode())


def read_offset():
    try:
        return int(open(OFFSET_FILE).read().strip())
    except Exception:
        return 0


def write_offset(v):
    try:
        open(OFFSET_FILE, "w").write(str(v))
    except Exception:
        pass


def edit_message(chat_id, message_id, text):
    try:
        api("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true",
        })
    except Exception as e:
        log(f"editMessage failed: {e}")


def handle_callback(cb):
    data = cb.get("data", "")
    msg = cb.get("message", {}) or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    message_id = msg.get("message_id")
    cb_id = cb.get("id")
    orig_text = msg.get("text", "")

    # 설정된 그룹의 탭만 처리 (안전)
    if chat_id != CHAT_ID:
        api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "권한 없음"})
        return

    if ":" not in data:
        api("answerCallbackQuery", {"callback_query_id": cb_id})
        return
    action, fname = data.split(":", 1)
    path = os.path.join(QUEUE, fname)

    if not os.path.exists(path):
        api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "이미 처리된 초안이에요"})
        return

    if action == "skip":
        os.makedirs(SKIPPED, exist_ok=True)
        shutil.move(path, os.path.join(SKIPPED, fname))
        api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "스킵했어요"})
        edit_message(chat_id, message_id, orig_text + "\n\n❌ <b>스킵됨</b>")
        log(f"skipped {fname}")
        return

    if action == "ok":
        api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "스레드에 게시 중…"})
        try:
            with open(path) as f:
                draft = json.load(f)
            posts = draft.get("posts") or []
            uid = ENV.get("THREADS_USER_ID")
            ttoken = ENV.get("THREADS_TOKEN")
            _, permalink = threads.post_series(uid, ttoken, posts)
            os.makedirs(POSTED, exist_ok=True)
            shutil.move(path, os.path.join(POSTED, fname))
            link = f"\n🔗 {permalink}" if permalink else ""
            edit_message(chat_id, message_id, orig_text + f"\n\n✅ <b>게시 완료</b>{link}")
            log(f"posted {fname} -> {permalink}")
        except Exception as e:
            log(f"POST FAILED {fname}: {e}")
            edit_message(chat_id, message_id, orig_text + f"\n\n⚠️ <b>게시 실패</b>: {e}\n초안은 큐에 남겨뒀어요.")


def main():
    if not TOKEN or not CHAT_ID:
        log("ERROR: telegram creds missing")
        return 1
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    log("===== threads listener start =====")
    offset = read_offset()
    while True:
        try:
            res = api("getUpdates", {
                "offset": offset, "timeout": 50,
                "allowed_updates": json.dumps(["callback_query"]),
            }, tmo=60)
            if not res.get("ok"):
                time.sleep(3)
                continue
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                write_offset(offset)
                if "callback_query" in upd:
                    try:
                        handle_callback(upd["callback_query"])
                    except Exception as e:
                        log(f"handle error: {e}")
        except urllib.error.HTTPError as e:
            if e.code == 409:
                log("409 conflict (다른 getUpdates 폴러 존재) — 5s 후 재시도")
                time.sleep(5)
            else:
                log(f"HTTP {e.code}: {e.read().decode()[:200]}")
                time.sleep(3)
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
