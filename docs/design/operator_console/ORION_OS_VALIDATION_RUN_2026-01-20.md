# ORION Shell OS — Validation Run (2026-01-20)

**Goal:** re-validate ORION “Shell OS” after restart + reconcile visual behavior with unit tests.

## Environment

- Host: `asvtsxkioz`
- Repo: `/home/sonra44/QIKI_DTMP`
- Runtime: Docker Compose (`docker-compose.phase1.yml` + `docker-compose.operator.yml`)

## Evidence

### `docker compose ... ps`

Observed running + healthy services (excerpt):

- `qiki-nats-phase1` — `Up ... (healthy)`
- `qiki-sim-phase1` — `Up ... (healthy)`
- `qiki-bios-phase1` — `Up ... (healthy)`
- `qiki-operator-console` — `Up ... (healthy)`

### Rebuild to include current workspace code

- Rebuilt and restarted operator console to ensure the running container matches the current repo diff:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`

### ORION attach (tmux-driven, non-invasive session)

- Dedicated tmux session created: `codex_orion_check`
- Attach: `docker attach qiki-operator-console`

Observed (via `tmux capture-pane`):

- Events list rendered (rows like `sensor/thermal/core`, `power/bus/main`)
- Bottom keybar includes `F1 System`, `F3 Events`, `F4 Console`, `F9 Help`, `F10 Quit`

#### Pause/live (Ctrl+Y)

- `Ctrl+Y` produced `Events paused/События пауза` in `Output/Вывод`
- `Ctrl+Y` again produced `Events live/События живое` in `Output/Вывод`

#### Keybar shows paused/unread (while paused)

- While paused on the Events screen, keybar prefixed Events token:
  - `▶F3 Paused/Пауза События`
- After publishing a new incident key while paused, keybar showed unread count + paused:
  - `▶F3 1 Paused/Пауза События`
- `r` cleared unread while paused (log line: `Unread cleared/Непрочитано очищено`) and keybar returned to:
  - `▶F3 Paused/Пауза События`

#### Generating a new incident key (for unread proof)

- Published `RADAR_SIGNAL_LOSS` by sending `qiki.events.v1.radar.ppi.signal` with payload `{source:sensor, subject:ppi, value:0}` (3 messages spanning >2s to satisfy `min_duration_s`), while Events were paused.

#### Clear (x)

- `x` produced `Cleared acknowledged incidents/Очищено подтверж инцидентов: 0`
- ACK action could not be confirmed via tmux key injection in this run (needs manual focus/selection verification).

#### Ack + clear via commands (deterministic, no focus dependency)

- `ack RADAR_SIGNAL_LOSS|radar|sensor|ppi` logged `Acknowledged/Подтверждено: ...`
- `clear` logged `Cleared acknowledged incidents/Очищено подтвержденных инцидентов: 1`

### Unit tests (Docker)

Command:

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_events_pause_unread.py src/qiki/services/operator_console/tests/test_events_ack_clear.py src/qiki/services/operator_console/tests/test_events_rowkey_normalization.py`

Result:

- `3 passed` (pytest)

## Checklist summary (✅/❌)

- ✅ Preflight: services up + `healthy`
- ✅ `Ctrl+Y` pause/live works (observed in `Output/Вывод`)
- ✅ Paused/unread is visible in always-visible chrome (keybar) while paused
- ✅ Unit tests for pause/unread + ack/clear semantics + rowkey normalization pass
- ✅ ACK/Clear proven via commands (`ack <key>`, `clear`) with evidence in `Output/Вывод`
- ⚠️ tmux resize stability not fully proven by captures (needs manual run at target sizes, see checklist)
