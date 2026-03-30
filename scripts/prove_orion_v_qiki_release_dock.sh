#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PHASE1=(-f docker-compose.phase1.yml)

echo "[prove] phase1 status"
docker compose "${PHASE1[@]}" ps

echo "[prove] executing live ORION V QIKI release-dock smoke"
docker compose "${PHASE1[@]}" exec -T qiki-dev python tools/orion_v_qiki_release_dock_smoke.py
