#!/usr/bin/env python3
"""Check long-form newsletter length and house style before mailing."""

import re
import sys


def main():
    if len(sys.argv) != 2:
        print("usage: validate_newsletter.py <newsletter.md>", file=sys.stderr)
        return 2
    text = open(sys.argv[1], encoding="utf-8").read()
    svg_count = len(re.findall(r"<svg\b", text, re.I))
    prose = re.sub(r"<svg\b.*?</svg>", "", text, flags=re.I | re.S)
    prose_len = len(prose.strip())
    errors = []
    if not 5000 <= prose_len <= 8000:
        errors.append(f"본문 분량 {prose_len}자, 목표 5000~8000자")
    if not 2 <= svg_count <= 4:
        errors.append(f"인라인 도표 {svg_count}개, 목표 2~4개")
    if sum(1 for line in prose.splitlines() if line.startswith("## ")) < 3:
        errors.append("소제목 3개 미만")
    if any(mark in text for mark in ("·", "・", "—", "–")):
        errors.append("금지 문장부호 포함")
    if errors:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"OK: newsletter prose={prose_len}, svg={svg_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
