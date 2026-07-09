#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf '[prove] Этап 2 «радар» — юнит (per-sensor треки / sensor_id / гейт GetRadarFrame / ротация)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest tests/unit/test_block0_radar_ingest.py -q
printf '\n[prove] Этап 2 live: гейт 0.9 + стабильный sensor_id + доля refresh-циклов с радаром\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_radar_track_visible_smoke.py
