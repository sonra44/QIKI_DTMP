# ORION Launch Canon Cleanup

## 1. What drift existed

- Canonical operator entrypoint was already `src/qiki/services/operator_console/main_orion_v.py`.
- Supported live operator path was already `./scripts/run_orion_v_live.sh`, which executes `docker exec -it qiki-operator-console python main_orion_v.py`.
- `docker-compose.operator.yml` already launched `python main_orion_v.py`.
- But `src/qiki/services/operator_console/Dockerfile` still defaulted to `python main_orion.py`, which silently pointed to the non-canonical runtime path whenever the image was started without the compose override.
- `docs/RESTART_CHECKLIST.md` told the operator to open `./scripts/run_orion_v_live.sh` before explicitly bringing up the ORION overlay container.
- Some active docs/runbooks still described `main_orion.py` as the runtime/default ORION path instead of clearly marking it as legacy/reference.

## 2. What was changed

- Changed `src/qiki/services/operator_console/Dockerfile` default `CMD` from `python main_orion.py` to `python main_orion_v.py`.
- Added an explicit compatibility note in `docker-compose.operator_orionv.yml`: it is kept as a transitional/non-canonical override, while `docker-compose.operator.yml` is the supported overlay.
- Synced current operator docs/runbooks so they agree on one supported launch canon:
  - `docs/ORION_V_QUICKSTART.md`
  - `docs/ORION_V_RUNBOOK.md`
  - `docs/RESTART_CHECKLIST.md`
  - `docs/design/operator_console/ORION_OS_SYSTEM.md`
  - `docs/agents/orion_tui_agent.md`
  - `docs/ops/STATE_HEALTH_RUNBOOK.md`
- Updated the restart checklist so the ORION overlay container is explicitly started before using `./scripts/run_orion_v_live.sh`.
- Marked legacy/transitional launch artifacts explicitly instead of leaving them looking like the default path.

## 3. What remains legacy but intentionally preserved

- `src/qiki/services/operator_console/main_orion.py` remains in the repo and was not deleted.
- `docker-compose.operator_orionv.yml` remains in the repo as a transitional/compatibility override for older proofs.
- Legacy overlay/profile paths were not removed.
- No ORION runtime logic, ownership subjects/services, q-core, bridge, or q-sim logic were changed.

## 4. How to launch canonical ORION V now

1. Start the supported stack overlay:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
```

2. Start the canonical live operator TTY under `tmux`:

```bash
./scripts/run_orion_v_live.sh
```

3. Under the hood, the canonical live path remains:

```bash
docker exec -it qiki-operator-console python main_orion_v.py
```

Notes:
- `docker-compose.operator.yml` is the supported default overlay.
- `docker-compose.operator_orionv.yml` is preserved but transitional/non-canonical.
- `main_orion.py` remains legacy/reference only and is not the default runtime path.

## 5. Validation performed

- Read and compared:
  - `src/qiki/services/operator_console/Dockerfile`
  - `docker-compose.operator.yml`
  - `docker-compose.operator_orionv.yml`
  - `scripts/run_orion_v_live.sh`
  - active ORION launch/runbook docs listed above
- Rendered canonical compose config:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml config
```

Result: `operator-console` command resolves to `main_orion_v.py`.

- Rendered canonical + transitional compose config:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml config
```

Result: `operator-console` command resolves to `python -m qiki.services.operator_console.main_orion_v`.

- Rebuilt the operator console image directly from `src/qiki/services/operator_console/Dockerfile` and inspected image config.

Result: image default `Cmd` is now `["python","main_orion_v.py"]`.

- No runtime ownership/service contracts were edited.
