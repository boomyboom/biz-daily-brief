#!/usr/bin/env python3
"""Convert a daily brief JSON into Obsidian notes (제2의 뇌).

- Writes a daily note (market or biz, auto-detected).
- For each entity (stock/sector/theme/asset/concept/case/source), ensures a
  stub note exists and appends a dated timeline bullet linking to the daily note.
Idempotent per (entity, date).

Usage: python3 brief_to_obsidian.py <brief.json> [vault_path]
Vault resolves from arg > OBSIDIAN_VAULT env/.env > default.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VAULT = "/Users/boomyboom/Documents/Obsidian Vault"


def load_env_vault():
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        for line in open(p):
            s = line.strip()
            if s.startswith("OBSIDIAN_VAULT=") and "=" in s:
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OBSIDIAN_VAULT") or DEFAULT_VAULT


BAD = re.compile(r'[\\/:*?"<>|#\^\[\]]')


def safe_name(s):
    s = (s or "").strip().replace("\n", " ")
    s = BAD.sub("", s)
    return s[:80].strip() or "무제"


def ensure_dirs(vault):
    for d in ["10_주식뇌/_데일리", "10_주식뇌/종목", "10_주식뇌/섹터", "10_주식뇌/테마",
              "10_주식뇌/매크로", "20_사업뇌/_데일리", "20_사업뇌/개념", "20_사업뇌/사례",
              "20_사업뇌/인물기업", "20_사업뇌/분야", "30_종합"]:
        os.makedirs(os.path.join(vault, d), exist_ok=True)


def append_timeline(vault, folder, name, etype, date, context, daily_link, extra_fm=None):
    """Ensure entity note exists; append a dated bullet (idempotent per date+daily)."""
    name = safe_name(name)
    if not name:
        return None
    path = os.path.join(vault, folder, f"{name}.md")
    if not os.path.exists(path):
        fm = [f"type: {etype}", f"name: {name}"]
        for k, v in (extra_fm or {}).items():
            if v:
                fm.append(f"{k}: {v}")
        header = "---\n" + "\n".join(fm) + "\n---\n\n" + f"# {name}\n\n## 이력\n"
        open(path, "w").write(header)
    content = open(path).read()
    marker = f"[[{daily_link}]]"
    # 같은 날 같은 데일리 노트 중복 방지
    for line in content.splitlines():
        if line.startswith(f"- {date}") and marker in line:
            return name
    bullet = f"- {date} {marker}" + (f" · {context}" if context else "")
    if "## 이력" not in content:
        content += "\n## 이력\n"
    content = content.rstrip() + "\n" + bullet + "\n"
    open(path, "w").write(content)
    return name


def link(name):
    n = safe_name(name)
    return f"[[{n}]]" if n else ""


def build_market(vault, b, date):
    daily = f"{date} 시장"
    kr = b.get("kr", {}) or {}
    us = b.get("us", {}) or {}
    L = ["---", "type: 데일리-시장", f"date: {date}", "tags: [주식뇌, 시장브리핑]", "---", ""]
    L.append(f"# {daily}")
    if b.get("headline"):
        L.append(f"> {b['headline']}")
    L.append("")
    # 지수
    idx = (kr.get("indices") or []) + (us.get("indices") or [])
    if idx:
        L.append("## 지수")
        for i in idx:
            L.append(f"- {i.get('name')}: {i.get('value')} ({i.get('change_pct')})")
        L.append("")
    # 화제 종목
    stocks = []
    for s in (kr.get("hot_stocks") or []):
        stocks.append((s, "KR"))
    for s in (us.get("notable") or []):
        stocks.append((s, "US"))
    for s in (b.get("spotlight") or []):
        stocks.append((s, s.get("market", "")))
    if stocks:
        L.append("## 종목")
        for s, mkt in stocks:
            nm = s.get("name") or s.get("ticker")
            ctx = f"{s.get('change_pct','')} {s.get('reason') or s.get('thesis','')}".strip()
            append_timeline(vault, "10_주식뇌/종목", nm, "종목", date, ctx[:120], daily,
                            {"ticker": s.get("ticker"), "market": mkt})
            L.append(f"- {link(nm)} {s.get('change_pct','')} — {s.get('reason') or s.get('thesis','')}")
        L.append("")
    # 섹터
    secs = (b.get("sectors", {}) or {}).get("kr", []) + (b.get("sectors", {}) or {}).get("us", [])
    strong = [s for s in secs if str(s.get("change_pct", "")).startswith("+")]
    if strong:
        L.append("## 섹터 (강세)")
        for s in strong:
            append_timeline(vault, "10_주식뇌/섹터", s.get("name"), "섹터", date,
                            s.get("change_pct", ""), daily)
            L.append(f"- {link(s.get('name'))} {s.get('change_pct')}")
        L.append("")
    # 테마
    if b.get("top_themes"):
        L.append("## 테마")
        for t in b["top_themes"]:
            append_timeline(vault, "10_주식뇌/테마", t.get("theme"), "테마", date,
                            (t.get("summary") or "")[:120], daily)
            L.append(f"- {link(t.get('theme'))}: {t.get('summary','')}")
        L.append("")
    # 매크로 자산
    if b.get("assets"):
        L.append("## 매크로")
        for a in b["assets"]:
            if a.get("value") in (None, "", "미확인"):
                continue
            append_timeline(vault, "10_주식뇌/매크로", a.get("name"), "매크로", date,
                            f"{a.get('value')} ({a.get('change_pct','')})", daily)
            L.append(f"- {link(a.get('name'))}: {a.get('value')} ({a.get('change_pct','')})")
        L.append("")
    return os.path.join(vault, "10_주식뇌/_데일리", f"{daily}.md"), "\n".join(L)


def build_biz(vault, b, date):
    daily = f"{date} 비즈"
    L = ["---", "type: 데일리-비즈", f"date: {date}", "tags: [사업뇌, 비즈브리핑]", "---", ""]
    L.append(f"# {daily}")
    if b.get("headline"):
        L.append(f"> {b['headline']}")
    L.append("")
    if b.get("insights"):
        L.append("## 인사이트")
        for s in b["insights"]:
            L.append(f"- **{s.get('title')}** — {s.get('takeaway','')}")
        L.append("")
    if b.get("trends"):
        L.append("## 트렌드/개념")
        for t in b["trends"]:
            append_timeline(vault, "20_사업뇌/개념", t.get("theme"), "개념", date,
                            (t.get("summary") or "")[:120], daily)
            L.append(f"- {link(t.get('theme'))}: {t.get('summary','')}")
        L.append("")
    if b.get("cases"):
        L.append("## 사례")
        for c in b["cases"]:
            nm = f"{c.get('who','')} 사례"
            append_timeline(vault, "20_사업뇌/사례", nm, "사례", date,
                            f"{c.get('what','')} {c.get('numbers','')}".strip()[:120], daily)
            L.append(f"- {link(nm)}: {c.get('what','')} ({c.get('numbers','')})")
        L.append("")
    if b.get("sources_used"):
        srcs = []
        for s in b["sources_used"]:
            nm = s.get("name")
            if nm and nm not in srcs:
                srcs.append(nm)
                append_timeline(vault, "20_사업뇌/인물기업", nm, "인물기업", date, "", daily)
        if srcs:
            L.append("## 출처")
            L.append(" · ".join(link(s) for s in srcs))
            L.append("")
    return os.path.join(vault, "20_사업뇌/_데일리", f"{daily}.md"), "\n".join(L)


def main():
    if len(sys.argv) < 2:
        print("usage: brief_to_obsidian.py <brief.json> [vault]", file=sys.stderr)
        return 1
    brief_path = sys.argv[1]
    vault = sys.argv[2] if len(sys.argv) > 2 else load_env_vault()
    b = json.load(open(brief_path))
    date = b.get("date") or os.path.basename(brief_path).replace(".json", "")
    ensure_dirs(vault)
    if "insights" in b:
        path, content = build_biz(vault, b, date)
    else:
        path, content = build_market(vault, b, date)
    open(path, "w").write(content)
    print(f"OK: wrote {os.path.relpath(path, vault)} (+ entity timelines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
