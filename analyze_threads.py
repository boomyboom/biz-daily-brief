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
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://graph.threads.net/v1.0"
GROWTH = os.path.join(ROOT, "threads", "growth_insights.md")
SUMMARY = os.path.join(ROOT, "logs", "analytics_summary.txt")
HISTORY = os.path.join(ROOT, "threads", "analytics_history")
KST = timezone(timedelta(hours=9))


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

    today = datetime.now(KST).strftime("%Y-%m-%d")
    os.makedirs(HISTORY, exist_ok=True)
    previous = {}
    older = sorted(path for path in os.listdir(HISTORY)
                   if path.endswith(".json") and path[:10] < today)
    if older:
        try:
            old_rows = json.load(open(os.path.join(HISTORY, older[-1])))
            previous = {row["id"]: row for row in old_rows}
        except Exception:
            previous = {}

    # 최근 25개를 매일 비교한다. 100개를 순차 조회하면 Meta API 지연 시
    # launchd 실행이 오래 걸리므로, 일일 학습에는 최신 묶음만 사용한다.
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
        created_kst = ""
        try:
            stamp = p["timestamp"].replace("Z", "+0000")
            try:
                created = datetime.fromisoformat(stamp)
            except ValueError:
                fmt = "%Y-%m-%dT%H:%M:%S.%f%z" if "." in stamp else "%Y-%m-%dT%H:%M:%S%z"
                created = datetime.strptime(stamp, fmt)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            local = created.astimezone(KST)
            hour = local.strftime("%H시")
            created_kst = local.isoformat(timespec="seconds")
        except Exception:
            pass
        old_views = int((previous.get(p["id"]) or {}).get("views") or 0)
        is_new = p["id"] not in previous
        rows.append({
            "id": p["id"], "text": text, "views": views,
            "delta_views": max(0, views - old_views),
            "is_new": is_new,
            "likes": metric(ins, "likes"), "replies": metric(ins, "replies"),
            "reposts": metric(ins, "reposts"), "quotes": metric(ins, "quotes"),
            "hour": hour, "created_kst": created_kst, "len": len(text),
        })

    with open(os.path.join(HISTORY, f"{today}.json"), "w") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)

    rows.sort(key=lambda r: r["views"], reverse=True)
    top = rows[:5]
    recent = sorted(rows, key=lambda r: r["delta_views"], reverse=True)[:5]

    # growth_insights.md (드래프터가 참고)
    lines = ["# 성장 참고 (자동 분석)", "",
             f"_업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}_", "",
             "## 최근 조회 증가가 컸던 글"]
    for r in recent:
        lines.append(f"- +{r['delta_views']}뷰, 누적 {r['views']}뷰 | {r['hour']} | {r['len']}자 | {r['text'][:50]}")
    lines += ["", "## 누적 조회수 상위"]
    for r in top:
        lines.append(f"- 👀{r['views']} ♥{r['likes']} 💬{r['replies']} 🔁{r['reposts']} "
                     f"| {r['hour']} | {r['len']}자 | {r['text'][:50]}")
    # 간단 패턴
    if rows:
        best_hours = {}
        for r in rows:
            if r["hour"]:
                best_hours.setdefault(r["hour"], []).append(r["delta_views"])
        hour_avg = sorted(((h, sum(v) / len(v)) for h, v in best_hours.items()),
                          key=lambda x: x[1], reverse=True)[:3]
        lines += ["", "## 참고 패턴"]
        if hour_avg:
            lines.append("- 반응 좋은 시간대(평균 증가 조회수): " +
                         ", ".join(f"{h} {int(a)}" for h, a in hour_avg))
        lines += [
                  "- 위 글들의 **훅 스타일, 길이, 시간대**를 배워라 (짧고 강한 궁금증 훅이 잘 먹힘).",
                  "- **주제는 우리 레인(비즈, 시장, 창업) 유지**. 개인글 주제를 따라가지 마라. 배울 건 형식이지 주제가 아니다.",
                  "- 반응 낮았던 형식(너무 길거나 밋밋한 것)은 반복하지 마라."]
    os.makedirs(os.path.dirname(GROWTH), exist_ok=True)
    open(GROWTH, "w").write("\n".join(lines) + "\n")

    # 텔레그램 요약
    s = ["📊 지난 분석 이후 스레드 조회 증가"]
    for r in recent[:3]:
        s.append(f"+{r['delta_views']}뷰, 누적 {r['views']}뷰, 리포스트 {r['reposts']} | {r['text'][:35]}")
    open(SUMMARY, "w").write("\n".join(s) + "\n")
    print(f"OK: analyzed {len(rows)} posts → growth_insights.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
