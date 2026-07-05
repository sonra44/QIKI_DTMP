#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] ADR-0020 процедурная установка — юнит (P0 мост, P1 захват/гейты, P2 время, P3 UI)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest \
  tests/unit/test_decision_body_bridge_p0.py \
  tests/unit/test_orion_v_attach_procedure_p1.py \
  tests/unit/test_orion_v_attach_procedure_p2.py \
  tests/unit/test_orion_v_attach_procedure_p3.py -q
printf '\n[prove] ADR-0020 live: процедурный цикл с развилками/hold + визуальная правда F5\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_module_attach_p4_smoke.py
