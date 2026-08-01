#!/usr/bin/env python3
"""Deterministic release checks for the daily business brief."""

import json
import os
import sys
from collections import Counter
from urllib.parse import urlparse

BAD_PUNCT = ("·", "・", "—", "–")
SENSITIVE = (
    "대통령", "국회의원", "정당", "선거", "탄핵", "좌파", "우파",
    "젠더갈등", "남녀갈등", "지역갈등", "인종갈등", "참사", "재난",
)


def walk(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]")
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{path}.{key}" if path else key)


def source_rows(brief):
    rows = []
    for key in ("insights", "trends", "cases", "tools"):
        for item in brief.get(key) or []:
            url = item.get("source_url")
            if url:
                rows.append((item.get("source_name") or item.get("name") or item.get("who") or key, url))
    quote = brief.get("quote") or {}
    if quote.get("source_url"):
        rows.append((quote.get("author") or "quote", quote["source_url"]))
    for item in brief.get("sources_used") or []:
        if item.get("url"):
            rows.append((item.get("name") or "source", item["url"]))
    return rows


def validate(path):
    errors = []
    try:
        brief = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        return [f"JSON 읽기 실패: {exc}"]
    if brief.get("date") != os.path.basename(path)[:10]:
        errors.append("date가 파일명 날짜와 다름")
    if not str(brief.get("headline") or "").strip():
        errors.append("headline 누락")
    if len(brief.get("insights") or []) < 3:
        errors.append("인사이트 3개 미만")
    if "정보 제공용" not in str(brief.get("disclaimer") or ""):
        errors.append("면책 고지 누락")
    for text_path, value in walk(brief):
        if text_path.endswith("url"):
            continue
        if any(mark in value for mark in BAD_PUNCT):
            errors.append(f"{text_path}: 금지 문장부호 포함")
        hit = next((word for word in SENSITIVE if word in value), None)
        if hit:
            errors.append(f"{text_path}: 민감 주제 검토 필요 ({hit})")
    rows = source_rows(brief)
    unique_urls = {url for _, url in rows}
    if len(unique_urls) < 3:
        errors.append("서로 다른 출처 URL 3개 미만")
    names = Counter(name for name, _ in rows)
    if rows and max(names.values()) / len(rows) > 0.5:
        errors.append("한 출처 비중이 50% 초과")
    domains = set()
    for _, url in rows:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors.append("올바르지 않은 출처 URL")
        elif parsed.netloc:
            domains.add(parsed.netloc.lower())
    if len(domains) < 3:
        errors.append("출처 도메인 3개 미만")
    return errors


def main():
    if len(sys.argv) != 2:
        print("usage: validate_biz_brief.py <brief.json>", file=sys.stderr)
        return 2
    errors = validate(sys.argv[1])
    if errors:
        print(f"FAIL: {len(errors)}개 검증 오류", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"OK: validated {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
