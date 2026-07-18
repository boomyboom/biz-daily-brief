#!/usr/bin/env bash
# Usage: ./send_telegram.sh "message text" [chat_id]
# chat_id defaults to $TELEGRAM_CHAT_ID from .env if omitted.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN not set (check .env)" >&2
  exit 1
fi

TEXT="${1:?message text required}"
CHAT_ID="${2:-${TELEGRAM_CHAT_ID:-}}"
if [ -z "$CHAT_ID" ]; then
  echo "chat_id required (pass as 2nd arg or set TELEGRAM_CHAT_ID in .env)" >&2
  exit 1
fi

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d text="${TEXT}"
echo
