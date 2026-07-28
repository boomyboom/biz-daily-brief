#!/usr/bin/env python3
"""Strip AI-tell punctuation from every string in a brief JSON, in place.

The prompts already forbid 가운뎃점 and 긴 줄표, but the model still slips them
in. Cleaning the JSON once means Telegram, Obsidian, the dashboard and every
downstream consumer stay consistent instead of each filtering separately.

Usage: python3 humanize_brief.py briefs/2026-07-28-kr.json
"""
import json
import re
import sys


def humanize(t):
    t = re.sub(r"[ \t]*[·・][ \t]*", ", ", t)
    t = re.sub(r"[ \t]*[—–][ \t]*", ", ", t)
    t = re.sub(r"(,[ \t]*){2,}", ", ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t


def walk(node):
    if isinstance(node, str):
        return humanize(node)
    if isinstance(node, list):
        return [walk(v) for v in node]
    if isinstance(node, dict):
        # URL 등 값은 건드리지 않는다
        return {k: (v if isinstance(v, str) and k.endswith("url") else walk(v))
                for k, v in node.items()}
    return node


def main():
    if len(sys.argv) < 2:
        print("usage: humanize_brief.py <brief.json>", file=sys.stderr)
        return 1
    path = sys.argv[1]
    raw = open(path).read()
    data = json.loads(raw)
    cleaned = walk(data)
    out = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
    before = raw.count("·") + raw.count("—") + raw.count("–")
    after = out.count("·") + out.count("—") + out.count("–")
    if out != raw:
        open(path, "w").write(out)
    print(f"OK: {path} cleaned ({before} -> {after})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
