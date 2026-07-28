#!/usr/bin/env python3
"""Convert a daily blog markdown post into Tistory-ready HTML.

Tistory's Open API was shut down (Feb 2024), so posts must be pasted into the
web editor. This produces clean HTML that pastes correctly into Tistory's
HTML mode — no external CSS, simple tags only.

Usage:
    python3 blog_to_html.py                    # latest posts/*/blog.md
    python3 blog_to_html.py posts/2026-07-28/blog.md
Writes <same dir>/blog.html and prints its path.
"""
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, "posts")


def humanize(t):
    """Remove AI-tell punctuation (가운뎃점, 긴 줄표) that the owner dislikes."""
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


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def inline(t):
    """Markdown inline → HTML (escape first, then apply markup)."""
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    t = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    return t


def md_to_html(md):
    lines = md.replace("\r", "").split("\n")
    out, para, in_ul, in_ol = [], [], False, False

    def flush_p():
        nonlocal para
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_p()
            close_lists()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush_p(); close_lists()
            # 티스토리 본문은 h1을 제목이 차지하므로 한 단계 낮춰 사용
            level = min(len(m.group(1)) + 1, 4)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue
        if re.match(r"^(---|\*\*\*|___)\s*$", line):
            flush_p(); close_lists()
            out.append("<hr>")
            continue
        m = re.match(r"^>\s?(.*)", line)
        if m:
            flush_p(); close_lists()
            out.append(f"<blockquote><p>{inline(m.group(1))}</p></blockquote>")
            continue
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            flush_p()
            if in_ol:
                out.append("</ol>"); in_ol = False
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            flush_p()
            if in_ul:
                out.append("</ul>"); in_ul = False
            if not in_ol:
                out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        para.append(line.strip())

    flush_p(); close_lists()
    return "\n".join(out)


def split_title(md):
    """First '# ' line becomes the post title; the rest is the body."""
    lines = md.replace("\r", "").split("\n")
    title = ""
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            title = ln[2:].strip()
            body_start = i + 1
            break
        if ln.strip():
            break
    return title, "\n".join(lines[body_start:])


def convert(path):
    md = humanize(open(path).read())
    title, body = split_title(md)
    html = md_to_html(body)
    out_path = os.path.join(os.path.dirname(path), "blog.html")
    with open(out_path, "w") as f:
        if title:
            f.write(f"<!-- 제목: {title} -->\n")
        f.write(html + "\n")
    return out_path, title


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        cands = sorted(glob.glob(os.path.join(POSTS, "*", "blog.md")))
        if not cands:
            print("no blog.md found", file=sys.stderr)
            return 1
        path = cands[-1]
    out, title = convert(path)
    print(f"OK: {out}")
    if title:
        print(f"TITLE: {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
