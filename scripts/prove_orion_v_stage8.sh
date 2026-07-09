#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] Этап 8 «command-surface» — юнит (реестр/полнота/quit-confirm/палитра/cap-гейт)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest \
  tests/unit/test_orion_command_surface_registry.py \
  tests/unit/test_shared_supercap_gate.py \
  tests/unit/test_orion_palette_typed_commands.py \
  tests/unit/test_block0_console_hygiene.py -q -p no:warnings
printf '\n[prove] Этап 8 live: help-группы → палитра→роутер (sim ACK) → cap-чип → quit-модал\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -u tools/orion_v_stage8_command_surface_smoke.py
