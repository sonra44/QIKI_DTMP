#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  python tools/orion_v_qiki_tactical_state_shift_smoke.py
