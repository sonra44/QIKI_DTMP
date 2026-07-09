#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] Этап 6 «страница РАДАР» — юнит (риск/строка трека/эфир чист/LOST-эвикция)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_f1_radar_page.py tests/unit/test_orion_mfd_page_content_pack.py -q
printf '\n[prove] Этап 6 live: эфир чист при STOPPED → wire-трек → LOST-эвикция\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -u tools/orion_v_f1_radar_page_smoke.py
