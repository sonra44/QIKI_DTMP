#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

STACK=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)

printf '[prove] phase1/operator status\n'
docker compose "${STACK[@]}" ps q-core-intents qiki-dev q-sim-service operator-console q-bios-service

printf '\n[prove] live ORION V observation route smoke (safe)\n'
docker compose -f docker-compose.phase1.yml exec -T -e QIKI_OBSERVATION_STYLE=safe qiki-dev \
  python tools/orion_v_qiki_observation_objective_seed_smoke.py

printf '\n[prove] live ORION V observation route smoke (slow)\n'
docker compose -f docker-compose.phase1.yml exec -T -e QIKI_OBSERVATION_STYLE=slow qiki-dev \
  python tools/orion_v_qiki_observation_objective_seed_smoke.py
