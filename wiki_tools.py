#!/usr/bin/env python3
"""Vault housekeeping: migrate old entity notes, rebuild index.md, append log.md.

These are the deterministic parts of wiki upkeep. Anything requiring judgement
(rewriting summaries, spotting contradictions) belongs to the weekly Opus pass.

Usage:
    python3 wiki_tools.py migrate     # one-off: restructure existing notes
    python3 wiki_tools.py index       # rebuild index.md
    python3 wiki_tools.py log "메시지"  # append a line to log.md
"""
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VAULT = "/Users/boomyboom/Documents/Obsidian Vault"

ENTITY_DIRS = [
    ("10_주식뇌/종목", "종목"), ("10_주식뇌/섹터", "섹터"),
    ("10_주식뇌/테마", "테마"), ("10_주식뇌/매크로", "매크로"),
    ("20_사업뇌/개념", "개념"), ("20_사업뇌/사례", "사례"),
    ("20_사업뇌/인물기업", "인물기업"), ("20_사업뇌/분야", "분야"),
    ("20_사업뇌/기회", "기회"),
]
DAILY_DIRS = [("10_주식뇌/_데일리", "데일리 시장"), ("20_사업뇌/_데일리", "데일리 비즈")]


def vault_path():
    for p in (os.path.join(HERE, ".env"),):
        if os.path.exists(p):
            for line in open(p):
                if line.strip().startswith("OBSIDIAN_VAULT="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OBSIDIAN_VAULT") or DEFAULT_VAULT


def split_front(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def history_lines(body):
    if "## 이력" not in body:
        return []
    tail = body.split("## 이력", 1)[1]
    return [ln for ln in tail.splitlines() if ln.startswith("- 20")]


def migrate(vault):
    """Add the summary sections and flip history to newest-first."""
    changed = 0
    for rel, _ in ENTITY_DIRS:
        d = os.path.join(vault, rel)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(d, fn)
            try:
                text = open(path).read()
            except Exception:
                continue
            if "## 현재 상황" in text:
                continue                      # 이미 새 형식
            front, body = split_front(text)
            hist = history_lines(body)
            hist.sort(key=lambda ln: ln[2:12], reverse=True)
            title = fn[:-3]
            newest = hist[0][2:12] if hist else datetime.now().strftime("%Y-%m-%d")
            if "updated:" not in front:
                front = (front + f"\nupdated: {newest}").strip()
            new = (f"---\n{front}\n---\n\n# {title}\n\n"
                   "## 현재 상황\n(주간 유지보수가 채운다)\n\n"
                   "## 반복 패턴\n(주간 유지보수가 채운다)\n\n"
                   "## 관련\n\n"
                   "## 이력\n" + "\n".join(hist) + "\n")
            try:
                open(path, "w").write(new)
                changed += 1
            except Exception as e:
                print(f"  skip {fn}: {e.__class__.__name__}")
    print(f"migrated {changed} note(s)")


def build_index(vault):
    """Catalogue every page so the agent can find things without embeddings."""
    L = ["---", "type: 색인", "tags: [운영]", "---", "",
         "# 색인", "", f"_자동 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}_", "",
         "규칙은 [[WIKI_SCHEMA]], 시간순 기록은 [[log]] 를 본다.", ""]
    total = 0
    for rel, label in ENTITY_DIRS + DAILY_DIRS:
        d = os.path.join(vault, rel)
        if not os.path.isdir(d):
            continue
        rows = []
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(d, fn)
            try:
                text = open(path).read()
            except Exception:
                continue
            name = fn[:-3]
            n = len(history_lines(text))
            m = re.search(r"^updated:\s*(\S+)", text, re.M)
            when = m.group(1) if m else ""
            meta = ", ".join(x for x in [f"{n}회 언급" if n else "", when] if x)
            rows.append(f"- [[{name}]]" + (f" ({meta})" if meta else ""))
        if rows:
            total += len(rows)
            L.append(f"## {label} ({len(rows)})")
            L.extend(rows)
            L.append("")
    L.insert(9, f"전체 {total}개 페이지.\n")
    out = os.path.join(vault, "index.md")
    open(out, "w").write("\n".join(L))
    print(f"index.md rebuilt: {total} pages")


def append_log(vault, message):
    """Append a parseable, chronological entry (grep '^## \\[' log.md | tail)."""
    path = os.path.join(vault, "log.md")
    if not os.path.exists(path):
        open(path, "w").write("---\ntype: 로그\ntags: [운영]\n---\n\n# 기록\n\n"
                              "시간순 추가 전용. `grep \"^## \\[\" log.md | tail -5` 로 최근 항목을 본다.\n\n")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a") as f:
        f.write(f"## [{stamp}] {message}\n\n")
    print(f"logged: {message}")


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    v = vault_path()
    cmd = sys.argv[1]
    if cmd == "migrate":
        migrate(v)
    elif cmd == "index":
        build_index(v)
    elif cmd == "log":
        append_log(v, " ".join(sys.argv[2:]) or "(내용 없음)")
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
