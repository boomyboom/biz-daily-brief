#!/usr/bin/env python3
"""Turn one biz piece (a Threads draft) into a paste-ready HTML article.

The owner does not want raw thread drafts in email; they want something they can
paste into Tistory. So each biz slot mails an article built from that slot's
topic: the thread's own narrative, plus the matching insight from today's brief
(summary, takeaway, source) so it has enough substance to stand as a post.

Usage: python3 piece_to_html.py threads/queue/pending-20260729-0902.json
"""
import glob
import html as H
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))


def humanize(t):
    t = re.sub(r"[ \t]*[·・][ \t]*", ", ", t or "")
    t = re.sub(r"[ \t]*[—–][ \t]*", ", ", t)
    t = re.sub(r"(,[ \t]*){2,}", ", ", t)
    return t


def esc(s):
    return H.escape(str(s or ""))


def today_brief(date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    p = os.path.join(ROOT, "briefs", f"{date}.json")
    if os.path.exists(p):
        return json.load(open(p))
    cands = sorted(glob.glob(os.path.join(ROOT, "briefs", "20*-*-*.json")))
    return json.load(open(cands[-1])) if cands else {}


def match_insight(brief, topic, posts):
    """Find the insight this piece came from, by keyword overlap."""
    text = (topic or "") + " " + " ".join(posts or [])
    words = {w for w in re.findall(r"[가-힣A-Za-z]{2,}", text)}
    best, score = None, 0
    for ins in (brief.get("insights") or []) + (brief.get("trends") or []):
        blob = " ".join(str(ins.get(k, "")) for k in ("title", "theme", "summary", "takeaway"))
        hits = len(words & set(re.findall(r"[가-힣A-Za-z]{2,}", blob)))
        if hits > score:
            best, score = ins, hits
    return best if score >= 3 else None


def build(draft, brief):
    topic = humanize(draft.get("topic") or "")
    posts = [humanize(p) for p in (draft.get("posts") or [])]
    ins = match_insight(brief, topic, posts)

    title = (ins.get("title") if ins else "") or topic or "오늘의 비즈 인사이트"
    title = humanize(title)

    P = [f"<h2>{esc(title)}</h2>"]
    for chunk in posts:
        for para in re.split(r"\n\s*\n", chunk.strip()):
            if para.strip():
                P.append("<p>" + esc(para.strip()).replace("\n", "<br>") + "</p>")

    if ins:
        if ins.get("summary"):
            P.append(f"<h3>조금 더 자세히</h3><p>{esc(humanize(ins['summary']))}</p>")
        if ins.get("takeaway"):
            P.append(f"<h3>바로 써먹기</h3><p>{esc(humanize(ins['takeaway']))}</p>")
        src = ins.get("source_name") or ins.get("source_type")
        url = ins.get("source_url")
        if src or url:
            link = f'<a href="{esc(url)}">{esc(src or url)}</a>' if url else esc(src)
            P.append(f'<p style="font-size:13px;color:#666">출처: {link}</p>')

    return title, "\n".join(P)


def main():
    if len(sys.argv) < 2:
        print("usage: piece_to_html.py <draft.json>", file=sys.stderr)
        return 1
    draft = json.load(open(sys.argv[1]))
    title, html = build(draft, today_brief())
    print(f"<!-- 제목: {title} -->")
    print(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
