#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] M6 гейт одобрения — юнит\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_orion_v_qiki_approve_m6.py -q
printf '\n[prove] M6 live: не-allowed кандидат до шины не доходит\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_approve_gate_smoke.py
