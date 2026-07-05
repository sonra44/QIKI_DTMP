#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] M7-M9 live-wiring — юнит (спуф/предусловия/policy-контракт)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_orion_v_qiki_body_attach_live.py -q
printf '\n[prove] M7-M9 live: полный цикл intent→candidate→approve→мост→тело→аудит\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_body_attach_live_smoke.py
