#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

STACK=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)

printf '[prove] phase1/operator status\n'
docker compose "${STACK[@]}" ps q-core-intents qiki-dev q-sim-service operator-console q-bios-service

printf '\n[prove] live ORION V observation objective seed smoke\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_observation_objective_seed_smoke.py
