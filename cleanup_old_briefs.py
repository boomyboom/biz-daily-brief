#!/usr/bin/env python3
"""Remove briefs older than RETENTION_DAYS and regenerate manifest.json."""
import json
import os
import glob
import re
from datetime import datetime, date

ROOT = os.path.dirname(os.path.abspath(__file__))
BRIEFS_DIR = os.path.join(ROOT, "briefs")
RETENTION_DAYS = 30
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json$")


def main():
    os.makedirs(BRIEFS_DIR, exist_ok=True)
    today = date.today()
    kept = []
    for path in sorted(glob.glob(os.path.join(BRIEFS_DIR, "20*-*-*.json"))):
        m = DATE_RE.search(os.path.basename(path))
        if not m:
            continue
        d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        if (today - d).days > RETENTION_DAYS:
            os.remove(path)
            print(f"removed old brief: {os.path.basename(path)}")
        else:
            kept.append(m.group(1))

    kept.sort(reverse=True)
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "latest": kept[0] if kept else None,
        "dates": kept,
    }
    with open(os.path.join(BRIEFS_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"manifest updated: {len(kept)} briefs, latest={manifest['latest']}")


if __name__ == "__main__":
    main()
