#!/usr/bin/env python3
"""Deterministically remove an awkward closing question from Threads drafts.

Only the LAST post is trimmed (a question in the hook is fine). Any trailing
sentence that ends with '?' is stripped; if the last post becomes empty it is
dropped. Idempotent. Processes all pending-*.json in threads/queue by default,
or a specific file passed as argv[1].
"""
import json
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(ROOT, "threads", "queue")


def strip_trailing_question(text):
    t = (text or "").rstrip()
    while t.endswith("?") or t.endswith("？"):
        boundaries = list(re.finditer(r"[.!?。！？\n]", t[:-1]))
        if boundaries:
            t = t[: boundaries[-1].end()].rstrip()
        else:
            return ""  # entire text was one question
    return t


def process_posts(posts):
    if not posts:
        return posts
    new_last = strip_trailing_question(posts[-1])
    if new_last:
        posts[-1] = new_last
    else:
        posts.pop()
    return posts


def process_file(path):
    try:
        d = json.load(open(path))
    except Exception:
        return False
    posts = d.get("posts")
    if not isinstance(posts, list) or not posts:
        return False
    before = list(posts)
    d["posts"] = process_posts(posts)
    if d["posts"] != before:
        json.dump(d, open(path, "w"), ensure_ascii=False, indent=2)
        return True
    return False


def main():
    targets = [sys.argv[1]] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(QUEUE, "pending-*.json")))
    n = 0
    for p in targets:
        if process_file(p):
            n += 1
            print(f"trimmed closing question: {os.path.basename(p)}")
    print(f"done ({n} file(s) trimmed)")


if __name__ == "__main__":
    main()
