# ORION BIOS Projection Alignment

Date: 2026-03-25

## Goal

Align ORION BIOS first-load projection with the real canonical `q_bios_service` payload, without changing BIOS schema or introducing new fields.

## Confirmed drift

Canonical BIOS payload already provides:
- `post_results`
- `all_systems_go`
- `event_schema_version`
- `source`
- `subject`

The ORION boot screen path already used `post_results`, but the first-load event announcement path in legacy ORION still tried to count non-existent `components`.

That made the first-load message drift away from the real payload contract.

## Fix applied

File:
- [src/qiki/services/operator_console/main_orion.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_orion.py)

Changed only the first-load BIOS announcement path:
- replaced `components` lookup with `post_results`
- replaced `components_count` with `device_count`
- changed the operator message suffix from `components` to `devices` / `устройств`

Current projection behavior:
- status still comes from `all_systems_go`
- device count now comes from `len(post_results)` when present
- no dependency remains on non-existent `components`

## Compatibility

The fix stays compatible with the current canonical BIOS payload:
- no BIOS producer changes
- no schema changes
- no new downstream fields

If `post_results` is absent or malformed, ORION still emits the BIOS loaded message without a device count, which preserves tolerant downstream behavior.

## Unit confirmation

Added narrow test:
- [tests/unit/test_orion_bios_projection_alignment.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_bios_projection_alignment.py)

What it checks:
- first-load BIOS message is emitted on `qiki.events.v1.bios_status`
- device count comes from `post_results`
- no `components` wording survives in the emitted message

Run:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_bios_projection_alignment.py
```

Result:
- `1 passed`

## Done check

- ORION first-load BIOS message now matches the real canonical payload shape
- there is no runtime dependence on non-existent `components`
- a narrow unit test confirms the aligned projection path
