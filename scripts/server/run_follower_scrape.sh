#!/usr/bin/env bash
# First full follower scrape on an always-on Linux box. Fetches every
# tracked game that is due, one request every COMMUNITY_INTERVAL seconds.
# A 429 stops the collector at once; this script then waits an hour and
# tries again, so while blocked it sends about one request an hour.
# Progress is saved every 200 games; safe to stop and restart.
#
# Env vars (optional):
#   REPO                repo checkout (default: two folders up from this script)
#   DATA_DIR            output folder (default: $REPO/_data)
#   COMMUNITY_INTERVAL  seconds between requests (default 5)
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
DATA_DIR="${DATA_DIR:-$REPO/_data}"
INTERVAL="${COMMUNITY_INTERVAL:-5}"
cd "$REPO"

if [ ! -x .venv/bin/python ]; then
  echo "creating virtualenv"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q .
fi

# The follower plan needs an upcoming snapshot. Take the newest one from the
# data branch instead of asking Steam for it again.
git fetch -q origin data
latest=$(git ls-tree --name-only origin/data upcoming/snapshots/ | sort | tail -1)
mkdir -p "$DATA_DIR/upcoming/snapshots"
git show "origin/data:$latest" > "$DATA_DIR/$latest"
echo "using snapshot $latest"

while true; do
  set +e
  .venv/bin/python -m pipeline.collect_followers \
    --data-dir "$DATA_DIR" --community-interval "$INTERVAL" \
    --budget-minutes 1440 --fail-if-incomplete
  code=$?
  set -e
  if [ "$code" -eq 0 ]; then
    echo "follower scrape complete"
    exit 0
  fi
  echo "collector exited with $code and games are still due; trying again in 60 minutes"
  sleep 3600
done
