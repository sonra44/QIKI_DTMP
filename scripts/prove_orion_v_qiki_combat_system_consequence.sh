#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

printf '[prove] G2-QIKI-007 local ORION/QSim smoke\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_combat_system_consequence_smoke.py
