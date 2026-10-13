#!/usr/bin/env bash
# Two one-off review jobs on an always-on Linux box, one after the other (they
# share Steam's review API and this IP, so running them together would double
# the request rate):
#   1. free-game recount: free games' reviews counted again with everyone's
#      reviews, not only Steam purchases (about 16,200 requests, about 4.5 h)
#   2. reviews by language for a sample of 1,000 paid launches
#      (about 11,000 requests, about 3 h), see pipeline/sample_languages.py
# Each is rerun while it exits with 3 (work left: both save progress and go on
# where they stopped), at most MAX_TRIES times; any other failure stops the
# script, and the language sample only starts once the recount is complete.
# Afterwards copy back
# history/games.csv and history/reviews_by_language.csv (scripts/server/README.md).
#
# Env vars (optional):
#   REPO       repo checkout (default: two folders up from this script)
#   DATA_DIR   where history/games.csv lives (default: $REPO/_data)
#   MAX_TRIES  runs per job before giving up (default: 10)
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
DATA_DIR="${DATA_DIR:-$REPO/_data}"
MAX_TRIES="${MAX_TRIES:-10}"
cd "$REPO"
export PYTHONPATH="$REPO"  # this checkout's code, whatever is installed in .venv

if [ ! -x .venv/bin/python ]; then
  echo "creating virtualenv"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q .
fi

run_until_done() {
  label=$1
  shift
  for try in $(seq 1 "$MAX_TRIES"); do
    set +e
    .venv/bin/python -m "$@" --data-dir "$DATA_DIR" --budget-minutes 720 --fail-if-incomplete
    code=$?
    set -e
    if [ "$code" -eq 0 ]; then
      echo "$label complete"
      return 0
    fi
    if [ "$code" -ne 3 ]; then
      echo "$label failed with exit code $code; stopping (see the error above)"
      return 1
    fi
    if [ "$try" -lt "$MAX_TRIES" ]; then
      echo "$label has work left (try $try of $MAX_TRIES); trying again in 5 minutes"
      sleep 300
    fi
  done
  echo "$label did not finish after $MAX_TRIES tries; check the log"
  return 1
}

run_until_done "free-game recount" pipeline.collect_history --skip-listing
run_until_done "language sample" pipeline.sample_languages
echo "all review jobs complete"
