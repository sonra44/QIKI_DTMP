#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

printf '[prove] M3 gateway — юнит + HTTP E2E (fake upstream)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m pytest src/qiki/services/qiki_gateway/tests -q

printf '\n[prove] M3 gateway — live-процесс: изоляция реального ключа, vkey, fail-closed\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/qiki_gateway_smoke.py

printf '\n[prove] M3 gateway — /healthz живого сервиса (fail-closed без реального ключа)\n'
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://qiki-gateway:8090/healthz', timeout=5)))"
