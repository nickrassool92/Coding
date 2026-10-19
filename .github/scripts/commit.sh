#!/usr/bin/env bash
# Usage: commit.sh <data file> <new file> <message>
# Commits the new data when it has changed, or when the stored copy is over 6 hours old (so the
# "updated" time in the app stays honest), then pushes, rebasing onto any other refresh that landed first.
set -euo pipefail
file="$1"; new="$2"; msg="$3"
last=$(git log -1 --format=%ct -- "$file" 2>/dev/null || echo 0)
if python3 -I .github/scripts/changed.py "$file" "$new" || [ $(( $(date +%s) - ${last:-0} )) -gt 21600 ]; then
  cp "$new" "$file"
else
  echo "No change worth committing."; exit 0
fi
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add "$file"
git commit -m "$msg"
for i in 1 2 3 4; do
  git pull --rebase origin "$GITHUB_REF_NAME" && git push origin "HEAD:$GITHUB_REF_NAME" && exit 0
  sleep $((i * 5))
done
exit 1
