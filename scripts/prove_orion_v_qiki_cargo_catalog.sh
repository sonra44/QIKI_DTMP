#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] P1 каталог отсека — юнит (загрузчик fail-closed + policy-доклад)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_module_catalog_p1.py -q
printf '\n[prove] P1 live: «доложи отсек» по реальной шине\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_cargo_list_smoke.py
