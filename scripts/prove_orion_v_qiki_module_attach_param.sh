#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] P2/P3 параметризация — юнит (парсер, пломба==тело, отказы конвейера)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest \
  tests/unit/test_qiki_attach_parse_p2.py tests/unit/test_orion_v_body_attach_p3.py \
  tests/unit/test_orion_v_qiki_body_attach_live.py -q
printf '\n[prove] P4 live: параметризованный цикл + негативы (леджер/класс/паспорт/занято/deferred)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_module_attach_p4_smoke.py
