#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

STACK=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)

printf '[prove] phase1 status\n'
docker compose "${STACK[@]}" ps qiki-dev q-sim-service operator-console q-bios-service

printf '\n[prove] live ORION V QIKI safe-observation smoke\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_safe_observation_smoke.py
