#!/usr/bin/env bash
# API + UI together. Ctrl-C stops both.
set -e
cd "$(dirname "$0")"
python3 -m uvicorn api:app --port 8010 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
cd ui && npm run dev
