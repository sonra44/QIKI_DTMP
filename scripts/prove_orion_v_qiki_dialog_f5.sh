#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

printf '[prove] phase1 status\n'
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps qiki-dev q-sim-service operator-console

printf '\n[prove] live ORION V M1: экран F5 QIKI/ДИАЛОГ (read-only)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_dialog_f5_smoke.py
