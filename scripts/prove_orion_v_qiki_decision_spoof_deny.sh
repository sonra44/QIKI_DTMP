#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] M5 CommandDecision — юнит (RED спуфинг первым)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_command_decision_m5.py -q
printf '\n[prove] M5 live RED: подменённая команда НЕ публикуется в execute-пути\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_qiki_decision_spoof_deny_smoke.py
