#!/usr/bin/env python3
"""Render an SVG card to PNG and publish it so Threads can fetch it.

Threads' API takes an image by public URL, not by upload, so the PNG has to be
reachable on the open web. The market-brief repo is already a GitHub Pages site,
so cards go there under cards/ and get a stable URL.

No image libraries are installed on this machine, so conversion goes through
headless Chrome, which also gets Korean font rendering right.

Usage:
    python3 make_card.py card.svg 2026-08-02-gilead
Prints the public URL on success.
"""
import os
import re
import subprocess
import sys
import tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGES_REPO = "/Applications/BoomyBoom"
CARDS_DIR = os.path.join(PAGES_REPO, "cards")
PUBLIC_BASE = "https://boomyboom.github.io/market-daily-brief/cards"
WIDTH, HEIGHT = 1000, 1000        # 스레드에서 잘 보이는 정사각형


def svg_to_png(svg_text, out_path, width=WIDTH, height=HEIGHT):
    if not os.path.exists(CHROME):
        raise RuntimeError("Chrome not found; needed for SVG rendering")
    html = ('<html><body style="margin:0;background:#fff">'
            + svg_text + "</body></html>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        tmp = f.name
    try:
        r = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={out_path}", f"--window-size={width},{height}", tmp],
            capture_output=True, text=True, timeout=120)
        if not os.path.exists(out_path):
            raise RuntimeError(r.stderr.strip()[:300] or "chrome produced no file")
    finally:
        os.unlink(tmp)
    return out_path


def publish(png_path, slug):
    """Commit the card to the Pages repo and return its public URL."""
    os.makedirs(CARDS_DIR, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]", "-", slug)[:60] + ".png"
    dest = os.path.join(CARDS_DIR, name)
    if os.path.abspath(png_path) != os.path.abspath(dest):
        with open(png_path, "rb") as a, open(dest, "wb") as b:
            b.write(a.read())
    git = "/usr/bin/git"
    env = dict(os.environ, PATH="/opt/homebrew/bin:" + os.environ.get("PATH", ""))
    subprocess.run([git, "add", dest], cwd=PAGES_REPO, env=env, capture_output=True)
    subprocess.run([git, "commit", "-q", "-m", f"card: {name}"],
                   cwd=PAGES_REPO, env=env, capture_output=True)
    p = subprocess.run([git, "push", "-q", "origin", "main"],
                       cwd=PAGES_REPO, env=env, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"push failed: {p.stderr.strip()[:200]}")
    return f"{PUBLIC_BASE}/{name}"


def main():
    if len(sys.argv) < 3:
        print("usage: make_card.py <svg file> <slug>", file=sys.stderr)
        return 1
    svg = open(sys.argv[1]).read()
    slug = sys.argv[2]
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        png = f.name
    try:
        svg_to_png(svg, png)
        url = publish(png, slug)
        print(url)
    finally:
        if os.path.exists(png):
            os.unlink(png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
