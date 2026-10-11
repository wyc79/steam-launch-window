#!/usr/bin/env bash
# Run the history backfill on an always-on Linux box (e.g. a Raspberry Pi)
# until every game has its 30-day review count. Safe to stop and restart:
# progress is saved to history/games.csv every 200 games.
#
# Env vars (optional):
#   REPO      repo checkout (default: two folders up from this script)
#   DATA_DIR  where history/games.csv lives (default: $REPO/_data)
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
DATA_DIR="${DATA_DIR:-$REPO/_data}"
cd "$REPO"

if [ ! -x .venv/bin/python ]; then
  echo "creating virtualenv"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q .
fi

listing=()
if [ -f "$DATA_DIR/history/games.csv" ]; then
  # The game list came over with the file; only fill in the missing counts.
  listing=(--skip-listing)
fi

while true; do
  set +e
  .venv/bin/python -m pipeline.collect_history \
    --data-dir "$DATA_DIR" "${listing[@]}" \
    --budget-minutes 720 --fail-if-incomplete
  code=$?
  set -e
  if [ "$code" -eq 0 ]; then
    echo "backfill complete"
    exit 0
  fi
  listing=(--skip-listing)
  echo "collector exited with $code and work remains; trying again in 5 minutes"
  sleep 300
done
