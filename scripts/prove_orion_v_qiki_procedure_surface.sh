#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

STACK=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)

printf '[prove] phase1/operator status\n'
docker compose "${STACK[@]}" ps qiki-dev q-sim-service operator-console q-bios-service

printf '\n[prove] live ORION V QIKI procedure-surface smoke\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_procedure_surface_smoke.py
