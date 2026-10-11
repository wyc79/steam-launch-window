#!/usr/bin/env bash
# Commit everything in the data branch checkout (_data) and push it.
# Usage: scripts/commit_data.sh "message"
set -euo pipefail

cd "${DATA_DIR:-_data}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "no data changes"
  exit 0
fi
git commit -q -m "$1"
for attempt in 1 2 3; do
  if git push -q origin HEAD:data; then
    exit 0
  fi
  echo "push failed (attempt $attempt), rebasing on the remote data branch"
  git pull -q --rebase origin data
done
exit 1
