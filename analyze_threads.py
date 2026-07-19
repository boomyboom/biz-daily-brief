#!/usr/bin/env python3
"""Nightly Threads performance analysis → growth feedback.

Pulls insights (views/likes/replies/reposts) for recent posts, finds what
worked, writes threads/growth_insights.md (read by the drafters) and prints a
short Telegram-ready summary to logs/analytics_summary.txt.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://graph.threads.net/v1.0"
GROWTH = os.path.join(ROOT, "threads", "growth_insights.md")
SUMMARY = os.path.join(ROOT, "logs", "analytics_summary.txt")


def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get(path, params):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def metric(insights, name):
    for m in insights.get("data", []):
        if m.get("name") == name:
            v = m.get("values", [{}])
            return v[0].get("value", 0) if v else 0
    return 0


def main():
    env = load_env()
    token = env.get("THREADS_TOKEN")
    if not token:
        print("ERROR: THREADS_TOKEN missing", file=sys.stderr)
        return 1

    posts = get("me/threads", {"fields": "id,text,timestamp,media_type",
                               "limit": 25, "access_token": token}).get("data", [])
    rows = []
    for p in posts:
        # 답글 체인 하위글 제외 대략: 텍스트가 있고 최상위인 것 위주(간단화: 전부 조회)
        try:
            ins = get(f"{p['id']}/insights",
                      {"metric": "views,likes,replies,reposts,quotes", "access_token": token})
        except Exception:
            continue
        views = metric(ins, "views")
        text = (p.get("text") or "").replace("\n", " ")
        hour = ""
        try:
            hour = datetime.strptime(p["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").strftime("%H시")
        except Exception:
            pass
        rows.append({
            "text": text, "views": views,
            "likes": metric(ins, "likes"), "replies": metric(ins, "replies"),
            "reposts": metric(ins, "reposts"), "quotes": metric(ins, "quotes"),
            "hour": hour, "len": len(text),
        })

    rows.sort(key=lambda r: r["views"], reverse=True)
    top = rows[:5]

    # growth_insights.md (드래프터가 참고)
    lines = ["# 성장 참고 (자동 분석)", "",
             f"_업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}_", "",
             "## 최근 반응 좋았던 글 (조회수 순)"]
    for r in top:
        lines.append(f"- 👀{r['views']} ♥{r['likes']} 💬{r['replies']} 🔁{r['reposts']} "
                     f"| {r['hour']} | {r['len']}자 | {r['text'][:50]}")
    # 간단 패턴
    if rows:
        best_hours = {}
        for r in rows:
            if r["hour"]:
                best_hours.setdefault(r["hour"], []).append(r["views"])
        hour_avg = sorted(((h, sum(v) / len(v)) for h, v in best_hours.items()),
                          key=lambda x: x[1], reverse=True)[:3]
        lines += ["", "## 참고 패턴",
                  "- 반응 좋은 시간대(평균 조회수): " +
                  ", ".join(f"{h} {int(a)}" for h, a in hour_avg),
                  "- 위 글들의 **훅 스타일·길이·시간대**를 배워라 (짧고 강한 궁금증 훅이 잘 먹힘).",
                  "- **주제는 우리 레인(비즈·시장·창업) 유지** — 개인글 주제를 따라가지 마라. 배울 건 '형식'이지 '주제'가 아니다.",
                  "- 반응 낮았던 형식(너무 길거나 밋밋한 것)은 반복하지 마라."]
    os.makedirs(os.path.dirname(GROWTH), exist_ok=True)
    open(GROWTH, "w").write("\n".join(lines) + "\n")

    # 텔레그램 요약
    s = ["📊 어젯밤~오늘 스레드 성과 (조회수 top)"]
    for r in top[:3]:
        s.append(f"👀{r['views']} 🔁{r['reposts']} · {r['text'][:35]}")
    open(SUMMARY, "w").write("\n".join(s) + "\n")
    print(f"OK: analyzed {len(rows)} posts → growth_insights.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
