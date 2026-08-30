#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "== 1 harvest";  python3 harvest.py --all
echo "== 2 panel";    python3 panel.py
echo "== 3 tests";    python3 tests/test_core.py
echo "== 4 train";    python3 train.py --both
echo "== 5 score";    python3 score.py --month 2026-07 --top 50
echo "== 6 audit";    python3 audit.py
echo "== 7 ablation"; python3 ablation.py
echo; echo "serve: python3 -m uvicorn api:app --port 8010"
