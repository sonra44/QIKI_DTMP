# QIKI_DTMP — Session status (2025-12-12)

## What changed

- Fixed pytest cache permissions issue:
  - `QIKI_DTMP/.pytest_cache/v/**` was root-owned; now user-owned.
  - `QIKI_DTMP/pytest.ini` includes `cache_dir=/tmp/pytest_cache` to avoid repo write-permission issues.

- Operator Console docker overlay:
  - `QIKI_DTMP/docker-compose.operator.yml` adjusted to work as an overlay with `docker-compose.phase1.yml`.
  - Removed duplicate NATS service; aligned env vars (`GRPC_HOST/GRPC_PORT`), set external network name to `qiki_dtmp_qiki-network-phase1`.
  - Start command: `python main.py`.

## Verification

- `pytest -q` in `QIKI_DTMP` passes (60 passed, 2 skipped).
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml config` succeeds (only warns that `version` is obsolete).

## Next step

- Run Operator Console on top of Phase1:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d operator-console`

## Project notes

- Journal entry created: `QIKI_DTMP/journal/2025-12-12_pytest_cache_and_operator_compose/status.md`.
