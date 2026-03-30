#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

STACK=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)

printf '[prove] operator stack status\n'
docker compose "${STACK[@]}" ps operator-console qiki-dev q-sim-service q-bios-service

printf '\n[prove] live ORION V F1 quick-actions smoke\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_f1_quick_actions_smoke.py
