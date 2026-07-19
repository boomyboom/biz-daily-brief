#!/usr/bin/env python3
"""Refresh the long-lived Threads access token and update .env.

Threads long-lived tokens last ~60 days and can be refreshed (no app secret
needed) once they are >24h old:
  GET /refresh_access_token?grant_type=th_refresh_token&access_token=...

Run periodically (e.g. daily) so the token never expires. Safe to run on a
token <24h old — the API just declines and we leave .env unchanged.
"""
import json
import os
import sys
import re
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, ".env")
API = "https://graph.threads.net/v1.0"


def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def set_env_value(key, value):
    lines = open(ENV_PATH).read().splitlines()
    out, found = [], False
    for line in lines:
        if re.match(rf"\s*{re.escape(key)}\s*=", line):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    open(ENV_PATH, "w").write("\n".join(out) + "\n")


def main():
    env = load_env()
    token = env.get("THREADS_TOKEN")
    if not token:
        print("ERROR: THREADS_TOKEN missing", file=sys.stderr)
        return 1
    url = f"{API}/refresh_access_token?grant_type=th_refresh_token&access_token={token}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            res = json.loads(r.read().decode())
    except Exception as e:
        # <24h old or short-lived token → refuse; leave as-is
        print(f"refresh skipped/failed: {e}", file=sys.stderr)
        return 0
    new = res.get("access_token")
    if new:
        set_env_value("THREADS_TOKEN", new)
        print(f"OK: token refreshed, expires_in={res.get('expires_in')}s")
        return 0
    print(f"no token in response: {res}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
