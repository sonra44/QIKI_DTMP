#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] Срез staleness — юнит (пороги/M5-эвикция/пауза-xpdr/консольные призраки)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_radar_staleness.py tests/unit/test_f1_radar_page.py -q
printf '\n[prove] Срез staleness live: пауза↔xpdr один мир → живое «уст» → dead скрыт\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -u tools/orion_v_radar_staleness_smoke.py
