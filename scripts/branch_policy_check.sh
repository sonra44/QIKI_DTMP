#!/usr/bin/env bash
set -euo pipefail

BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$BRANCH" == "HEAD" ]]; then
  echo "INFO: detached HEAD; skipping task branch naming policy check." >&2
  exit 0
fi

if [[ "$BRANCH" == "main" ]]; then
  echo "FAIL: work on main is forbidden. create task branch first." >&2
  exit 1
fi

if [[ ! "$BRANCH" =~ ^task-[0-9]{4,}-[a-z0-9-]+$ ]]; then
  echo "FAIL: branch '$BRANCH' must match task-<id>-<slug>." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "WARN: tracked changes are present. ensure they belong to one task." >&2
fi

if git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  LOCAL_SHA="$(git rev-parse HEAD)"
  REMOTE_SHA="$(git rev-parse "origin/$BRANCH")"
  if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
    echo "INFO: local and origin/$BRANCH differ (expected before push)."
    echo "      local : $LOCAL_SHA"
    echo "      remote: $REMOTE_SHA"
  else
    echo "OK: local equals origin/$BRANCH ($LOCAL_SHA)."
  fi
else
  echo "INFO: origin/$BRANCH not found yet (first push expected)."
fi

MAIN_BASE="$(git merge-base HEAD origin/main 2>/dev/null || true)"
if [[ -z "$MAIN_BASE" ]]; then
  echo "WARN: origin/main not available locally. run: git fetch origin main" >&2
else
  MAIN_HEAD="$(git rev-parse origin/main)"
  if [[ "$MAIN_BASE" != "$MAIN_HEAD" ]]; then
    echo "WARN: branch is not rebased on latest origin/main." >&2
    echo "      run: git fetch origin && git rebase origin/main" >&2
  else
    echo "OK: branch includes latest origin/main base."
  fi
fi

echo "PASS: branch policy check completed."
