#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

find analyzer -type d -name '__pycache__' -prune -exec rm -rf {} +
find scripts -type d -name '__pycache__' -prune -exec rm -rf {} +
find src -type d -name '__pycache__' -prune -exec rm -rf {} +
find tests -type d -name '__pycache__' -prune -exec rm -rf {} +
find src -maxdepth 3 -type d -name '*.egg-info' -prune -exec rm -rf {} +

find analyzer/data/static -type f ! -name '.gitkeep' -delete
find analyzer/data/runtime -type f ! -name '.gitkeep' -delete
find analyzer/data/derived -type f ! -name '.gitkeep' -delete
find analyzer/data -maxdepth 1 -type f -name '*.json' -delete
find tmp -type f ! -name '.gitkeep' -delete

rm -f analyzer/data/analyzer.sqlite3 analyzer/data/analyzer.sqlite3-shm analyzer/data/analyzer.sqlite3-wal
