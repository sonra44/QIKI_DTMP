#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] Этап 7 «идентичность QIKI» — юнит (формат/канон-12/tooltip-проводка/N>0)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_f1_qiki_identity.py -q
printf '\n[prove] Этап 7 live: серийник из живой телеметрии + honesty-строка панели QIKI\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -u tools/orion_v_f1_identity_smoke.py
