#!/usr/bin/env python3
"""Polish Threads drafts before sending:
1) humanize: remove AI-tell punctuation (·, em/en dash) → natural commas/words.
2) strip a trailing '?'-ending sentence from the LAST post (a hook question is fine).

Processes threads/queue/pending-*.json (posts[]) and
threads/replies_queue/pending-reply-*.json (draft). Idempotent.
Usage: python3 strip_closing_question.py [file]
"""
import json
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(ROOT, "threads", "queue")
RQUEUE = os.path.join(ROOT, "threads", "replies_queue")


def humanize(text):
    """Replace AI-tell punctuation with natural writing."""
    if not text:
        return text
    t = text
    # 가운뎃점 · 과 긴 줄표 —, – → 쉼표(자연스러운 나열/연결)
    t = re.sub(r"[ \t]*[·・][ \t]*", ", ", t)
    t = re.sub(r"[ \t]*[—–][ \t]*", ", ", t)
    # 정리: 중복 쉼표/공백, 줄 끝·시작의 군더더기
    t = re.sub(r"(,[ \t]*){2,}", ", ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    lines = []
    for ln in t.split("\n"):
        ln = ln.rstrip()
        ln = re.sub(r"^\s*,\s*", "", ln)       # 줄 시작 쉼표 제거
        ln = re.sub(r"\s*,\s*$", "", ln)       # 줄 끝 쉼표 제거
        ln = re.sub(r",\s*([.!?])", r"\1", ln)  # ", ." → "."
        lines.append(ln)
    return "\n".join(lines)


def strip_trailing_question(text):
    t = (text or "").rstrip()
    while t.endswith("?") or t.endswith("？"):
        b = list(re.finditer(r"[.!?。！？\n]", t[:-1]))
        if b:
            t = t[: b[-1].end()].rstrip()
        else:
            return ""
    return t


def process_queue_file(path):
    try:
        d = json.load(open(path))
    except Exception:
        return False
    posts = d.get("posts")
    if not isinstance(posts, list) or not posts:
        return False
    before = list(posts)
    posts = [humanize(p) for p in posts]
    last = strip_trailing_question(posts[-1])
    if last:
        posts[-1] = last
    else:
        posts.pop()
    if posts != before:
        d["posts"] = posts
        json.dump(d, open(path, "w"), ensure_ascii=False, indent=2)
        return True
    return False


def process_reply_file(path):
    try:
        d = json.load(open(path))
    except Exception:
        return False
    draft = d.get("draft")
    if not draft:
        return False
    new = humanize(draft)
    if new != draft:
        d["draft"] = new
        json.dump(d, open(path, "w"), ensure_ascii=False, indent=2)
        return True
    return False


def main():
    if len(sys.argv) > 1:
        p = sys.argv[1]
        (process_reply_file if "pending-reply-" in p else process_queue_file)(p)
        print(f"polished {os.path.basename(p)}")
        return
    n = 0
    for p in glob.glob(os.path.join(QUEUE, "pending-*.json")):
        if process_queue_file(p):
            n += 1
    for p in glob.glob(os.path.join(RQUEUE, "pending-reply-*.json")):
        if process_reply_file(p):
            n += 1
    print(f"polished ({n} file(s))")


if __name__ == "__main__":
    main()
