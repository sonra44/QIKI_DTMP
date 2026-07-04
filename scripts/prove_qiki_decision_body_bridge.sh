#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] M7-M9 мост решение→тело — юнит\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_decision_body_bridge_m7.py -q
printf '\n[prove] M7-M9 live: решение проведено к ГОТОВОМУ конвейеру тела + JSONL-трасса\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/qiki_decision_body_bridge_smoke.py
